# 管理端智能体技能绑定组件化改造方案（给 KIMI）

## 1. 任务目标

把管理端智能体的技能绑定能力从“全量预加载 + 普通多选下拉”升级为“可搜索、按技能包分类、可分页”的共享组件，并同时落地到以下两条链路：

1. 管理端智能体新增 / 编辑表单
2. 管理端智能体详情页的技能绑定 Tab

目标不是改 AI 运行时语义，也不是改 SkillPackage 架构；目标是把“给 Agent 选 Skill”的交互做成可扩展的正式方案。

---

## 2. 当前问题

### 2.1 当前实现方式

当前技能绑定 UI 分散在两个地方：

- `frontend/apps/web-antd/src/views/admin/ai/agents/modules/form.vue`
- `frontend/apps/web-antd/src/views/admin/ai/agents/detail.vue`

它们都依赖：

- `frontend/apps/web-antd/src/views/admin/ai/agents/data.ts` 中的 `getSkillSelectOptions()`

当前逻辑是：

1. 拉取 `GET /admin/ai/skills?page[size]=500`
2. 拉取 `GET /admin/ai/skill-packages/select?include_system=true`
3. 前端本地把技能和技能包拼起来
4. 用普通 `ASelect` 多选展示

### 2.2 已知问题

当前方案即使修好了 “`pkgResp.map is not a function`” 的 bug，仍然存在结构性问题：

1. **全量预加载不可扩展**
   - 技能越来越多时，`page[size]=500` 本身就不可靠
   - 技能包越来越多时，前端本地拼装会越来越慢
   - 多选下拉一次性塞大量 option，交互会迅速劣化

2. **缺少正式的“按技能包分类”交互**
   - 现在只是把 `skill.name · package.name` 拼成一行字符串
   - 这不是按技能包分类，只是字符串拼接
   - 当技能数和包数上来后，用户几乎无法理解全局结构

3. **没有真正的服务端搜索 / 分页绑定体验**
   - 现在的搜索是下拉框局部过滤，不是面向大数据量的远程检索
   - 无法稳定支持“按技能名搜”“按包名搜”“翻页继续选”

4. **详情页新增技能存在隐性数据回退风险**
   - `frontend/apps/web-antd/src/views/admin/ai/agents/detail.vue` 里新增技能走的是 `batchBindAIAgentSkillsApi`
   - 这个接口是“替换模式”：先删光再重建
   - 当前新增技能时只传 `skill_ids`，没有把已有 grant 的 `default_consent_mode` 一起带回去
   - 结果是：如果某些已有技能原本是 `ask` / `reject`，用户只要新增一次技能，就可能把它们静默重置为 `auto`

这一条必须在本次改造里顺手修掉。

---

## 3. 本次改造的正确方向

### 3.1 不要继续补丁式增强普通多选框

不要继续在 `ASelect mode="multiple"` 上打补丁，例如：

- 再塞更多 option tag
- 再拼接更长 label
- 再做一层前端本地 package 分组
- 再把 `page[size]` 调更大

这条路不适合长期维护。

### 3.2 正确做法：做一个共享的“技能绑定选择器”组件

应该新增一个共享业务组件，专门服务于管理端 Agent 的 Skill 绑定场景。

建议组件名：

- `AgentSkillBindingPicker.vue`

建议路径：

- `frontend/apps/web-antd/src/components/business/agent-skill-binding-picker/AgentSkillBindingPicker.vue`

如需要拆分：

- `types.ts`
- `use-agent-skill-binding-picker.ts`
- `index.ts`

这个组件要负责：

- 服务端搜索
- 服务端分页
- 技能包分类展示
- 选中项跨分页保留
- 选中项的 consent mode 草稿维护
- 返回完整的“待绑定技能 + consent mode”结果

---

## 4. 架构边界

### 4.1 不改运行时真相

本次改造**不改变**下面这条真相：

```text
Agent
  -> AgentSkillGrant
  -> Skill
  -> SkillResolver
  -> ToolDefinition
```

也就是说：

- 不是重新引入包级绑定
- 不是让 Agent 绑定 `SkillPackage`
- 不是改变 `SkillPackage` 的目录 / 来源 / 归组定位

本次只是把“给 Agent 选 Skill”的管理端交互做完整。

### 4.2 不扩散到 tenant / user

本次范围只限 **admin 管理端**：

- `admin/ai/agents` 表单
- `admin/ai/agents/:id` 详情页

不处理：

- tenant 侧 Agent 技能绑定 UI
- user 侧任何页面
- dashboard / plugin widget

---

## 5. 推荐的最终交互形态

不要再把“绑定技能”做成普通下拉。推荐做成一个 **弹窗 / 抽屉型选择器**。

### 5.1 推荐 UI 结构

建议用一个中大型 Drawer 或 Modal，结构如下：

