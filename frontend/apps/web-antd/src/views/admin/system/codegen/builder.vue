<script lang="ts" setup>
/**
 * 代码生成器三栏可视化构建器 / Codegen Visual Builder
 *
 * 三栏布局: 组件面板 | 字段卡片列表 | 属性面板 + 表单预览
 */
import type { CodegenVersionItem } from '#/api/admin/codegen';
import type { Recordable } from '@vben/types';

import { Page } from '@vben/common-ui';
import yaml from 'js-yaml';
import { computed, defineAsyncComponent, onMounted, onUnmounted, ref, watch } from 'vue';
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router';

import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Collapse,
  CollapsePanel,
  Dropdown,
  Input,
  List,
  Menu,
  MenuItem,
  Modal,
  Radio,
  Select,
  Tooltip,
} from 'ant-design-vue';
import { IconifyIcon } from '@vben/icons';

import {
  createCodegenConfigApi,
  downloadCodegenPreviewZipApi,
  getCodegenConfigDetailApi,
  getCodegenConfigVersionApi,
  getCodegenConfigVersionsApi,
  getCodegenOptionsApi,
  getCodegenPresetApi,
  postCodegenConfigRestoreVersionApi,
  postCodegenGenerateApi,
  postCodegenValidateApi,
  updateCodegenConfigApi,
} from '#/api/admin/codegen';
import { message } from 'ant-design-vue';
import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';
import { downloadText } from '#/utils/download';

import type { PaletteItem } from './modules/ComponentPalette.vue';
import { createFieldFromPalette, ensureFieldKeys } from './modules/field-utils';
import { inferFieldConfigForMerge, pluralize } from './modules/infer';

const ComponentPalette = defineAsyncComponent(() => import('./modules/ComponentPalette.vue'));
const FieldPropertyPanel = defineAsyncComponent(() => import('./modules/FieldPropertyPanel.vue'));
const WysiwygCenter = defineAsyncComponent(() => import('./modules/WysiwygCenter.vue'));
const CodePreviewModal = defineAsyncComponent(() => import('./modules/CodePreviewModal.vue'));
const ExpertModal = defineAsyncComponent(() => import('./modules/ExpertModal.vue'));
const DbTableImportModal = defineAsyncComponent(() => import('./modules/DbTableImportModal.vue'));

defineOptions({ name: 'AdminSystemCodegenBuilder' });

const route = useRoute();
const router = useRouter();
const store = useCodegenBuilderStore();

const wysiwygRef = ref<InstanceType<typeof WysiwygCenter> | null>(null);
const resourceInputRef = ref<HTMLElement | null>(null);

const codePreviewOpen = ref(false);
const expertModalOpen = ref(false);
const dbImportOpen = ref(false);
const isSaving = ref(false);
const isGenerating = ref(false);
const validationErrors = ref<Array<{ code: string; message: string; path: string; field: string }>>([]);
const importYamlVisible = ref(false);
const importYamlText = ref('');
const isImporting = ref(false);
const versionHistoryVisible = ref(false);
const versionList = ref<CodegenVersionItem[]>([]);
const isVersionLoading = ref(false);
const isRestoring = ref(false);
const versionPreviewVisible = ref(false);
const versionPreviewContent = ref('');
const versionPreviewNote = ref('');
const versionPreviewLoadingIds = ref<Set<number>>(new Set());
const resultModalVisible = ref(false);
const lastResult = ref<{
  success: boolean;
  files_created: string[];
  files_modified: string[];
  conflicts: Array<Record<string, string>>;
  errors: string[];
} | null>(null);

const moduleOptions = ref<Array<{ label: string; value: string }>>([]);

const configId = computed(() => {
  const id = route.params.id;
  if (id == null || id === '' || id === 'new') return null;
  const num = Number(id);
  return !isNaN(num) ? num : null;
});
const isNewMode = computed(() => !configId.value);

const resource = computed({
  get: () => (store.configJson.resource as string) || '',
  set: (v) => store.updateConfig({ resource: v }),
});
const moduleVal = computed({
  get: () => (store.configJson.module as string) || 'system',
  set: (v) => store.updateConfig({ module: v }),
});
const displayName = computed({
  get: () => (store.configJson.display_name as string) || '',
  set: (v) => store.updateConfig({ display_name: v }),
});
const displayNameEn = computed({
  get: () => (store.configJson.display_name_en as string) || '',
  set: (v) => store.updateConfig({ display_name_en: v }),
});
const resourcePlural = computed({
  get: () => (store.configJson.resource_plural as string) || '',
  set: (v) => store.updateConfig({ resource_plural: v }),
});
const model = computed(() => (store.configJson.model as Record<string, unknown>) || {});
const endpoints = computed(() => (store.configJson.endpoints as Record<string, unknown>[]) || []);
const firstEndpoint = computed(() => endpoints.value[0] || {});
const frontend = computed(() => (firstEndpoint.value?.frontend as Record<string, unknown>) || {});

