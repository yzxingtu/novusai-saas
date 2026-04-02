# Phase 3: 增强调用日志 - 实施方案

**任务**: 在调用日志中增加 `call_type` 字段，区分主对话调用和内部调用  
**预计时间**: 1-2 小时  
**优先级**: P1 (高)

---

## 一、背景和目标

### 问题描述
对话 618 的调用日志 1071 实际上是内部记忆提取调用，不是主对话调用，导致：
- CLI 显示误导性信息（显示 success 但对话无回复）
- 无法区分主调用和内部调用
- 对话统计不准确

### 目标
1. 在 `ai_call_logs` 表添加 `call_type` 字段
2. 区分三种调用类型：
   - `main_chat`: 主对话调用（用户发起的对话）
   - `internal_memory`: 内部记忆提取调用
   - `internal_tool`: 内部工具调用
3. CLI 查询对话时只显示主调用日志
4. 为未来的调用统计和分析提供基础

---

## 二、技术方案

### 2.1 数据库迁移

**文件**: `backend/migrations/versions/20260402_add_call_type_to_ai_call_logs.py`

**迁移内容**:
```python
def upgrade():
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
    
    # 2. 创建索引（提升查询性能）
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

def downgrade():
    op.drop_index('idx_ai_call_logs_conv_call_type', 'ai_call_logs')
    op.drop_index('idx_ai_call_logs_call_type', 'ai_call_logs')
    op.drop_column('ai_call_logs', 'call_type')
```

**注意事项**:
- 使用 `server_default='main_chat'` 确保现有数据兼容
- 字段长度 50 足够容纳未来扩展
- 复合索引优化对话查询性能

### 2.2 模型修改

**文件**: `backend/app/models/ai/call_log.py`

**修改位置**: 在 `request_type` 字段后添加

**代码**:
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

**同时更新 `__filterable__` 字典**:
```python
__filterable__ = {
    # ... 现有字段 ...
    "call_type": "call_type",  # 添加这一行
    # ... 其他字段 ...
}
```

### 2.3 创建枚举类

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
        return [e.value for e in cls]
```

### 2.4 修改调用日志创建逻辑

**需要修改的文件**（按优先级）:

1. **主对话调用** - `backend/app/services/ai/conversation_service.py`
   - 查找创建调用日志的位置
   - 添加 `call_type=CallTypeEnum.MAIN_CHAT`

2. **内部记忆调用** - 查找记忆提取相关代码
   - 可能在 `backend/app/ai/engine/` 或 `backend/app/services/ai/`
   - 添加 `call_type=CallTypeEnum.INTERNAL_MEMORY`

3. **内部工具调用** - 查找工具调用相关代码
   - 添加 `call_type=CallTypeEnum.INTERNAL_TOOL`

**修改模式**:
```python
# 修改前
call_log = await call_log_repo.create(
    tenant_id=tenant_id,
    provider_id=provider_id,
    # ... 其他字段
)

