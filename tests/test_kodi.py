import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from yleareena.errors import YleUnavailableError


@pytest.mark.parametrize("action", ["play", "browse_tv"])
def test_errors_finish_the_correct_kodi_operation(monkeypatch, action: str) -> None:
    plugin = SimpleNamespace(setResolvedUrl=Mock(), endOfDirectory=Mock())
    gui = SimpleNamespace(ListItem=Mock(), Dialog=lambda: SimpleNamespace(ok=Mock()))
    addon = SimpleNamespace(getAddonInfo=lambda _: "plugin.video.ylearenakodi", getLocalizedString=lambda _: "Error")
    monkeypatch.setitem(sys.modules, "xbmc", SimpleNamespace(log=Mock(), LOGERROR=1))
    monkeypatch.setitem(sys.modules, "xbmcgui", gui)
    monkeypatch.setitem(sys.modules, "xbmcplugin", plugin)
    monkeypatch.setitem(sys.modules, "xbmcaddon", SimpleNamespace(Addon=lambda: addon))
    monkeypatch.setattr(sys, "argv", ["plugin://test", "1", f"?action={action}&id=1-123"])
    spec = importlib.util.spec_from_file_location("kodi_entry_test", Path(__file__).parent.parent / "default.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_dispatch", Mock(side_effect=YleUnavailableError("Unavailable")))

    module.main()

    if action == "play":
        plugin.setResolvedUrl.assert_called_once_with(1, False, gui.ListItem.return_value)
        plugin.endOfDirectory.assert_not_called()
    else:
        plugin.endOfDirectory.assert_called_once_with(1, succeeded=False)
        plugin.setResolvedUrl.assert_not_called()