const hasAdmin = computed(() => endpoints.value.some((e) => e.scope === 'admin'));
const hasTenant = computed(() => endpoints.value.some((e) => e.scope === 'tenant'));
const softDelete = computed({
  get: () => (model.value.soft_delete as boolean) ?? true,
  set: (v) => store.updateConfig({ model: { ...model.value, soft_delete: v } }),
});
const dataPermission = computed({
  get: () => (model.value.data_permission as boolean) ?? false,
  set: (v) => store.updateConfig({ model: { ...model.value, data_permission: v } }),
});
const feMode = computed({
  get: () => (frontend.value.mode as string) || 'table',
  set: (v) => {
    const list = [...endpoints.value];
    if (list.length > 0) {
      const next = list.map((ep) => ({
        ...ep,
        frontend: { ...((ep.frontend as Record<string, unknown>) || {}), mode: v },
      }));
      store.updateConfig({ endpoints: next });
    }
  },
});

/** 创建默认 endpoint / Create default endpoint for scope */
function createDefaultEndpoint(scope: 'admin' | 'tenant'): Record<string, unknown> {
  const r = (store.configJson.resource_plural as string) || (store.configJson.resource as string) || 'items';
  const plural = r.endsWith('s') ? r : `${r}s`;
  return {
    scope,
    data_mode: scope === 'admin' ? 'independent' : 'independent',
    route_prefix: `/${plural}`,
    frontend: {
      mode: 'table',
      page_size: 20,
      default_sort: '-created_at',
      recycle_bin: false,
      export: false,
      import: false,
      drag_sort: false,
    },
  };
}

function onAdminChange(checked: boolean) {
  if (checked) {
    const hasAdminEp = endpoints.value.some((e) => (e.scope as string) === 'admin');
    if (!hasAdminEp) {
      const next = [createDefaultEndpoint('admin'), ...endpoints.value];
      store.updateConfig({ endpoints: next });
      syncBaseClassFromEndpoints(next);
    }
  } else {
    const next = endpoints.value.filter((e) => (e.scope as string) !== 'admin');
    if (next.length === 0) {
      message.warning($t('admin.system.codegen.builder.atLeastOneScope'));
      return;
    }
    store.updateConfig({ endpoints: next });
    syncBaseClassFromEndpoints(next);
  }
}

function onTenantChange(checked: boolean) {
  if (checked) {
    const hasTenantEp = endpoints.value.some((e) => (e.scope as string) === 'tenant');
    if (!hasTenantEp) {
      const next = [...endpoints.value, createDefaultEndpoint('tenant')];
      store.updateConfig({ endpoints: next });
      syncBaseClassFromEndpoints(next);
    }
  } else {
    const next = endpoints.value.filter((e) => (e.scope as string) !== 'tenant');
    if (next.length === 0) {
      message.warning($t('admin.system.codegen.builder.atLeastOneScope'));
      return;
    }
    store.updateConfig({ endpoints: next });
    syncBaseClassFromEndpoints(next);
  }
}

function syncBaseClassFromEndpoints(eps: Record<string, unknown>[]) {
  const hasTenant = eps.some((e) => (e.scope as string) === 'tenant');
  const m = model.value;
  const nextClass = hasTenant ? 'TenantModel' : 'BaseModel';
  if ((m.base_class as string) !== nextClass) {
    store.updateConfig({ model: { ...m, base_class: nextClass } });
  }
}

function onResourceChange(v: string) {
  store.updateConfig({ resource: v });
  if (v && !(store.configJson.resource_plural as string)) {
    store.updateConfig({ resource_plural: pluralize(v) });
  }
  const m = (store.configJson.model as Record<string, unknown>) || {};
  if (v && !m.table_name) {
    store.updateConfig({ model: { ...m, table_name: v } });
  }
}

function onPaletteAdd(item: PaletteItem) {
  // WysiwygCenter 为异步组件，可能尚未挂载；此时直接更新 store 确保添加生效
  if (wysiwygRef.value) {
    wysiwygRef.value.addFromPalette(item);
  } else {
    const arr = (store.configJson.fields as Recordable[]) || [];
    const current = ensureFieldKeys(arr);
    const newField = createFieldFromPalette(item, current);
    const next = [...current, newField];
    store.updateConfig({ fields: next });
    store.selectedFieldKey = newField.__key as string;
  }
}

