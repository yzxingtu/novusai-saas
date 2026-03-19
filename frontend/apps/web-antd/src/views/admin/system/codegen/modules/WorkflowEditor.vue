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
const GAP = 80;

const store = useCodegenBuilderStore();

type WorkflowColor = 'default' | 'error' | 'processing' | 'success' | 'warning';

interface WorkflowStatusValue {
  color?: WorkflowColor;
  label_zh?: string;
  value: string;
}

interface WorkflowTransition {
  action: string;
  from: string;
  label_zh: string;
  permission: string;
  requires_comment: boolean;
  to: string;
}

interface WorkflowConfig {
  status_field?: string;
  transitions?: WorkflowTransition[];
}

function normalizeTransition(
  transition?: Partial<WorkflowTransition>,
): WorkflowTransition {
  return {
    action: transition?.action ?? '',
    from: transition?.from ?? '',
    label_zh: transition?.label_zh ?? '',
    permission: transition?.permission ?? '',
    requires_comment: Boolean(transition?.requires_comment),
    to: transition?.to ?? '',
  };
}

const workflow = computed<WorkflowConfig>(
  () => (store.configJson.workflow as WorkflowConfig) || {},
);

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
  const m = new Map<string, WorkflowStatusValue[]>();
  for (const f of enumFields.value) {
    const vals = (f.enum_values as Array<Record<string, unknown>>) || [];
    m.set(
      f.name as string,
      vals.map((v) => ({
        value: String(v.value ?? v),
        label_zh: v.label_zh as string,
        color: ((v.color as WorkflowColor | undefined) || 'default') as WorkflowColor,
      })),
    );
  }
  return m;
});

const transitions = computed<WorkflowTransition[]>(() =>
  Array.isArray(workflow.value.transitions)
    ? workflow.value.transitions.map((transition) => normalizeTransition(transition))
    : [],
);

const statusField = computed(() => (workflow.value.status_field as string) || '');

const currentStatusValues = computed(() => {
  if (!statusField.value) return [];
  return statusValuesMap.value.get(statusField.value) || [];
});

const statusSelectOptions = computed(() =>
  currentStatusValues.value.map((v) => ({ label: v.label_zh || v.value, value: v.value })),
);

function updateWorkflow(patch: Partial<WorkflowConfig>) {
  store.updateConfig({ workflow: { ...workflow.value, ...patch } });
}

function addTransition() {
  const vals = currentStatusValues.value;
  if (!vals.length) return;
  const from = vals[0]?.value ?? '';
  const to = vals[1]?.value ?? vals[0]?.value ?? '';
  const list = [...transitions.value];
  const newT = { from, to, action: '', permission: '', requires_comment: false, label_zh: '' };
  const isDup = list.some(
    (t) => String(t.from ?? '') === from && String(t.to ?? '') === to && String((t.action as string) ?? '').trim() === '',
  );
  if (isDup) return;
  list.push(newT);
  updateWorkflow({ transitions: list });
}

function removeTransition(index: number) {
  const list = transitions.value.filter((_, i) => i !== index);
  updateWorkflow({ transitions: list });
}

function updateTransition(index: number, patch: Partial<WorkflowTransition>) {
  const list = transitions.value;
  if (index < 0 || index >= list.length) return;
  const next = [...list];
  const current = next[index];
  if (!current) return;
  const merged = normalizeTransition({ ...current, ...patch });
  const from = merged.from;
  const to = merged.to;
  const action = merged.action.trim();
  const isDup = next.some(
    (transition, i) =>
      i !== index &&
      transition.from === from &&
      transition.to === to &&
      transition.action.trim() === action,
  );
  if (isDup) return;
  next[index] = merged;
  updateWorkflow({ transitions: next });
}

function onStatusFieldChange(value: unknown) {
  updateWorkflow({
    status_field: typeof value === 'string' && value ? value : undefined,
  });
}

function onTransitionSelectChange(
  index: number,
  field: 'from' | 'to',
  value: unknown,
) {
  if (field === 'from') {
    updateTransition(index, { from: typeof value === 'string' ? value : '' });
    return;
  }
  updateTransition(index, { to: typeof value === 'string' ? value : '' });
}

function onRequiresCommentChange(index: number, value: unknown) {
  updateTransition(index, { requires_comment: Boolean(value) });
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
          @change="onStatusFieldChange"
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
            @change="(value) => onTransitionSelectChange(idx, 'from', value)"
          />
          <span class="text-muted-foreground">→</span>
          <Select
            :value="t.to"
            :options="statusSelectOptions"
            class="w-24"
            size="small"
            :placeholder="$t('admin.system.codegen.enum.to')"
            @change="(value) => onTransitionSelectChange(idx, 'to', value)"
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
            @change="(value) => onRequiresCommentChange(idx, value)"
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
