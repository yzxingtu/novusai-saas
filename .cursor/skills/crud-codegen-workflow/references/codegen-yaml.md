# Codegen YAML 速查

## 目录

- [最小结构](#最小结构)
- [字段类型映射](#字段类型映射)
- [端点与权限](#端点与权限)
- [常用预设](#常用预设)
- [简写规则](#简写规则)

## 最小结构

```yaml
module: tenant
resource: notice
display_name: 公告
display_name_en: Notice

model:
  base_class: TenantModel

fields:
  - name: title
    type: String(200)
    required: true
    comment: "标题 / Title"
    searchable: true
    column: true
    form: input

endpoints:
  - scope: tenant
    data_mode: tenant_only
    route_prefix: notices
    permission:
      resource: notice
      parent_resource: system_mgmt
```

## 字段类型映射

| YAML 类型 | SQLAlchemy | TypeScript | 默认表单组件 |
|-----------|------------|------------|-------------|
| `String(n)` | `String(n)` | `string` | `Input` |
| `Text` | `Text` | `string` | `Textarea` |
| `Integer` | `Integer` | `number` | `InputNumber` |
| `Float` | `Float` | `number` | `InputNumber` |
| `Boolean` | `Boolean` | `boolean` | `Switch` |
| `DateTime` | `DateTime` | `string` | `DatePicker` |
| `Enum` | `Enum` | `string` | `Select` |
| `ForeignKey(table)` | `Integer + FK` | `number` | `ApiSelect` |

## 端点与权限

一个资源可以配置多端：

- `scope: admin`
- `scope: tenant`

端点里重点看：

- `route_prefix`
- `permission.resource`
- `permission.parent_resource`
- `menu.parent`
- `menu.icon`

## 常用预设

```bash
novusai codegen init -t simple
novusai codegen init -t tree
novusai codegen init -t dual_scope
novusai codegen init -t workflow
```

## 简写规则

- `searchable: true` -> filterable + ilike 搜索
- `column: true` -> 列默认展示
- `form: input` -> `form.component: Input`

YAML 写完后，先 `validate`，再 `preview`，最后 `generate`。
