"""The browser demo's ported maths, checked against the Python it was ported from.

`web/sun.js`, `web/geo.js` and `web/config.js` are hand-written ports — "near-verbatim
port of sun.py", says the header — of the subtlest code in the project: the NOAA
declination series, the equation of time, the boundary-latitude solve, and the
projection. `web/themes.js` is protected from drift by a generator and a test. The
maths had neither, so a fix landing in `sun.py` and not in `sun.js` was invisible.

Both implementations are handed the same pinned inputs and their answers compared to
1e-9. Run through pytest rather than a second JavaScript test runner because that is
already how this repo checks its generated files (`test_wiki_docs`, `test_web_themes`
both shell out), and one runner and one CI job is enough for eight assertions.

Skipped where node is absent, so `pip install -e .[test] && pytest` still passes on a
machine that has no interest in the demo.
"""

import json
import math
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from worldtime import geo, render, sun

NODE = shutil.which("node")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")

pytestmark = pytest.mark.skipif(
    NODE is None or not os.path.isdir(WEB),
    reason="needs node and the web/ demo, which ship with the repo, not the package",
)

# Pinned instants: two solstices, an equinox, a leap day, and a year boundary.
INSTANTS = [
    (2024, 6, 20, 9, 30),
    (2024, 12, 21, 0, 0),
    (2024, 3, 20, 12, 0),
    (2024, 2, 29, 18, 45),
    (2025, 1, 1, 23, 59),
]