async function onSave() {
  const json = store.configJson;
  const r = (json.resource as string) || '';
  const mod = (json.module as string) || '';
  const disp = (json.display_name as string) || '';
  if (!r?.trim()) {
    message.warning($t('admin.system.codegen.validation.resource_required'));
    return;
  }
  if (!mod?.trim()) {
    message.warning($t('admin.system.codegen.validation.module_required'));
    return;
  }
  if (!disp?.trim()) {
    message.warning($t('admin.system.codegen.validation.display_name_required'));
    return;
  }
  // 保存前校验 / Validate before save
  try {
    const vResult = await postCodegenValidateApi({ config_json: json });
    if (!vResult.valid) {
      validationErrors.value = vResult.errors ?? [];
      message.warning($t('admin.system.codegen.builder.saveValidateFailed'));
      return;
    }
  } catch (e) {
    message.error($t('common.failed'));
    return;
  }
  isSaving.value = true;
  try {
    const name = (json.name as string) || (json.display_name as string) || $t('admin.system.codegen.unnamed');
    const displayNameEn = (json.display_name_en as string) || r;
    if (store.configId != null) {
      await updateCodegenConfigApi(store.configId, {
        name,
        resource: r,
        module: mod,
        display_name: disp,
        display_name_en: displayNameEn,
        config_json: json,
      });
      store.saveConfig(store.configId, json);
      validationErrors.value = [];
      message.success($t('admin.system.codegen.messages.saveSuccess'));
      return;
    }
    const res = await createCodegenConfigApi({
      name,
      resource: r,
      module: mod,
      display_name: disp,
      display_name_en: displayNameEn,
      config_json: json,
    });
    store.saveConfig(res.id, res.config_json || json);
    validationErrors.value = [];
    message.success($t('admin.system.codegen.messages.saveSuccess'));
    router.replace(`/admin/system/codegen/${res.id}/edit`);
  } catch (e) {
    console.error(e);
    message.error($t('common.failed'));
  } finally {
    isSaving.value = false;
  }
}

async function doGenerate() {
  validationErrors.value = [];
  try {
    const vResult = await postCodegenValidateApi({ config_json: store.configJson });
    if (!vResult.valid) {
      validationErrors.value = vResult.errors ?? [];
      message.warning($t('admin.system.codegen.generate.validateFirst'));
      return;
    }
    const payload =
      store.configId != null
        ? { config_id: store.configId, force: false }
        : { config_json: store.configJson, force: false };
    const result = await postCodegenGenerateApi(payload);
    lastResult.value = result;
    resultModalVisible.value = true;
    if (result.success) {
      message.success($t('admin.system.codegen.messages.generateSuccess'));
    } else if (result.errors?.length) {
      message.error(result.errors.join('; '));
    }
  } catch (e) {
    message.error(e instanceof Error ? e.message : $t('common.failed'));
  } finally {
    isGenerating.value = false;
  }
}

function closeResultModal() {
  resultModalVisible.value = false;
  lastResult.value = null;
}

async function onGenerate() {
  const r = (store.configJson.resource as string) || '';
  Modal.confirm({
    title: $t('admin.system.codegen.builder.generateConfirmTitle'),
    content: $t('admin.system.codegen.builder.generateConfirmContent', { resource: r }),
    onOk: async () => {
      isGenerating.value = true;
      await doGenerate();
    },
  });
}

function onExportYaml() {
  const json = store.configJson;
  if (!json || Object.keys(json).length === 0) {
    message.warning($t('admin.system.codegen.builder.exportEmpty'));
    return;
  }
  const content = yaml.dump(json, { indent: 2, lineWidth: -1 });
  const name = (json.resource as string) || 'codegen';
  downloadText(content, { filename: `${name}.yaml`, mimeType: 'text/x-yaml' });
  message.success($t('shared.common.exportSuccess'));
}

function onImportYaml() {
  importYamlText.value = '';
  importYamlVisible.value = true;
}

function onImportYamlFile(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    importYamlText.value = (reader.result as string) || '';
  };
  reader.onerror = () => {
    message.error($t('admin.system.codegen.builder.importFileReadError'));
  };
  reader.readAsText(file, 'utf-8');
  input.value = '';
}

