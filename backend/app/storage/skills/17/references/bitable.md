# 多维表格

本模块提供飞书多维表格（Bitable）的完整生命周期管理能力，包括创建多维表格、列出已有多维表格、查看表结构、查询、新增和更新记录。Agent 无需手动获取 app_token，可直接通过 API 创建或列出多维表格。

## 所需权限

- `bitable:app` — 读写多维表格
- `drive:drive` — 访问云空间（创建/列出多维表格时需要）
- 对于已有的多维表格，需确保应用已被添加为协作者（云文档右上角「...」→「更多」→「添加文档应用」）

## API 端点

### 1. 创建多维表格

创建一个新的多维表格，返回 app_token 和默认数据表 table_id。

```
POST /bitable/apps
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | ✅ | 多维表格名称 |
| `folder_token` | string | 否 | 目标文件夹 token，省略时创建在应用根目录 |

**请求示例：**

```bash
curl -X POST http://127.0.0.1:8002/bitable/apps \
  -H "Content-Type: application/json" \
  -d '{"name": "项目跟踪表"}'
```

**响应示例：**

```json
{
  "app_token": "NQRxbRkBMa6OnZsjtERcxhNWnNh",
  "name": "项目跟踪表",
  "url": "https://xxx.feishu.cn/base/NQRxbRkBMa6OnZsjtERcxhNWnNh",
  "default_table_id": "tbl0xe5g8PP3U3cS",
  "folder_token": "fldcnxxxxxx"
}
```

### 2. 列出多维表格

列出指定文件夹下的所有多维表格。

```
GET /bitable/apps
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `folder_token` | string | 否 | 文件夹 token，省略时列出应用根目录下的多维表格 |

**请求示例：**

```bash
curl "http://127.0.0.1:8002/bitable/apps"
```

**响应示例：**

```json
{
  "folder_token": "fldcnxxxxxx",
  "bitables": [
    {
      "app_token": "NQRxbRkBMa6OnZsjtERcxhNWnNh",
      "name": "项目跟踪表",
      "url": "https://xxx.feishu.cn/base/NQRxbRkBMa6OnZsjtERcxhNWnNh",
      "created_time": "1708300800",
      "modified_time": "1708387200",
      "owner_id": "ou_xxx"
    }
  ]
}
```

### 3. 列出字段

获取数据表的字段（列）定义，了解表结构后再进行数据操作。

```
GET /bitable/fields
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `app_token` | string | ✅ | 多维表格 App Token |
| `table_id` | string | ✅ | 数据表 ID |

**请求示例：**

```bash
curl "http://127.0.0.1:8002/bitable/fields?app_token=NQRxbRkBMa6OnZsjtERcxhNWnNh&table_id=tbl0xe5g8PP3U3cS"
```

**响应示例：**

```json
{
  "fields": [
    {"field_id": "fld001", "field_name": "任务名称", "type": 1, "is_primary": true, "property": {}},
    {"field_id": "fld002", "field_name": "状态", "type": 3, "is_primary": false, "property": {"options": [{"name": "待开始"}, {"name": "进行中"}, {"name": "已完成"}]}},
    {"field_id": "fld003", "field_name": "截止日期", "type": 5, "is_primary": false, "property": {}}
  ]
}
```

### 4. 列出数据表

获取多维表格中的数据表列表。

```
GET /bitable/tables
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `app_token` | string | ✅ | 多维表格 App Token |

**请求示例：**

```bash
curl "http://127.0.0.1:8002/bitable/tables?app_token=NQRxbRkBMa6OnZsjtERcxhNWnNh"
```

**响应示例：**

```json
{
  "tables": [
    {"table_id": "tbl0xe5g8PP3U3cS", "name": "项目任务"},
    {"table_id": "tblABC123", "name": "成员列表"}
  ]
}
```

### 5. 查询记录

根据条件查询多维表格中的记录。

