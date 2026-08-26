#!/usr/bin/env python3
"""Derive the lon/lat -> pixel affine for the ThinkPad map's 1400x1050 reference frame.

Ground truth: the original worldtime.cities.js places each city's clock at
(OffsetX, OffsetY) in a 1400-wide reference (ratio = imgWidth/1400, so on the
1400x1050 base the offsets ARE the pixel coords). We pair those with each city's
real lat/lon and least-squares fit:

    x = ax*lon + bx*lat + cx
    y = ay*lon + by*lat + cy

Prints the coefficients (to hardcode into geo.py) + per-city residuals, and writes
an overlay PNG (computed = green ring, original offset = red dot) for visual check.
"""
import numpy as np
from PIL import Image, ImageDraw

CAL = {
    "San Francisco": (-122.42, 37.77, 62, 430),
    "New York":      (-74.01, 40.71, 295, 419),
    "Buenos Aires":  (-58.38, -34.61, 339, 810),
    "London":        (-0.13, 51.51, 556, 358),
    "Paris":         (2.35, 48.85, 576, 376),
    "Moscow":        (37.62, 55.76, 776, 286),
    "Beijing":       (116.41, 39.90, 1080, 438),
    "Tokyo":         (139.69, 35.68, 1168, 450),
    "Sydney":        (151.21, -33.87, 1218, 796),
    "Jakarta":       (106.85, -6.21, 1029, 650),
}

names = list(CAL)
lon = np.array([CAL[n][0] for n in names])
lat = np.array([CAL[n][1] for n in names])
px = np.array([CAL[n][2] for n in names], float)
py = np.array([CAL[n][3] for n in names], float)

A = np.column_stack([lon, lat, np.ones_like(lon)])
cx, *_ = np.linalg.lstsq(A, px, rcond=None)
cy, *_ = np.linalg.lstsq(A, py, rcond=None)

print("X: ax=%.6f bx=%.6f cx=%.4f" % tuple(cx))
print("Y: ay=%.6f by=%.6f cy=%.4f" % tuple(cy))

fx = A @ cx
fy = A @ cy
print("\nresiduals (px):")
for i, n in enumerate(names):
    print("  %-14s dx=%+6.1f dy=%+6.1f" % (n, fx[i] - px[i], fy[i] - py[i]))
print("RMS: dx=%.1f dy=%.1f" % (np.sqrt(((fx-px)**2).mean()), np.sqrt(((fy-py)**2).mean())))

img = Image.open("../assets/world.time.1400x1050.png").convert("RGB")
d = ImageDraw.Draw(img)
for i, n in enumerate(names):
    d.ellipse([px[i]-4, py[i]-4, px[i]+4, py[i]+4], fill=(255, 60, 60))
    cxx, cyy = fx[i], fy[i]
    d.ellipse([cxx-7, cyy-7, cxx+7, cyy+7], outline=(60, 255, 60), width=2)
img.save("/tmp/calib_overlay.png")
print("\nwrote /tmp/calib_overlay.png")
