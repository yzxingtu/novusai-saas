<script lang="ts" setup>
/**
 * 工作流编辑器 / Workflow editor
 *
 * 状态字段选择（从 enum 字段）、transitions、颜色映射、VueFlow 流程图可视化
 * VueFlow 异步加载，加载失败时显示友好提示
 */
import type { Node, Edge } from '@vue-flow/core';

import { computed, defineAsyncComponent, h } from 'vue';

import { Button, Form, Input, Select, Switch } from 'ant-design-vue';

import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';

defineOptions({ name: 'WorkflowEditor' });

const VueFlow = defineAsyncComponent({
  loader: () => import('@vue-flow/core').then((m) => m.VueFlow ?? m.default),
  loadingComponent: { render: () => null },
  errorComponent: {
    setup() {
      const msg = $t('admin.system.codegen.enum.loadFailed');
      return () => h('div', { class: 'rounded border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive' }, msg);
    },
  },
});

const Background = defineAsyncComponent({
  loader: () => import('@vue-flow/background').then((m) => m.Background ?? m.default),
  loadingComponent: { render: () => null },
});

const NODE_WIDTH = 100;
const NODE_HEIGHT = 36;
const GAP = 80;

const store = useCodegenBuilderStore();

const workflow = computed({
  get: () => (store.configJson.workflow as Record<string, unknown>) || {},
  set: (v) => store.updateConfig({ workflow: v }),
});

const fields = computed(
  () => (store.configJson.fields as Array<Record<string, unknown>>) || [],
);

const enumFields = computed(() =>
  fields.value.filter((f) => f.type === 'Enum' || (f.enum_values && Array.isArray(f.enum_values))),
);

const statusFieldOptions = computed(() =>
  enumFields.value.map((f) => ({ label: (f.name as string) || f.comment, value: f.name as string })),
);

const statusValuesMap = computed(() => {
  const m = new Map<string, Array<{ value: string; label_zh?: string; color?: string }>>();
  for (const f of enumFields.value) {
    const vals = (f.enum_values as Array<Record<string, unknown>>) || [];
    m.set(
      f.name as string,
      vals.map((v) => ({
        value: String(v.value ?? v),
        label_zh: v.label_zh as string,
        color: (v.color as string) || 'default',
      })),
    );
  }
  return m;
});

const transitions = computed(() => {
  const t = (workflow.value.transitions as Array<Record<string, unknown>>) || [];
  return t;
});

const statusField = computed(() => (workflow.value.status_field as string) || '');

const currentStatusValues = computed(() => {
  if (!statusField.value) return [];
  return statusValuesMap.value.get(statusField.value) || [];
});

const statusSelectOptions = computed(() =>
  currentStatusValues.value.map((v) => ({ label: v.label_zh || v.value, value: v.value })),
);

const colorOptions = computed(() => [
  { label: $t('admin.system.codegen.enum.colorOptions.default'), value: 'default' },
  { label: $t('admin.system.codegen.enum.colorOptions.success'), value: 'success' },
  { label: $t('admin.system.codegen.enum.colorOptions.warning'), value: 'warning' },
  { label: $t('admin.system.codegen.enum.colorOptions.error'), value: 'error' },
  { label: $t('admin.system.codegen.enum.colorOptions.processing'), value: 'processing' },
]);

function updateWorkflow(patch: Record<string, unknown>) {
  store.updateConfig({ workflow: { ...workflow.value, ...patch } });
}

function addTransition() {
  const vals = currentStatusValues.value;
  if (!vals.length) return;
  const list = [...transitions.value];
  list.push({
    from: vals[0]?.value ?? '',
    to: vals[0]?.value ?? '',
    action: '',
    permission: '',
    requires_comment: false,
    label_zh: '',
  });
  updateWorkflow({ transitions: list });
}

function removeTransition(index: number) {
  const list = transitions.value.filter((_, i) => i !== index);
  updateWorkflow({ transitions: list });
}

function updateTransition(index: number, patch: Record<string, unknown>) {
  const list = transitions.value;
  if (index < 0 || index >= list.length) return;
  const next = [...list];
  next[index] = { ...next[index], ...patch };
  updateWorkflow({ transitions: next });
}

/** VueFlow 节点：每个状态一个节点，水平排列 / VueFlow nodes: one per status, horizontal layout */
const flowNodes = computed<Node[]>(() => {
  const vals = currentStatusValues.value;
  return vals.map((v, i) => ({
    id: v.value,
    type: 'default',
    position: { x: i * (NODE_WIDTH + GAP), y: 0 },
    data: { label: v.label_zh || v.value },
  }));
});

/** VueFlow 边：每个 transition 一条边 / VueFlow edges: one per transition */
const flowEdges = computed<Edge[]>(() =>
  transitions.value.map((t, i) => ({
    id: `e-${i}-${t.from}-${t.to}`,
    source: String(t.from ?? ''),
    target: String(t.to ?? ''),
    label: (t.label_zh as string) || (t.action as string) || '',
  })),
);
</script>

