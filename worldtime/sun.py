"""Day/night terminator math (PORTABLE CORE, stdlib only).

Computes the subsolar point (where the sun is directly overhead) for a given UTC
instant, then the terminator latitude for any longitude. The terminator is the
great circle 90 degrees from the subsolar point; a point (lat, lon) is in daylight
when the solar elevation is positive:

    sin(lat)*sin(dec) + cos(lat)*cos(dec)*cos(lon - sublon) > 0

Solving elevation = 0 for the boundary latitude at a given longitude gives:

    tan(lat_term) = -cos(lon - sublon) / tan(dec)

This is seasonally accurate (declination changes the tilt), unlike the original
wallpaper's single sliding shadow image.
"""

import math
from datetime import UTC, datetime


def subsolar_point(dt_utc: datetime) -> tuple[float, float]:
    """Return (sublat, sublon) in degrees for the given UTC time.

    sublat is the solar declination; sublon is the longitude where it is solar
    noon. Uses the NOAA approximation (good to a fraction of a degree).
    """
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=UTC)
    dt_utc = dt_utc.astimezone(UTC)

    # Day of year (1-based) and fractional hour.
    doy = dt_utc.timetuple().tm_yday
    hour = dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0

    # Fractional year (radians).
    gamma = 2.0 * math.pi / 365.0 * (doy - 1 + (hour - 12) / 24.0)

    # Solar declination (radians) -> degrees.
    dec = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.001480 * math.sin(3 * gamma)
    )
    sublat = math.degrees(dec)

    # Equation of time (minutes).
    eot = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )

    # Subsolar longitude: solar noon (true solar time = 720 min) over this meridian.
    minutes_utc = dt_utc.hour * 60 + dt_utc.minute + dt_utc.second / 60.0
    sublon = (720.0 - (minutes_utc + eot)) / 4.0
    # Normalise to [-180, 180].
    sublon = (sublon + 180.0) % 360.0 - 180.0
    return sublat, sublon


def boundary_lat(lon: float, sublat: float, sublon: float, elevation: float = 0.0) -> float:
    """Latitude (deg) where the solar elevation equals `elevation`, clamped [-90, 90].

    Solving  sin(elev) = sin(lat)*sin(dec) + cos(lat)*cos(dec)*cos(H)  for lat:
    write the RHS as R*sin(lat + phi) with R = hypot(sin dec, cos dec cos H) and
    phi = atan2(cos dec cos H, sin dec); then lat = asin(sin(elev)/R) - phi.

    elevation = 0 is the day/night terminator; -6 / -12 / -18 are the civil /
    nautical / astronomical twilight boundaries. When there is no crossing in a
    column (|sin(elev)/R| > 1: that band's whole column is lit or dark), the value
    saturates to a pole, which clamps correctly for polygon filling.
    """
    dec = math.radians(sublat)
    h = math.radians(lon - sublon)
    e = math.radians(elevation)
    a = math.sin(dec)
    b = math.cos(dec) * math.cos(h)
    r = math.hypot(a, b)
    if r < 1e-9:
        return 0.0
    arg = max(-1.0, min(1.0, math.sin(e) / r))
    phi = math.atan2(b, a)
    lat = math.degrees(math.asin(arg) - phi)
    return max(-90.0, min(90.0, lat))


def terminator_lat(lon: float, sublat: float, sublon: float) -> float:
    """Day/night terminator latitude (solar elevation 0) at the given longitude."""
    return boundary_lat(lon, sublat, sublon, 0.0)


def night_is_south(sublat: float) -> bool:
    """True when the night (dark) hemisphere is south of the terminator.

    The north pole is lit exactly when the sun's declination is positive, so the
    dark region lies to the south then, and to the north otherwise.
    """
    return sublat > 0
