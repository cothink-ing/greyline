"""The wiki's reference pages are generated from `greyline help <topic>` — this is
the check that keeps the published pages from drifting away from the code, the way
the README's hand-maintained copies of them did."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "gen_wiki.py")
WIKI = os.path.join(ROOT, "docs", "wiki")

pytestmark = pytest.mark.skipif(
    not os.path.exists(TOOL), reason="tools/ and docs/ ship with the repo, not with the package"
)


def test_generated_pages_are_in_sync():
    rc = subprocess.run(
        [sys.executable, TOOL, "--check"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert rc.returncode == 0, rc.stderr.strip() or "docs/wiki is stale"


def test_every_help_topic_has_a_page():
    from greyline import helptext

    topics = set(helptext.topic_names()) - {"topics"}
    generated = {topic for _, topic, _, _ in _pages()}
    assert topics == generated, "a `greyline help` topic has no wiki page (or vice versa)"


def test_generated_pages_describe_no_particular_machine():
    """The help pages name the config dir, the packaged theme dir and the backend
    running right now. None of that is true for a reader of the wiki."""
    for title, *_ in _pages():
        text = Path(WIKI, f"{title}.md").read_text(encoding="utf-8")
        assert os.path.expanduser("~") not in text, f"{title}.md leaks a home directory"
        assert ROOT not in text, f"{title}.md leaks the checkout path"
        assert "Detected here" not in text, f"{title}.md names this machine's backend"


def _pages():
    return _gen_wiki().PAGES


def test_normalise_is_platform_independent(monkeypatch):
    """A Windows checkout has to generate byte-identical pages, or --check fails
    there and nowhere else. It did, until the separators were normalised too."""
    gen_wiki = _gen_wiki()
    monkeypatch.setattr(gen_wiki.os, "sep", "\\")
    monkeypatch.setattr(gen_wiki, "ROOT", "D:\\a\\greyline\\greyline")
    sentinel = "C:\\Temp\\tmp42"
    windows_output = "\n".join(
        [
            f"Your config: {sentinel}\\greyline\\config.toml",
            "Detected here: sway",
            "  D:\\a\\greyline\\greyline\\greyline\\themes\\modus.toml",
        ]
    )
    assert gen_wiki._normalise(windows_output, sentinel) == "\n".join(
        [
            "Your config: ~/.config/greyline/config.toml",
            "  greyline/themes/modus.toml",
        ]
    )


def _gen_wiki():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import gen_wiki

    return gen_wiki


def test_bundled_geodata_is_prepared():
    """The Natural Earth files are shipped stripped and rounded (see NOTICE and
    tools/prep_geodata.py). Re-vendoring an upstream file without re-running the
    script would silently put 1.7 MB back into the wheel."""
    tool = os.path.join(ROOT, "tools", "prep_geodata.py")
    rc = subprocess.run([sys.executable, tool, "--check"], capture_output=True, text=True, cwd=ROOT)
    assert rc.returncode == 0, rc.stderr.strip() or "geodata is not prepared"
