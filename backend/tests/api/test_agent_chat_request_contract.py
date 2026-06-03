"""
Test type: structural
Scope: public agent chat request contract for admin, tenant, and user surfaces.
Mock strategy: Source-level assertions only; the contract is that transport
schemas no longer expose or forward retired batch-message input.
"""

from __future__ import annotations

from pathlib import Path


def test_agent_chat_api_does_not_forward_retired_messages_batch_input() -> None:
    """中文: 测试类型 structural；三端 chat API 不再转发退役 messages 输入。

    EN: Test type structural; the three chat API surfaces no longer forward
    retired messages input.
    """
    backend_root = Path(__file__).resolve().parents[2]
    api_files = [
        backend_root / "app/api/admin/ai_agent_chat.py",
        backend_root / "app/api/tenant/agent_chat.py",
        backend_root / "app/api/user/agent_chat.py",
    ]

    for api_file in api_files:
        source = api_file.read_text(encoding="utf-8")
        assert "messages=data.messages" not in source
        assert "data.messages" not in source


def test_agent_chat_services_do_not_keep_retired_messages_batch_branch() -> None:
    """中文: 测试类型 structural；服务层不再保留退役 messages 批量分支。

    EN: Test type structural; service layer no longer keeps the retired
    messages batch branch.
    """
    backend_root = Path(__file__).resolve().parents[2]
    service_files = [
        backend_root / "app/services/ai/agent_chat_service.py",
        backend_root / "app/services/ai/agent_chat_command_service.py",
    ]

    for service_file in service_files:
        source = service_file.read_text(encoding="utf-8")
        assert "messages: list[str]" not in source
        assert "messages=messages" not in source
        assert "batch = messages" not in source