def _node(body):
    """Evaluate an ES module in web/ and parse the JSON it prints.

    The import base is built with `Path.as_uri()`, not by pasting the path after
    `file://`: on Windows that produces `file://D:\\a\\greyline\\web`, whose
    backslashes are then eaten as escape sequences by the JavaScript string literal,
    and node is handed `file://Dagreylineweb`.
    """
    assert NODE is not None  # guarded by pytestmark; narrows the type for mypy
    script = f"const W = {Path(WEB).as_uri()!r};\n{body}"
    result = subprocess.run(
        [NODE, "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        cwd=WEB,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _utc_args():
    return ", ".join(f"[{y},{m - 1},{d},{h},{mi}]" for y, m, d, h, mi in INSTANTS)


def test_subsolar_point_matches_python():
    got = _node(f"""
        const {{ subsolarPoint }} = await import(W + '/sun.js');
        const out = [{_utc_args()}].map((a) => subsolarPoint(new Date(Date.UTC(...a))));
        console.log(JSON.stringify(out));
    """)
    for (y, m, d, h, mi), (js_lat, js_lon) in zip(INSTANTS, got, strict=True):
        py_lat, py_lon = sun.subsolar_point(datetime(y, m, d, h, mi, tzinfo=UTC))
        assert js_lat == pytest.approx(py_lat, abs=1e-9), f"declination at {y}-{m}-{d}"
        assert js_lon == pytest.approx(py_lon, abs=1e-9), f"subsolar longitude at {y}-{m}-{d}"


def test_boundary_lat_matches_python_across_the_globe():
    """Every twilight elevation at every 15° of longitude — the terminator's shape."""
    lons = list(range(-180, 181, 15))
    elevations = [0.0, -6.0, -12.0, -18.0]
    got = _node(f"""
        const {{ subsolarPoint, boundaryLat }} = await import(W + '/sun.js');
        const [lat, lon] = subsolarPoint(new Date(Date.UTC(2024, 5, 20, 9, 30)));
        const out = [];
        for (const e of {json.dumps(elevations)})
          for (const g of {json.dumps(lons)}) out.push(boundaryLat(g, lat, lon, e));
        console.log(JSON.stringify(out));
    """)
    sublat, sublon = sun.subsolar_point(datetime(2024, 6, 20, 9, 30, tzinfo=UTC))
    expected = [sun.boundary_lat(lon, sublat, sublon, e) for e in elevations for lon in lons]
    assert len(got) == len(expected)
    for js, py in zip(got, expected, strict=True):
        assert js == pytest.approx(py, abs=1e-9)


def test_night_hemisphere_agrees():
    got = _node("""
        const { nightIsSouth } = await import(W + '/sun.js');
        console.log(JSON.stringify([10, -10, 0].map(nightIsSouth)));
    """)
    assert got == [sun.night_is_south(10), sun.night_is_south(-10), sun.night_is_south(0)]


def test_projection_matches_python():
    """geo.js ports both geo.py's constants and render.py's vector projection."""
    size = (1600, 900)
    points = [(0, 0), (139.69, 35.68), (-122.42, 37.77), (180, -60), (-180, 60)]
    got = _node(f"""
        const {{ makeProjection }} = await import(W + '/geo.js');
        const p = makeProjection({size[0]}, {size[1]});
        const pts = {json.dumps(points)};
        console.log(JSON.stringify({{
          scale: p.scale,
          toPx: pts.map(([lon, lat]) => p.toPx(lon, lat)),
          xToLon: [0, 400, 800, 1600].map((x) => p.xToLon(x)),
          latToY: [-90, -45, 0, 45, 90].map((l) => p.latToY(l)),
        }}));
    """)
    proj = render._vector_projection(*size)
    assert got["scale"] == pytest.approx(proj.scale, abs=1e-12)
    for (lon, lat), (jx, jy) in zip(points, got["toPx"], strict=True):
        px, py = proj.to_px(lon, lat)
        assert jx == pytest.approx(px, abs=1e-9) and jy == pytest.approx(py, abs=1e-9)
    for x, jl in zip([0, 400, 800, 1600], got["xToLon"], strict=True):
        assert jl == pytest.approx(proj.x_to_lon(x), abs=1e-9)
    for lat, jy in zip([-90, -45, 0, 45, 90], got["latToY"], strict=True):
        assert jy == pytest.approx(proj.lat_to_y(lat), abs=1e-9)


def test_geo_constants_match():
    got = _node("""
        const g = await import(W + '/geo.js');
        console.log(JSON.stringify({
          REF_W: g.REF_W, REF_H: g.REF_H, AX: g.AX, BY: g.BY,
          lon: g.VECTOR_LON_CENTER, lat: g.VECTOR_LAT_CENTER,
        }));
    """)
    assert got["REF_W"] == geo.REF_W and got["REF_H"] == geo.REF_H
    assert got["AX"] == geo.AX and got["BY"] == geo.BY
    assert got["lon"] == render.VECTOR_LON_CENTER
    assert got["lat"] == render.VECTOR_LAT_CENTER


@pytest.mark.parametrize("fmt", ["24h", "12h"])
def test_clock_labels_match_python(fmt):
    """Covers midnight and noon, where 12-hour formatting traditionally goes wrong."""
    cities = [
        {"name": "London", "tz": "Europe/London"},
        {"name": "Tokyo", "tz": "Asia/Tokyo"},
        {"name": "Kathmandu", "tz": "Asia/Kathmandu"},  # UTC+5:45
    ]
    stamps = [(2024, 6, 20, 15, 0), (2024, 1, 15, 3, 30), (2024, 1, 15, 12, 0)]
    got = _node(f"""
        const {{ labelLines }} = await import(W + '/config.js');
        const cities = {json.dumps(cities)};
        const out = [];
        for (const a of {json.dumps([[y, m - 1, d, h, mi] for y, m, d, h, mi in stamps])})
          for (const c of cities)
            out.push(labelLines(c, new Date(Date.UTC(...a)), {fmt!r}));
        console.log(JSON.stringify(out));
    """)
    expected = []
    for y, m, d, h, mi in stamps:
        dt = datetime(y, m, d, h, mi, tzinfo=UTC)
        for c in cities:
            local = dt.astimezone(ZoneInfo(c["tz"]))
            expected.append([c["name"], render._fmt_time(local, fmt)])
    assert got == expected


def test_the_ported_modules_are_the_ones_under_test():
    """A guard against this file quietly testing nothing if web/ is restructured."""
    for name in ("sun.js", "geo.js", "config.js"):
        assert os.path.isfile(os.path.join(WEB, name)), name
    assert math.isfinite(sun.boundary_lat(0.0, 23.4, 0.0, 0.0))
