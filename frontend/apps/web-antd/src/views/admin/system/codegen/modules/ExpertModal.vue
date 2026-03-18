<script lang="ts" setup>
/**
 * 专家模式弹窗 / Expert Modal
 *
 * 3 Tab 分区：模型与数据、界面与功能、高级特性
 * 3-Tab layout: Model & Data, UI & Features, Advanced Features
 */
import type { Recordable } from '@vben/types';

import { computed, ref, watch } from 'vue';

import {
  Form,
  Input,
  InputNumber,
  Modal,
  Radio,
  Segmented,
  Select,
  Switch,
  Tabs,
} from 'ant-design-vue';

import { getCodegenParentResourcesApi } from '#/api/admin/codegen';
import { IconPicker } from '#/components/business/icon-picker';
import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';

import CompositeUniqueEditor from './CompositeUniqueEditor.vue';
import CustomActionsEditor from './CustomActionsEditor.vue';
import DetailGroupEditor from './DetailGroupEditor.vue';
import RelationsEditor from './RelationsEditor.vue';
import WorkflowEditor from './WorkflowEditor.vue';

defineOptions({ name: 'ExpertModal' });

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ 'update:open': [boolean] }>();

const store = useCodegenBuilderStore();

const modalOpen = computed({
  get: () => props.open,
  set: (v) => emit('update:open', v),
});

const model = computed(
  () => (store.configJson.model as Record<string, unknown>) || {},
);
const treeConfig = computed(
  () => (model.value.tree as Record<string, unknown>) || {},
);
const endpoints = computed(
  () => (store.configJson.endpoints as Array<Record<string, unknown>>) || [],
);

const activeEndpointIdx = ref(0);
const hasDualScope = computed(() => endpoints.value.length > 1);

const currentEndpoint = computed(() =>
  endpoints.value[activeEndpointIdx.value] || {},
);
const firstEndpoint = computed(() => endpoints.value[0] || {});
const frontend = computed(
  () => (currentEndpoint.value?.frontend as Record<string, unknown>) || {},
);
const permission = computed(
  () =>
    (currentEndpoint.value?.permission as Record<string, unknown>) || {},
);
const menu = computed(
  () => (permission.value?.menu as Record<string, unknown>) || {},
);
const batch = computed(
  () => (currentEndpoint.value?.batch as Record<string, unknown>) || {},
);
const clone = computed(
  () => (store.configJson.clone as Record<string, unknown>) || {},
);
const detail = computed(
  () => (store.configJson.detail as Record<string, unknown>) || {},
);
const workflow = computed(
  () => (store.configJson.workflow as Record<string, unknown>) || {},
);
const actions = computed(
  () => (store.configJson.actions as Array<Record<string, unknown>>) || [],
);
const fields = computed(
  () => (store.configJson.fields as Array<Record<string, unknown>>) || [],
);
const deleteDeps = computed({
  get: () => (model.value.__delete_deps__ as string[]) || [],
  set: (v) =>
    store.updateConfig({
      model: { ...model.value, __delete_deps__: v },
    }),
});

const fieldOptions = computed(() =>
  fields.value
    .filter((f) => (f.type as string) !== 'divider' && f.type !== '__divider__' && !f.divider && (f.name || '').toString().trim())
    .map((f) => ({ label: ((f.name as string) || '').trim(), value: (f.name as string)?.trim() || '' })),
);

const parentResourceOptions = ref<Array<{ label: string; value: string }>>([]);

const activeTab = ref('model');

const dataModeOptions = computed(() => [
  {
    label: $t('admin.system.codegen.enum.independent'),
    value: 'independent',
  },
  {
    label: $t('admin.system.codegen.enum.crossTenant'),
    value: 'cross_tenant',
  },
]);

const formColumnsOptions = [
  { label: '1', value: 1 },
  { label: '2', value: 2 },
];

const baseClassOptions = computed(() => [
  { label: $t('admin.system.codegen.model.baseModel'), value: 'BaseModel' },
  { label: $t('admin.system.codegen.model.tenantModel'), value: 'TenantModel' },
]);

const sortOrderOptions = computed(() => [
  { label: $t('admin.system.codegen.advanced.sortOrderAsc'), value: 'asc' },
  { label: $t('admin.system.codegen.advanced.sortOrderDesc'), value: 'desc' },
]);

async function loadParentResources() {
  try {
    const arr = await getCodegenParentResourcesApi();
    parentResourceOptions.value = (arr || []).map((item) =>
      typeof item === 'string' ? { label: item, value: item } : item,
    );
  } catch {
    parentResourceOptions.value = [];
  }
}

