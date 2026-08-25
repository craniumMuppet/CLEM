"""Historical v2.29.22 regression-path compatibility marker.

Active release-integrity coverage moved to test_v22923_engineering_corrections.py.
The file remains packaged so historical v2.29.22 tooling does not reference a
missing path.
"""

from pathlib import Path


def test_v22922_regression_path_is_superseded_by_v22923_suite() -> None:
    active_suite = Path(__file__).with_name("test_v22923_engineering_corrections.py")
    assert active_suite.is_file()