#### 顶部筛选区

- 关键词搜索框
  - 支持搜技能名
  - 支持搜技能 key
  - 支持搜技能描述
  - 支持搜技能包名

- 技能包过滤器
  - 使用远程 `ApiSelect`
  - 支持搜索技能包
  - 支持分页

- 可选附加过滤
  - 仅显示启用技能（默认开启）
  - 技能类型过滤（可选，非 P0）

#### 主体区域

左侧：技能候选列表

- 当前页结果按 `package_id / package_name` 分组
- 每个分组显示：
  - 包名
  - 包来源 / system / plugin 等标签
  - 当前页命中的技能数

- 每个技能项显示：
  - 技能名
  - 技能类型 Tag
  - 是否系统技能
  - 简短描述
  - 所属包信息
  - 复选框 / 勾选状态

右侧：已选技能列表

- 已选数量
- 按选择顺序展示
- 每项可移除
- 每项显示 consent mode 下拉
  - `auto`
  - `ask`
  - `reject`

底部：分页与提交区

- 当前页码
- 每页数量
- 上一页 / 下一页
- 确认 / 取消

### 5.2 为什么不用“普通远程 Select + OptGroup”

`ApiSelect` 适合做：

- 包过滤器
- 轻量远程单选 / 多选

但这次场景除了远程搜索，还要求：

- 技能包分类展示
- 大量结果浏览
- 已选项跨分页保留
- consent mode 草稿管理
- 在 form 和 detail 两条链路复用

所以主交互不应该只靠 `ApiSelect` 一个控件扛住，应该做成独立业务组件。

---

## 6. 后端方案

### 6.1 新增专用技能选择接口

不要再继续复用：

- `GET /admin/ai/skills?page[size]=500`

建议新增专用接口：

- `GET /admin/ai/skills/select`

用途：

- 专门给 Agent 技能绑定选择器提供远程分页数据

### 6.2 返回格式

复用现有 `SelectResponse`：

- `backend/app/schemas/common/select.py`

返回格式建议：

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

### 6.3 接口参数建议

建议至少支持这些参数：

- `search`
  - 搜技能名
  - 搜 skill key
  - 搜技能描述
  - 搜技能包名

- `package_id`
  - 可选
  - 用于按技能包过滤

- `page`
  - 默认 `1`

- `page_size`
  - 默认 `20`

- `include_system`
  - 默认 `true`
  - 管理端绑定技能通常应该能看到系统技能

- `only_active`
  - 默认 `true`

### 6.4 后端实现建议

建议修改这些文件：

- `backend/app/api/admin/skills.py`
- `backend/app/services/ai/skill_service.py`
- `backend/app/repositories/ai/skill_repository.py`

推荐做法：

1. 在 `AdminSkillController` 新增 `/select`
2. 在 `AdminSkillService` 新增类似 `get_binding_select_options(...)`
3. 在 `AdminSkillRepository` 新增带 `SkillPackage` join 的查询方法

### 6.5 查询逻辑要求

后端查询不要只看 `skills` 表本身，必须 join `skill_packages`，因为需要：

- `package_name`
- `source_plugin`
- 未来按技能包名搜索

搜索条件建议：

- `skills.name ILIKE`
- `skills.key ILIKE`
- `skills.description ILIKE`
- `skill_packages.name ILIKE`

排序建议：

1. `skill_packages.sort_order`
2. `skill_packages.created_at desc`
3. `skills.sort_order`
4. `skills.created_at desc`

### 6.6 技能包下拉接口同步补分页

现有：

- `GET /admin/ai/skill-packages/select`

目前只有：

- `search`
- `include_system`

建议顺手扩展支持：

- `page`
- `page_size`

因为新的技能绑定选择器顶部“技能包过滤器”最好直接复用这个接口做远程搜索 + 分页。

建议改动文件：

- `backend/app/api/admin/skill_packages.py`
- `frontend/apps/web-antd/src/api/admin/skill-packages.ts`

---

## 7. 前端方案

## 7.1 新增共享组件

建议新增：

- `frontend/apps/web-antd/src/components/business/agent-skill-binding-picker/AgentSkillBindingPicker.vue`

可选拆分：

- `frontend/apps/web-antd/src/components/business/agent-skill-binding-picker/types.ts`
- `frontend/apps/web-antd/src/components/business/agent-skill-binding-picker/index.ts`

### 7.2 组件职责

该组件负责：

1. 拉取远程技能候选项
2. 拉取远程技能包过滤项
3. 管理搜索 / 翻页 / 包过滤状态
4. 把当前页结果按技能包分组渲染
5. 在不同页之间保留已选项
6. 管理每个已选 skill 的 consent mode
7. 向父页面返回完整的选择结果

### 7.3 建议的组件输入输出

#### Props

