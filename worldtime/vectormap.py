"""Phase B: a scalable vector world map drawn from Natural Earth data (public domain).

Draws ocean + land + country borders + real (zig-zag) timezone boundaries with Pillow at
the target resolution (supersampled for smooth coastlines). No raster ThinkPad artwork is
used, so the result is crisp at any resolution and cleanly licensed (Natural Earth is
public domain).

The projection is supplied by render (the raster map's calibrated affine, shared so the
map, terminator and clocks line up). Its visible window spans < 360° of longitude and is
NOT centred on 0, so each feature is drawn at three longitude offsets (0, ±360°) and the
copies that fall off-canvas are culled — this fills both edges and the antimeridian
seamlessly.

Timezone boundaries come from `ne_10m_time_zones` (honest, jogging around country borders,
straight in open ocean). The UTC+0 zone is filled green (the GMT column) and the
International Date Line (`ne_10m_geographic_lines`) is drawn red on top.
"""

import functools
import json
import os

from PIL import Image, ImageDraw

GEO_DIR = os.path.join(os.path.dirname(__file__), "geodata")

# Latitude beyond which a timezone polygon edge is treated as an artificial polar cap
# (the data closes ocean zones with a HORIZONTAL edge at ±90); only such near-horizontal
# cap edges are dropped — the vertical zone lines still run pole to pole.
POLAR_CAP_LAT = 89.0
# Longitude beyond which an edge is treated as an antimeridian split seam (NE cuts zones
# at ±180); these straight seams are skipped so the red IDL is the only date-line marking.
SEAM_LON = 179.5


@functools.lru_cache(maxsize=4)
def _outer_rings(filename):
    """Outer rings of every polygon in a GeoJSON file: list of [(lon, lat), ...].

    Holes are ignored (negligible at 110m; e.g. the Caspian reads as land).
    """
    with open(os.path.join(GEO_DIR, filename), encoding="utf-8") as f:
        gj = json.load(f)
    rings = []
    for feat in gj["features"]:
        geom = feat["geometry"]
        coords = geom["coordinates"]
        polys = [coords] if geom["type"] == "Polygon" else coords
        for poly in polys:
            if poly:
                rings.append(poly[0])
    return rings


@functools.lru_cache(maxsize=4)
def _zone_features(filename):
    """[(zone_offset_or_None, [outer_ring, ...]), ...] for a timezone polygon file.

    Handles both Polygon and MultiPolygon. `zone` is a float (can be fractional, e.g.
    5.75) — the UTC offset of that band.
    """
    with open(os.path.join(GEO_DIR, filename), encoding="utf-8") as f:
        gj = json.load(f)
    out = []
    for feat in gj["features"]:
        geom = feat["geometry"]
        coords = geom["coordinates"]
        polys = [coords] if geom["type"] == "Polygon" else coords
        rings = [poly[0] for poly in polys if poly]
        out.append((feat["properties"].get("zone"), rings))
    return out


@functools.lru_cache(maxsize=4)
def _named_lines(filename, name_substr):
    """Line segments [(lon, lat), ...] of features whose `name` contains name_substr.

    Handles both LineString and MultiLineString.
    """
    with open(os.path.join(GEO_DIR, filename), encoding="utf-8") as f:
        gj = json.load(f)
    segs: list[list[list[float]]] = []  # GeoJSON coords: each segment is [[lon, lat], ...]
    for feat in gj["features"]:
        if name_substr not in (feat["properties"].get("name") or ""):
            continue
        geom = feat["geometry"]
        coords = geom["coordinates"]
        segs += [coords] if geom["type"] == "LineString" else coords
    return segs


