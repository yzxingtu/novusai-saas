# 给 KIMI 的直接提示词

你现在接手的是“管理端 Agent 技能绑定组件化改造”任务，不是 SkillPackage 语义重构，也不是 tenant 侧或 dashboard 任务。

先完整阅读这份执行方案：

- `E:/git_clone/novusai-saas-yudi/docs/design/admin-agent-skill-binding-picker-plan-20260322.md`

然后严格按方案执行。不要先输出泛泛计划，直接进入实现。

你的任务目标只有一个：

把管理端 Agent 的技能绑定，从“全量预加载 + 普通多选下拉”升级成“可搜索、按技能包分类、可分页、跨页保留已选项、可维护 consent mode 的共享业务组件”，并同时接到以下两条链路：

1. 管理端智能体新增 / 编辑表单
2. 管理端智能体详情页的技能绑定 Tab

你必须先建立并保持下面这个架构真相：

```text
Agent
  -> AgentSkillGrant
  -> Skill
  -> SkillResolver
  -> ToolDefinition

SkillPackage = 目录 / 来源 / 归组单元
```

换句话说：

- 不要把 Agent 改成“绑定 SkillPackage”
- 不要把 SkillPackage 恢复成运行时绑定单元
- 不要改 AI runtime / resolver / AgentSkillGrant 的语义
- 本次只是升级“给 Agent 选 Skill”的管理端交互和对应 selector 接口

这次任务明确不处理：

- tenant / user 侧技能绑定 UI
- dashboard / plugin widget
- SkillPackage 信息架构再收口
- 无关数据库迁移
- 任何与当前问题无关的样式大改

你必须先理解当前问题：

1. 现有实现分散在：
   - `frontend/apps/web-antd/src/views/admin/ai/agents/modules/form.vue`
   - `frontend/apps/web-antd/src/views/admin/ai/agents/detail.vue`
   - `frontend/apps/web-antd/src/views/admin/ai/agents/data.ts`
2. 当前逻辑依赖全量拉取：
   - `GET /admin/ai/skills?page[size]=500`
   - `GET /admin/ai/skill-packages/select?include_system=true`
3. 即使修好了 `pkgResp.map is not a function`，这个方案仍然不可扩展：
   - 技能多了会卡
   - 技能包多了很难选
   - 没有正式的“按技能包分类”交互
   - 没有真正的远程搜索与分页
4. 详情页还有一个必须修掉的隐患：
   - `batchBindAIAgentSkillsApi` 是替换模式
   - 如果只传新增 `skill_ids`，不把已有 grant 的 `default_consent_mode` 一起带回去，就会把已有 `ask/reject` 静默重置成 `auto`

你必须按下面的方向实现，不要走偏：

## 一、组件方向

不要继续补丁式增强普通 `ASelect mode="multiple"`。

必须新增一个共享业务组件，建议路径：

- `frontend/apps/web-antd/src/components/business/agent-skill-binding-picker/AgentSkillBindingPicker.vue`

必要时可拆分：

- `frontend/apps/web-antd/src/components/business/agent-skill-binding-picker/types.ts`
- `frontend/apps/web-antd/src/components/business/agent-skill-binding-picker/index.ts`

这个组件必须负责：

- 远程搜索技能
- 技能包过滤
- 技能包分页过滤
- 候选技能分页
- 按技能包分组展示当前页技能
- 跨分页保留已选技能
- 维护每个已选 skill 的 `default_consent_mode`
- 给父层返回完整草稿，而不是零散的 `number[]`

建议统一前端草稿结构：

```ts
interface AgentSkillBindingDraftItem {
  skill_id: number;
  skill_name: string;
  package_id: number | null;
  package_name: string | null;
  skill_type: string | null;
  is_system: boolean;
  source_plugin: null | string;
  default_consent_mode: 'auto' | 'ask' | 'reject';
}
```

不要继续同时维护：

- `selectedSkills`
- `pendingSkillIds`
- `consentModes`

而应该统一成一套 `selectedSkillDrafts` / `selectedMap`。

## 二、后端接口方向

不要继续让 Agent 技能选择依赖 `GET /admin/ai/skills?page[size]=500`。

你应新增专用 selector 接口：

- `GET /admin/ai/skills/select`

建议修改：

- `backend/app/api/admin/skills.py`
- `backend/app/services/ai/skill_service.py`
- `backend/app/repositories/ai/skill_repository.py`

这个接口至少支持：

- `search`
  - 搜技能名
  - 搜 `skill key`
  - 搜技能描述
  - 搜技能包名
- `package_id`
- `page`
- `page_size`
- `include_system`
- `only_active`

查询时必须 join `skill_packages`，因为要返回：

- `package_name`
- `source_plugin`
- 未来按包名搜索

建议返回格式：

```json
{
  "items": [
    {
      "label": "get_page_context",
      "value": 52,
      "extra": {
        "package_id": 194,
        "package_name": "页面感知交互",
        "skill_type": "builtin",
        "skill_key": "get_page_context",
        "description": "获取页面上下文",
        "is_system": true,
        "is_active": true,
        "source_plugin": null,
        "tenant_id": null
      }
    }
  ],
  "total": 123,
  "page": 1,
  "page_size": 20,
  "has_more": true
}
```

同时你应扩展：

- `GET /admin/ai/skill-packages/select`

让它支持：

- `search`
- `include_system`
- `page`
- `page_size`

因为顶部“技能包过滤器”要复用它做远程搜索 + 分页。

相关改动文件：

- `backend/app/api/admin/skill_packages.py`
- `frontend/apps/web-antd/src/api/admin/skill-packages.ts`

