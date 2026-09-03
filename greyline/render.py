"""Compose the World Time wallpaper image (PORTABLE CORE; deps: Pillow).

Pipeline (see plan): work in the map's 1400x1050 calibration frame for the smooth
day/night + twilight overlays and the home timezone-column highlight; cover-crop the
composited map to the target output size; then draw the city clocks at NATIVE output
resolution so text stays crisp on HiDPI panels.
"""

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFont, ImageOps

from . import cache, geo, sun, themes, vectormap
from .themes import _hex

ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets")
BASE_1400 = os.path.join(ASSET_DIR, "world.time.1400x1050.png")
LOGO_PNG = os.path.join(ASSET_DIR, "tux.png")

TWILIGHT_ELEVATIONS = (0.0, -6.0, -12.0, -18.0)

DARKNESS_ALPHA = {"subtle": 28, "medium": 40, "dramatic": 55}

FONT_CANDIDATES = [
    "Aporetic Sans",
    "AporeticSans",
    "Aporetic-Sans",
    "DejaVuSans.ttf",
    "DejaVu Sans",
    "segoeui.ttf",
    "arial.ttf",
    "Helvetica.ttc",
    "SFNS.ttf",
    "Arial.ttf",
]
FONT_BOLD_CANDIDATES = [
    "Aporetic Sans Bold",
    "AporeticSans-Bold",
    "DejaVuSans-Bold.ttf",
    "DejaVu Sans Bold",
    "segoeuib.ttf",
    "arialbd.ttf",
    "Helvetica.ttc",
    "SFNS.ttf",
    "Arial Bold.ttf",
]


@dataclass(frozen=True)
class Options:
    """Everything about a render the user chooses, as one value.

    These are exactly the knobs `config.toml` exposes, which is why they travel
    together: `from_config` is the only place the config dict is translated, and
    `render` reads nothing else from it. Keeping them out of `render`'s signature is
    what stops that signature growing a parameter per feature — it had twenty-six.

    Defaults here are the defaults a user gets, so `Options()` renders the same
    wallpaper as a config file that sets nothing.
    """

    theme: str = "modus"
    theme_overrides: dict | None = None
    fmt: str = "24h"
    twilight_bands: bool = True
    darkness: str = "subtle"
    column_highlight: bool = True
    home_color: str | None = None
    label_bg_alpha: int = 130
    map_style: str = "vector"
    logo: bool = True
    logo_path: str | None = None
    logo_color: str | None = None
    logo_invert: bool = False
    logo_scale: float = 1.0
    logo_max_height: float = 0.0
    bar_height: int = 0
    desaturate: bool = False
    font_scale: float = 1.0

    @classmethod
    def from_config(cls, cfg):
        """Build options from a loaded config dict.

        `config.load` has already checked every key against the schema, so the casts
        below cannot fail on a config that got this far; they are here to normalise
        TOML's ints-where-floats-are-fine, not to validate.
        """
        tw = cfg.get("twilight", {})
        home = cfg.get("home", {})
        default_alpha = 130 if cfg.get("label_background", True) else 0
        return cls(
            theme=cfg.get("theme", "modus"),
            theme_overrides=cfg.get("colors") or None,
            fmt=cfg.get("format", "24h"),
            twilight_bands=bool(tw.get("bands", True)),
            darkness=tw.get("darkness", "subtle"),
            column_highlight=bool(home.get("column_highlight", True)),
            home_color=home.get("color"),
            label_bg_alpha=int(cfg.get("label_bg_alpha", default_alpha)),
            map_style=cfg.get("map_style", "vector"),
            logo=bool(cfg.get("logo", True)),
            logo_path=cfg.get("logo_path"),
            logo_color=cfg.get("logo_color"),
            logo_invert=bool(cfg.get("logo_invert", False)),
            logo_scale=float(cfg.get("logo_scale", 1.0)),
            logo_max_height=float(cfg.get("logo_max_height", 0.0)),
            bar_height=int(cfg.get("bar_height", 0)),
            desaturate=bool(cfg.get("desaturate", False)),
            font_scale=float(cfg.get("font_scale", 1.0)),
        )


def _load_font(size, candidates, explicit=None):
    for name in ([explicit] if explicit else []) + candidates:
        if not name:
            continue
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


class Projection:
    """Maps geographic lon/lat to OUTPUT pixel coordinates (and back, for x and lat).

    `scale` is a sizing factor (relative to the 1400-wide reference) for fonts/dots so
    both map styles look consistent.
    """

    def __init__(self, to_px, x_to_lon, lat_to_y, scale):
        self.to_px = to_px
        self.x_to_lon = x_to_lon
        self.lat_to_y = lat_to_y
        self.scale = scale