def build_base(out_w, out_h, theme, font, to_px, ss=2, home_offset=None):
    """Render the vector world map base (ocean, land, borders, timezone boundaries).

    `to_px(lon, lat) -> (x, y)` is the output-space projection (supplied by render so the
    map, terminator and clocks share one mapping). `theme` provides
    ocean/land/border/grid/grid_label/gmt/idl/column colours. `ss` is the supersampling
    factor. The whole canvas is filled with ocean first, so any vertical margins read as
    seamless ocean, not letterbox bars. `home_offset` (UTC hours) highlights that zone's
    real polygon with the `column` colour (None disables).
    """
    W, H = out_w * ss, out_h * ss
    img = Image.new("RGBA", (W, H), (*tuple(theme["ocean"]), 255))
    d = ImageDraw.Draw(img)

    def px(lon, lat):
        x, y = to_px(lon, lat)
        return x * ss, y * ss

    # Pixel shift for a +360° longitude step (the projection is affine in lon).
    dx = px(360.0, 0.0)[0] - px(0.0, 0.0)[0]

    def wrap_copies(pts):
        """Yield `pts` shifted by each longitude wrap (0, ±360°), culling off-canvas copies."""
        xs = [p[0] for p in pts]
        lo, hi = min(xs), max(xs)
        for k in (0.0, dx, -dx):
            if hi + k < 0 or lo + k > W:
                continue
            yield [(x + k, y) for x, y in pts] if k else pts

    def composite(layer):
        nonlocal img, d
        img = Image.alpha_composite(img, layer)
        d = ImageDraw.Draw(img)

    # Land fill (Antarctica included — the equator-centred frame puts its −90 data edge at
    # the very bottom, so it reads as the south pole rather than an ugly mid-map cut-off).
    land = (*tuple(theme["land"]), 255)
    for ring in _outer_rings("ne_110m_land.geojson"):
        for c in wrap_copies([px(lon, lat) for lon, lat in ring]):
            d.polygon(c, fill=land)

    # Country borders (thin strokes).
    border = (*tuple(theme["border"]), 255)
    bw = max(1, round(ss))
    for ring in _outer_rings("ne_110m_admin_0_countries.geojson"):
        pts = [px(lon, lat) for lon, lat in ring]
        for c in wrap_copies(pts):
            d.line([*c, c[0]], fill=border, width=bw)

    zones = _zone_features("ne_10m_time_zones.geojson")

    def fill_zone(offset, color):
        """Fill every timezone polygon at `offset` (UTC hours) with `color`, on its own
        layer (honest — follows the zig-zag boundary; the polar extent falls off the
        frame and is clipped by the canvas)."""
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        zd = ImageDraw.Draw(layer)
        for zone, rings in zones:
            if zone is None or abs(zone - offset) > 0.01:
                continue
            for ring in rings:
                for c in wrap_copies([px(lon, lat) for lon, lat in ring]):
                    zd.polygon(c, fill=tuple(color))
        composite(layer)

    # Green UTC+0 column (GMT) + the home city's timezone column — both fill the real zone
    # polygons so the highlight follows the zig-zag boundaries, not a straight band.
    fill_zone(0, theme["gmt"])
    if home_offset is not None:
        fill_zone(home_offset, theme["column"])

    # Timezone boundaries: each zone polygon's meridional edges, drawn as the grid. Polar
    # caps (horizontal edges at ±90) and antimeridian split seams (at ±180) are skipped so
    # only the honest dividing lines remain.
    grid_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(grid_layer)
    gw = max(1, ss)
    for _zone, rings in zones:
        for ring in rings:
            n = len(ring)
            base = [px(lon, lat) for lon, lat in ring]
            drawn = []  # per-segment keep flags
            for i in range(n):
                lon0, lat0 = ring[i]
                lon1, lat1 = ring[(i + 1) % n]
                cap = (lat0 >= POLAR_CAP_LAT and lat1 >= POLAR_CAP_LAT) or (
                    lat0 <= -POLAR_CAP_LAT and lat1 <= -POLAR_CAP_LAT
                )
                seam = abs(lon0) >= SEAM_LON and abs(lon1) >= SEAM_LON
                drawn.append(not (cap or seam))
            for c in wrap_copies(base):
                run: list[tuple[float, float]] = []  # batch kept segments into one polyline
                for i in range(n):
                    if drawn[i]:
                        if not run:
                            run = [c[i]]
                        run.append(c[(i + 1) % n])
                    elif len(run) >= 2:
                        ld.line(run, fill=tuple(theme["grid"]), width=gw)
                        run = []
                if len(run) >= 2:
                    ld.line(run, fill=tuple(theme["grid"]), width=gw)
    composite(grid_layer)

    # International Date Line — red, on top, wrapped so the +180/−180 pieces join up.
    idl = (*tuple(theme["idl"]), 255)
    iw = max(2, round(2 * ss))
    for seg in _named_lines("ne_10m_geographic_lines.geojson", "Date Line"):
        pts = [px(lon, lat) for lon, lat in seg]
        for c in wrap_copies(pts):
            d.line(c, fill=idl, width=iw)

    img = img.resize((out_w, out_h), Image.Resampling.LANCZOS)

    # Per-column UTC-offset labels at the bottom, drawn at native res for crisp text.
    # Placed on the nominal hour meridian (open ocean there, so they sit on the grid);
    # off-frame columns are skipped under the cropped projection.
    d2 = ImageDraw.Draw(img)
    label_col = tuple(theme["grid_label"])
    for off in range(-12, 13):
        x = to_px(off * 15, 0.0)[0]
        if x < 0 or x > out_w:
            continue
        text = "0" if off == 0 else f"{off:+d}"
        d2.text((x, out_h - 3), text, anchor="ms", font=font, fill=label_col)

    return img