function updateConfig(patch: Record<string, unknown>) {
  store.updateConfig(patch);
}

/** 解析 default_sort 为字段名（支持 -field 前缀格式和 field desc 格式） */
function parseDefaultSortField(s: string | undefined): string {
  if (!s || !s.trim()) return '';
  const trimmed = s.trim();
  if (trimmed.startsWith('-')) return trimmed.slice(1).trim();
  const parts = trimmed.split(/\s+/);
  return parts[0] || '';
}

/** 解析 default_sort 为排序方向（支持 -field 前缀格式和 field desc 格式） */
function parseDefaultSortOrder(s: string | undefined): 'asc' | 'desc' {
  if (!s || !s.trim()) return 'desc';
  const trimmed = s.trim();
  if (trimmed.startsWith('-')) return 'desc';
  const parts = trimmed.split(/\s+/);
  const order = (parts[1] || 'desc').toLowerCase();
  return order === 'asc' ? 'asc' : 'desc';
}

function updateModel(patch: Record<string, unknown>) {
  store.updateConfig({ model: { ...model.value, ...patch } });
}

function updateTree(patch: Record<string, unknown>) {
  updateModel({ tree: { ...treeConfig.value, ...patch } });
}

function setActiveEndpointIdx(v: number) {
  activeEndpointIdx.value = v;
}

function updateEndpoints(patch: Record<string, unknown>, idx?: number) {
  const i = idx ?? activeEndpointIdx.value;
  const list = [...endpoints.value];
  if (list.length <= i) {
    while (list.length <= i) list.push({});
  }
  list[i] = { ...list[i], ...patch };
  store.updateConfig({ endpoints: list });
}

/** 更新当前 endpoint 的 frontend；mode 变更时联动所有 endpoint */
function updateFrontend(patch: Record<string, unknown>) {
  const list = [...endpoints.value];
  if (list.length === 0) return;
  const modePatch = patch.mode !== undefined;
  if (modePatch && list.length > 1) {
    const next = list.map((ep) => ({
      ...ep,
      frontend: { ...((ep.frontend as Record<string, unknown>) || {}), ...patch },
    }));
    store.updateConfig({ endpoints: next });
  } else {
    const i = activeEndpointIdx.value;
    list[i] = {
      ...list[i],
      frontend: { ...frontend.value, ...patch },
    };
    store.updateConfig({ endpoints: list });
  }
}

function updatePermission(patch: Record<string, unknown>) {
  const list = [...endpoints.value];
  const i = activeEndpointIdx.value;
  if (list.length > i) {
    const perm = (list[i]?.permission as Record<string, unknown>) || {};
    list[i] = {
      ...list[i],
      permission: { ...perm, ...patch },
    };
    store.updateConfig({ endpoints: list });
  }
}

function updateMenu(patch: Record<string, unknown>) {
  updatePermission({ menu: { ...menu.value, ...patch } });
}

const modalWidth = computed(() =>
  typeof window !== 'undefined' ? Math.min(960, window.innerWidth * 0.9) : 900,
);

watch(
  () => props.open,
  (v) => { if (v) loadParentResources(); },
  { immediate: false },
);
</script>