def _cover_transform(ref_w, ref_h, out_w, out_h, anchor):
    """Scale + crop offsets mapping the ref frame onto the output (cover)."""
    scale = max(out_w / ref_w, out_h / ref_h)
    crop_x = (ref_w * scale - out_w) * anchor[0]
    crop_y = (ref_h * scale - out_h) * anchor[1]
    return scale, crop_x, crop_y


def _raster_projection(out_w, out_h, anchor):
    """Phase-A projection: the calibrated 1400x1050 affine, then cover-crop to output."""
    sc, cx, cy = _cover_transform(geo.REF_W, geo.REF_H, out_w, out_h, anchor)

    def to_px(lon, lat):
        rx, ry = geo.lonlat_to_px(lon, lat)
        return rx * sc - cx, ry * sc - cy

    proj = Projection(
        to_px,
        x_to_lon=lambda x: geo.x_to_lon((x + cx) / sc),
        lat_to_y=lambda lat: geo.lat_to_y(lat) * sc - cy,
        scale=sc,
    )
    return proj, (sc, cx, cy)


VECTOR_LON_CENTER = 12.0
VECTOR_LAT_CENTER = 0.0


def _vector_projection(out_w, out_h):
    ppd_lon = out_w / 360.0
    ppd_lat = ppd_lon * (abs(geo.BY) / abs(geo.AX))
    cx, cy = out_w / 2.0, out_h / 2.0
    return Projection(
        to_px=lambda lon, lat: (
            cx + (lon - VECTOR_LON_CENTER) * ppd_lon,
            cy + (VECTOR_LAT_CENTER - lat) * ppd_lat,
        ),
        x_to_lon=lambda x: VECTOR_LON_CENTER + (x - cx) / ppd_lon,
        lat_to_y=lambda lat: cy + (VECTOR_LAT_CENTER - lat) * ppd_lat,
        scale=out_w / geo.REF_W,
    )


def _vector_base(out_w, out_h, theme, font, proj, home_offset, font_desc):
    """The vector map base, served from the disk cache when it is there.

    Everything this draws is fixed for a given size, theme, font and home offset —
    the terminator and the clocks are composited on top afterwards — so on a machine
    whose wallpaper updates once a minute it is worth exactly one build per change.
    The browser demo has cached it on the same key from the start; this is the same
    idea in a process that cannot keep anything in memory between ticks.
    """
    key = cache.key_for((out_w, out_h), theme, font_desc, home_offset)
    cached = cache.load(key)
    if cached is not None:
        return cached
    base = vectormap.build_base(
        out_w, out_h, theme, font, proj.to_px, home_offset=home_offset
    ).convert("RGBA")
    cache.store(key, base)
    return base


def _terminator_polygon(elevation, sublat, sublon, proj, w, h, step=3, day_side=False):
    """Polygon (output px) for the region darker than `elevation` (or the lit side)."""
    pts = []
    x = 0
    while x <= w:
        lat = sun.boundary_lat(proj.x_to_lon(x), sublat, sublon, elevation)
        pts.append((x, max(0.0, min(float(h), proj.lat_to_y(lat)))))
        x += step
    close_bottom = sun.night_is_south(sublat) != day_side
    pts += [(w, h), (0, h)] if close_bottom else [(w, 0), (0, 0)]
    return pts


def _blend_region(base, layer_rgb, op):
    """Apply a blend `op` (ImageChops.multiply / .screen) of `layer_rgb` onto `base`,
    preserving base's alpha. The layer is a no-op colour everywhere except the band
    polygon (white for multiply, black for screen), so only that region changes."""
    mixed = op(base.convert("RGB"), layer_rgb)
    mixed.putalpha(base.getchannel("A"))
    return mixed


