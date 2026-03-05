# 详情页 UI 模式规范

本文档描述 NovusAI SaaS 中**资源详情页**的标准布局和可复用组件模式，  
以 `admin/ai/agents/detail.vue` 为参考实现。

---

## 整体页面结构

```
<Page auto-content-height>
  <Spin :spinning="loading">
    <!-- 1. 空状态 -->
    <div v-if="!loading && !resource" class="py-20"><Empty /></div>

    <div v-if="resource" class="flex flex-col gap-4">
      <!-- 2. Hero Header 卡片 -->
      ...

      <!-- 3. Tabs 容器（rounded border bg-card） -->
      <div class="rounded-xl border bg-card">
        <Tabs :active-key="activeTab" class="px-2 pt-1" @change="onTabChange">
          ...
        </Tabs>
      </div>
    </div>
  </Spin>
</Page>
```

---

## 一、Hero Header

用于详情页顶部，展示资源标识、状态标签、元信息芯片行。

```vue
<div class="relative overflow-hidden rounded-xl border bg-card shadow-sm">
  <!-- 渐变背景装饰 -->
  <div class="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-transparent" />

  <div class="relative p-6">
    <!-- 顶行：返回按钮（左）+ 状态标签（右） -->
    <div class="mb-5 flex items-center justify-between">
      <button
        class="flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        @click="goBack"
      >
        <IconifyIcon icon="lucide:chevron-left" class="size-4" />
        {{ $t('common.back') }}
      </button>
      <div class="flex items-center gap-2">
        <Tag v-if="resource.is_system" color="purple" class="!mr-0">系统</Tag>
        <Tag :color="getStatusColor(resource.status)" class="!mr-0">{{ getStatusText(resource.status) }}</Tag>
      </div>
    </div>

    <!-- 身份区块：头像 + 名称 + 描述 + 芯片行 -->
    <div class="flex items-start gap-5">
      <!-- 头像 -->
      <div
        class="flex size-16 shrink-0 items-center justify-center rounded-2xl text-2xl font-bold shadow-sm ring-2 ring-offset-2 ring-offset-card bg-primary/10 text-primary ring-primary/20"
      >
        {{ (resource.name || '?').charAt(0).toUpperCase() }}
      </div>

      <div class="min-w-0 flex-1">
        <h1 class="mb-1 text-xl font-bold text-foreground">{{ resource.name }}</h1>
        <p class="mb-4 text-sm text-muted-foreground">
          {{ resource.description || $t('...noDescription') }}
        </p>

        <!-- 元信息芯片行 -->
        <div class="flex flex-wrap items-center gap-2">
          <!-- 文本芯片 -->
          <div class="flex items-center gap-1.5 rounded-lg border border-border/50 bg-background px-3 py-1 text-xs text-foreground">
            <IconifyIcon icon="lucide:brain" class="size-3.5 text-primary/70" />
            {{ resource.model_name }}
          </div>

          <!-- 带颜色的 Tag 芯片 -->
          <Tag :color="getScopeColor(resource.scope)" class="!mr-0 !text-xs">
            <div class="flex items-center gap-1">
              <IconifyIcon :icon="getScopeIcon(resource.scope)" class="size-3" />
              {{ getScopeText(resource.scope) }}
            </div>
          </Tag>

          <!-- 功能状态芯片（可点击跳转 Tab） -->
          <button
            class="flex items-center gap-1.5 rounded-lg border px-3 py-1 text-xs font-medium transition-all duration-200 hover:opacity-80"
            :class="featureEnabled
              ? 'border-green-500/30 bg-green-500/10 text-green-600 dark:text-green-400'
              : 'border-border/50 bg-background text-muted-foreground'"
            @click="jumpToFeatureTab"
          >
            <IconifyIcon icon="lucide:git-branch" class="size-3.5" />
            <span v-if="featureEnabled">已开启</span>
            <span v-else>未开启</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</div>
```

**设计要点：**
- 渐变背景 `from-primary/5` 使卡片与页面区分
- 头像：`size-16 rounded-2xl ring-2 ring-offset-2`，系统资源用琥珀色
- 功能状态芯片：绑定 `@click="jumpToFeatureTab()"` 可直接跳转对应 Tab
- 状态标签统一放右上角，不混入芯片行

---

## 二、Tab 标签页（带图标）