<template>
  <Modal
    v-model:open="modalOpen"
    :title="$t('admin.system.codegen.advanced.title')"
    :width="modalWidth"
    destroy-on-close
    :footer="null"
  >
    <p class="text-muted-foreground mb-4 text-sm">
      {{ $t('admin.system.codegen.expert.intro') }}
    </p>
    <Form.Item v-if="hasDualScope" :label="$t('admin.system.codegen.endpoint.scope')" class="mb-4">
      <Segmented
        :value="activeEndpointIdx"
        :options="endpoints.map((ep, i) => ({ label: $t(`admin.system.codegen.enum.${ep.scope || 'admin'}`), value: i }))"
        @change="(v) => setActiveEndpointIdx(Number(v))"
      />
    </Form.Item>
    <Tabs v-model:active-key="activeTab" class="max-h-[70vh] overflow-y-auto">
      <!-- Tab 1: 模型与数据 -->
      <Tabs.TabPane :tab="$t('admin.system.codegen.expert.tabModel')" key="model">
        <Form layout="vertical" class="space-y-4">
          <p class="text-muted-foreground text-xs">
            {{ $t('admin.system.codegen.expert.desc.model') }}
          </p>
          <Form.Item :label="$t('admin.system.codegen.model.baseClass')">
            <Select
              :value="model.base_class"
              :options="baseClassOptions"
              class="w-full"
              @change="(v: string) => updateModel({ base_class: v })"
            />
          </Form.Item>
          <Form.Item :label="$t('admin.system.codegen.model.tableName')">
            <Input
              :value="model.table_name"
              :placeholder="$t('admin.system.codegen.model.placeholder.tableName')"
              @update:value="(v: string) => updateModel({ table_name: v })"
            />
          </Form.Item>
          <div class="flex flex-wrap gap-4">
            <div class="flex items-center gap-2">
              <Switch
                :checked="model.soft_delete !== false"
                @update:checked="(v: boolean) => updateModel({ soft_delete: v })"
              />
              <span>{{ $t('admin.system.codegen.model.softDelete') }}</span>
            </div>
            <div class="flex items-center gap-2">
              <Switch
                :checked="!!model.data_permission"
                @update:checked="(v: boolean) => updateModel({ data_permission: v })"
              />
              <span>{{ $t('admin.system.codegen.model.dataPermission') }}</span>
            </div>
          </div>

          <p class="text-muted-foreground pt-2 text-xs">
            {{ $t('admin.system.codegen.expert.desc.endpoint') }}
          </p>
          <Form.Item :label="$t('admin.system.codegen.endpoint.routePrefix')">
            <Input
              :value="currentEndpoint.route_prefix"
              :placeholder="$t('admin.system.codegen.endpoint.routePrefixPlaceholder')"
              @update:value="(v: string) => updateEndpoints({ route_prefix: v })"
            />
          </Form.Item>
          <Form.Item :label="$t('admin.system.codegen.endpoint.dataMode')">
            <Select
              :value="currentEndpoint.data_mode"
              :options="dataModeOptions"
              class="w-full"
              @change="(v: string) => updateEndpoints({ data_mode: v })"
            />
          </Form.Item>

          <p class="text-muted-foreground pt-2 text-xs">
            {{ $t('admin.system.codegen.expert.desc.deleteDeps') }}
          </p>
          <Form.Item>
            <Select
              v-model:value="deleteDeps"
              :options="parentResourceOptions"
              mode="multiple"
              allow-clear
              class="w-full"
              :placeholder="$t('admin.system.codegen.model.deleteDepsPlaceholder')"
            />
          </Form.Item>
        </Form>
      </Tabs.TabPane>

      <!-- Tab 2: 界面与功能 -->
      <Tabs.TabPane :tab="$t('admin.system.codegen.expert.tabUi')" key="ui">
        <Form layout="vertical" class="space-y-4">
          <p class="text-muted-foreground text-xs">
            {{ $t('admin.system.codegen.expert.desc.features') }}
          </p>
          <div class="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
            <div class="flex items-center gap-2">
              <Switch
                :checked="!!frontend.recycle_bin"
                @update:checked="(v: boolean) => updateFrontend({ recycle_bin: v })"
              />
              <span>{{ $t('admin.system.codegen.expert.recycleBin') }}</span>
            </div>
            <div class="flex items-center gap-2">
              <Switch
                :checked="!!frontend.export"
                @update:checked="(v: boolean) => updateFrontend({ export: v })"
              />
              <span>{{ $t('admin.system.codegen.expert.export') }}</span>
            </div>
            <div class="flex items-center gap-2">
              <Switch
                :checked="!!batch?.delete"
                @update:checked="(v: boolean) => updateEndpoints({ batch: { ...(batch || {}), delete: v } })"
              />
              <span>{{ $t('admin.system.codegen.expert.batchDelete') }}</span>
            </div>
            <div class="flex items-center gap-2">
              <Switch
                :checked="frontend.drag_sort"
                @update:checked="(v: boolean) => updateFrontend({ drag_sort: v })"
              />
              <span>{{ $t('admin.system.codegen.frontend.dragSort') }}</span>
            </div>
            <div class="flex items-center gap-2">
              <Switch
                :checked="clone.enabled"
                @update:checked="(v: boolean) => updateConfig({ clone: { ...clone, enabled: v } })"
              />
              <span>{{ $t('admin.system.codegen.advanced.cloneEnabled') }}</span>
            </div>
            <div class="flex items-center gap-2">
              <Switch
                :checked="frontend.mode === 'card'"
                @update:checked="(v: boolean) => updateFrontend({ mode: v ? 'card' : 'table' })"
              />
              <span>{{ $t('admin.system.codegen.advanced.cardMode') }}</span>
            </div>
          </div>
          <Form.Item :label="$t('admin.system.codegen.expert.formColumns')">
            <Radio.Group
              :value="frontend.form_columns ?? 1"
              :options="formColumnsOptions"
              @update:value="(v: number) => updateFrontend({ form_columns: v })"
            />
          </Form.Item>
          <Form.Item v-if="clone.enabled" :label="$t('admin.system.codegen.advanced.cloneExcludeFields')">
            <Select
              :value="clone.exclude_fields ?? []"
              :options="fieldOptions"
              mode="multiple"
              allow-clear
              class="w-full"
              @change="(v: string[]) => updateConfig({ clone: { ...clone, exclude_fields: v } })"
            />
          </Form.Item>

          <p class="text-muted-foreground pt-2 text-xs">
            {{ $t('admin.system.codegen.expert.desc.defaultSort') }}
          </p>
          <Form.Item :label="$t('admin.system.codegen.advanced.defaultSortField')">
            <Select
              :value="parseDefaultSortField(frontend.default_sort as string)"
              :options="fieldOptions"
              allow-clear
              :placeholder="$t('admin.system.codegen.advanced.defaultSortFieldPlaceholder')"
              class="w-full"
              @change="(v: string) => {
                const order = parseDefaultSortOrder(frontend.default_sort as string);
                updateFrontend({ default_sort: v ? (order === 'desc' ? `-${v}` : v) : undefined });
              }"
            />
          </Form.Item>
          <Form.Item :label="$t('admin.system.codegen.advanced.defaultSortOrder')">
            <Radio.Group
              :value="parseDefaultSortOrder(frontend.default_sort as string)"
              :options="sortOrderOptions"
              @update:value="(v: string) => {
                const field = parseDefaultSortField(frontend.default_sort as string) || 'id';
                updateFrontend({ default_sort: v === 'desc' ? `-${field}` : field });
              }"
            />
          </Form.Item>

          <p class="text-muted-foreground pt-2 text-xs">
            {{ $t('admin.system.codegen.expert.desc.menu') }}
          </p>
          <Form.Item :label="$t('admin.system.codegen.endpoint.menuTitle')">
            <Input
              :value="menu.title"
              @update:value="(v: string) => updateMenu({ title: v })"
            />
          </Form.Item>
          <Form.Item :label="$t('admin.system.codegen.endpoint.menuIcon')">
            <IconPicker
              :value="menu.icon"
              @update:value="(v: string) => updateMenu({ icon: v })"
            />
          </Form.Item>

          <p class="text-muted-foreground pt-2 text-xs">
            {{ $t('admin.system.codegen.expert.desc.detailGroups') }}
          </p>
          <DetailGroupEditor />
        </Form>
      </Tabs.TabPane>

      <!-- Tab 3: 高级特性 -->
      <Tabs.TabPane :tab="$t('admin.system.codegen.expert.tabAdvanced')" key="advanced">
        <Form layout="vertical" class="space-y-4">
          <p class="text-muted-foreground text-xs">
            {{ $t('admin.system.codegen.expert.desc.tree') }}
          </p>
          <div class="flex items-center gap-2">
            <Switch
              :checked="treeConfig.enabled"
              @update:checked="(v: boolean) => updateTree({ enabled: v })"
            />
            <span>{{ $t('admin.system.codegen.advanced.treeEnabled') }}</span>
          </div>
          <template v-if="treeConfig.enabled">
            <Form.Item :label="$t('admin.system.codegen.advanced.parentField')">
              <Input
                :value="treeConfig.parent_field"
                @update:value="(v: string) => updateTree({ parent_field: v })"
              />
            </Form.Item>
            <Form.Item :label="$t('admin.system.codegen.advanced.maxDepth')">
              <InputNumber
                :value="treeConfig.max_depth"
                :min="1"
                :max="20"
                class="!w-24"
                @update:value="(v: number) => updateTree({ max_depth: v })"
              />
            </Form.Item>
          </template>

          <p class="text-muted-foreground pt-2 text-xs">
            {{ $t('admin.system.codegen.expert.desc.relations') }}
          </p>
          <RelationsEditor />

          <p class="text-muted-foreground pt-2 text-xs">
            {{ $t('admin.system.codegen.expert.desc.unique') }}
          </p>
          <CompositeUniqueEditor />

          <p class="text-muted-foreground pt-2 text-xs">
            {{ $t('admin.system.codegen.expert.desc.workflow') }}
          </p>
          <WorkflowEditor />

          <p class="text-muted-foreground pt-2 text-xs">
            {{ $t('admin.system.codegen.expert.desc.customActions') }}
          </p>
          <CustomActionsEditor />
        </Form>
      </Tabs.TabPane>
    </Tabs>
  </Modal>
</template>
