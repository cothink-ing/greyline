"""The browser demo's palettes are generated from worldtime/themes/*.toml — this is
the check that keeps them from drifting apart again (they did, pre-0.7)."""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "sync_web_themes.py")


@pytest.mark.skipif(not os.path.exists(TOOL),
                    reason="tools/ and web/ ship with the repo, not with the package")
def test_web_themes_js_is_in_sync():
    rc = subprocess.run(
        [sys.executable, TOOL, "--check"], capture_output=True, text=True, cwd=ROOT,
    )
    assert rc.returncode == 0, rc.stderr.strip() or "web/themes.js is stale"
