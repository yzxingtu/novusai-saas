---
name: admin-table-hero
description: NovusAI 管理端表格页 Hero 技能。当需要把 admin 列表或表格页做成系统日志、供应商管理这种顶部 hero 头、chips、metrics、quick-start 卡片时使用。
---

# 管理端表格页 Hero 技能

## 何时使用

- 新建 admin 列表/表格页，需要从普通 `Page description` 升级成更完整的头部
- 旧页面只有表格和搜索栏，需要补 hero、状态 chips、步骤引导或 summary metrics
- 用户明确要求“参考系统日志页”或“参考供应商管理页”的头部做法

## 先选页面模式

- 纯运维/观测页：参考 `frontend/apps/web-antd/src/views/admin/system/system-logs/index.vue`
- AI 基础设施 onboarding 页：参考 `frontend/apps/web-antd/src/views/admin/ai/providers/index.vue`
- 普通业务列表/目录页：做“页面特色 hero”，不要套用基础设施 quick-start
- 简单表格页：只保留 `hero + Grid` 两段，不要硬凑三段卡片

## Hero 分类

### 1. 基础设施 quick-start hero

只用于同一条配置链路中的页面，例如：

- 供应商管理
- API Key 管理
- 模型管理
- AI 表策略
- 健康状态

这类页面可以共享同一组步骤、预计耗时、流程 chips，因为它们本来就在同一条 AI 网关配置路径上。

### 2. 页面特色 hero

用于知识库、技能包、调用日志、使用量、对话、操作审计、配额等页面。

这类 hero 必须展示该页面自己的信息，不要再出现：

- `当前模块: xxx`
- `流程: 添加供应商 / 配置 API Key / 添加模型 / 健康检查`
- `预计耗时: 约 8 分钟`
- `4 个步骤`

页面特色 hero 应优先展示：

- 该页真正的业务摘要，例如总调用数、知识库总量、当前选中包、过滤状态、审计范围
- 该页核心分析维度，例如 `Token / 成本 / 延迟`、`文档 / 分块 / 存储`
- 该页主操作上下文，例如当前 tab、当前筛选、当前选中实体、是否存在风险/异常

## 必守规则

- 不要同时保留 `Page :description` 和自定义 hero；改成 `content-class="flex flex-col gap-4 !p-4"`
- hero 外层统一用卡片容器：

```vue
<section class="rounded-[20px] border border-border/70 bg-card px-4 py-3 shadow-sm">
```

- hero 第一行固定是：左侧 `icon + h1 + subtitle`，右侧 `metrics pills`
- hero 第二行优先放 chips，承载当前模块、状态、流程、文件、预计耗时等关键信息
- 如果页面有 onboarding，就把步骤放在同一张 hero 卡片内，用 `grid` 做 2/4 列步骤卡
- 数据表格保持独立一段；简单页面不要再拆第三段
- 用户可见文案必须走 i18n，不能把中文或英文直接写进模板
- hero 的 chips 和 metrics 必须来自该页面现有数据或明确业务语义；不要为了“看起来完整”硬塞无关信息
- 同一组件可以复用，但内容模型必须按页面类型切换；禁止把 quick-start 组件直接复用到非基础设施页

## Hero 骨架

```vue
<Page auto-content-height content-class="flex flex-col gap-4 !p-4">
  <section class="rounded-[20px] border border-border/70 bg-card px-4 py-3 shadow-sm">
    <div class="flex flex-col gap-3 2xl:flex-row 2xl:items-start 2xl:justify-between">
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <span class="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary" />
          <h1 class="text-base font-semibold text-foreground" />
          <span class="hidden text-xs text-muted-foreground xl:inline" />
        </div>

        <div class="mt-2 flex flex-wrap gap-2">
          <span class="inline-flex max-w-full items-center gap-2 rounded-full border border-transparent px-2.5 py-1 text-xs" />
        </div>
      </div>

      <div class="flex flex-wrap gap-2">
        <span class="rounded-xl border border-border/60 bg-background/80 px-3 py-2 text-xs text-muted-foreground" />
      </div>
    </div>
  </section>

  <Grid />
</Page>
```

## Quick Start 版本

- 步骤卡片放在 hero 卡片内部，不再额外套旧版 `QuickStartGuide`
- 步骤容器统一：

```vue
<div class="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
```

- 单个步骤卡统一：

```vue
<router-link class="group rounded-2xl border border-border/60 bg-background/80 px-4 py-3 transition-all hover:border-primary/20 hover:bg-accent/40">
```

- 步骤编号使用右上角圆形 badge，步骤 icon 用 40px 方形 iconWrap
- 移动端允许自然堆叠，不要强行保持 4 列

## 页面特色版本

- 不要出现步骤卡片
- chips 优先放：
  - 当前筛选
  - 当前 tab
  - 当前选中对象
  - 业务范围
  - 核心分析维度
- metrics 优先复用页面现有统计卡片、summary 数据、聚合 counters；如果页面没有汇总数据，可以只保留 title + desc + chips
- 如果页面原本就有一排统计卡片，优先考虑把它们并入 hero，而不是 hero 和统计卡片重复表达同一组数字

## 应该放什么

- chips：当前模块、关键状态、当前文件、配置流程、预计耗时
- metrics：数量、体量、步骤数、总耗时；只放 2 到 3 个，避免变成 KPI 墙
- subtitle：一句话说明页面价值，不要重复标题
- actions：只有运维/观测页才适合在 hero 右侧放刷新、下载、复制等操作

页面特色 hero 的推荐内容：

- 调用日志：总调用、成功率、平均延迟、总费用
- 使用量统计：总调用、总 Token、总费用、趋势维度
- 知识库：知识库数、文档数、分块数、总存储
- 配额管理：启用规则数、风险规则数、限速规则数、当前 tab
- 技能包：当前选中包、角色、运行时绑定模式、来源摘要
- 对话管理：企业/用户/消息/费用等当前查看维度
- 操作审计：操作类型、安全等级、请求/响应/错误明细能力

## 明确禁止

- 禁止 hero 上方再出现一段裸 `paragraph` 描述
- 禁止沿用旧的可关闭 `QuickStartGuide` 来替代 hero 卡片
- 禁止为了“像系统日志”而把简单 CRUD 页面拆成三段以上
- 禁止 chips 写成长段说明文字；长信息应截断或下沉到正文
- 禁止在 hero 中塞过多按钮，尤其是与主表格操作重复的按钮
- 禁止把基础设施 quick-start 文案复制到知识库、技能包、调用日志、用量、对话、审计、配额这类页面

## 完成后检查

- 桌面端：hero、Grid、步骤卡之间间距是否稳定
- 移动端：chips 是否换行正常，步骤卡是否自然堆叠
- 浏览器回归至少检查一次目标页和参考页，避免写成另一套视觉语言

## 现成参考

- `frontend/apps/web-antd/src/views/admin/system/system-logs/index.vue`
- `frontend/apps/web-antd/src/views/admin/ai/providers/index.vue`
