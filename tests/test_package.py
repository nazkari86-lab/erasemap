from importlib.metadata import version

import erasemap


def test_package_version_matches_metadata() -> None:
    assert erasemap.__version__ == version("erasemap")