def _overlay_night(base, dt, theme, bands, alpha, proj):
    """Composite the day/night terminator with stepped twilight bands.

    Rather than alpha-compositing an opaque dark scrim (a "normal" blend, which mutes
    every pixel toward the same colour and so flattens the map's GMT grid lines and
    country borders), each band is mixed into the base multiplicatively/screen — a colour
    mix that tints toward night / brightens toward day while PRESERVING the contrast of
    fine lines underneath (works for both the raster art and the vector map):
      - day-side LIGHT washes (SCREEN toward the sun) — brighten the lit hemisphere;
      - night-side DARK washes (MULTIPLY toward midnight) — deepen the dark hemisphere.
    The civil/nautical/astronomical elevations are stacked, so each twilight band is a
    distinct step.
    """
    w, h = base.size
    sublat, sublon = sun.subsolar_point(dt)
    elevations = TWILIGHT_ELEVATIONS if bands else (0.0,)

    def stack(day_side, base_color, tint, op):
        nonlocal base
        for elev in elevations:
            layer = Image.new("RGB", (w, h), base_color)
            ImageDraw.Draw(layer).polygon(
                _terminator_polygon(elev, sublat, sublon, proj, w, h, day_side=day_side),
                fill=tint,
            )
            base = _blend_region(base, layer, op)

    dw = theme.get("day_wash")
    if dw:
        a = dw[3] if len(dw) > 3 else 255
        tint = tuple(round(c * a / 255) for c in dw[:3])
        stack(day_side=True, base_color=(0, 0, 0), tint=tint, op=ImageChops.screen)

    night = theme.get("night")
    if alpha > 0 and night:
        t = alpha / 255.0
        tint = tuple(round(255 - (255 - c) * t) for c in night)
        stack(day_side=False, base_color=(255, 255, 255), tint=tint, op=ImageChops.multiply)
    return base


def _recolor_dark(img, light_rgb, thresh=70):
    """Recolour near-black pixels (the wordmark text) to `light_rgb`, keeping coloured
    parts (the IBM bars) intact — so the logo reads on a dark background.

    A pixel is "near-black" when its brightest channel is under `thresh` and it is not
    fully transparent. Expressed in whole-image operations rather than a Python loop
    over `img.load()`: the logo is ~10% of the wallpaper's width, so at 4K that loop ran
    a couple of hundred thousand iterations of interpreted code on every tick that had
    `logo_invert` set — which, now that the map itself is cached, was a visible share of
    the remaining work.

    Alpha is carried over untouched, so anti-aliased edges survive.
    """
    r, g, b, a = img.split()
    brightest = ImageChops.lighter(ImageChops.lighter(r, g), b)
    is_dark = brightest.point(lambda v: 255 if v < thresh else 0)
    mask = ImageChops.multiply(is_dark, a.point(lambda v: 255 if v else 0))

    rgb = img.convert("RGB")
    rgb.paste(Image.new("RGB", img.size, tuple(light_rgb)), mask=mask)
    out = rgb.convert("RGBA")
    out.putalpha(a)
    return out


def _mono_logo(img, rgb):
    """Recolour the whole logo to a single colour (a flat silhouette), keeping its alpha
    (anti-aliased edges preserved). Used for an all-white logo, etc."""
    out = Image.new("RGBA", img.size, (*tuple(rgb), 255))
    out.putalpha(img.getchannel("A"))
    return out


def _draw_logo(
    canvas,
    theme,
    logo_path,
    bar_height=0,
    logo_color=None,
    logo_invert=False,
    logo_scale=1.0,
    logo_max_height=0.0,
):
    """Composite the logo, pinned to the bottom-left CORNER of the wallpaper (anchored to
    the canvas, independent of the map framing). Returns its bbox or None.

    `bar_height` lifts it above a status bar overlaying the bottom of the wallpaper.
    `logo_color` (hex) recolours the whole logo to a flat silhouette (e.g. all-white).
    `logo_invert` recolours the near-black pixels to light while keeping other colours —
    handy for a dark wordmark on a dark theme; off by default so colour logos (e.g. Tux)
    composite as-is.
    `logo_max_height` caps the drawn height to that fraction of the canvas height (0 = no
    cap); useful for tall/portrait logos that would otherwise blow up at the fixed width.
    """
    try:
        logo = Image.open(logo_path).convert("RGBA")
    except OSError:
        return None
    target_w = max(24, round(canvas.width * 0.104 * logo_scale))
    target_h = round(target_w * logo.height / logo.width)
    if logo_max_height and target_h > canvas.height * logo_max_height:
        target_h = round(canvas.height * logo_max_height)
        target_w = max(1, round(target_h * logo.width / logo.height))
    logo = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)
    mono = _hex(logo_color)
    if mono:
        logo = _mono_logo(logo, mono)
    elif logo_invert:
        logo = _recolor_dark(logo, tuple(theme.get("logo", (235, 235, 235))))
    pad = round(canvas.width * 0.018)
    x, y = pad, canvas.height - target_h - pad - bar_height
    canvas.alpha_composite(logo, (x, y))
    return (x, y, x + target_w, y + target_h)


