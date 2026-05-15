from __future__ import annotations

from pathlib import Path

from app.core import hosts_helper
from app.core.config import settings


class _FakeLogger:
    def __init__(self) -> None:
        self.infos: list[str] = []
        self.warnings: list[str] = []

    def info(self, message: str, *args) -> None:
        assert args == ()
        self.infos.append(message)

    def warning(self, message: str, *args) -> None:
        assert args == ()
        self.warnings.append(message)


def _patch_windows_hosts(monkeypatch, hosts_path: Path) -> None:
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    monkeypatch.setattr(hosts_helper.platform, "system", lambda: "Windows")
    monkeypatch.setitem(hosts_helper._HOSTS_PATHS, "Windows", hosts_path)


def test_runtime_info_reports_writable_when_hosts_file_can_be_opened(
    monkeypatch, tmp_path
):
    """中文: 真实可打开写句柄时才报告可写。EN: Report writable only when a write handle can be opened."""
    hosts_path = tmp_path / "hosts"
    hosts_path.write_text("", encoding="utf-8")
    _patch_windows_hosts(monkeypatch, hosts_path)

    result = hosts_helper.get_runtime_info()

    assert result["enabled"] is True
    assert result["can_write_hint"] is True
    assert result["requires_elevation"] is False


def test_runtime_info_does_not_trust_os_access_when_hosts_open_is_denied(
    monkeypatch, tmp_path
):
    """中文: Windows ACL/UAC 下 os.access 可能误报，必须以实际打开结果为准。EN: Under Windows ACL/UAC, os.access can be optimistic; the open probe wins."""
    hosts_path = tmp_path / "hosts"
    hosts_path.write_text("", encoding="utf-8")
    _patch_windows_hosts(monkeypatch, hosts_path)
    monkeypatch.setattr(hosts_helper.os, "access", lambda *_args, **_kwargs: True)

    original_open = Path.open

    def deny_hosts_open(self: Path, *args, **kwargs):
        if self == hosts_path:
            raise PermissionError("denied")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny_hosts_open)

    result = hosts_helper.get_runtime_info()

    assert result["enabled"] is True
    assert result["can_write_hint"] is False
    assert result["requires_elevation"] is True


def test_add_host_entry_success_log_interpolates_values(monkeypatch, tmp_path):
    """中文: hosts 写入成功日志不能泄漏占位符。EN: Successful hosts write logs must interpolate values."""
    hosts_path = tmp_path / "hosts"
    hosts_path.write_text("", encoding="utf-8")
    _patch_windows_hosts(monkeypatch, hosts_path)
    fake_logger = _FakeLogger()
    monkeypatch.setattr(hosts_helper, "logger", fake_logger)

    assert hosts_helper.add_host_entry("demo.local") is True

    assert "127.0.0.1  demo.local" in hosts_path.read_text(encoding="utf-8")
    assert len(fake_logger.infos) == 1
    assert "%s" not in fake_logger.infos[0]
    assert "demo.local" in fake_logger.infos[0]
    assert str(hosts_path) in fake_logger.infos[0]


def test_permission_warning_log_interpolates_values(monkeypatch, tmp_path):
    """中文: 权限失败提示必须显示真实命令和路径。EN: Permission warnings must show real command and path values."""
    hosts_path = tmp_path / "hosts"
    _patch_windows_hosts(monkeypatch, hosts_path)
    fake_logger = _FakeLogger()
    monkeypatch.setattr(hosts_helper, "logger", fake_logger)

    hosts_helper._print_permission_warning("add", "w2w.w.cn", hosts_path)

    assert len(fake_logger.warnings) == 1
    warning = fake_logger.warnings[0]
    assert "%s" not in warning
    assert "Cannot add hosts entry" in warning
    assert "Action : add" in warning
    assert "w2w.w.cn" in warning
    assert str(hosts_path) in warning
    assert "python -m app.core.hosts_helper add w2w.w.cn" in warning
