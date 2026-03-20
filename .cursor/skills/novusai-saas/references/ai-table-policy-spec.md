# AI 表策略声明规范

## 设计理念

AI 表策略采用**白名单声明制**：只有在 Model 类上显式声明 `__ai_policy__` 的表才对 AI 可见。
未声明的表对 AI 完全不可见，确保敏感表不会被意外暴露。

## 声明方式

在 Model 类上添加 `__ai_policy__` 类属性：

### 完整声明

```python
class MyModel(TenantModel):
    __tablename__ = "my_models"

    __ai_policy__ = {
        "label": "我的模型",           # 中文显示名
        "keywords": ["模型", "model"], # AI 匹配关键词
        "allow_read": True,           # 允许 AI 查询（默认 True）
        "allow_create": False,        # 允许 AI 创建（默认 False）
        "allow_update": False,        # 允许 AI 修改（默认 False）
        "allow_delete": False,        # 允许 AI 删除（默认 False）
        "max_rows": 200,              # 单次最大行数（默认 200）
        "blocked_columns": [],        # 隐藏列（默认自动检测）
        "readonly_columns": [],       # 只读列（默认系统列）
    }
```

### 简写声明

```python
class MyModel(TenantModel):
    __ai_policy__ = True  # 全部使用默认值
```

## 同步机制

1. 管理员在 /admin/ai/table-policies 点击「同步」
2. `sync_table_policies()` 遍历 `Base.registry.mappers`
3. 只处理有 `__ai_policy__` 属性的 Model
4. 为新表创建 AITablePolicy 记录，已有策略不覆盖
5. 管理员可在 UI 中进一步调整权限

## 与技能包的关系

```
Model.__ai_policy__  →  同步  →  AITablePolicy 记录
                                      ↓
                                Skill(type=data_intelligence).config.table_policy_ids
                                      ↓
                                SkillPackage（如"平台数据管理"）
                                      ↓
                                Agent 绑定技能包
                                      ↓
                                对话时生成 data_query/create/update/delete 工具
```

## 安全准则

- 敏感表（admins, permissions, api_keys 等）**绝对不添加** `__ai_policy__`
- 默认所有 CRUD 权限为 False（仅 read=True），需要写操作必须显式开启
- `blocked_columns` 默认自动检测包含 password/secret/token 等关键词的列
- 管理员可在 UI 中进一步收紧权限（但不能扩大代码声明中未允许的权限）
