"""Geographic <-> pixel mapping for the ThinkPad map (PORTABLE CORE, no deps).

The ThinkPad "World Time" artwork is an equirectangular world map, cropped and
offset (it is NOT centred on lon 0). We model lon/lat -> pixel as a 2D affine in
the map's native 1400x1050 reference frame:

    x = AX*lon + BX*lat + CX
    y = AY*lon + BY*lat + CY

The coefficients were least-squares fit (reference/calibrate.py) from the 10 cities
in the original worldtime.cities.js, each pairing a real lon/lat with the author's
OffsetX/OffsetY. RMS residual ~17 px over 1400; the near-zero cross terms (BX, AY)
confirm the projection is equirectangular with negligible rotation/shear.

All rendering happens in this 1400x1050 frame, then the final image is cover-scaled
to the target output resolution (see render.py). That keeps a single calibration.
"""

REF_W = 1400
REF_H = 1050

AX, BX, CX = 4.207694, 0.039820, 583.0723
AY, BY, CY = -0.005353, -5.260840, 625.3477


def lonlat_to_px(lon: float, lat: float) -> tuple[float, float]:
    """Map geographic lon/lat (degrees) to (x, y) pixels in the 1400x1050 frame."""
    x = AX * lon + BX * lat + CX
    y = AY * lon + BY * lat + CY
    return x, y


def x_to_lon(x: float) -> float:
    """Inverse of the x mapping (BX is negligible, so we ignore the lat term).

    Used to sweep the terminator across pixel columns.
    """
    return (x - CX) / AX


def lat_to_y(lat: float) -> float:
    """Map a latitude to its y pixel (lon term negligible; use frame centre lon)."""
    return BY * lat + CY
