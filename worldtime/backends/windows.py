"""Windows backend (beta, untested) — set the desktop wallpaper via the Win32 API.

Windows has a single logical desktop wallpaper set through
``SystemParametersInfoW(SPI_SETDESKWALLPAPER, ...)``, reached here with stdlib
``ctypes`` (no dependency). This sets one image for the whole desktop; true
per-monitor wallpapers need the ``IDesktopWallpaper`` COM interface, which is not
wired up yet — so ``outputs()`` reports a single combined output.

Status: written without a Windows machine to test on. See the README's
"Windows & macOS (beta, untested)" section.
"""

import sys

# SystemParametersInfoW action + flags (winuser.h).
SPI_SETDESKWALLPAPER = 0x0014
SPIF_UPDATEINIFILE = 0x01  # persist the choice to the user profile
SPIF_SENDCHANGE = 0x02  # broadcast WM_SETTINGCHANGE so the change is live
# GetSystemMetrics indices (winuser.h).
SM_CXSCREEN = 0
SM_CYSCREEN = 1


def available():
    return sys.platform == "win32"


def outputs():
    """A single combined output sized to the primary screen (1920x1080 fallback).

    Per-monitor sizing/targeting is deferred (needs IDesktopWallpaper); one image
    covers the whole desktop for now.
    """
    width, height = 1920, 1080
    try:
        import ctypes

        # type-ignores: ctypes.windll/WinError only exist in Windows typeshed;
        # mypy runs on the Linux platform and this module is gated at runtime.
        w = int(ctypes.windll.user32.GetSystemMetrics(SM_CXSCREEN))  # type: ignore[attr-defined]
        h = int(ctypes.windll.user32.GetSystemMetrics(SM_CYSCREEN))  # type: ignore[attr-defined]
        if w > 0 and h > 0:
            width, height = w, h
    except Exception:
        pass
    return [{"name": "default", "width": width, "height": height, "scale": 1.0}]


def apply(name, png_path):
    import ctypes

    # SPI_SETDESKWALLPAPER takes the path as the pvParam (unicode) argument.
    ok = ctypes.windll.user32.SystemParametersInfoW(  # type: ignore[attr-defined]
        SPI_SETDESKWALLPAPER, 0, png_path, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
    )
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]