```vue
<Tabs :active-key="activeTab" class="px-2 pt-1" @change="onTabChange">
  <TabPane key="overview">
    <template #tab>
      <span class="flex items-center gap-1.5 px-1">
        <IconifyIcon icon="lucide:layout-dashboard" class="size-3.5" />
        概览
      </span>
    </template>
    <div class="p-5 pt-3"><!-- 内容 --></div>
  </TabPane>

  <!-- 带状态圆点（如路由已启用） -->
  <TabPane key="routing">
    <template #tab>
      <span class="flex items-center gap-1.5 px-1">
        <IconifyIcon icon="lucide:git-branch" class="size-3.5" />
        智能路由
        <span v-if="isFeatureEnabled" class="inline-block size-2 rounded-full bg-green-500" />
      </span>
    </template>
    <div class="p-5 pt-3"><!-- 内容 --></div>
  </TabPane>
</Tabs>
```

**常用 Tab 图标映射：**

| Tab | icon |
|-----|------|
| 概览 | `lucide:layout-dashboard` |
| 模型参数 | `lucide:sliders` |
| 对话配置 | `lucide:message-circle` |
| 技能/绑定 | `lucide:puzzle` |
| 配额管理 | `lucide:gauge` |
| 智能路由 | `lucide:git-branch` |
| 权限 | `lucide:shield` |
| 日志 | `lucide:scroll-text` |
| 设置 | `lucide:settings` |

---

## 三、概览 Tab：信息卡片网格

用于展示资源的只读基础字段（状态、模式、模型等）。

```vue
<div class="grid grid-cols-2 gap-3 md:grid-cols-4">
  <!-- 单个信息卡片 -->
  <div class="rounded-xl border bg-accent/30 p-4">
    <div class="mb-1.5 flex items-center gap-1.5">
      <IconifyIcon icon="lucide:activity" class="size-3.5 text-muted-foreground" />
      <span class="text-xs text-muted-foreground">状态</span>
    </div>
    <!-- 值区域：可以是 Tag、文本、任意组件 -->
    <Tag :color="getStatusColor(resource.status)" class="!mr-0 !text-xs">
      {{ getStatusText(resource.status) }}
    </Tag>
  </div>

  <div class="rounded-xl border bg-accent/30 p-4">
    <div class="mb-1.5 flex items-center gap-1.5">
      <IconifyIcon icon="lucide:brain" class="size-3.5 text-muted-foreground" />
      <span class="text-xs text-muted-foreground">模型</span>
    </div>
    <span class="text-sm font-medium">{{ resource.model_name || '-' }}</span>
  </div>
</div>
```

**规则：**
- 列数：2 列（移动端）/ 3~4 列（桌面）
- 背景：`bg-accent/30`（只读区域），`bg-background`（可编辑卡片）
- 标签行：`text-xs text-muted-foreground` + `size-3.5` 图标
- 值区域：`text-sm font-medium` 或 `Tag`

---

## 四、带图标标题的表单区块

用于可编辑字段（提示词、欢迎语、参数等），每个字段一个圆角卡片。

```vue
<!-- 单个表单区块 -->
<div class="rounded-xl border bg-accent/30 p-5">
  <!-- 区块标题行：图标 + 标签 + 右侧操作按钮 -->
  <div class="mb-3 flex items-center justify-between">
    <div class="flex items-center gap-2">
      <div class="flex size-7 items-center justify-center rounded-lg bg-primary/10">
        <IconifyIcon icon="lucide:message-square-code" class="size-4 text-primary" />
      </div>
      <span class="text-sm font-semibold">系统提示词</span>
    </div>
    <!-- 右侧操作（可选） -->
    <Button v-if="!editing" size="small" type="link" @click="startEdit">
      <IconifyIcon icon="lucide:pencil" class="mr-1 size-3.5" />
      {{ $t('common.edit') }}
    </Button>
    <div v-else class="flex gap-2">
      <Button size="small" @click="cancelEdit">{{ $t('common.cancel') }}</Button>
      <Button size="small" type="primary" :loading="saving" @click="save">{{ $t('common.save') }}</Button>
    </div>
  </div>

  <!-- 字段内容 -->
  <div v-if="!editing" class="min-h-[60px] whitespace-pre-wrap text-sm leading-relaxed text-foreground">
    {{ resource.system_prompt || '-' }}
  </div>
  <Textarea v-else v-model:value="draft" :rows="8" class="w-full" />
</div>
```

**图标色规范（区块标题左侧小图标背景色）：**