```
POST /bitable/records/search
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `app_token` | string | ✅ | 多维表格 App Token |
| `table_id` | string | ✅ | 数据表 ID |
| `field_names` | list[string] | 否 | 指定返回的字段名称 |
| `filter` | object | 否 | 筛选条件 |
| `sort` | list[object] | 否 | 排序条件 |
| `page_size` | int | 否 | 每页数量，默认 20，最大 500 |

**请求示例：**

```bash
# 查询所有记录
curl -X POST http://127.0.0.1:8002/bitable/records/search \
  -H "Content-Type: application/json" \
  -d '{
    "app_token": "NQRxbRkBMa6OnZsjtERcxhNWnNh",
    "table_id": "tbl0xe5g8PP3U3cS",
    "field_names": ["任务名称", "负责人", "状态"],
    "filter": {
      "conjunction": "and",
      "conditions": [
        {"field_name": "状态", "operator": "is", "value": ["进行中"]}
      ]
    }
  }'
```

**响应示例：**

```json
{
  "total": 3,
  "items": [
    {
      "record_id": "recyOaMB2F",
      "fields": {
        "任务名称": [{"text": "完成 API 对接", "type": "text"}],
        "负责人": [{"id": "ou_xxx", "name": "张三"}],
        "状态": "进行中"
      }
    }
  ]
}
```

### 6. 新增记录

向数据表中新增一条记录。

```
POST /bitable/records
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `app_token` | string | ✅ | 多维表格 App Token |
| `table_id` | string | ✅ | 数据表 ID |
| `fields` | object | ✅ | 字段数据（键为字段名，值为对应数据） |

**请求示例：**

```bash
curl -X POST http://127.0.0.1:8002/bitable/records \
  -H "Content-Type: application/json" \
  -d '{
    "app_token": "NQRxbRkBMa6OnZsjtERcxhNWnNh",
    "table_id": "tbl0xe5g8PP3U3cS",
    "fields": {
      "任务名称": "设计数据库表结构",
      "状态": "待开始",
      "优先级": "高",
      "截止日期": 1708300800000
    }
  }'
```

### 7. 更新记录

更新数据表中的一条记录。

```
PUT /bitable/records/{record_id}
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `app_token` | string | ✅ | 多维表格 App Token |
| `table_id` | string | ✅ | 数据表 ID |
| `fields` | object | ✅ | 要更新的字段数据 |

**请求示例：**

```bash
curl -X PUT http://127.0.0.1:8002/bitable/records/recyOaMB2F \
  -H "Content-Type: application/json" \
  -d '{
    "app_token": "NQRxbRkBMa6OnZsjtERcxhNWnNh",
    "table_id": "tbl0xe5g8PP3U3cS",
    "fields": {
      "状态": "已完成",
      "完成日期": 1708387200000
    }
  }'
```

## 字段类型说明

| 字段类型 | 写入格式 | 示例 |
|----------|----------|------|
| 多行文本 | string 或 text 对象数组 | `"Hello"` 或 `[{"text":"Hello","type":"text"}]` |
| 数字 | number | `2323.23` |
| 单选 | string | `"选项1"` |
| 多选 | list[string] | `["选项1", "选项2"]` |
| 日期 | int (毫秒时间戳) | `1690992000000` |
| 复选框 | boolean | `true` |
| 人员 | list[object] | `[{"id": "ou_xxx"}]` |
| 超链接 | object | `{"text": "链接", "link": "https://..."}` |

## 获取 App Token

多维表格的 `app_token` 有三种获取方式：
1. **通过 API 创建**: 调用 `POST /bitable/apps` 创建新多维表格，响应中包含 app_token
2. **通过 API 列出**: 调用 `GET /bitable/apps` 列出已有多维表格，获取 app_token
3. **从 URL 提取**: URL 格式 `https://xxx.feishu.cn/base/{app_token}`

## 飞书 API 参考

| 本地端点 | 飞书 API |
|----------|----------|
| `POST /bitable/apps` | `POST /open-apis/bitable/v1/apps` |
| `GET /bitable/apps` | `GET /open-apis/drive/v1/files` (筛选 type=bitable) |
| `GET /bitable/fields` | `GET /open-apis/bitable/v1/apps/:app_token/tables/:table_id/fields` |
| `GET /bitable/tables` | `GET /open-apis/bitable/v1/apps/:app_token/tables` |
| `POST /bitable/records/search` | `POST /open-apis/bitable/v1/apps/:app_token/tables/:table_id/records/search` |
| `POST /bitable/records` | `POST /open-apis/bitable/v1/apps/:app_token/tables/:table_id/records` |
| `PUT /bitable/records/{record_id}` | `PUT /open-apis/bitable/v1/apps/:app_token/tables/:table_id/records/:record_id` |
