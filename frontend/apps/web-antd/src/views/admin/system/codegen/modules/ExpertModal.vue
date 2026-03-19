<script lang="ts" setup>
/**
 * 专家模式弹窗 / Expert Modal
 *
 * 3 Tab 分区：模型与数据、界面与功能、高级特性
 * 3-Tab layout: Model & Data, UI & Features, Advanced Features
 */
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

type BuilderField = Record<string, unknown>;

interface TreeConfig {
  enabled?: boolean;
  max_depth?: number;
  parent_field?: string;
}

interface ModelConfig extends Record<string, unknown> {
  __delete_deps__?: string[];
  base_class?: string;
  data_permission?: boolean;
  soft_delete?: boolean;
  table_name?: string;
  tree?: TreeConfig;
}

interface EndpointFrontend extends Record<string, unknown> {
  default_sort?: string;
  drag_sort?: boolean;
  export?: boolean;
  form_columns?: number;
  mode?: 'card' | 'table';
  operation_options?: string[];
  recycle_bin?: boolean;
}

interface EndpointMenuConfig extends Record<string, unknown> {
  icon?: string;
  title?: string;
}

interface EndpointPermissionConfig extends Record<string, unknown> {
  menu?: EndpointMenuConfig;
}

interface EndpointConfig extends Record<string, unknown> {
  data_mode?: string;
  frontend?: EndpointFrontend;
  permission?: EndpointPermissionConfig;
  route_prefix?: string;
  scope?: string;
}

interface BatchConfig extends Record<string, unknown> {
  delete?: boolean;
}

interface CloneConfig extends Record<string, unknown> {
  enabled?: boolean;
  exclude_fields?: string[];
}

interface DetailConfig extends Record<string, unknown> {
  enabled?: boolean;
  mode?: 'drawer' | 'page';
  name_field?: string;
}