| 语义 | bg 色 | 图标色 |
|------|-------|--------|
| 主功能/提示词 | `bg-primary/10` | `text-primary` |
| 温度/参数 | `bg-orange-500/10` | `text-orange-500` |
| Token 数量 | `bg-blue-500/10` | `text-blue-500` |
| 概率/Top P | `bg-purple-500/10` | `text-purple-500` |
| 欢迎语 | `bg-green-500/10` | `text-green-500` |
| 推荐问题 | `bg-cyan-500/10` | `text-cyan-500` |
| 输入变量 | `bg-violet-500/10` | `text-violet-500` |
| 上下文历史 | `bg-amber-500/10` | `text-amber-500` |

---

## 五、模型参数 Tab：3 列参数卡片

```vue
<div class="grid max-w-2xl grid-cols-1 gap-4 md:grid-cols-3">
  <div class="rounded-xl border bg-accent/30 p-5">
    <div class="mb-3 flex items-center gap-2">
      <div class="flex size-7 items-center justify-center rounded-lg bg-orange-500/10">
        <IconifyIcon icon="lucide:thermometer" class="size-4 text-orange-500" />
      </div>
      <label class="text-sm font-medium">Temperature</label>
    </div>
    <InputNumber v-model:value="modelTemp" :min="0" :max="2" :step="0.1" class="w-full" />
  </div>
  <!-- 其他参数卡片... -->
</div>
<div class="mt-5">
  <Button type="primary" :loading="saving" @click="save">{{ $t('common.save') }}</Button>
</div>
```

---

## 六、技能/绑定 Tab：列表行

不使用 `<Card>` wrapper，直接用圆角 `div` 行，视觉更轻。

```vue
<!-- 添加区（搜索+按钮） -->
<div class="flex items-center gap-3 rounded-xl border bg-accent/30 p-4">
  <ASelect v-model:value="selectedNew" class="flex-1" ... />
  <Button type="primary" :disabled="!selectedNew" @click="bind">
    <IconifyIcon icon="lucide:plus" class="mr-1" />添加
  </Button>
</div>

<!-- 绑定项行（自动绑定） -->
<div class="flex items-center justify-between rounded-xl border border-primary/20 bg-primary/5 px-4 py-3">
  <div class="flex items-center gap-3">
    <IconifyIcon icon="lucide:lock" class="size-4 text-primary/50" />
    <span class="text-sm font-medium">{{ binding.name }}</span>
  </div>
  <Tag color="blue" class="!text-[10px]">自动</Tag>
</div>

<!-- 绑定项行（手动绑定，悬停高亮） -->
<div class="flex items-center justify-between rounded-xl border bg-background px-4 py-3 transition-colors hover:bg-accent/30">
  <div class="flex items-center gap-3">
    <div class="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-sm font-bold text-primary">
      {{ binding.name.charAt(0) }}
    </div>
    <span class="text-sm font-medium">{{ binding.name }}</span>
  </div>
  <div class="flex items-center gap-2">
    <Tag color="green">自动授权</Tag>
    <Button size="small" danger @click="unbind(binding.id)">
      <IconifyIcon icon="lucide:x" />
    </Button>
  </div>
</div>
```

---

## 七、功能开关 Tab（智能路由模式）

核心是**主开关卡片** + **启用后展开的功能卡片网格**。

### 主开关卡片

```vue
<div
  class="mb-5 rounded-xl border-2 p-5 transition-all duration-300"
  :class="featureEnabled ? 'border-green-500/30 bg-green-500/5' : 'border-border bg-accent/20'"
>
  <div class="flex items-start gap-4">
    <!-- 功能图标 -->
    <div
      class="flex size-12 shrink-0 items-center justify-center rounded-xl transition-all duration-300"
      :class="featureEnabled ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"
    >
      <IconifyIcon icon="lucide:git-branch" class="size-6" />
    </div>

    <div class="flex-1">
      <div class="flex items-center justify-between gap-4">
        <div>
          <h3 class="text-base font-semibold text-foreground">功能名称</h3>
          <p class="mt-0.5 text-sm text-muted-foreground">功能说明文字</p>
        </div>
        <Switch v-model:checked="featureEnabled" class="shrink-0" />
      </div>

      <!-- 启用时显示状态标签 -->
      <div
        v-if="featureEnabled"
        class="mt-3 inline-flex items-center gap-1.5 rounded-full bg-green-500/10 px-3 py-1 text-xs font-medium text-green-600 dark:text-green-400"
      >
        <span class="inline-block size-1.5 rounded-full bg-green-500" />
        已启用
      </div>
    </div>
  </div>
</div>
```

