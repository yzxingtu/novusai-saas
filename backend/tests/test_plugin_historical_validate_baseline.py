"""Historical/sample plugin validate baseline tests. / 历史/样例插件 validate 基线测试。"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = _BACKEND_DIR / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import plugin_cli as pc


@pytest.mark.parametrize(
    "plugin_dir",
    [
        _BACKEND_DIR
        / "plugins/.backups/netdisk/1.0.0_20260316_201902/files",
        _BACKEND_DIR
        / "plugins/.backups/novus-crud-code/1.0.0_20260314_083358/files",
        _BACKEND_DIR
        / "plugins/.backups/regression-probe/0.0.1_20260303_090249/files",
        _BACKEND_DIR
        / "plugins/.backups/example-weather/1.0.0_20260303_091616/files",
    ],
)
def test_historical_plugin_validate_baseline(
    plugin_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        pc.cmd_validate(SimpleNamespace(dir=str(plugin_dir)))

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "plugin.yaml valid" in out