## 三、前端接入范围

你必须接到两个落地点：

1. `frontend/apps/web-antd/src/views/admin/ai/agents/modules/form.vue`
2. `frontend/apps/web-antd/src/views/admin/ai/agents/detail.vue`

### form.vue

不要再让表单里的普通多选下拉承担大规模技能选择。

建议交互：

- 表单内保留“技能绑定”区块
- 展示已选数量
- 提供“选择技能”按钮
- 点击后打开 `AgentSkillBindingPicker`
- 用户确认后写回统一草稿
- 保存 Agent 成功后，再调用 `batchBindAIAgentSkillsApi`

### detail.vue

不要再保留“简单新增 skill ids”的多选下拉作为主要入口。

建议交互：

- 顶部提供“管理技能绑定”按钮
- 点击后打开同一个 `AgentSkillBindingPicker`
- 打开时预填当前 grants
- 用户可以搜索、按包看、翻页、选择、取消、设置 consent mode
- 点击确认后，父页面执行一次全量 `batchBind`

注意：detail 页提交时必须传最终全量：

- `skill_ids`
- `default_consent_modes`

不能只传新增 skill。否则会覆盖已有 `ask/reject` 配置。

原有下方的已绑定卡片建议保留，用于：

- 快速查看
- 单项解绑
- 单项启停
- 单项调整 consent mode

## 四、实现要求

你必须满足这些要求：

1. 候选技能支持远程搜索
2. 候选技能支持远程分页
3. 顶部技能包过滤器支持远程搜索 + 分页
4. 当前页结果按技能包分组展示
5. 已选技能支持跨页保留
6. 已选技能可单独修改 consent mode
7. form 与 detail 共用同一个业务组件
8. 不允许 silent failure

错误处理要求：

- 页面可见错误态或 toast
- 至少保留 `console.error('[AgentSkillBindingPicker]', error)`
- 不能再像旧逻辑一样 catch 后直接回空数组装没事

## 五、建议修改文件

后端：

- `backend/app/api/admin/skills.py`
- `backend/app/services/ai/skill_service.py`
- `backend/app/repositories/ai/skill_repository.py`
- `backend/app/api/admin/skill_packages.py`

前端 API / 类型：

- `frontend/apps/web-antd/src/api/admin/skills.ts`
- `frontend/apps/web-antd/src/api/admin/skill-packages.ts`

前端组件：

- `frontend/apps/web-antd/src/components/business/agent-skill-binding-picker/AgentSkillBindingPicker.vue`
- `frontend/apps/web-antd/src/components/business/agent-skill-binding-picker/index.ts`
- 如需要：`types.ts`

前端页面：

- `frontend/apps/web-antd/src/views/admin/ai/agents/modules/form.vue`
- `frontend/apps/web-antd/src/views/admin/ai/agents/detail.vue`
- `frontend/apps/web-antd/src/views/admin/ai/agents/data.ts`

多语言：

- `frontend/apps/web-antd/src/locales/langs/zh-CN/admin/ai.json`
- `frontend/apps/web-antd/src/locales/langs/en-US/admin/ai.json`

## 六、浏览器与验收要求

按项目技能规范执行：

- 不要启动新的前后端服务
- 直接使用现成环境
- 优先用 `chrome-devtools`
- 先看 network / console

本地管理端登录信息：

- `http://localhost:5666/admin/login`
- 用户名：`admin`
- 密码：`admin123456`

必测页面：

1. `http://localhost:5666/admin/ai/agents`
2. 新建 Agent 打开表单
3. 编辑任意 Agent 打开表单
4. `http://localhost:5666/admin/ai/agents/59?tab=skills`

必查请求：

- `GET /admin/ai/skills/select`
- `GET /admin/ai/skill-packages/select`
- `GET /admin/ai/agents/{id}/skills`
- `PUT /admin/ai/agents/{id}/skills/batch`

验收重点：

- 搜索能收敛结果
- 换页后已选项不丢
- 页面内确实按技能包分组
- form 页可以新建 / 编辑并正确回显
- detail 页通过 picker 保存后，已有 `ask/reject` 不会被重置为 `auto`

## 七、静态校验要求

你至少必须执行：

```powershell
backend\.venv\Scripts\python -m py_compile `
  backend/app/api/admin/skills.py `
  backend/app/services/ai/skill_service.py `
  backend/app/repositories/ai/skill_repository.py `
  backend/app/api/admin/skill_packages.py
```

```powershell
pnpm exec vue-tsc --noEmit -p frontend/apps/web-antd/tsconfig.json
```

如果新增了别的 Python 文件，也要一并纳入 `py_compile`。

## 八、禁止事项

你不要做这些事：

- 把绑定真相从 Skill 改回 SkillPackage
- 顺手改 tenant 侧页面
- 顺手改 dashboard / widget / plugin manifest
- 引入与现有 repo 风格冲突的新状态管理方案
- 写一堆一次性的页面内临时代码而不抽共享组件
- 为了偷懒继续用 `page[size]=500`

## 九、最终回复格式

你完成后必须按这个结构汇报：

1. 结论
2. 已完成的改动
3. 组件最终 API / 数据结构
4. 新增 / 修改了哪些后端接口
5. 如何保证 detail 页 `batchBind` 不再覆盖已有 consent mode
6. 静态校验结果
7. 浏览器实测结果
8. 仍未处理的非阻塞问题

最后再强调一遍：

这次不是“修一下下拉框”，而是把管理端 Agent 的 Skill 绑定升级为正式的共享业务组件。范围只限 admin，运行时语义不能动。