- `modelValue`
  - 当前已选技能草稿

- `mode`
  - `replace`
  - `append`

- `title`
  - 弹窗标题

- `excludeSkillIds`
  - 可选
  - detail 页可用于隐藏已绑定技能，或者标记成 disabled

- `confirmText`
  - 可选

#### Emits

- `update:modelValue`
- `confirm`
- `cancel`

### 7.4 建议的数据结构

前端建议引入统一类型：

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

这样 form 和 detail 都用同一种中间态，不要一处用 `number[]`，另一处用 `{label,value}`，第三处又用 grants。

### 7.5 组件内部状态建议

组件内部至少维护：

- `searchKeyword`
- `selectedPackageId`
- `page`
- `pageSize`
- `total`
- `loading`
- `currentPageItems`
- `selectedMap`
  - `Map<number, AgentSkillBindingDraftItem>`

用 `Map` 的原因：

- 便于跨页保留
- 便于去重
- 便于更新某个 skill 的 consent mode

### 7.6 组件内部展示逻辑

当前页接口返回的是扁平 skill 列表，组件内再按 `package_id` 分组：

```ts
currentPageGroups = [
  {
    package_id: 194,
    package_name: '页面感知交互',
    items: [ ...skills ],
  },
]
```

这能满足“按技能包分类”，同时避免后端返回复杂树结构。

### 7.7 错误处理

这次不要再有 silent failure。

必须做到：

- 页面上有明确错误态
- 至少 `console.error('[AgentSkillBindingPicker]', error)`
- 接口失败时用户能看到 toast / empty state，而不是悄悄变成空列表

---

## 8. 两个落地点的接入方案

## 8.1 智能体新增 / 编辑表单

目标文件：

- `frontend/apps/web-antd/src/views/admin/ai/agents/modules/form.vue`

### 当前问题

- 当前在 drawer 里直接放了一个多选 `ASelect`
- 选项全靠 `getSkillSelectOptions()` 一次性预加载

### 改造建议

改成：

1. 表单里保留“技能绑定”区块
2. 区块顶部显示：
   - 已选技能数量
   - “选择技能”按钮
3. 点击按钮打开 `AgentSkillBindingPicker`
4. 选择完成后，把结果写回本地 `draft`
5. 下方继续展示已选技能和 consent mode，但不再由下拉框承担选择能力

### 保存逻辑

表单成功后仍然使用：

- `batchBindAIAgentSkillsApi`

但入参必须来自新的统一草稿结构：

- `skill_ids`
- `default_consent_modes`

不要再靠：

- `selectedSkills`
- `pendingSkillIds`
- `consentModes`

这三套松散状态并存。

建议统一成一套 `selectedSkillDrafts`。

---

## 8.2 智能体详情页技能绑定 Tab

目标文件：

- `frontend/apps/web-antd/src/views/admin/ai/agents/detail.vue`

### 当前问题

当前详情页里：

- 已绑定列表是一套
- 新增技能又是一套单独的 `ASelect`
- 新增技能时直接 `batchBind`，但没有把已有非 `auto` 的 consent mode 一起带回去

这会导致已有配置被重置。

### 改造建议

详情页不要再保留那个简单的“加几个 skill id”的多选下拉。

建议改成：

1. 技能绑定 Tab 顶部显示：
   - “管理技能绑定”按钮
2. 点击后打开同一个 `AgentSkillBindingPicker`
3. 打开时预填当前 grants
4. 用户在 picker 里可以：
   - 搜
   - 按技能包看
   - 翻页
   - 勾选 / 取消
   - 设置 consent mode
5. 点击确认后，父页面执行一次全量 `batchBind`

### detail 页提交逻辑必须修正

必须注意：

- `batchBindAIAgentSkillsApi` 是替换模式

因此确认时必须传：

1. 最终全量 `skill_ids`
2. 最终全量 `default_consent_modes`

不能只传新增的 skill。

否则会把已有 grant 上的非默认 consent mode 丢掉。

这条是本次改造的硬性要求。

### 是否保留下方已有绑定卡片

建议保留。

保留理由：

- 顶部 picker 负责“批量管理”
- 下方卡片继续负责“快速查看 / 启停 / 单项解绑 / 单项调整 consent mode”

这样不会丢失 detail 页已有的运维效率。

---

## 9. API 与前端类型建议

### 9.1 前端 API 文件

建议修改：

- `frontend/apps/web-antd/src/api/admin/skills.ts`
- `frontend/apps/web-antd/src/api/admin/skill-packages.ts`

### 9.2 新增技能选择接口类型

建议加：