### 功能子卡片（2×2 网格，条件渲染）

```vue
<div v-if="featureEnabled" class="grid grid-cols-1 gap-4 md:grid-cols-2">
  <!-- 单个功能子卡片 -->
  <div class="rounded-xl border bg-background p-5 shadow-sm">
    <div class="mb-4 flex items-center gap-3">
      <div class="flex size-9 items-center justify-center rounded-xl bg-amber-500/10">
        <IconifyIcon icon="lucide:layers" class="size-5 text-amber-500" />
      </div>
      <div>
        <div class="text-sm font-semibold">功能标题</div>
        <div class="text-xs text-muted-foreground">帮助说明文字</div>
      </div>
    </div>
    <!-- 控件 -->
    <ASelect v-model:value="value" class="w-full" :allow-clear="true" :placeholder="'请选择'" />
  </div>
</div>
```

**子卡片图标色参考（同上方色规范）：**
- 成本上限 → `bg-amber-500/10 text-amber-500` `lucide:layers`
- Vision 模型 → `bg-violet-500/10 text-violet-500` `lucide:eye`
- 长上下文模型 → `bg-blue-500/10 text-blue-500` `lucide:scroll-text`
- 触发阈值 → `bg-cyan-500/10 text-cyan-500` `lucide:gauge`

---

## 八、只读横幅（租户端平台资源）

```vue
<div
  v-if="!isOwned"
  class="flex items-center gap-1.5 rounded-lg border border-warning/30 bg-warning/10 px-3 py-1 text-xs font-medium text-warning"
>
  <IconifyIcon icon="lucide:lock" class="size-3.5" />
  {{ $t('tenant.ai.agent.readonlyHint') }}
</div>
```

放在 Hero Header 的芯片行中，或单独成一行横幅。

---

## 九、保存按钮规范

每个 Tab 底部保存按钮统一：

```vue
<!-- 独立 div，与上方内容保持 mt-5 间距 -->
<div class="mt-5">
  <Button type="primary" :loading="saving" @click="saveXxx">
    {{ $t('common.save') }}
  </Button>
</div>
```

仅租户端有权限限制时：

```vue
<div v-if="isOwned" class="mt-5">
  <Button type="primary" :loading="saving" @click="saveXxx">{{ $t('common.save') }}</Button>
</div>
```

---

## 十、Tab 切换懒加载模式

```typescript
function onTabChange(key: string | number) {
  activeTab.value = String(key);
  if (!resource.value) return;
  switch (key) {
    case 'modelParams': initModelParams(); break;
    case 'skills':      { loadBindings(); loadOptions(); break; }
    case 'routing':     { initRouting(); loadRoutingModelOptions(); break; }
  }
}

// URL query 参数支持直接定位 Tab
onMounted(async () => {
  await loadResource();
  const tab = route.query.tab as string | undefined;
  if (tab) {
    activeTab.value = tab;
    onTabChange(tab);
  }
});
```

URL 格式：`/admin/ai/agents/123?tab=routing`

---

## 十一、新建详情页快速检查清单

- [ ] `<Page auto-content-height>` 作为根
- [ ] Hero Header：渐变背景、`size-16 rounded-2xl ring-2` 头像、h1 + 描述、芯片行
- [ ] 所有 Tab 使用 `#tab` 插槽 + `IconifyIcon` 图标
- [ ] 功能状态 Tab 添加绿色圆点 `class="inline-block size-2 rounded-full bg-green-500"`
- [ ] 信息卡片：`bg-accent/30 rounded-xl border p-4`
- [ ] 表单区块：`bg-accent/30 rounded-xl border p-5` + 图标标题行
- [ ] 参数卡片（model params）：`bg-accent/30 rounded-xl border p-5` + `size-7 rounded-lg` 图标
- [ ] 功能开关卡片：`border-2` + 颜色条件类 + 展开子卡片网格
- [ ] 绑定行：`rounded-xl border px-4 py-3` + `hover:bg-accent/30`
- [ ] 保存按钮：独立 `div class="mt-5"`
- [ ] `onMounted` 处理 `route.query.tab` 实现 URL 直达 Tab
- [ ] 租户端：`isTenantOwned` 控制编辑按钮/Save 按钮的 `v-if`