function asBoolean(value: unknown): boolean {
  return Boolean(value);
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function asNumberOrUndefined(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : [];
}

const modalOpen = computed<boolean>({
  get: () => props.open,
  set: (v) => emit('update:open', v),
});

const model = computed<ModelConfig>(
  () => (store.configJson.model as ModelConfig) || {},
);
const treeConfig = computed<TreeConfig>(
  () => (model.value.tree as TreeConfig) || {},
);
const endpoints = computed<EndpointConfig[]>(
  () => (store.configJson.endpoints as EndpointConfig[]) || [],
);

const activeEndpointIdx = ref(0);
const hasDualScope = computed(() => endpoints.value.length > 1);

const currentEndpoint = computed(() =>
  endpoints.value[activeEndpointIdx.value] || ({} as EndpointConfig),
);
const frontend = computed<EndpointFrontend>(
  () => (currentEndpoint.value.frontend as EndpointFrontend) || {},
);
const permission = computed<EndpointPermissionConfig>(
  () => (currentEndpoint.value.permission as EndpointPermissionConfig) || {},
);
const menu = computed<EndpointMenuConfig>(
  () => (permission.value.menu as EndpointMenuConfig) || {},
);
const batch = computed<BatchConfig>(
  () => (store.configJson.batch as BatchConfig) || {},
);
const clone = computed<CloneConfig>(
  () => (store.configJson.clone as CloneConfig) || {},
);
const detail = computed<DetailConfig>(
  () => (store.configJson.detail as DetailConfig) || {},
);
const fields = computed<BuilderField[]>(
  () => (store.configJson.fields as BuilderField[]) || [],
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
    .filter(
      (f) =>
        f.type !== 'divider' &&
        f.type !== '__divider__' &&
        !f.divider &&
        asString(f.name).trim(),
    )
    .map((f) => ({ label: asString(f.name).trim(), value: asString(f.name).trim() })),
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
    parentResourceOptions.value = arr.map((item) => ({ label: item, value: item }));
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

function updateModel(patch: Partial<ModelConfig>) {
  store.updateConfig({ model: { ...model.value, ...patch } });
}

function updateTree(patch: Partial<TreeConfig>) {
  updateModel({ tree: { ...treeConfig.value, ...patch } });
}

function setActiveEndpointIdx(v: number) {
  activeEndpointIdx.value = v;
}

function updateEndpoints(patch: Partial<EndpointConfig>, idx?: number) {
  const i = idx ?? activeEndpointIdx.value;
  const list = [...endpoints.value];
  if (list.length <= i) {
    while (list.length <= i) list.push({});
  }
  list[i] = { ...(list[i] || {}), ...patch };
  store.updateConfig({ endpoints: list });
}

/** 更新当前 endpoint 的 frontend；mode 变更时联动所有 endpoint */
function updateFrontend(patch: Partial<EndpointFrontend>) {
  const list = [...endpoints.value];
  if (list.length === 0) return;
  const modePatch = patch.mode !== undefined;
  if (modePatch && list.length > 1) {
    const next = list.map((ep) => ({
      ...ep,
        frontend: { ...((ep.frontend as EndpointFrontend) || {}), ...patch },
    }));
    store.updateConfig({ endpoints: next });
  } else {
    const i = activeEndpointIdx.value;
    const current = list[i];
    if (!current) return;
    list[i] = {
      ...current,
      frontend: { ...frontend.value, ...patch },
    };
    store.updateConfig({ endpoints: list });
  }
}

function updatePermission(patch: Partial<EndpointPermissionConfig>) {
  const list = [...endpoints.value];
  const i = activeEndpointIdx.value;
  const current = list[i];
  if (current) {
    const perm = (current.permission as EndpointPermissionConfig) || {};
    list[i] = {
      ...current,
      permission: { ...perm, ...patch },
    };
    store.updateConfig({ endpoints: list });
  }
}

function updateMenu(patch: Partial<EndpointMenuConfig>) {
  updatePermission({ menu: { ...menu.value, ...patch } });
}

/** 更新 detail.enabled 并同步 operation_options */
function updateDetailEnabled(enabled: boolean) {
  store.updateConfig({ detail: { ...detail.value, enabled } });
  const list = [...endpoints.value];
  for (let i = 0; i < list.length; i++) {
    const ep = list[i];
    if (!ep) continue;
    const fe = (ep.frontend as Record<string, unknown>) || {};
    const opts = (fe.operation_options as string[]) || ['edit', 'delete'];
    const hasDetail = opts.includes('detail');
    if (enabled && !hasDetail) {
      list[i] = {
        ...ep,
        frontend: { ...fe, operation_options: [...opts, 'detail'] },
      };
    } else if (!enabled && hasDetail) {
      list[i] = {
        ...ep,
        frontend: { ...fe, operation_options: opts.filter((x) => x !== 'detail') },
      };
    }
  }
  if (list.some((ep, i) => ep !== endpoints.value[i])) {
    store.updateConfig({ endpoints: list });
  }
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
        @change="(value) => setActiveEndpointIdx(asNumber(value))"
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
              @change="(value) => updateModel({ base_class: asString(value) })"
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
                @update:checked="(value) => updateModel({ soft_delete: asBoolean(value) })"
              />
              <span>{{ $t('admin.system.codegen.model.softDelete') }}</span>
            </div>
            <div class="flex items-center gap-2">
              <Switch
                :checked="!!model.data_permission"
                @update:checked="(value) => updateModel({ data_permission: asBoolean(value) })"
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
              @change="(value) => updateEndpoints({ data_mode: asString(value) })"
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
                @update:checked="(value) => updateFrontend({ recycle_bin: asBoolean(value) })"
              />
              <span>{{ $t('admin.system.codegen.expert.recycleBin') }}</span>
            </div>
            <div class="flex items-center gap-2">
              <Switch
                :checked="!!frontend.export"
                @update:checked="(value) => updateFrontend({ export: asBoolean(value) })"
              />
              <span>{{ $t('admin.system.codegen.expert.export') }}</span>
            </div>
            <div class="flex items-center gap-2">
              <Switch
                :checked="!!batch?.delete"
                @update:checked="(value) => store.updateConfig({ batch: { ...(batch || {}), delete: asBoolean(value) } })"
              />
              <span>{{ $t('admin.system.codegen.expert.batchDelete') }}</span>
            </div>
            <div class="flex items-center gap-2">
              <Switch
                :checked="frontend.drag_sort"
                @update:checked="(value) => updateFrontend({ drag_sort: asBoolean(value) })"
              />
              <span>{{ $t('admin.system.codegen.frontend.dragSort') }}</span>
            </div>
            <div class="flex items-center gap-2">
              <Switch
                :checked="clone.enabled"
                @update:checked="(value) => updateConfig({ clone: { ...clone, enabled: asBoolean(value) } })"
              />
              <span>{{ $t('admin.system.codegen.advanced.cloneEnabled') }}</span>
            </div>
            <div class="flex items-center gap-2">
              <Switch
                :checked="frontend.mode === 'card'"
                @update:checked="(value) => updateFrontend({ mode: asBoolean(value) ? 'card' : 'table' })"
              />
              <span>{{ $t('admin.system.codegen.advanced.cardMode') }}</span>
            </div>
          </div>
          <Form.Item :label="$t('admin.system.codegen.expert.formColumns')">
            <Radio.Group
              :value="frontend.form_columns ?? 1"
              :options="formColumnsOptions"
              @update:value="(value) => updateFrontend({ form_columns: asNumber(value, 1) })"
            />
          </Form.Item>
          <Form.Item v-if="clone.enabled" :label="$t('admin.system.codegen.advanced.cloneExcludeFields')">
            <Select
              :value="clone.exclude_fields ?? []"
              :options="fieldOptions"
              mode="multiple"
              allow-clear
              class="w-full"
              @change="(value) => updateConfig({ clone: { ...clone, exclude_fields: asStringArray(value) } })"
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
              @change="(value) => {
                const fieldValue = asString(value);
                const order = parseDefaultSortOrder(frontend.default_sort as string);
                updateFrontend({ default_sort: fieldValue ? (order === 'desc' ? `-${fieldValue}` : fieldValue) : undefined });
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
            {{ $t('admin.system.codegen.expert.desc.detail') }}
          </p>
          <div class="flex items-center gap-2">
            <Switch
              :checked="!!detail.enabled"
              @update:checked="(value) => updateDetailEnabled(asBoolean(value))"
            />
            <span>{{ $t('admin.system.codegen.frontend.detailEnabled') }}</span>
          </div>
          <template v-if="detail.enabled">
            <Form.Item :label="$t('admin.system.codegen.detail.mode')">
              <Radio.Group
                :value="detail.mode || 'drawer'"
                :options="[
                  { label: $t('admin.system.codegen.detail.modeDrawer'), value: 'drawer' },
                  { label: $t('admin.system.codegen.detail.modePage'), value: 'page' },
                ]"
                @update:value="(value) => updateConfig({ detail: { ...detail, mode: asString(value) } })"
              />
            </Form.Item>
            <Form.Item :label="$t('admin.system.codegen.detail.nameField')">
              <Select
                :value="detail.name_field"
                :options="fieldOptions"
                allow-clear
                class="w-full"
                :placeholder="$t('admin.system.codegen.detail.nameFieldPlaceholder')"
                @change="(value) => updateConfig({ detail: { ...detail, name_field: asString(value) || undefined } })"
              />
            </Form.Item>
          </template>
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
              @update:checked="(value) => updateTree({ enabled: asBoolean(value) })"
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
                @update:value="(value) => updateTree({ max_depth: asNumberOrUndefined(value) })"
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