async function onConfirmImportYaml() {
  const raw = importYamlText.value.trim();
  if (!raw) return;
  let parsed: Record<string, unknown>;
  try {
    parsed = yaml.load(raw) as Record<string, unknown>;
  } catch {
    message.error($t('admin.system.codegen.builder.importYamlParseError'));
    return;
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    message.error($t('admin.system.codegen.builder.importYamlParseError'));
    return;
  }
  isImporting.value = true;
  try {
    const result = await postCodegenValidateApi({ config_json: parsed });
    if (!result.valid) {
      const msgs = (result.errors ?? []).map((e) => e.message).filter(Boolean);
      message.error(msgs.join('; ') || $t('admin.system.codegen.builder.importYamlValidateError'));
      return;
    }
    store.loadConfig(null, parsed);
    validationErrors.value = [];
    importYamlVisible.value = false;
    message.success($t('admin.system.codegen.builder.importYamlSuccess'));
  } catch (e) {
    console.error(e);
    message.error($t('common.failed'));
  } finally {
    isImporting.value = false;
  }
}

async function onOpenVersionHistory() {
  const id = configId.value;
  if (!id) return;
  versionHistoryVisible.value = true;
  isVersionLoading.value = true;
  try {
    versionList.value = await getCodegenConfigVersionsApi(id);
  } catch (e) {
    console.error(e);
    message.error($t('common.failed'));
    versionHistoryVisible.value = false;
  } finally {
    isVersionLoading.value = false;
  }
}

async function onRestoreVersion(v: CodegenVersionItem) {
  const id = configId.value;
  if (!id || !v.id) return;
  Modal.confirm({
    title: $t('admin.system.codegen.builder.versionRestoreConfirm'),
    onOk: async () => {
      isRestoring.value = true;
      try {
        const restored = await postCodegenConfigRestoreVersionApi(id, v.id);
        store.loadConfig(restored.id, restored.config_json || {});
        validationErrors.value = [];
        versionHistoryVisible.value = false;
        message.success($t('admin.system.codegen.builder.versionRestoreSuccess'));
        message.info($t('admin.system.codegen.builder.versionRestoreUndoCleared'));
      } catch (e) {
        console.error(e);
        message.error($t('common.failed'));
      } finally {
        isRestoring.value = false;
      }
    },
  });
}

