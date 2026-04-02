# Phase 3: 增强调用日志 - AI 执行提示词

你是一个 Python 后端工程师，负责在 NovusAI SaaS 项目中实施 Phase 3：增强调用日志功能。

---

## 任务目标

在 `ai_call_logs` 表中添加 `call_type` 字段，区分主对话调用和内部调用，解决对话 618 中调用日志混淆的问题。

---

## 背景信息

**问题**: 对话 618 的调用日志 1071 是内部记忆提取调用，不是主对话调用，导致 CLI 显示误导性信息。

**目标**: 
- 添加 `call_type` 字段区分调用类型
- CLI 查询对话时只显示主调用日志
- 为未来的调用统计提供基础

**详细方案**: 见 `.trellis/tasks/04-02-conversation-618-diagnosis/phase3-implementation-plan.md`

---

## 实施步骤

### Step 1: 创建数据库迁移 (必做)

**创建文件**: `backend/migrations/versions/20260402_add_call_type_to_ai_call_logs.py`

**参考最近的迁移文件**: `backend/migrations/versions/20260305_add_tenant_scoped_unique_constraints.py`

**迁移内容**:
```python
"""add call_type to ai_call_logs

Adds call_type field to distinguish main chat calls from internal calls.

Revision ID: 20260402_call_type
Revises: 20260305_tenant_uq
Create Date: 2026-04-02 00:00:00.000000+00:00
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "20260402_call_type"
down_revision: str | Sequence[str] | None = "20260305_tenant_uq"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add call_type field and indexes"""
    # 1. 添加 call_type 字段
    op.add_column(
        'ai_call_logs',
        sa.Column(
            'call_type',
            sa.String(length=50),
            server_default='main_chat',
            nullable=False,
            comment='调用类型: main_chat/internal_memory/internal_tool'
        )
    )
    
    # 2. 创建单字段索引
    op.create_index(
        'idx_ai_call_logs_call_type',
        'ai_call_logs',
        ['call_type']
    )
    
    # 3. 创建复合索引（conversation_id + call_type）
    op.create_index(
        'idx_ai_call_logs_conv_call_type',
        'ai_call_logs',
        ['conversation_id', 'call_type']
    )


def downgrade() -> None:
    """Remove call_type field and indexes"""
    op.drop_index('idx_ai_call_logs_conv_call_type', 'ai_call_logs')
    op.drop_index('idx_ai_call_logs_call_type', 'ai_call_logs')
    op.drop_column('ai_call_logs', 'call_type')
```

**执行迁移**:
```bash
cd backend
python -m app.cli db upgrade heads
```

**验证迁移**:
```bash
# 检查字段是否创建
python -c "from app.models.ai.call_log import AICallLog; print(AICallLog.__table__.columns.keys())"
```

---

### Step 2: 创建枚举类 (必做)

**文件**: `backend/app/enums/ai.py`

**在文件末尾添加**:
```python
class CallTypeEnum(str, Enum):
    """AI 调用类型枚举 / AI call type enum"""
    
    MAIN_CHAT = "main_chat"  # 主对话调用
    INTERNAL_MEMORY = "internal_memory"  # 内部记忆提取
    INTERNAL_TOOL = "internal_tool"  # 内部工具调用
    
    @classmethod
    def values(cls) -> list[str]:
        """返回所有枚举值"""
        return [e.value for e in cls]
```

**同时在文件顶部的 `__all__` 中添加**:
```python
__all__ = [
    # ... 现有导出 ...
    "CallTypeEnum",  # 添加这一行
]
```

---

### Step 3: 修改模型 (必做)

**文件**: `backend/app/models/ai/call_log.py`

**修改位置 1**: 在 `request_type` 字段后（约 156 行）添加:
```python
# 调用类型 / Call type (main_chat, internal_memory, internal_tool)
call_type: Mapped[str] = mapped_column(
    String(50),
    nullable=False,
    default='main_chat',
    server_default='main_chat',
    index=True,
    comment='调用类型: main_chat(主对话)/internal_memory(内部记忆)/internal_tool(内部工具)'
)
```

**修改位置 2**: 在 `__filterable__` 字典中（约 58 行）添加:
```python
__filterable__ = {
    # ... 现有字段 ...
    "request_type": "request_type",
    "call_type": "call_type",  # 添加这一行
    "status": "status",
    # ... 其他字段 ...
}
```

---

### Step 4: 修改调用日志创建逻辑 (必做)