# 修改后
call_log = await call_log_repo.create(
    tenant_id=tenant_id,
    provider_id=provider_id,
    call_type=CallTypeEnum.MAIN_CHAT,  # 或 INTERNAL_MEMORY / INTERNAL_TOOL
    # ... 其他字段
)
```

### 2.5 修改 CLI 显示逻辑

**文件**: `backend/app/cli.py`

**修改位置**: `_load_ai_conversation_snapshot` 函数中的调用日志查询

**修改前** (约 1302 行):
```python
AICallLog.conversation_id == conversation_id,
```

**修改后**:
```python
AICallLog.conversation_id == conversation_id,
AICallLog.call_type == 'main_chat',  # 只查询主对话调用
```

**同时在显示部分添加调用类型**:
```python
# 在日志输出中添加 call_type 显示
f"[log_id={log.id}] time={log.created_at} status={log.status} type={log.call_type}"
```

---

## 三、实施步骤

### Step 1: 创建数据库迁移 (15 分钟)
1. 创建迁移文件 `20260402_add_call_type_to_ai_call_logs.py`
2. 编写 upgrade 和 downgrade 函数
3. 运行 `novusai db upgrade heads` 验证迁移
4. 检查数据库确认字段和索引创建成功

### Step 2: 修改模型和枚举 (10 分钟)
1. 在 `app/enums/ai.py` 添加 `CallTypeEnum`
2. 在 `app/models/ai/call_log.py` 添加 `call_type` 字段
3. 更新 `__filterable__` 字典
4. 运行 `ruff check` 确保代码规范

### Step 3: 修改调用日志创建逻辑 (30-45 分钟)
1. 查找所有创建 `AICallLog` 的位置
2. 根据调用场景添加正确的 `call_type`
3. 重点关注：
   - 主对话流程
   - 记忆提取流程
   - 工具调用流程

### Step 4: 修改 CLI 显示 (15 分钟)
1. 修改 `_load_ai_conversation_snapshot` 函数
2. 添加 `call_type` 过滤条件
3. 在输出中显示调用类型
4. 测试 CLI 命令确认显示正确

### Step 5: 测试验证 (20-30 分钟)
1. 创建新对话，验证 `call_type='main_chat'`
2. 触发记忆提取，验证 `call_type='internal_memory'`
3. 使用 CLI 查询对话，确认只显示主调用
4. 检查数据库数据一致性

---

## 四、验收标准

### 必须满足
- [ ] 数据库迁移成功执行
- [ ] `call_type` 字段和索引创建成功
- [ ] `CallTypeEnum` 枚举类创建
- [ ] 模型字段添加并可用
- [ ] 新创建的主对话调用 `call_type='main_chat'`
- [ ] CLI 查询对话时只显示主调用日志
- [ ] CLI 输出中显示调用类型
- [ ] 通过 `ruff check` 代码检查
- [ ] 现有测试无回归

### 建议满足
- [ ] 内部记忆调用正确标记为 `internal_memory`
- [ ] 内部工具调用正确标记为 `internal_tool`
- [ ] 添加单元测试验证 `call_type` 逻辑

---

## 五、风险和注意事项

### 风险 1: 现有数据兼容性
**影响**: 中  
**缓解**: 使用 `server_default='main_chat'` 确保现有数据自动设置默认值

### 风险 2: 遗漏调用点
**影响**: 中  
**缓解**: 全局搜索 `AICallLog` 创建位置，逐一检查

### 风险 3: 性能影响
**影响**: 低  
**缓解**: 创建索引优化查询性能

### 注意事项
1. **迁移文件命名**: 使用 `20260402_` 前缀保持时间顺序
2. **字段默认值**: 必须同时设置 `default` 和 `server_default`
3. **索引策略**: 单字段索引 + 复合索引覆盖常见查询
4. **向后兼容**: 现有代码不传 `call_type` 时使用默认值 `main_chat`

---

## 六、测试计划

### 6.1 单元测试
```python
# tests/models/test_call_log.py
def test_call_log_default_call_type():
    """测试默认 call_type 为 main_chat"""
    log = AICallLog(...)
    assert log.call_type == 'main_chat'

def test_call_log_with_call_type():
    """测试指定 call_type"""
    log = AICallLog(..., call_type='internal_memory')
    assert log.call_type == 'internal_memory'
```

### 6.2 集成测试
```python
# tests/services/test_conversation_service.py
async def test_main_chat_call_type():
    """测试主对话调用的 call_type"""
    # 创建对话并发送消息
    # 验证调用日志的 call_type='main_chat'
```

### 6.3 CLI 测试
```bash
# 创建测试对话
python -m app.cli ai conversation create ...

# 查询对话，验证只显示主调用
python -m app.cli ai conversation show <id>

# 直接查询数据库验证
psql -c "SELECT id, call_type FROM ai_call_logs WHERE conversation_id=<id>;"
```

---

## 七、回滚计划

如果出现问题，执行以下步骤回滚：

```bash
# 1. 回滚数据库迁移
novusai db downgrade -1

# 2. 恢复代码
git revert <commit_hash>

# 3. 验证系统正常
novusai check
```

---

**创建日期**: 2026-04-02  
**任务**: Phase 3 - 增强调用日志  
**状态**: 待实施
