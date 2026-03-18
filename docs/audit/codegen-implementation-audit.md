# Codegen 实现审计报告

**审计时间**：2026-03-17  
**目的**：验证计划修复项是否正确实现，并识别遗漏问题

---

## 一、已正确实现项

| 计划项 | 状态 | 验证 |
|-------|------|------|
| 重复字段名 - createFieldFromPalette | ✅ | ensureUniqueName 已实现，对 TreeSelect/Cascader 等保留 type |
| 重复字段名 - addEmptyField | ✅ | 使用 field_${Date.now()} 经 ensureUniqueName |
| 重复字段名 - config_parser | ✅ | duplicate_field_name 校验已添加 |
| 重复字段名 - onNameChange | ✅ | 冲突时 message.warning 拒绝 |
| ID 列 | ✅ | data_table.ts.j2 已插入 id 列 |
| created_at sortable | ✅ | f.name == 'created_at' 时增加 sortable |
| model Table 导入 | ✅ | sqlalchemy 已含 Table |
| statusSelect field | ✅ | 传入 field: '{{ f.name }}' |
| searchDateRange | ✅ | 已替换 raw RangePicker |
| ForeignKey fieldName | ✅ | filter[{{ f.name }}][eq/in] |
| FieldPropertyPanel strVal | ✅ | placeholder、help_text、default、db_default、relation_display 等已用 strVal |
| fields setter ensureFieldKeys | ✅ | 已实现 |
| 拖拽 onEnd 返回新数组 | ✅ | arr.map((f,i)=>({...f,sort_order:i})) |
| ExpertModal fieldOptions | ✅ | DetailGroupEditor、CompositeUniqueEditor、RelationsEditor 已过滤 __divider__ |
| config_parser 保留字/格式 | ✅ | RESERVED_NAMES、FIELD_NAME_PATTERN、module/resource 校验 |
| 系统字段提示 | ✅ | FieldCardList 顶部 systemFieldsHint |
| DbTableImportModal 合并模式 | ✅ | 合并/覆盖选项，按 name 去重 |
| LiveFormPreview 组件 | ✅ | ApiTreeSelect、Cascader、TimePicker 已加 |

---

## 二、发现问题与修复建议

### 2.1 空 Alert（用户反馈）

**现象**：属性面板顶部出现空内容的信息 Alert，用户不知用途。

**根因**：`showRecommend && recommendMessage` 条件下，若 recommendMessage 为空白或翻译异常，仍会渲染 Alert。需确保仅在非空时渲染。

**修复**：`v-else-if="showRecommend && recommendMessage?.trim()"` 或 `recommendMessage.length > 0`

### 2.2 Vue warn: value=true 传入 AInput

**现象**：`Invalid prop: type check failed for prop "value". Expected String | Number | Symbol, got Boolean`

**可能位置**：
- `dict_code` Input 使用 `:value="selectedField.dict_code"` 未用 strVal，dict_code 可能为 boolean
- 其他未覆盖的 Input

**修复**：对所有可能非 string 的 Input 统一 strVal，包括 dict_code

### 2.3 已存在配置中的重复字段

**现象**：用户截图显示 3 个 sort_order，可能是加载旧配置/preset 所致。

**根因**：ensureUniqueName 仅在新添加时生效。从 DB/预设/YAML 加载的配置不会自动去重。

**修复**：在 loadConfig、applyPreset、onDbImported 等加载路径中，对 fields 按 name 去重（保留第一个，合并或提示冲突）

### 2.4 CRUD 菜单/权限多语言

**已修复**：
- frontend menu.json admin 增加 `"codegen": "代码生成器"`
- admin.system.codegen.action 增加 list/detail/create 等 19 项中英文

### 2.5 加载时重复字段去重

**已修复**：ensureFieldsHaveKey 中增加 dedupeFieldsByName，加载配置时同名字段自动后缀 _2、_3

---

## 三、建议修复顺序

1. 空 Alert + value 布尔修复（立即）
2. 加载时重复字段去重（P1）
3. codegen 菜单/权限多语言（P1）
