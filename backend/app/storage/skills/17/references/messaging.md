# 消息

本模块提供飞书消息发送能力，支持向个人或群聊发送文本、富文本和卡片等多种类型的消息。

## 所需权限

- `im:message:send_as_bot` — 以应用身份发送消息

## API 端点

### 1. 发送消息

向指定用户或群聊发送消息。

```
POST /messaging/send
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `receive_id` | string | ✅ | 接收者 ID |
| `receive_id_type` | string | ✅ | ID 类型：`open_id`/`user_id`/`email`/`chat_id` |
| `msg_type` | string | ✅ | 消息类型：`text`/`post`/`interactive`/`image`/`file` |
| `content` | string | ✅ | 消息内容（JSON 字符串） |

**发送文本消息：**

```bash
curl -X POST http://127.0.0.1:8002/messaging/send \
  -H "Content-Type: application/json" \
  -d '{
    "receive_id": "ou_xxx",
    "receive_id_type": "open_id",
    "msg_type": "text",
    "content": "{\"text\": \"你好，这是一条测试消息\"}"
  }'
```

**发送富文本消息：**

```bash
curl -X POST http://127.0.0.1:8002/messaging/send \
  -H "Content-Type: application/json" \
  -d '{
    "receive_id": "oc_xxx",
    "receive_id_type": "chat_id",
    "msg_type": "post",
    "content": "{\"zh_cn\":{\"title\":\"项目更新\",\"content\":[[{\"tag\":\"text\",\"text\":\"版本 2.0 已发布，主要更新：\"},{\"tag\":\"a\",\"text\":\"查看详情\",\"href\":\"https://example.com\"}]]}}"
  }'
```

**发送卡片消息：**

```bash
curl -X POST http://127.0.0.1:8002/messaging/send \
  -H "Content-Type: application/json" \
  -d '{
    "receive_id": "oc_xxx",
    "receive_id_type": "chat_id",
    "msg_type": "interactive",
    "content": "{\"elements\":[{\"tag\":\"markdown\",\"content\":\"**项目进度更新**\\n- 前端开发：80%\\n- 后端开发：60%\\n- 测试：30%\"}]}"
  }'
```

**响应示例：**

```json
{
  "message_id": "om_dc13264520392913993dd051dba21dcf",
  "msg_type": "text",
  "create_time": "1615380573411",
  "chat_id": "oc_5ad11d72b830411d72b836c20"
}
```

### 2. 回复消息

回复指定消息。

```
POST /messaging/reply
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `message_id` | string | ✅ | 要回复的消息 ID |
| `msg_type` | string | ✅ | 消息类型 |
| `content` | string | ✅ | 消息内容（JSON 字符串） |

**请求示例：**

```bash
curl -X POST http://127.0.0.1:8002/messaging/reply \
  -H "Content-Type: application/json" \
  -d '{
    "message_id": "om_xxx",
    "msg_type": "text",
    "content": "{\"text\": \"收到，我马上处理\"}"
  }'
```

## 消息内容格式

### 文本消息 (text)

```json
{"text": "你好，这是一条消息"}
```

支持 @ 用户：`{"text": "<at user_id=\"ou_xxx\">张三</at> 请查看"}`

### 富文本消息 (post)

```json
{
  "zh_cn": {
    "title": "标题",
    "content": [
      [
        {"tag": "text", "text": "普通文本"},
        {"tag": "a", "text": "链接文字", "href": "https://example.com"},
        {"tag": "at", "user_id": "ou_xxx"}
      ]
    ]
  }
}
```

### 卡片消息 (interactive)

```json
{
  "elements": [
    {"tag": "markdown", "content": "**标题**\n内容文本"},
    {
      "tag": "action",
      "actions": [
        {"tag": "button", "text": {"tag": "plain_text", "content": "确认"}, "type": "primary"}
      ]
    }
  ]
}
```

## 使用限制

- 向同一用户发送消息限频：**5 QPS**
- 向同一群组发送消息限频：群内机器人共享 **5 QPS**
- 文本消息最大 **150 KB**
- 卡片/富文本消息最大 **30 KB**

## 飞书 API 参考

| 本地端点 | 飞书 API |
|----------|----------|
| `POST /messaging/send` | `POST /open-apis/im/v1/messages` |
| `POST /messaging/reply` | `POST /open-apis/im/v1/messages/:message_id/reply` |