def _rect_overlap(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def _place_labels(items, obstacles, bounds, scale):
    """Assign each label a non-overlapping box around its dot (right/left/above/below).

    Greedy: home first, then left-to-right. Each label picks the candidate side with the
    least overlap against obstacles (dots, logo, screen edges) and already-placed labels.
    A city's `label_side` ("left"/"right"/"above"/"below") is tried first; it still falls
    back to another side rather than overlap badly or run off-screen.
    """
    gap = round(6 * scale)
    placed = list(obstacles)
    order = sorted(range(len(items)), key=lambda i: (not items[i]["is_home"], items[i]["px"]))
    default_sides = ["right", "left", "below", "above", "below-right", "below-left"]
    for i in order:
        it = items[i]
        px, py, w, h, g = it["px"], it["py"], it["w"], it["h"], it["dotr"] + gap
        anchors = {
            "right": (px + g, py - h / 2),
            "left": (px - g - w, py - h / 2),
            "below": (px - w / 2, py + g),
            "above": (px - w / 2, py - g - h),
            "below-right": (px + g, py + g),
            "below-left": (px - g - w, py + g),
        }
        pref = it.get("side")
        sides = (
            [pref] + [s for s in default_sides if s != pref] if pref in anchors else default_sides
        )
        candidates = [anchors[s] for s in sides]
        best, best_pen = None, None
        for bx, by in candidates:
            box = (bx, by, bx + w, by + h)
            pen = sum(_rect_overlap(box, o) for o in placed)
            off = (
                max(0, bounds[0] - bx)
                + max(0, (bx + w) - bounds[2])
                + max(0, bounds[1] - by)
                + max(0, (by + h) - bounds[3])
            )
            pen += off * (w + h) * 3
            if best_pen is None or pen < best_pen:
                best, best_pen = box, pen
            if pen == 0:
                break
        it["box"] = best
        placed.append(best)


def _fmt_time(local, fmt):
    if fmt == "12h":
        h = local.hour % 12 or 12
        return f"{h}:{local.minute:02d} {'AM' if local.hour < 12 else 'PM'}"
    return f"{local.hour:02d}:{local.minute:02d}"


def _label_lines(city, dt, fmt):
    """City label: name + local time. Kept deliberately simple."""
    local = dt.astimezone(ZoneInfo(city["tz"]))
    return [city["name"], _fmt_time(local, fmt)]


def render(
    cities,
    options=None,
    *,
    dt=None,
    out_size=None,
    font_path=None,
    font_bold_path=None,
    base_path=BASE_1400,
    crop_anchor=(0.5, 1.0),
):
    """Compose the wallpaper for one output.

    `options` carries everything the user configures (see `Options`); the keyword
    arguments are the things resolved per invocation instead — the instant, the
    output size, and the font files fontconfig picked.
    """
    opt = options or Options()
    th = themes.load_theme(opt.theme, overrides=opt.theme_overrides)
    logo_path = opt.logo_path or LOGO_PNG
    dt = dt or datetime.now(UTC)
    alpha = th.get("night_alpha", DARKNESS_ALPHA.get(opt.darkness, DARKNESS_ALPHA["subtle"]))
    home_rgb = _hex(opt.home_color) or tuple(th["home"])
    out_w, out_h = out_size or (geo.REF_W, geo.REF_H)

    home = next((c for c in cities if c.get("home")), None)
    home_offset = None
    if home and opt.column_highlight:
        local = dt.astimezone(ZoneInfo(home["tz"]))
        off = local.utcoffset()
        if off is not None:
            std = off - (local.dst() or timedelta(0))
            home_offset = std.total_seconds() / 3600.0

    if opt.map_style == "vector":
        proj = _vector_projection(out_w, out_h)
        scale = proj.scale
        grid_size = max(8, round(11 * scale))
        grid_font = _load_font(grid_size, FONT_CANDIDATES, font_path)
        canvas = _vector_base(
            out_w, out_h, th, grid_font, proj, home_offset, (font_path or "", grid_size)
        )
    else:
        proj, (sc, cx, cy) = _raster_projection(out_w, out_h, crop_anchor)
        scale = sc
        if not os.path.isfile(base_path):
            raise FileNotFoundError(
                f"raster map artwork not found at {base_path}. The IBM/Lenovo 'World Time' "
                'art is not bundled (see NOTICE); use map_style="vector" or supply your own '
                "1400x1050 map via base_path."
            )
        base = Image.open(base_path).convert("RGBA")
        if opt.desaturate:
            gray = ImageOps.grayscale(base)
            gray = ImageEnhance.Contrast(gray).enhance(1.5)
            gray = ImageEnhance.Brightness(gray).enhance(0.7)
            base = gray.convert("RGBA")
        scaled = base.resize(
            (round(geo.REF_W * sc), round(geo.REF_H * sc)), Image.Resampling.LANCZOS
        )
        canvas = scaled.crop((round(cx), round(cy), round(cx) + out_w, round(cy) + out_h))

    if opt.column_highlight and home and opt.map_style != "vector":
        hx, _hy = proj.to_px(home["lon"], home["lat"])
        x0, _ = proj.to_px(home["lon"] - 7.5, home["lat"])
        x1, _ = proj.to_px(home["lon"] + 7.5, home["lat"])
        col_w = abs(x1 - x0)
        band = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
        ImageDraw.Draw(band).rectangle(
            [hx - col_w / 2, 0, hx + col_w / 2, out_h], fill=tuple(th["column"])
        )
        canvas = Image.alpha_composite(canvas, band)

    canvas = _overlay_night(canvas, dt, th, opt.twilight_bands, alpha, proj)

    obstacles = []
    if opt.logo:
        b = _draw_logo(
            canvas,
            th,
            logo_path,
            opt.bar_height,
            opt.logo_color,
            opt.logo_invert,
            opt.logo_scale,
            opt.logo_max_height,
        )
        if b:
            obstacles.append(b)

    fs = max(8, round(16 * scale * opt.font_scale))
    fs_home = max(10, round(20 * scale * opt.font_scale))
    font = _load_font(fs, FONT_CANDIDATES, font_path)
    font_home = _load_font(fs_home, FONT_BOLD_CANDIDATES, font_bold_path)
    draw = ImageDraw.Draw(canvas)

    items = []
    for c in cities:
        px, py = proj.to_px(c["lon"], c["lat"])
        if px < -40 or px > out_w + 40 or py < -40 or py > out_h + 40:
            continue
        is_home = bool(c.get("home"))
        f = font_home if is_home else font
        text = "\n".join(_label_lines(c, dt, opt.fmt))
        bb = draw.multiline_textbbox((0, 0), text, font=f, spacing=2, anchor="la")
        items.append(
            {
                "c": c,
                "is_home": is_home,
                "f": f,
                "text": text,
                "px": px,
                "py": py,
                "ox": bb[0],
                "oy": bb[1],
                "w": bb[2] - bb[0],
                "h": bb[3] - bb[1],
                "dotr": round((6 if is_home else 4) * scale),
                "side": c.get("label_side"),
            }
        )

    dot_boxes = [
        (it["px"] - it["dotr"], it["py"] - it["dotr"], it["px"] + it["dotr"], it["py"] + it["dotr"])
        for it in items
    ]
    m = round(10 * scale)
    _place_labels(
        items, obstacles + dot_boxes, (m, m, out_w - m, out_h - m - opt.bar_height), scale
    )

    if opt.label_bg_alpha > 0 and items:
        plate_rgb = tuple(th.get("label_bg", (0, 0, 0))[:3])
        pad_x = max(4, round(10 * scale * opt.font_scale))
        pad_y = max(3, round(7 * scale * opt.font_scale))
        rad = max(3, round(7 * scale * opt.font_scale))
        plate = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        pd = ImageDraw.Draw(plate)
        for it in items:
            bx0, by0, bx1, by1 = it["box"]
            pd.rounded_rectangle(
                [bx0 - pad_x, by0 - pad_y, bx1 + pad_x, by1 + pad_y],
                radius=rad,
                fill=(*plate_rgb, opt.label_bg_alpha),
            )
        canvas = Image.alpha_composite(canvas, plate)
        draw = ImageDraw.Draw(canvas)

    for it in items:
        is_home = it["is_home"]
        dot = home_rgb if is_home else th["dot"]
        txt = home_rgb if is_home else th["text"]
        stroke = th["home_stroke"] if is_home else th["text_stroke"]
        r = it["dotr"]
        px, py = it["px"], it["py"]
        draw.ellipse(
            [px - r, py - r, px + r, py + r],
            fill=dot,
            outline=th["dot_outline"],
            width=max(1, round(scale)),
        )
        draw.multiline_text(
            (it["box"][0] - it["ox"], it["box"][1] - it["oy"]),
            it["text"],
            font=it["f"],
            fill=txt,
            spacing=2,
            anchor="la",
            stroke_width=max(1, round(scale)),
            stroke_fill=stroke,
        )

    return canvas.convert("RGB")