function formatVersionTime(iso: string | null) {
  if (!iso) return '-';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

async function onPreviewVersion(v: CodegenVersionItem) {
  const id = configId.value;
  if (!id || !v.id) return;
  versionPreviewVisible.value = true;
  versionPreviewNote.value = v.note || formatVersionTime(v.created_at) || '';
  versionPreviewLoadingIds.value = new Set([...versionPreviewLoadingIds.value, v.id]);
  versionPreviewContent.value = '';
  try {
    const res = await getCodegenConfigVersionApi(id, v.id);
    const json = res?.config_json ?? {};
    versionPreviewContent.value = yaml.dump(json, { indent: 2, lineWidth: -1 });
  } catch (e) {
    console.error(e);
    message.error($t('common.failed'));
    versionPreviewVisible.value = false;
  } finally {
    versionPreviewLoadingIds.value = new Set([...versionPreviewLoadingIds.value].filter((x) => x !== v.id));
  }
}

async function onDownloadZip() {
  try {
    await downloadCodegenPreviewZipApi(
      { config_json: store.configJson },
      { step: undefined },
    );
    message.success($t('admin.system.codegen.messages.downloadSuccess'));
  } catch (e) {
    const err = e as { response?: { data?: { detail?: { error?: string } | string } } };
    const detail = err?.response?.data?.detail;
    const msg =
      (typeof detail === 'object' && detail?.error) ||
      (typeof detail === 'string' ? detail : null) ||
      $t('admin.system.codegen.messages.downloadFail');
    message.error(msg);
  }
}

function onDbImported(patch: Record<string, unknown>) {
  const incoming = (patch.fields as Recordable[]) || [];
  const withInferred = incoming.map((f) => {
    const name = (f.name as string) || '';
    if (!name) return f;
    const inferred = inferFieldConfigForMerge(name);
    return { ...inferred, ...f, __key: f.__key || `f_${Date.now()}_${Math.random().toString(36).slice(2, 9)}` };
  });
  const mode = (patch._importMode as 'merge' | 'replace') || 'replace';
  const currentFields = (store.configJson.fields as Recordable[]) || [];
  let finalFields: Recordable[];
  if (mode === 'merge') {
    const incomingByName = new Map(withInferred.map((f) => [(f.name as string) || '', f]));
    const currentNames = new Set(currentFields.map((f) => (f.name as string) || '').filter(Boolean));
    const merged = currentFields.map((f) => {
      const n = (f.name as string) || '';
      const imp = incomingByName.get(n);
      return imp ? { ...f, ...imp } : f;
    });
    const appended = withInferred.filter((f) => !currentNames.has((f.name as string) || ''));
    finalFields = [...merged, ...appended];
  } else {
    finalFields = withInferred;
  }
  store.selectedFieldKey = null;
  const { _importMode: _m, ...rest } = patch as Record<string, unknown>;
  store.updateConfig({ ...rest, fields: finalFields });
  dbImportOpen.value = false;
}

async function loadConfigIfEdit() {
  const id = configId.value;
  if (id != null) {
    try {
      const config = await getCodegenConfigDetailApi(id);
      store.loadConfig(config.id, config.config_json || {});
    } catch (e) {
      const status = (e as { response?: { status?: number } })?.response?.status;
      if (status === 404) {
        message.error($t('admin.system.codegen.builder.configNotFound'));
      } else {
        message.error($t('common.failed'));
      }
      store.resetWizard();
      await router.replace({ name: 'AdminSystemCodegen' });
    }
    return;
  }
  const presetQuery = route.query.preset as string | undefined;
  if (presetQuery) {
    try {
      const res = await getCodegenPresetApi(presetQuery);
      const parsed = res?.parsed ?? {};
      if (parsed && typeof parsed === 'object') {
        store.loadConfig(null, parsed);
        return;
      }
    } catch {
      message.error($t('admin.system.codegen.builder.presetNotFound'));
    }
  }
  store.resetWizard();
}

const fields = computed(() => (store.configJson.fields as Recordable[]) || []);

function removeSelectedField() {
  const key = store.selectedFieldKey;
  if (!key) return;
  const next = fields.value.filter((f) => f.__key !== key);
  store.updateConfig({ fields: next });
  store.selectedFieldKey = null;
}

function selectPrevField() {
  const key = store.selectedFieldKey;
  if (!key) return;
  const idx = fields.value.findIndex((f) => f.__key === key);
  if (idx > 0) store.selectedFieldKey = fields.value[idx - 1].__key as string;
}

function selectNextField() {
  const key = store.selectedFieldKey;
  if (!key) return;
  const idx = fields.value.findIndex((f) => f.__key === key);
  if (idx >= 0 && idx < fields.value.length - 1) {
    store.selectedFieldKey = fields.value[idx + 1].__key as string;
  }
}

function handleKeydown(e: KeyboardEvent) {
  const target = e.target as HTMLElement;
  const tag = target?.tagName?.toLowerCase();
  if (tag === 'input' || tag === 'textarea' || target?.isContentEditable) return;

  if (e.ctrlKey && e.key === 'z') {
    e.preventDefault();
    e.shiftKey ? store.redo() : store.undo();
  } else if (e.ctrlKey && e.key === 'y') {
    e.preventDefault();
    store.redo();
  } else if (e.ctrlKey && e.key === 's') {
    e.preventDefault();
    onSave();
  } else if (e.key === 'Delete' && store.selectedFieldKey) {
    removeSelectedField();
  } else if (e.key === 'Escape') {
    store.selectedFieldKey = null;
  } else if (e.key === 'ArrowUp' && store.selectedFieldKey) {
    selectPrevField();
  } else if (e.key === 'ArrowDown' && store.selectedFieldKey) {
    selectNextField();
  }
}

function onBeforeUnload(e: BeforeUnloadEvent) {
  if (store.isDirty) {
    e.preventDefault();
    (e as BeforeUnloadEvent & { returnValue: string }).returnValue = '';
  }
}

onBeforeRouteLeave((_to, _from, next) => {
  if (store.isDirty) {
    Modal.confirm({
      title: $t('admin.system.codegen.toolbar.unsavedTitle'),
      content: $t('admin.system.codegen.toolbar.unsavedContent'),
      onOk: () => {
        store.isDirty = false;
        next();
      },
      onCancel: () => next(false),
    });
  } else {
    next();
  }
});

async function loadModules() {
  try {
    const opts = await getCodegenOptionsApi();
    const mods = opts?.system_modules ?? [];
    moduleOptions.value = mods.map((m: string) => ({
      label: $t(`admin.system.codegen.basic.moduleLabels.${m}`) as string,
      value: m,
    }));
  } catch {
    moduleOptions.value = [];
  }
}

onMounted(() => {
  loadConfigIfEdit();
  loadModules();
  document.addEventListener('keydown', handleKeydown);
  window.addEventListener('beforeunload', onBeforeUnload);
  if (isNewMode.value) {
    setTimeout(() => resourceInputRef.value?.focus(), 100);
  }
});

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown);
  window.removeEventListener('beforeunload', onBeforeUnload);
});

