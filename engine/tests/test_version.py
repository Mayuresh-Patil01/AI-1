import json
from pathlib import Path

from sortified import __version__


def test_engine_and_ui_versions_match():
    package = json.loads((Path(__file__).parents[2] / "ui" / "package.json").read_text())
    assert package["version"] == __version__, "Update the version in both engine/sortified/__init__.py and ui/package.json"