```ts
export interface AdminSkillSelectOptionExtra {
  package_id: null | number;
  package_name: null | string;
  skill_type: null | string;
  skill_key: null | string;
  description: null | string;
  is_system: boolean;
  is_active: boolean;
  source_plugin: null | string;
  tenant_id: null | number;
}

export interface AdminSkillSelectOption {
  label: string;
  value: number;
  extra?: AdminSkillSelectOptionExtra;
}

export interface AdminSkillSelectResponse {
  items: AdminSkillSelectOption[];
  total?: number;
  page?: number;
  page_size?: number;
  has_more?: boolean;
}
```

### 9.3 新增 API 方法

```ts
getSkillSelectApi(params)
```

不要再把 Agent 的技能选择逻辑塞在 `views/admin/ai/agents/data.ts` 里拼装。

远程取数属于 API 层职责。

---

## 10. 本次改造建议修改的文件

### 后端

- `backend/app/api/admin/skills.py`
- `backend/app/services/ai/skill_service.py`
- `backend/app/repositories/ai/skill_repository.py`
- `backend/app/api/admin/skill_packages.py`

### 前端 API / 类型

- `frontend/apps/web-antd/src/api/admin/skills.ts`
- `frontend/apps/web-antd/src/api/admin/skill-packages.ts`

### 前端共享组件

- `frontend/apps/web-antd/src/components/business/agent-skill-binding-picker/AgentSkillBindingPicker.vue`
- `frontend/apps/web-antd/src/components/business/agent-skill-binding-picker/index.ts`
- 如需要：`types.ts`

### 前端业务页

- `frontend/apps/web-antd/src/views/admin/ai/agents/modules/form.vue`
- `frontend/apps/web-antd/src/views/admin/ai/agents/detail.vue`
- `frontend/apps/web-antd/src/views/admin/ai/agents/data.ts`

### 多语言

- `frontend/apps/web-antd/src/locales/langs/zh-CN/admin/ai.json`
- `frontend/apps/web-antd/src/locales/langs/en-US/admin/ai.json`

---

## 11. 明确的完成标准

只有同时满足这些条件，才算完成：

1. 管理端新增智能体时，技能选择不再依赖全量预加载
2. 管理端编辑智能体时，技能选择不再依赖全量预加载
3. 管理端详情页技能绑定 Tab 不再依赖简单多选下拉
4. 技能选择器支持：
   - 搜索
   - 按技能包分类展示
   - 分页
   - 跨页保留已选技能
5. 技能包过滤器支持远程搜索和分页
6. detail 页通过 picker 提交时，不会重置已有 grant 的 `default_consent_mode`
7. 前端没有 silent failure；接口错误不会再无声吞掉
8. `vue-tsc` 通过
9. 相关 Python 文件 `py_compile` 通过
10. 浏览器至少验证：
   - 管理端新增 Agent 打开技能选择器可选技能
   - 管理端编辑 Agent 打开技能选择器可回显已选技能
   - 管理端详情页技能绑定可搜索、翻页、按包看、保存成功

---

## 12. 浏览器验证要求

按项目 skill / rule 执行：

- 优先 `chrome-devtools`
- 先看 network / console
- 不要混用多套浏览器 MCP

### 必测路径

1. `http://localhost:5666/admin/login`
2. `http://localhost:5666/admin/ai/agents`
3. 新建 Agent 打开表单
4. 编辑任意 Agent 打开表单
5. `http://localhost:5666/admin/ai/agents/59?tab=skills`

### 必查接口

- `GET /admin/ai/skills/select`
- `GET /admin/ai/skill-packages/select`
- `GET /admin/ai/agents/{id}/skills`
- `PUT /admin/ai/agents/{id}/skills/batch`

### 验收重点

- 搜索后结果更新
- 翻页后选择不会丢
- 按包分组展示正常
- 已选 skill 的 consent mode 保存后仍正确
- detail 页新增 skill 不会把原有 `ask/reject` 重置成 `auto`

---

## 13. KIMI 不要做的事

不要扩散到以下内容：

- tenant 侧技能绑定 UI
- SkillPackage 架构语义再重构
- dashboard / plugin widget
- 无关迁移
- 改 AI runtime / resolver / AgentSkillGrant 语义

本次只做：

- 管理端 Agent 技能绑定交互升级
- 相关接口支持
- 相关类型 / i18n / 页面接入

---

## 14. KIMI 交付时必须汇报的内容

KIMI 完成后必须给出：

1. 改了哪些文件
2. 共享组件的最终 API 是什么
3. 新增 / 修改了哪些后端接口
4. 如何保证 detail 页 `batchBind` 不再覆盖已有 consent mode
5. 跑了哪些静态校验
6. 浏览器实际验证了哪些页面和请求
7. 还有哪些已知非阻塞问题

---

## 15. 最终一句话

这次不是“修下拉框”，而是：

> 把管理端 Agent 的 Skill 绑定，从一次性拼装的大下拉，升级成正式的、可搜索、可分类、可分页、可保留配置的共享业务组件。