**需要查找的文件**:
```bash
# 查找所有创建 AICallLog 的位置
grep -r "AICallLog(" backend/app --include="*.py" | grep -v test | grep -v __pycache__
```

**主要修改点**:

1. **主对话调用** - 在 `backend/app/services/ai/conversation_service.py` 或类似文件中:
```python
# 导入枚举
from app.enums.ai import CallTypeEnum

# 修改创建调用日志的代码
call_log = await call_log_repo.create(
    tenant_id=tenant_id,
    provider_id=provider_id,
    call_type=CallTypeEnum.MAIN_CHAT,  # 添加这一行
    # ... 其他字段
)
```

2. **内部记忆调用** - 查找记忆提取相关代码:
```python
call_log = await call_log_repo.create(
    # ... 其他字段
    call_type=CallTypeEnum.INTERNAL_MEMORY,  # 添加这一行
)
```

3. **内部工具调用** - 查找工具调用相关代码:
```python
call_log = await call_log_repo.create(
    # ... 其他字段
    call_type=CallTypeEnum.INTERNAL_TOOL,  # 添加这一行
)
```

**注意**: 如果不确定某个调用的类型，默认使用 `CallTypeEnum.MAIN_CHAT`

---

### Step 5: 修改 CLI 显示逻辑 (必做)

**文件**: `backend/app/cli.py`

**修改位置**: 在 `_load_ai_conversation_snapshot` 函数中（约 1302 行）

**查找这段代码**:
```python
AICallLog.conversation_id == conversation_id,
```

**修改为**:
```python
AICallLog.conversation_id == conversation_id,
AICallLog.call_type == 'main_chat',  # 只查询主对话调用
```

**同时修改日志输出部分**（查找 `[log_id=` 相关输出）:
```python
# 修改前
f"[log_id={log.id}] time={log.created_at} status={log.status}"

# 修改后
f"[log_id={log.id}] time={log.created_at} status={log.status} type={log.call_type}"
```

---

### Step 6: 代码检查和测试 (必做)

**运行代码检查**:
```bash
cd backend
ruff check app/models/ai/call_log.py
ruff check app/enums/ai.py
ruff check app/cli.py
```

**运行现有测试**:
```bash
pytest tests/ -k "call_log" -v
```

**手动测试**:
```bash
# 1. 创建测试对话（如果有 CLI 命令）
python -m app.cli ai conversation create ...

# 2. 查询对话，验证只显示主调用
python -m app.cli ai conversation show <conversation_id>

# 3. 直接查询数据库验证
# 连接数据库后执行：
# SELECT id, conversation_id, call_type, status FROM ai_call_logs ORDER BY id DESC LIMIT 10;
```

---

## 验收标准

完成后，请确认以下所有项：

- [ ] 数据库迁移文件创建并执行成功
- [ ] `ai_call_logs` 表中存在 `call_type` 字段
- [ ] 两个索引创建成功（单字段 + 复合索引）
- [ ] `CallTypeEnum` 枚举类创建并导出
- [ ] `AICallLog` 模型添加 `call_type` 字段
- [ ] `__filterable__` 字典包含 `call_type`
- [ ] 至少主对话调用添加了 `call_type=CallTypeEnum.MAIN_CHAT`
- [ ] CLI 查询对话时过滤 `call_type='main_chat'`
- [ ] CLI 输出显示调用类型
- [ ] 通过 `ruff check` 检查
- [ ] 现有测试无回归

---

## 注意事项

1. **迁移文件命名**: 必须使用 `20260402_` 前缀
2. **字段默认值**: 必须同时设置 `default` 和 `server_default`
3. **向后兼容**: 不传 `call_type` 时自动使用 `main_chat`
4. **索引性能**: 复合索引优化对话查询
5. **代码规范**: 遵循项目现有代码风格

---

## 遇到问题时

1. **迁移失败**: 检查 `down_revision` 是否正确
2. **字段未创建**: 检查迁移是否执行成功
3. **导入错误**: 检查 `CallTypeEnum` 是否在 `__all__` 中导出
4. **测试失败**: 检查是否有测试依赖旧的数据结构

---

## 输出要求

完成后，请提供：

1. **修改的文件列表**
2. **迁移执行结果**（截图或日志）
3. **代码检查结果**（ruff check 输出）
4. **CLI 测试结果**（显示对话调用日志的截图）
5. **简短总结**（2-3 句话说明完成情况）

---

**任务**: Phase 3 - 增强调用日志  
**预计时间**: 1-2 小时  
**优先级**: P1