<template>
  <div class="flex flex-col gap-4">
    <Form layout="vertical">
      <Form.Item :label="$t('admin.system.codegen.enum.workflowStatusField')">
        <Select
          :value="statusField"
          :options="statusFieldOptions"
          :placeholder="$t('admin.system.codegen.enum.selectStatusField')"
          allow-clear
          class="w-full"
          @change="(v: string) => updateWorkflow({ status_field: v || undefined })"
        />
      </Form.Item>
    </Form>

    <template v-if="statusField">
      <div class="flex items-center justify-between">
        <h5 class="text-sm font-medium">{{ $t('admin.system.codegen.enum.transitions') }}</h5>
        <Button
          size="small"
          type="dashed"
          :disabled="currentStatusValues.length === 0"
          @click="addTransition"
        >
          {{ $t('admin.system.codegen.enum.addTransition') }}
        </Button>
      </div>
      <div class="flex flex-col gap-2">
        <div
          v-for="(t, idx) in transitions"
          :key="`t-${idx}-${t.from}-${t.to}`"
          class="flex flex-wrap items-center gap-2 rounded border border-border p-2"
        >
          <Select
            :value="t.from"
            :options="statusSelectOptions"
            class="w-24"
            size="small"
            :placeholder="$t('admin.system.codegen.enum.from')"
            @change="(v: string) => updateTransition(idx, { from: v })"
          />
          <span class="text-muted-foreground">→</span>
          <Select
            :value="t.to"
            :options="statusSelectOptions"
            class="w-24"
            size="small"
            :placeholder="$t('admin.system.codegen.enum.to')"
            @change="(v: string) => updateTransition(idx, { to: v })"
          />
          <Input
            :value="t.action"
            class="w-24"
            size="small"
            :placeholder="$t('admin.system.codegen.enum.action')"
            @update:value="(v: string) => updateTransition(idx, { action: v })"
          />
          <Input
            :value="t.label_zh"
            class="w-20"
            size="small"
            :placeholder="$t('admin.system.codegen.enum.label')"
            @update:value="(v: string) => updateTransition(idx, { label_zh: v })"
          />
          <Switch
            :checked="!!t.requires_comment"
            size="small"
            @change="(v: boolean) => updateTransition(idx, { requires_comment: v })"
          />
          <span class="text-muted-foreground text-xs">{{ $t('admin.system.codegen.enum.requiresComment') }}</span>
          <Button
            danger
            size="small"
            type="text"
            @click="removeTransition(idx)"
          >
            ×
          </Button>
        </div>
      </div>

      <!-- 颜色映射（在 enum_values 中已有 color，这里仅展示） -->
      <div
        v-if="currentStatusValues.length > 0"
        class="mt-3 rounded border border-border p-3"
      >
        <h5 class="mb-2 text-sm font-medium">{{ $t('admin.system.codegen.enum.colorMapping') }}</h5>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="v in currentStatusValues"
            :key="v.value"
            class="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs"
            :class="{
              'bg-muted': v.color === 'default',
              'bg-green-100 text-green-800': v.color === 'success',
              'bg-yellow-100 text-yellow-800': v.color === 'warning',
              'bg-red-100 text-red-800': v.color === 'error',
              'bg-blue-100 text-blue-800': v.color === 'processing',
            }"
          >
            {{ v.label_zh || v.value }} ({{ v.color }})
          </span>
        </div>
      </div>

      <!-- VueFlow 流程图预览 / VueFlow flow diagram preview -->
      <div
        v-if="flowNodes.length > 0"
        class="mt-3"
      >
        <h5 class="mb-2 text-sm font-medium">{{ $t('admin.system.codegen.enum.workflowDiagram') }}</h5>
        <div class="h-48 w-full min-w-0 rounded border border-border">
          <Suspense>
            <VueFlow
              :nodes="flowNodes"
              :edges="flowEdges"
              :nodes-draggable="false"
              :nodes-connectable="false"
              :elements-selectable="false"
              :min-zoom="0.2"
              :max-zoom="2"
              fit-view-on-init
              class="rounded"
            >
              <Background color="#94a3b8" :gap="12" />
            </VueFlow>
            <template #fallback>
              <div class="text-muted-foreground flex h-full items-center justify-center text-sm">
                {{ $t('common.loading') }}
              </div>
            </template>
          </Suspense>
        </div>
      </div>
    </template>

    <div
      v-else-if="enumFields.length === 0"
      class="text-muted-foreground rounded border border-dashed border-border py-4 text-center text-sm"
    >
      {{ $t('admin.system.codegen.enum.noEnumFields') }}
    </div>
  </div>
</template>