watch(
  () => route.params.id,
  () => loadConfigIfEdit(),
);
</script>

<template>
  <Page
    auto-content-height
    content-class="flex flex-col"
  >
    <Alert
      v-if="!isNewMode"
      :message="$t('admin.system.codegen.builder.editMode')"
      type="info"
      show-icon
      class="mb-3"
    />

    <!-- 顶部工具栏 -->
    <div class="flex shrink-0 items-center gap-3 border-b border-border px-4 py-2">
      <Button type="text" size="small" @click="router.push('/admin/system/codegen')">
        <IconifyIcon icon="lucide:arrow-left" class="size-4" />
      </Button>
      <Input
        ref="resourceInputRef"
        :model-value="resource"
        :placeholder="$t('admin.system.codegen.basic.resource')"
        class="!w-40"
        @update:model-value="onResourceChange"
      />
      <Select
        v-model:value="moduleVal"
        :options="moduleOptions"
        class="!w-32"
        :placeholder="$t('admin.system.codegen.basic.placeholder.module')"
      />
      <Input
        v-model:value="displayName"
        :placeholder="$t('admin.system.codegen.basic.displayName')"
        class="!w-36"
      />
      <Input
        v-model:value="displayNameEn"
        :placeholder="$t('admin.system.codegen.basic.displayNameEn')"
        class="!w-36"
      />
      <Tooltip :title="$t('admin.system.codegen.basic.resourcePluralHint')">
        <Input
          v-model:value="resourcePlural"
          :placeholder="$t('admin.system.codegen.basic.placeholder.resourcePlural')"
          class="!w-28"
        />
      </Tooltip>
      <div class="mx-2 h-6 w-px bg-border" />
      <Tooltip :title="$t('admin.system.codegen.toolbar.undo')">
        <Button :disabled="!store.canUndo" type="text" size="small" @click="store.undo()">
          <IconifyIcon icon="lucide:undo-2" class="size-4" />
        </Button>
      </Tooltip>
      <Tooltip :title="$t('admin.system.codegen.toolbar.redo')">
        <Button :disabled="!store.canRedo" type="text" size="small" @click="store.redo()">
          <IconifyIcon icon="lucide:redo-2" class="size-4" />
        </Button>
      </Tooltip>
      <Tooltip :title="$t('admin.system.codegen.toolbar.preview')">
        <Button type="text" size="small" @click="codePreviewOpen = true">
          <IconifyIcon icon="lucide:code-2" class="size-4" />
        </Button>
      </Tooltip>
      <div class="flex-1" />
      <Dropdown :trigger="['click']">
        <Button>
          {{ $t('admin.system.codegen.toolbar.more') }}
          <IconifyIcon icon="lucide:chevron-down" class="ml-1 size-4" />
        </Button>
        <template #overlay>
          <Menu>
            <MenuItem @click="onImportYaml">
              <IconifyIcon icon="lucide:upload" class="mr-1 size-4" />
              {{ $t('admin.system.codegen.toolbar.importYaml') }}
            </MenuItem>
            <MenuItem @click="onExportYaml">
              <IconifyIcon icon="lucide:download" class="mr-1 size-4" />
              {{ $t('admin.system.codegen.toolbar.exportYaml') }}
            </MenuItem>
            <MenuItem v-if="configId" @click="onOpenVersionHistory">
              <IconifyIcon icon="lucide:history" class="mr-1 size-4" />
              {{ $t('admin.system.codegen.toolbar.versionHistory') }}
            </MenuItem>
            <MenuItem @click="onDownloadZip">
              <IconifyIcon icon="lucide:archive" class="mr-1 size-4" />
              {{ $t('admin.system.codegen.toolbar.downloadZip') }}
            </MenuItem>
          </Menu>
        </template>
      </Dropdown>
      <Button :loading="isSaving" @click="onSave">
        <IconifyIcon icon="lucide:save" class="mr-1 size-4" />
        {{ $t('admin.system.codegen.toolbar.saveDraft') }}
      </Button>
      <Badge :count="validationErrors.length" :offset="[4, -4]" :show-zero="false">
        <Button type="primary" :loading="isGenerating" @click="onGenerate">
          <IconifyIcon icon="lucide:wand-2" class="mr-1 size-4" />
          {{ $t('admin.system.codegen.toolbar.generate') }}
        </Button>
      </Badge>
    </div>

    <!-- 三栏主体 -->
    <div class="flex min-h-0 flex-1 overflow-hidden">
      <ComponentPalette @add="onPaletteAdd" />
      <WysiwygCenter ref="wysiwygRef" class="min-w-80 flex-1 overflow-hidden" />
      <div class="flex w-80 shrink-0 flex-col overflow-hidden border-l border-border">
        <template v-if="store.selectedFieldKey">
          <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
            <div class="shrink-0 border-b border-border px-3 py-2 text-xs font-medium text-muted-foreground">
              {{ $t('admin.system.codegen.property.title') }}
            </div>
            <FieldPropertyPanel class="min-h-0 flex-1 overflow-y-auto" />
          </div>
        </template>
        <div v-else class="flex flex-1 flex-col items-center justify-center px-4 py-8 text-center text-muted-foreground text-sm">
          <IconifyIcon icon="lucide:mouse-pointer-click" class="mb-2 size-8" />
          <span>{{ $t('admin.system.codegen.property.selectFieldHint') }}</span>
        </div>
      </div>
    </div>

    <!-- 底部设置栏 -->
    <div class="flex shrink-0 items-center gap-4 border-t border-border px-4 py-2">
      <Checkbox :checked="hasAdmin" @change="(e) => onAdminChange(Boolean((e as { target?: { checked?: boolean } })?.target?.checked ?? false))">
        {{ $t('admin.system.codegen.enum.admin') }}
      </Checkbox>
      <Checkbox :checked="hasTenant" @change="(e) => onTenantChange(Boolean((e as { target?: { checked?: boolean } })?.target?.checked ?? false))">
        {{ $t('admin.system.codegen.enum.tenant') }}
      </Checkbox>
      <Radio.Group v-model:value="feMode" size="small">
        <Radio value="table">{{ $t('admin.system.codegen.frontend.table') }}</Radio>
        <Radio value="card">{{ $t('admin.system.codegen.frontend.card') }}</Radio>
      </Radio.Group>
      <span class="text-muted-foreground text-xs">{{ $t('admin.system.codegen.fieldConfig.fieldCount', { count: store.fieldCount }) }}</span>
      <Tooltip :title="$t('admin.system.codegen.builder.keyboardHint')">
        <IconifyIcon icon="lucide:keyboard" class="size-4 text-muted-foreground" />
      </Tooltip>
      <div class="flex-1" />
      <Button @click="dbImportOpen = true">
        <IconifyIcon icon="lucide:database" class="mr-1 size-4" />
        {{ $t('admin.system.codegen.builder.dbImportBtn') }}
      </Button>
      <Button @click="expertModalOpen = true">
        <IconifyIcon icon="lucide:settings-2" class="mr-1 size-4" />
        {{ $t('admin.system.codegen.advanced.button') }}
        <Badge
          v-if="store.expertItemCount > 0"
          :count="store.expertItemCount"
          :offset="[4, -4]"
          class="ml-1"
        />
      </Button>
      <Button @click="codePreviewOpen = true">
        <IconifyIcon icon="lucide:eye" class="mr-1 size-4" />
        {{ $t('admin.system.codegen.toolbar.preview') }}
      </Button>
    </div>

    <!-- Modals -->
    <CodePreviewModal v-model:open="codePreviewOpen" />
    <ExpertModal v-model:open="expertModalOpen" />
    <DbTableImportModal v-model:open="dbImportOpen" @applied="onDbImported" />

    <Modal
      v-model:open="importYamlVisible"
      :title="$t('admin.system.codegen.builder.importYamlTitle')"
      :ok-text="$t('common.confirm')"
      :cancel-text="$t('common.cancel')"
      :confirm-loading="isImporting"
      @ok="onConfirmImportYaml"
    >
      <div class="flex flex-col gap-2">
        <Input.TextArea
          v-model:value="importYamlText"
          :placeholder="$t('admin.system.codegen.builder.importYamlPlaceholder')"
          :rows="12"
          class="font-mono text-sm"
        />
        <label class="inline-flex cursor-pointer items-center gap-1 text-sm text-muted-foreground underline">
          <input
            type="file"
            accept=".yaml,.yml"
            class="sr-only"
            @change="onImportYamlFile"
          >
          <IconifyIcon icon="lucide:upload" class="size-4" />
          <span>{{ $t('admin.system.codegen.builder.importYamlSelectFile') }}</span>
        </label>
      </div>
    </Modal>

    <Modal
      v-model:open="versionHistoryVisible"
      :title="$t('admin.system.codegen.builder.versionHistoryTitle')"
      :footer="null"
      width="520"
    >
      <div v-if="!isVersionLoading && versionList.length === 0" class="py-8 text-center text-muted-foreground">
        {{ $t('admin.system.codegen.builder.versionEmpty') }}
      </div>
      <List
        v-else
        :loading="isVersionLoading"
        :data-source="versionList"
        size="small"
        class="max-h-80 overflow-y-auto"
      >
        <template #renderItem="{ item }">
          <List.Item class="flex items-center justify-between">
            <div class="flex flex-col gap-0.5">
              <span class="text-sm">{{ formatVersionTime(item.created_at) }}</span>
              <span v-if="item.note" class="text-xs text-muted-foreground">{{ item.note }}</span>
            </div>
            <div class="flex gap-0">
              <Button type="link" size="small" :loading="versionPreviewLoadingIds.has(item.id)" @click="onPreviewVersion(item)">
                {{ $t('admin.system.codegen.builder.versionPreview') }}
              </Button>
              <Button type="link" size="small" :loading="isRestoring" @click="onRestoreVersion(item)">
                {{ $t('admin.system.codegen.builder.versionRestore') }}
              </Button>
            </div>
          </List.Item>
        </template>
      </List>
    </Modal>

    <Modal
      v-model:open="versionPreviewVisible"
      :title="$t('admin.system.codegen.builder.versionPreviewTitle')"
      :footer="null"
      width="640"
    >
      <div v-if="versionPreviewNote" class="mb-2 text-sm text-muted-foreground">
        {{ versionPreviewNote }}
      </div>
      <div v-if="versionPreviewLoadingIds.size > 0" class="py-8 text-center text-muted-foreground">
        {{ $t('common.loading') }}
      </div>
      <Input.TextArea v-else :value="versionPreviewContent" readonly :rows="18" class="font-mono text-sm" />
    </Modal>

    <Modal
      v-model:open="resultModalVisible"
      :title="$t('admin.system.codegen.generate.resultTitle')"
      :footer="null"
      width="520"
    >
      <template v-if="lastResult">
        <div v-if="lastResult.conflicts?.length && !lastResult.success" class="mb-4">
          <Alert type="warning" show-icon :message="$t('admin.system.codegen.generate.partialWriteTitle')">
            <template #description>
              <p class="mb-2">{{ $t('admin.system.codegen.generate.partialWriteDesc') }}</p>
              <ul class="list-inside list-disc text-sm">
                <li v-for="(c, i) in lastResult.conflicts" :key="i">
                  {{ (c as Record<string, string>)?.path ?? JSON.stringify(c) }}
                </li>
              </ul>
            </template>
          </Alert>
        </div>
        <div v-if="lastResult.errors?.length" class="mb-4">
          <Alert type="error" :message="lastResult.errors.join(', ')" />
        </div>
        <Collapse
          v-if="
            lastResult.success ||
            lastResult.files_created?.length ||
            lastResult.files_modified?.length
          "
        >
          <CollapsePanel
            key="files"
            :header="
              $t('admin.system.codegen.generate.fileCountHeader', {
                create: lastResult.files_created?.length ?? 0,
                modify: lastResult.files_modified?.length ?? 0,
              })
            "
          >
            <div class="max-h-48 overflow-y-auto text-sm">
              <div v-for="p in lastResult.files_created" :key="'c-' + p" class="text-green-600">
                + {{ p }}
              </div>
              <div v-for="p in lastResult.files_modified" :key="'m-' + p" class="text-amber-600">
                ~ {{ p }}
              </div>
            </div>
          </CollapsePanel>
        </Collapse>
        <div class="mt-4 rounded border border-border p-3">
          <h5 class="mb-2 font-medium">{{ $t('admin.system.codegen.generate.nextSteps') }}</h5>
          <ul class="list-inside list-decimal space-y-1 text-sm">
            <li>{{ $t('admin.system.codegen.generate.checkMigration') }}</li>
            <li>{{ $t('admin.system.codegen.generate.runMigration') }}</li>
            <li>{{ $t('admin.system.codegen.generate.restartServer') }}</li>
            <li>{{ $t('admin.system.codegen.generate.reviewCode') }}</li>
          </ul>
        </div>
        <div class="mt-4 flex justify-end gap-2">
          <Button @click="closeResultModal">
            {{ $t('common.close') }}
          </Button>
        </div>
      </template>
    </Modal>
  </Page>
</template>
