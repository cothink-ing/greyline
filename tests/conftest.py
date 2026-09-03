"""Shared fixtures.

The renderer writes its map-base cache under `$XDG_CACHE_HOME`, and the suite renders
a few hundred images. Point that at a throwaway directory for every test so a test run
neither reads nor evicts the developer's real cache — and so cache-sensitive tests
start from a known-empty one.
"""

import pytest


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    return tmp_path / "cache" / "greyline"
