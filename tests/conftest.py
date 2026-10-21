import sys

import pytest


@pytest.fixture(autouse=True)
def trash(tmp_path, monkeypatch):
    """Point send2trash at a per-test trash (Linux, where CI runs the tests).

    send2trash reads XDG_DATA_HOME once, when first imported, so setting the variable isn't enough.
    """
    data_home = tmp_path / "xdg"
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    if sys.platform == "linux":
        import send2trash.plat_other as plat_other

        monkeypatch.setattr(plat_other, "XDG_DATA_HOME", bytes(data_home))
        monkeypatch.setattr(plat_other, "HOMETRASH_B", bytes(data_home / "Trash"))
        monkeypatch.setattr(plat_other, "HOMETRASH", str(data_home / "Trash"))
    return data_home / "Trash" / "files"
