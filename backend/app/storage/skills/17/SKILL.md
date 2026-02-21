---
name: 飞书办公套件
description: 飞书开放平台全面集成工具包。支持日历与会议室预约、消息发送、审批流程、多维表格操作、通讯录查询和考勤管理六大核心办公模块。
version: 1.0.0
icon: 🏢
metadata:
  clawdbot:
    emoji: 🏢
    requires:
      bins:
        - uv
      env:
        - FEISHU_APP_ID
        - FEISHU_APP_SECRET
    primaryEnv: FEISHU_APP_ID
---

# 🏢 飞书办公套件

*Feishu/Lark Office Toolkit — 让 Agent 成为你的飞书办公助手*

基于飞书开放平台 API 的全面集成工具包，覆盖日常办公六大核心场景。通过本技能包，你可以帮用户预约会议室、发送消息、发起审批、操作多维表格、查询通讯录和管理考勤。

## 📦 功能模块

### 1. 日历与会议室 (Calendar)
创建/更新/删除/查看日程，预约会议室，查询忙闲状态。
*   **核心能力**: 创建/更新/删除/查看日程、会议室预约、日程管理、忙闲查询
*   **详情**: [查看文档](references/calendar.md)

### 2. 消息 (Messaging)
向个人或群聊发送文本、富文本和卡片消息。
*   **核心能力**: 发送消息、回复消息、卡片交互
*   **详情**: [查看文档](references/messaging.md)

### 3. 审批 (Approval)
查看审批定义、列出可用审批类型、发起审批、查询审批状态、审批人操作（同意/拒绝/转交）、撤回审批申请。
*   **核心能力**: 查看审批定义、列出审批类型、创建审批、查询状态、审批人同意/拒绝/转交、撤回审批
*   **详情**: [查看文档](references/approval.md)

### 4. 多维表格 (Bitable)
创建多维表格、读写记录，实现结构化数据管理。
*   **核心能力**: 创建多维表格、列出多维表格、查看表结构、查询记录、新增记录、更新记录
*   **详情**: [查看文档](references/bitable.md)

### 5. 通讯录 (Contacts)
查询企业组织架构中的用户和部门信息。
*   **核心能力**: 用户查询、部门查询、组织架构浏览
*   **详情**: [查看文档](references/contacts.md)

### 6. 考勤 (Attendance)
查询员工打卡结果、补卡记录和考勤组信息。
*   **核心能力**: 打卡查询、补卡记录、考勤组管理
*   **详情**: [查看文档](references/attendance.md)

## ⚙️ 配置说明

### 前置条件

1. 在 [飞书开发者后台](https://open.feishu.cn/app) 创建自建应用
2. 为应用开启**机器人能力**
3. 根据需要的模块申请对应 API 权限（见下方权限列表）
4. 配置 **通讯录权限范围** — 在权限管理中将范围设为「全部成员」或指定部门
5. 发布应用版本并通过管理员审核

### 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `FEISHU_APP_ID` | ✅ | 飞书应用 App ID |
| `FEISHU_APP_SECRET` | ✅ | 飞书应用 App Secret |
| `FEISHU_APPROVAL_CODES` | 否 | 常用审批类型映射（JSON），如 `'{"\u8bf7\u5047":"CODE1","\u51fa\u5dee":"CODE2"}'` |

### 各模块所需权限
| 模块 | 权限标识 | 说明 |
||------|----------|------|
| 日历 | `calendar:calendar` | 读写日历及日程信息 |
| 日历 | `vc:room:readonly` | 查询/搜索会议室 |
| 消息 | `im:message:send_as_bot` | 以应用身份发消息 |
| 审批 | `approval:approval` | 读写审批信息 |
| 审批 | `approval:approval.list:readonly` | 查询审批实例列表 |
| 审批 | `approval:task` | 审批人操作（同意/拒绝/转交、查询任务） |
| 多维表格 | `bitable:app` | 读写多维表格 |
| 多维表格 | `drive:drive` | 访问云空间（创建/列出多维表格时需要） |
| 通讯录 | `contact:contact.base:readonly` | 读取通讯录基本信息 |
| 通讯录 | `contact:department.base:readonly` | 获取部门信息（搜索部门/用户时需要） |
| 通讯录 | `contact:user.base:readonly` | 获取用户姓名、头像等基础信息 |
| 通讯录/考勤 | `contact:user.employee_id:readonly` | 获取用户 ID（考勤模块 open_id 转 employee_id 时必需） |
| 考勤 | `attendance:task:readonly` | 导出打卡数据 |
| 考勤 | `attendance:task:readonly` | 导出打卡数据 |

## 🚀 快速开始

### 启动服务

```bash
cd {baseDir}/server
echo "FEISHU_APP_ID=your-app-id" > .env
echo "FEISHU_APP_SECRET=your-app-secret" >> .env
uv venv && uv pip install -e ".[dev]"
uv run --env-file .env uvicorn feishu_toolkit.main:app --host 127.0.0.1 --port 8002
```

### 验证服务

```bash
# 健康检查
curl http://127.0.0.1:8002/ping

# 查询会议室
curl http://127.0.0.1:8002/calendar/rooms

# 发送消息
curl -X POST http://127.0.0.1:8002/messaging/send \
  -H "Content-Type: application/json" \
  -d '{"receive_id": "ou_xxx", "receive_id_type": "open_id", "msg_type": "text", "content": "{\"text\": \"Hello!\"}"}'
```

## 使用场景

- 🏢 **会议室预约**: "帮我预约明天下午2点到3点的8楼大会议室"
- 💬 **消息通知**: "给产品组群发一条关于版本发布的通知"
- ✅ **审批流程**: "帮我发起一个出差审批"
- 📊 **数据管理**: "在项目跟踪表中新增一条任务记录"
- 👥 **人员查询**: "查一下市场部有哪些成员"
- ⏰ **考勤管理**: "查看我这周的打卡记录"

## 🔗 相关资源

*   [飞书开放平台](https://open.feishu.cn/)
*   [飞书开发者文档](https://open.feishu.cn/document/)
*   [API 调试台](https://open.feishu.cn/api-explorer)
