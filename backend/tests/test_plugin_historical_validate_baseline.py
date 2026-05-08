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

from plugin_cli_validate import cmd_validate  # noqa: E402


@pytest.mark.parametrize(
    ("plugin_dir", "expected_exit_code", "expected_fragment"),
    [
        (
            _BACKEND_DIR / "plugins/.backups/netdisk/1.0.0_20260316_201902/files",
            1,
            "Plugin metadata icon must be empty or 'icon.png'",
        ),
        (
            _BACKEND_DIR
            / "plugins/.backups/novus-crud-code/1.0.0_20260314_083358/files",
            1,
            "Plugin metadata icon must be empty or 'icon.png'",
        ),
        (
            _BACKEND_DIR
            / "plugins/.backups/regression-probe/0.0.1_20260303_090249/files",
            0,
            "plugin.yaml valid",
        ),
        (
            _BACKEND_DIR
            / "plugins/.backups/example-weather/1.0.0_20260303_091616/files",
            0,
            "plugin.yaml valid",
        ),
    ],
)
def test_historical_plugin_validate_baseline(
    plugin_dir: Path,
    expected_exit_code: int,
    expected_fragment: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    if not plugin_dir.exists() or not plugin_dir.is_dir():
        pytest.skip(f"Historical plugin fixture not found: {plugin_dir}")

    with pytest.raises(SystemExit) as exc:
        cmd_validate(SimpleNamespace(dir=str(plugin_dir)))

    assert exc.value.code == expected_exit_code
    out = capsys.readouterr().out
    if "Not a directory:" in out:
        pytest.skip(f"Historical plugin fixture not found: {plugin_dir}")
    assert expected_fragment in out
