#!/usr/bin/env python3
"""Prepare the bundled Natural Earth GeoJSON: drop unused properties, round coordinates.

The files under worldtime/geodata/ are Natural Earth (public domain), but they are not
byte-for-byte upstream — they are upstream put through this script, and this docstring
is the record of what was done to them:

    properties   Only the ones greyline reads survive: `zone` on the timezone polygons
                 (which band a shape belongs to) and `name` on the geographic lines
                 (to find the Date Line). Natural Earth ships fifteen fields per
                 timezone feature — `tz_namesum`, `map_color8`, `dst_places` and the
                 rest — and none of them are ever looked at. Dropping them cannot
                 change a pixel.

    coordinates  Rounded to 3 decimal places, about 110 m. A pixel at 4K is roughly
                 10 km of longitude, so this is a hundredth of a pixel. It is not
                 quite free: Pillow's ImageDraw has no antialiasing, so the map is
                 drawn hard-edged at 2x and downsampled, and a coordinate moving a
                 hundredth of a pixel can still flip which supersampled pixel a
                 hairline border lands in. Measured at 1080p that shows up on 0.25%
                 of pixels, all of them on 1px lines. 2dp would halve the file again
                 and disturb 1.9%, which starts to be visible; 3dp is the point where
                 the saving stops being free but the difference still is not.

Together: 4.57 MB to 2.91 MB in the wheel, and 1.57 MB to 0.87 MB gzipped over the
wire for the browser demo, whose first paint was dominated by the 10m timezone file.

    python tools/prep_geodata.py --source /tmp/natural-earth --out worldtime/geodata
    python tools/prep_geodata.py --check   # fail if the bundled files are not prepared
"""

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEO_DIR = os.path.join(ROOT, "worldtime", "geodata")

PRECISION = 3

# filename -> the properties greyline actually reads from it.
KEEP = {
    "ne_110m_land.geojson": set(),
    "ne_110m_admin_0_countries.geojson": set(),
    "ne_10m_time_zones.geojson": {"zone"},
    "ne_10m_geographic_lines.geojson": {"name"},
}


def _round(node, places):
    if isinstance(node, list):
        return [_round(x, places) for x in node]
    if isinstance(node, float):
        return round(node, places)
    return node


def prepare(raw, keep, places=PRECISION):
    """Return the prepared GeoJSON bytes for one file."""
    gj = json.loads(raw)
    for feature in gj["features"]:
        feature["geometry"]["coordinates"] = _round(feature["geometry"]["coordinates"], places)
        feature["properties"] = {k: v for k, v in feature["properties"].items() if k in keep}
    return json.dumps(gj, separators=(",", ":")).encode("utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", help="directory of upstream Natural Earth GeoJSON")
    ap.add_argument("--out", default=GEO_DIR, help="directory to write into")
    ap.add_argument(
        "--check",
        action="store_true",
        help="verify the bundled files are already prepared; write nothing",
    )
    args = ap.parse_args(argv)

    if args.check:
        stale = []
        for name, keep in KEEP.items():
            path = os.path.join(GEO_DIR, name)
            with open(path, "rb") as f:
                current = f.read()
            if prepare(current, keep) != current:
                stale.append(name)
        if stale:
            print(f"not prepared, run tools/prep_geodata.py: {', '.join(stale)}", file=sys.stderr)
            return 1
        return 0

    if not args.source:
        ap.error("--source is required unless --check is given")
    for name, keep in KEEP.items():
        with open(os.path.join(args.source, name), "rb") as f:
            raw = f.read()
        out = prepare(raw, keep)
        with open(os.path.join(args.out, name), "wb") as f:
            f.write(out)
        print(f"{name}: {len(raw) / 1e6:.2f} MB -> {len(out) / 1e6:.2f} MB", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
