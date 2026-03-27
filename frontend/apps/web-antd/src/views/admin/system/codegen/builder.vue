<script lang="ts" setup>
import type { PaletteItem } from './modules/ComponentPalette.vue';

/**
 * 代码生成器三栏可视化构建器 / Codegen Visual Builder
 *
 * 三栏布局: 组件面板 | 字段卡片列表 | 属性面板 + 表单预览
 */
import type {
  CodegenConfigInfo,
  CodegenVersionItem,
  PreviewResult,
} from '#/api/admin/codegen';

import {
  computed,
  defineAsyncComponent,
  h,
  nextTick,
  onMounted,
  onUnmounted,
  ref,
  watch,
} from 'vue';
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Collapse,
  CollapsePanel,
  Dropdown,
  Input,
  List,
  Menu,
  MenuItem,
  message,
  Modal,
  Radio,
  Select,
  Tag,
  Tooltip,
} from 'ant-design-vue';
import yaml from 'js-yaml';

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
  postCodegenPreviewApi,
  postCodegenValidateApi,
  updateCodegenConfigApi,
} from '#/api/admin/codegen';
import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';
import { formatDate } from '#/utils/common';
import { downloadText } from '#/utils/download';

import { createFieldFromPalette, ensureFieldKeys } from './modules/field-utils';
import { inferFieldConfigForMerge, pluralize } from './modules/infer';

defineOptions({ name: 'AdminSystemCodegenBuilder' });
const ComponentPalette = defineAsyncComponent(
  () => import('./modules/ComponentPalette.vue'),
);
const CodegenValidationPanel = defineAsyncComponent(
  () => import('./modules/CodegenValidationPanel.vue'),
);
const FieldPropertyPanel = defineAsyncComponent(
  () => import('./modules/FieldPropertyPanel.vue'),
);
const WysiwygCenter = defineAsyncComponent(
  () => import('./modules/WysiwygCenter.vue'),
);
const CodePreviewModal = defineAsyncComponent(
  () => import('./modules/CodePreviewModal.vue'),
);
const ExpertModal = defineAsyncComponent(
  () => import('./modules/ExpertModal.vue'),
);
const DbTableImportModal = defineAsyncComponent(
  () => import('./modules/DbTableImportModal.vue'),
);

const route = useRoute();
const router = useRouter();
const store = useCodegenBuilderStore();

const wysiwygRef = ref<InstanceType<typeof WysiwygCenter> | null>(null);
const resourceInputRef = ref<HTMLElement | null>(null);
const builderTopRef = ref<HTMLElement | null>(null);

const codePreviewOpen = ref(false);
const expertModalOpen = ref(false);
const dbImportOpen = ref(false);
const isSaving = ref(false);
const isGenerating = ref(false);
const isPreparingGenerate = ref(false);
const validationErrors = ref<
  Array<{ code: string; field: string; message: string; path: string }>
>([]);
const configMeta = ref<CodegenConfigInfo | null>(null);
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
const lastResult = ref<null | {
  config_id?: null | number;
  conflicts: Array<Record<string, string>>;
  errors: string[];
  files_created: string[];
  files_modified: string[];
  migration?: null | {
    error?: string;
    message?: string;
    migration_path?: string;
    phase?: string;
    success?: boolean;
  };
  module?: null | string;
  resource?: null | string;
  success: boolean;
  table_name?: null | string;
}>(null);
type GenerateNextStepKey =
  | 'checkMigration'
  | 'migrationAlreadyApplied'
  | 'migrationNoChanges'
  | 'restartIfNeeded'
  | 'reviewCode'
  | 'runMigration';

const moduleOptions = ref<Array<{ label: string; value: string }>>([]);
const COMMON_MODULE_KEYS = ['system', 'business', 'tenant', 'ai'] as const;

const resultNextSteps = computed<GenerateNextStepKey[]>(() => {
  const result = lastResult.value;
  if (!result) return [];

  const steps: GenerateNextStepKey[] = [];
  const migration = result.migration;
  const hasWrittenFiles =
    (result.files_created?.length ?? 0) > 0 ||
    (result.files_modified?.length ?? 0) > 0;

  if (migration?.migration_path) {
    steps.push('checkMigration');
  }

  if (migration?.phase === 'noop') {
    steps.push('migrationNoChanges');
  } else if (migration?.success) {
    steps.push('migrationAlreadyApplied');
  } else if (migration || result.success) {
    steps.push('runMigration');
  }

  if (hasWrittenFiles) {
    steps.push('restartIfNeeded');
  }

  steps.push('reviewCode');
  return steps;
});

const hasPreviewSnapshot = computed(() => {
  const cache = store.previewCache;
  return Boolean(
    cache?.error ||
    cache?.files?.length ||
    cache?.conflicts?.length ||
    cache?.warnings?.length,
  );
});

const configId = computed(() => {
  const id = route.params.id;
  if (id === null || id === undefined || id === '' || id === 'new') {
    return null;
  }
  const num = Number(id);
  return Number.isNaN(num) ? null : num;
});
const isNewMode = computed(() => !configId.value);
const currentLifecycleStatus = computed(
  () => configMeta.value?.status || 'draft',
);
const currentManifestPresent = computed(() =>
  Boolean(configMeta.value?.manifest_present),
);
const builderHeadline = computed(() => {
  const resourceValue = (store.configJson.resource as string) || '';
  if (resourceValue) return resourceValue;
  return isNewMode.value
    ? $t('admin.system.codegen.builder.heroTitleNew')
    : $t('admin.system.codegen.builder.heroTitleEdit');
});
const builderSubline = computed(() => {
  const moduleValue = (store.configJson.module as string) || 'system';
  const displayValue = (store.configJson.display_name as string) || '';
  if (displayValue) {
    return $t('admin.system.codegen.builder.heroDescNamed', {
      module: moduleValue,
      display: displayValue,
    });
  }
  return isNewMode.value
    ? $t('admin.system.codegen.builder.heroDescNew')
    : $t('admin.system.codegen.builder.heroDescEdit');
});

const resource = computed({
  get: () => (store.configJson.resource as string) || '',
  set: (v) => store.updateConfig({ resource: v }),
});
const moduleVal = computed({
  get: () => (store.configJson.module as string) || 'system',
  set: (v) => store.updateConfig({ module: v }),
});
const normalizedModuleOptions = computed(() => {
  const seen = new Set<string>();
  const merged: Array<{ label: string; value: string }> = [];
  const candidateCodes = [
    ...moduleOptions.value.map((item) => item.value),
    ...COMMON_MODULE_KEYS,
    moduleVal.value || 'system',
  ];

  for (const code of candidateCodes) {
    if (!code || seen.has(code)) continue;
    seen.add(code);
    const key = `admin.system.codegen.basic.moduleLabels.${code}`;
    const translated = $t(key) as string;
    merged.push({
      label: translated === key ? code : translated,
      value: code,
    });
  }

  return merged;
});
const commonModuleOptions = computed(() =>
  normalizedModuleOptions.value.filter((item) =>
    COMMON_MODULE_KEYS.includes(
      item.value as (typeof COMMON_MODULE_KEYS)[number],
    ),
  ),
);
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
const model = computed(
  () => (store.configJson.model as Record<string, unknown>) || {},
);
const endpoints = computed(
  () => (store.configJson.endpoints as Record<string, unknown>[]) || [],
);
const firstEndpoint = computed(() => endpoints.value[0] || {});
const frontend = computed(
  () => (firstEndpoint.value?.frontend as Record<string, unknown>) || {},
);

const hasAdmin = computed(() =>
  endpoints.value.some((e) => e.scope === 'admin'),
);
const hasTenant = computed(() =>
  endpoints.value.some((e) => e.scope === 'tenant'),
);
const scopeCount = computed(
  () => Number(hasAdmin.value) + Number(hasTenant.value),
);
const feMode = computed({
  get: () => (frontend.value.mode as string) || 'table',
  set: (v) => {
    const list = [...endpoints.value];
    if (list.length > 0) {
      const next = list.map((ep) => ({
        ...ep,
        frontend: {
          ...(ep.frontend as Record<string, unknown>),
          mode: v,
        },
      }));
      store.updateConfig({ endpoints: next });
    }
  },
});

function getStatusBadgeColor(status: string): string {
  const map: Record<string, string> = {
    draft: 'default',
    generated: 'processing',
    applied: 'success',
    rolled_back: 'warning',
  };
  return map[status] || 'default';
}

function getStatusBadgeText(status: string): string {
  const map: Record<string, string> = {
    draft: $t('admin.system.codegen.status_options.draft'),
    generated: $t('admin.system.codegen.status_options.generated'),
    applied: $t('admin.system.codegen.status_options.applied'),
    rolled_back: $t('admin.system.codegen.status_options.rolled_back'),
  };
  return map[status] || status || '-';
}

const lifecycleBadges = computed(() => [
  {
    key: 'status',
    color: getStatusBadgeColor(currentLifecycleStatus.value),
    text: getStatusBadgeText(currentLifecycleStatus.value),
  },
  {
    key: 'manifest',
    color: currentManifestPresent.value ? 'success' : 'default',
    text: currentManifestPresent.value
      ? $t('admin.system.codegen.manifest.present')
      : $t('admin.system.codegen.manifest.absent'),
  },
  {
    key: 'dirty',
    color: store.isDirty ? 'warning' : 'default',
    text: store.isDirty
      ? $t('admin.system.codegen.builder.unsavedChanges')
      : $t('admin.system.codegen.builder.savedState'),
  },
]);

const previewSummary = computed(() => store.previewCache?.summary ?? null);
const previewWarningCount = computed(
  () => store.previewCache?.warnings?.length ?? 0,
);
const previewConflictCount = computed(
  () => store.previewCache?.conflicts?.length ?? 0,
);

/** 创建默认 endpoint / Create default endpoint for scope */
function createDefaultEndpoint(
  scope: 'admin' | 'tenant',
): Record<string, unknown> {
  const plural =
    (store.configJson.resource_plural as string) ||
    pluralize((store.configJson.resource as string) || 'item');
  return {
    scope,
    data_mode: scope === 'admin' ? 'independent' : 'tenant_isolated',
    route_prefix: `/${plural}`,
    frontend: {
      mode: 'table',
      page_size: 20,
      default_sort: '-created_at',
      search_default_open: false,
      quick_search: true,
      recycle_bin: false,
      export: false,
      import: false,
      drag_sort: false,
    },
  };
}

function onAdminChange(checked: boolean) {
  const previousEndpoints = [...endpoints.value];
  if (checked) {
    const hasAdminEp = endpoints.value.some(
      (e) => (e.scope as string) === 'admin',
    );
    if (!hasAdminEp) {
      const next = [createDefaultEndpoint('admin'), ...endpoints.value];
      store.updateConfig({ endpoints: next });
      syncBaseClassFromEndpoints(next, previousEndpoints);
    }
  } else {
    const next = endpoints.value.filter((e) => (e.scope as string) !== 'admin');
    if (next.length === 0) {
      message.warning($t('admin.system.codegen.builder.atLeastOneScope'));
      return;
    }
    store.updateConfig({ endpoints: next });
    syncBaseClassFromEndpoints(next, previousEndpoints);
  }
}

function onTenantChange(checked: boolean) {
  const previousEndpoints = [...endpoints.value];
  if (checked) {
    const hasTenantEp = endpoints.value.some(
      (e) => (e.scope as string) === 'tenant',
    );
    if (!hasTenantEp) {
      const next = [...endpoints.value, createDefaultEndpoint('tenant')];
      store.updateConfig({ endpoints: next });
      syncBaseClassFromEndpoints(next, previousEndpoints);
    }
  } else {
    const next = endpoints.value.filter(
      (e) => (e.scope as string) !== 'tenant',
    );
    if (next.length === 0) {
      message.warning($t('admin.system.codegen.builder.atLeastOneScope'));
      return;
    }
    store.updateConfig({ endpoints: next });
    syncBaseClassFromEndpoints(next, previousEndpoints);
  }
}

function extractCheckboxChecked(event: unknown): boolean {
  return Boolean(
    (event as { target?: { checked?: boolean } })?.target?.checked ?? false,
  );
}

function getSuggestedBaseClassFromEndpoints(
  eps: Record<string, unknown>[],
): 'BaseModel' | 'TenantModel' {
  const hasTenant = eps.some((e) => (e.scope as string) === 'tenant');
  return hasTenant ? 'TenantModel' : 'BaseModel';
}

function syncBaseClassFromEndpoints(
  eps: Record<string, unknown>[],
  previousEps: Record<string, unknown>[] = endpoints.value,
) {
  const m = model.value;
  const currentClass = String(m.base_class || '');
  const previousSuggested = getSuggestedBaseClassFromEndpoints(previousEps);
  const nextSuggested = getSuggestedBaseClassFromEndpoints(eps);

  if (
    (!currentClass || currentClass === previousSuggested) &&
    currentClass !== nextSuggested
  ) {
    store.updateConfig({ model: { ...m, base_class: nextSuggested } });
  }
}

function shouldSyncAutoRoutePrefix(
  routePrefix: string,
  previousResource: string,
  previousPlural: string,
): boolean {
  const normalized = routePrefix.trim();
  const candidates = new Set(['/items']);

  if (previousResource) {
    candidates.add(`/${previousResource}`);
    candidates.add(`/${pluralize(previousResource)}`);
  }
  if (previousPlural) {
    candidates.add(`/${previousPlural}`);
  }

  return !normalized || candidates.has(normalized);
}

function onResourceChange(v: string) {
  const previousResource = (store.configJson.resource as string) || '';
  const previousPlural = (store.configJson.resource_plural as string) || '';
  const nextPlural = v ? pluralize(v) : '';
  const m = (store.configJson.model as Record<string, unknown>) || {};
  const currentTableName = String(m.table_name || '');
  const shouldUpdatePlural =
    Boolean(v) &&
    (!previousPlural || previousPlural === pluralize(previousResource));
  const shouldUpdateTableName =
    Boolean(v) &&
    (!currentTableName ||
      currentTableName === previousResource ||
      currentTableName === previousPlural);
  const nextEndpoints = endpoints.value.map((ep) => {
    const routePrefix = String(ep.route_prefix || '');
    if (
      !shouldSyncAutoRoutePrefix(routePrefix, previousResource, previousPlural)
    ) {
      return ep;
    }
    return {
      ...ep,
      route_prefix: nextPlural ? `/${nextPlural}` : routePrefix,
    };
  });

  const patch: Record<string, unknown> = { resource: v };
  if (shouldUpdatePlural) {
    patch.resource_plural = nextPlural;
  }
  if (shouldUpdateTableName) {
    patch.model = { ...m, table_name: nextPlural };
  }
  if (
    nextEndpoints.some(
      (ep, index) => ep.route_prefix !== endpoints.value[index]?.route_prefix,
    )
  ) {
    patch.endpoints = nextEndpoints;
  }
  store.updateConfig(patch);
}

function onPaletteAdd(item: PaletteItem) {
  // WysiwygCenter 为异步组件，可能尚未挂载；此时直接更新 store 确保添加生效
  if (wysiwygRef.value) {
    wysiwygRef.value.addFromPalette(item);
  } else {
    const arr = (store.configJson.fields as Record<string, unknown>[]) || [];
    const current = ensureFieldKeys(arr);
    const newField = createFieldFromPalette(item, current);
    const next = [...current, newField];
    store.updateConfig({ fields: next });
    store.selectedFieldKey = newField.__key as string;
  }
}

async function refreshConfigMeta(targetId?: null | number) {
  const id = targetId ?? store.configId ?? configId.value;
  if (!id) {
    configMeta.value = null;
    return;
  }
  try {
    configMeta.value = await getCodegenConfigDetailApi(id);
  } catch {
    configMeta.value = null;
  }
}

function setPreviewSnapshot(preview: PreviewResult) {
  store.setPreviewCache({
    files: preview.files ?? [],
    summary: preview.summary,
    warnings: preview.warnings ?? [],
    conflicts: preview.conflicts ?? [],
    timestamp: Date.now(),
    error: preview.error ?? undefined,
  });
}

function focusBuilderTop() {
  builderTopRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  resourceInputRef.value?.focus?.();
}

function locateValidationIssue(item: { field?: string; path?: string }) {
  const path = String(item.path || '');
  const fieldName = String(item.field || '');

  const fieldIndexMatch = path.match(/^fields\[(\d+)\]/);
  if (fieldIndexMatch) {
    const index = Number(fieldIndexMatch[1]);
    const field = fields.value[index];
    if (field?.__key) {
      store.selectedFieldKey = String(field.__key);
      nextTick(() => {
        document
          .querySelector(`[data-field-key="${String(field.__key)}"]`)
          ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
      return;
    }
  }

  if (fieldName) {
    const targetField = fields.value.find((field) => field.name === fieldName);
    if (targetField?.__key) {
      store.selectedFieldKey = String(targetField.__key);
      nextTick(() => {
        document
          .querySelector(`[data-field-key="${String(targetField.__key)}"]`)
          ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
      return;
    }
  }

  focusBuilderTop();
}

async function buildGeneratePreviewSnapshot() {
  const preview = await postCodegenPreviewApi({
    config_json: store.configJson,
  });
  setPreviewSnapshot(preview);
  return preview;
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
    message.warning(
      $t('admin.system.codegen.validation.display_name_required'),
    );
    return;
  }
  // 保存前校验 / Validate before save
  try {
    const vResult = await postCodegenValidateApi({
      config_json: json,
      mode: 'draft',
    });
    if (!vResult.valid) {
      validationErrors.value = vResult.errors ?? [];
      message.warning($t('admin.system.codegen.builder.saveValidateFailed'));
      return;
    }
  } catch {
    message.error($t('common.failed'));
    return;
  }
  isSaving.value = true;
  try {
    const name =
      (json.name as string) ||
      (json.display_name as string) ||
      $t('admin.system.codegen.unnamed');
    const displayNameEn = (json.display_name_en as string) || r;
    if (store.configId !== null && store.configId !== undefined) {
      const updated = await updateCodegenConfigApi(store.configId, {
        name,
        resource: r,
        module: mod,
        display_name: disp,
        display_name_en: displayNameEn,
        config_json: json,
      });
      store.saveConfig(store.configId, json);
      configMeta.value = updated;
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
    configMeta.value = res;
    validationErrors.value = [];
    message.success($t('admin.system.codegen.messages.saveSuccess'));
    router.replace(`/admin/system/codegen/${res.id}/edit`);
  } catch (error) {
    console.error(error);
    message.error($t('common.failed'));
  } finally {
    isSaving.value = false;
  }
}

async function doGenerate(force = false) {
  validationErrors.value = [];
  try {
    const vResult = await postCodegenValidateApi({
      config_json: store.configJson,
      mode: 'generate',
    });
    if (!vResult.valid) {
      validationErrors.value = vResult.errors ?? [];
      message.warning($t('admin.system.codegen.generate.validateFirst'));
      return;
    }
    const payload =
      store.configId === null || store.configId === undefined
        ? { config_json: store.configJson, force, auto_migrate: true }
        : { config_id: store.configId, force, auto_migrate: true };
    const result = await postCodegenGenerateApi(payload);
    lastResult.value = result;
    resultModalVisible.value = true;
    if (
      (store.configId === null || store.configId === undefined) &&
      result.config_id !== null &&
      result.config_id !== undefined
    ) {
      store.loadConfig(result.config_id, store.configJson);
      router.replace(`/admin/system/codegen/${result.config_id}/edit`);
    }
    await refreshConfigMeta(
      result.config_id ?? store.configId ?? configId.value,
    );
    if (result.success) {
      message.success($t('admin.system.codegen.messages.generateSuccess'));
    } else if (result.errors?.length) {
      message.error(result.errors.join('; '));
    }
  } catch (error) {
    message.error(error instanceof Error ? error.message : $t('common.failed'));
  } finally {
    isGenerating.value = false;
  }
}

function closeResultModal() {
  resultModalVisible.value = false;
  lastResult.value = null;
}

function openPreviewFromResult() {
  resultModalVisible.value = false;
  codePreviewOpen.value = true;
}

async function onGenerate() {
  const r = (store.configJson.resource as string) || '';
  const forceGenerate = ref(false);
  isPreparingGenerate.value = true;
  try {
    const preview = await buildGeneratePreviewSnapshot();
    const summary = preview.summary ?? {
      create_count: 0,
      modify_count: 0,
      backend_files: 0,
      frontend_files: 0,
      total_lines: 0,
    };
    const conflicts = preview.conflicts?.length ?? 0;
    const warnings = preview.warnings?.length ?? 0;

    Modal.confirm({
      title: $t('admin.system.codegen.builder.generateConfirmTitle'),
      width: 560,
      okType: conflicts > 0 ? 'danger' : 'primary',
      content: h('div', { class: 'flex flex-col gap-3' }, [
        h(
          'p',
          { class: 'm-0 text-sm text-muted-foreground' },
          $t('admin.system.codegen.builder.generateConfirmContent', {
            resource: r,
          }),
        ),
        h(
          'div',
          {
            class:
              'grid grid-cols-2 gap-2 rounded-2xl border border-border bg-muted/20 p-3 text-sm',
          },
          [
            h('div', [
              h(
                'div',
                { class: 'text-xs text-muted-foreground' },
                $t('admin.system.codegen.resource'),
              ),
              h('div', { class: 'font-mono font-medium' }, r || '-'),
            ]),
            h('div', [
              h(
                'div',
                { class: 'text-xs text-muted-foreground' },
                $t('admin.system.codegen.builder.metricFields'),
              ),
              h('div', { class: 'font-medium' }, String(store.fieldCount)),
            ]),
            h('div', [
              h(
                'div',
                { class: 'text-xs text-muted-foreground' },
                $t('admin.system.codegen.builder.previewCreateFiles'),
              ),
              h(
                'div',
                { class: 'font-medium' },
                String(summary.create_count ?? 0),
              ),
            ]),
            h('div', [
              h(
                'div',
                { class: 'text-xs text-muted-foreground' },
                $t('admin.system.codegen.builder.previewModifyFiles'),
              ),
              h(
                'div',
                { class: 'font-medium' },
                String(summary.modify_count ?? 0),
              ),
            ]),
            h('div', [
              h(
                'div',
                { class: 'text-xs text-muted-foreground' },
                $t('admin.system.codegen.generate.conflicts'),
              ),
              h(
                'div',
                {
                  class:
                    conflicts > 0
                      ? 'font-medium text-amber-600'
                      : 'font-medium',
                },
                String(conflicts),
              ),
            ]),
            h('div', [
              h(
                'div',
                { class: 'text-xs text-muted-foreground' },
                $t('admin.system.codegen.builder.previewWarnings'),
              ),
              h(
                'div',
                {
                  class:
                    warnings > 0 ? 'font-medium text-amber-600' : 'font-medium',
                },
                String(warnings),
              ),
            ]),
          ],
        ),
        conflicts > 0
          ? h(
              'div',
              {
                class:
                  'rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-700',
              },
              $t('admin.system.codegen.builder.generateConflictWarning'),
            )
          : null,
        warnings > 0
          ? h(
              'div',
              {
                class:
                  'rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-xs leading-5 text-sky-700',
              },
              $t('admin.system.codegen.builder.generateWarningHint'),
            )
          : null,
        h(
          Checkbox,
          {
            defaultChecked: false,
            onChange: (event: unknown) => {
              forceGenerate.value = extractCheckboxChecked(event);
            },
          },
          {
            default: () =>
              $t('admin.system.codegen.confirm.generateForceLabel'),
          },
        ),
        h(
          'p',
          { class: 'm-0 text-xs text-muted-foreground' },
          $t('admin.system.codegen.confirm.generateForceHint'),
        ),
      ]),
      onOk: async () => {
        isGenerating.value = true;
        await doGenerate(forceGenerate.value);
      },
    });
  } catch {
    Modal.confirm({
      title: $t('admin.system.codegen.builder.generateConfirmTitle'),
      content: h('div', { class: 'flex flex-col gap-3' }, [
        h(
          'p',
          { class: 'm-0 text-sm text-muted-foreground' },
          $t('admin.system.codegen.builder.generateConfirmContent', {
            resource: r,
          }),
        ),
        h(
          Checkbox,
          {
            defaultChecked: false,
            onChange: (event: unknown) => {
              forceGenerate.value = extractCheckboxChecked(event);
            },
          },
          {
            default: () =>
              $t('admin.system.codegen.confirm.generateForceLabel'),
          },
        ),
        h(
          'p',
          { class: 'm-0 text-xs text-muted-foreground' },
          $t('admin.system.codegen.confirm.generateForceHint'),
        ),
      ]),
      onOk: async () => {
        isGenerating.value = true;
        await doGenerate(forceGenerate.value);
      },
    });
  } finally {
    isPreparingGenerate.value = false;
  }
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
  reader.addEventListener('load', () => {
    importYamlText.value = (reader.result as string) || '';
  });
  reader.addEventListener('error', () => {
    message.error($t('admin.system.codegen.builder.importFileReadError'));
  });
  reader.readAsText(file, 'utf8');
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
    const result = await postCodegenValidateApi({
      config_json: parsed,
      mode: 'draft',
    });
    if (!result.valid) {
      const msgs = (result.errors ?? []).map((e) => e.message).filter(Boolean);
      message.error(
        msgs.join('; ') ||
          $t('admin.system.codegen.builder.importYamlValidateError'),
      );
      return;
    }
    configMeta.value = null;
    store.loadConfig(null, parsed);
    validationErrors.value = [];
    importYamlVisible.value = false;
    message.success($t('admin.system.codegen.builder.importYamlSuccess'));
  } catch (error) {
    console.error(error);
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
  } catch (error) {
    console.error(error);
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
        message.success(
          $t('admin.system.codegen.builder.versionRestoreSuccess'),
        );
        message.info(
          $t('admin.system.codegen.builder.versionRestoreUndoCleared'),
        );
      } catch (error) {
        console.error(error);
        message.error($t('common.failed'));
      } finally {
        isRestoring.value = false;
      }
    },
  });
}

function formatVersionTime(iso: null | string) {
  return formatDate(iso) ?? '-';
}

function formatConflictItem(conflict: unknown): string {
  if (
    conflict &&
    typeof conflict === 'object' &&
    'path' in (conflict as Record<string, unknown>)
  ) {
    const path = (conflict as Record<string, unknown>).path;
    if (typeof path === 'string' && path) {
      return path;
    }
  }
  return JSON.stringify(conflict);
}

async function onPreviewVersion(v: CodegenVersionItem) {
  const id = configId.value;
  if (!id || !v.id) return;
  versionPreviewVisible.value = true;
  versionPreviewNote.value = v.note || formatVersionTime(v.created_at) || '';
  versionPreviewLoadingIds.value = new Set([
    v.id,
    ...versionPreviewLoadingIds.value,
  ]);
  versionPreviewContent.value = '';
  try {
    const res = await getCodegenConfigVersionApi(id, v.id);
    const json = res?.config_json ?? {};
    versionPreviewContent.value = yaml.dump(json, { indent: 2, lineWidth: -1 });
  } catch (error) {
    console.error(error);
    message.error($t('common.failed'));
    versionPreviewVisible.value = false;
  } finally {
    versionPreviewLoadingIds.value = new Set(
      [...versionPreviewLoadingIds.value].filter((x) => x !== v.id),
    );
  }
}

async function onDownloadZip() {
  try {
    await downloadCodegenPreviewZipApi(
      { config_json: store.configJson },
      { step: undefined },
    );
    message.success($t('admin.system.codegen.messages.downloadSuccess'));
  } catch (error) {
    const err = error as {
      response?: { data?: { detail?: string | { error?: string } } };
    };
    const detail = err?.response?.data?.detail;
    const msg =
      (typeof detail === 'object' && detail?.error) ||
      (typeof detail === 'string' ? detail : null) ||
      $t('admin.system.codegen.messages.downloadFail');
    message.error(msg);
  }
}

function onDbImported(patch: Record<string, unknown>) {
  const incoming = (patch.fields as Record<string, unknown>[]) || [];
  const withInferred = incoming.map((f) => {
    const name = (f.name as string) || '';
    if (!name) return f;
    const inferred = inferFieldConfigForMerge(name);
    return {
      ...inferred,
      ...f,
      __key:
        f.__key || `f_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
    };
  });
  const mode = (patch._importMode as 'merge' | 'replace') || 'replace';
  const currentFields =
    (store.configJson.fields as Record<string, unknown>[]) || [];
  let finalFields: Record<string, unknown>[];
  if (mode === 'merge') {
    const incomingByName = new Map(
      withInferred.map((f) => [(f.name as string) || '', f]),
    );
    const currentNames = new Set(
      currentFields.map((f) => (f.name as string) || '').filter(Boolean),
    );
    const merged = currentFields.map((f) => {
      const n = (f.name as string) || '';
      const imp = incomingByName.get(n);
      return imp ? { ...f, ...imp } : f;
    });
    const appended = withInferred.filter(
      (f) => !currentNames.has((f.name as string) || ''),
    );
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
  if (id !== null && id !== undefined) {
    try {
      const config = await getCodegenConfigDetailApi(id);
      configMeta.value = config;
      store.loadConfig(config.id, config.config_json || {});
      store.showFieldManager = true;
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response
        ?.status;
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
        configMeta.value = null;
        store.loadConfig(null, parsed);
        store.showFieldManager = true;
        return;
      }
    } catch {
      message.error($t('admin.system.codegen.builder.presetNotFound'));
    }
  }
  configMeta.value = null;
  store.resetWizard();
  store.updateConfig({ module: 'system' });
  store.showFieldManager = true;
}

const fields = computed(
  () => (store.configJson.fields as Record<string, unknown>[]) || [],
);

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
  const prevField = idx > 0 ? fields.value[idx - 1] : undefined;
  if (prevField) store.selectedFieldKey = prevField.__key as string;
}

function selectNextField() {
  const key = store.selectedFieldKey;
  if (!key) return;
  const idx = fields.value.findIndex((f) => f.__key === key);
  const nextField =
    idx !== -1 && idx < fields.value.length - 1
      ? fields.value[idx + 1]
      : undefined;
  if (nextField) store.selectedFieldKey = nextField.__key as string;
}

function handleKeydown(e: KeyboardEvent) {
  const target = e.target as HTMLElement;
  const tag = target?.tagName?.toLowerCase();
  if (tag === 'input' || tag === 'textarea' || target?.isContentEditable)
    return;

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
      label: (() => {
        const key = `admin.system.codegen.basic.moduleLabels.${m}`;
        const translated = $t(key) as string;
        return translated === key ? m : translated;
      })(),
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
  async () => {
    if (store.isDirty) {
      return new Promise<void>((resolve) => {
        Modal.confirm({
          title: $t('admin.system.codegen.toolbar.unsavedTitle'),
          content: $t('admin.system.codegen.toolbar.unsavedContent'),
          okText: $t('common.discard'),
          cancelText: $t('common.cancel'),
          onOk: () => {
            loadConfigIfEdit();
            resolve();
          },
          onCancel: () => resolve(),
        });
      });
    }
    loadConfigIfEdit();
  },
);
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-2.5">
    <Card ref="builderTopRef" :body-style="{ padding: '10px' }">
      <div class="flex flex-col gap-2.5">
        <div
          class="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between"
        >
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-1.5">
              <span
                class="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground"
              >
                <IconifyIcon icon="lucide:square-pen" class="size-3.5" />
                {{
                  isNewMode
                    ? $t('admin.system.codegen.builder.heroBadgeNew')
                    : $t('admin.system.codegen.builder.heroBadgeEdit')
                }}
              </span>
              <span
                class="text-lg font-semibold tracking-tight text-foreground"
              >
                {{ builderHeadline }}
              </span>
              <Tag
                v-for="badge in lifecycleBadges"
                :key="badge.key"
                :color="badge.color"
                class="!mr-0"
              >
                {{ badge.text }}
              </Tag>
            </div>
            <div class="mt-1 text-xs text-muted-foreground">
              {{ builderSubline }}
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-2 xl:justify-end">
            <Button
              type="text"
              size="small"
              @click="router.push('/admin/system/codegen')"
            >
              <IconifyIcon icon="lucide:arrow-left" class="mr-1 size-4" />
              {{ $t('common.back') }}
            </Button>
            <Tooltip :title="$t('admin.system.codegen.toolbar.undo')">
              <Button
                :disabled="!store.canUndo"
                type="text"
                size="small"
                @click="store.undo()"
              >
                <IconifyIcon icon="lucide:undo-2" class="size-4" />
              </Button>
            </Tooltip>
            <Tooltip :title="$t('admin.system.codegen.toolbar.redo')">
              <Button
                :disabled="!store.canRedo"
                type="text"
                size="small"
                @click="store.redo()"
              >
                <IconifyIcon icon="lucide:redo-2" class="size-4" />
              </Button>
            </Tooltip>
            <Tooltip :title="$t('admin.system.codegen.toolbar.preview')">
              <Button
                v-access:code="['action.codegen.preview']"
                type="text"
                size="small"
                @click="codePreviewOpen = true"
              >
                <IconifyIcon icon="lucide:code-2" class="size-4" />
              </Button>
            </Tooltip>
            <Dropdown :trigger="['click']">
              <Button size="small">
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
                  <MenuItem
                    v-if="configId"
                    v-access:code="['action.codegen.update']"
                    @click="onOpenVersionHistory"
                  >
                    <IconifyIcon icon="lucide:history" class="mr-1 size-4" />
                    {{ $t('admin.system.codegen.toolbar.versionHistory') }}
                  </MenuItem>
                  <MenuItem
                    v-access:code="['action.codegen.preview']"
                    @click="onDownloadZip"
                  >
                    <IconifyIcon icon="lucide:archive" class="mr-1 size-4" />
                    {{ $t('admin.system.codegen.toolbar.downloadZip') }}
                  </MenuItem>
                  <MenuItem
                    v-access:code="['action.codegen.db']"
                    @click="dbImportOpen = true"
                  >
                    <IconifyIcon icon="lucide:database" class="mr-1 size-4" />
                    {{ $t('admin.system.codegen.builder.dbImportBtn') }}
                  </MenuItem>
                  <MenuItem @click="expertModalOpen = true">
                    <IconifyIcon icon="lucide:settings-2" class="mr-1 size-4" />
                    {{ $t('admin.system.codegen.advanced.button') }}
                  </MenuItem>
                </Menu>
              </template>
            </Dropdown>
            <Button
              v-access:code="['action.codegen.update']"
              size="small"
              :loading="isSaving"
              @click="onSave"
            >
              <IconifyIcon icon="lucide:save" class="mr-1 size-4" />
              {{ $t('admin.system.codegen.toolbar.saveDraft') }}
            </Button>
            <Badge
              :count="validationErrors.length"
              :offset="[4, -4]"
              :show-zero="false"
            >
              <Button
                v-access:code="['action.codegen.generate']"
                type="primary"
                size="small"
                :loading="isGenerating || isPreparingGenerate"
                @click="onGenerate"
              >
                <IconifyIcon icon="lucide:wand-2" class="mr-1 size-4" />
                {{ $t('admin.system.codegen.toolbar.generate') }}
              </Button>
            </Badge>
          </div>
        </div>

        <div
          class="grid gap-2 rounded-xl border border-border/70 bg-muted/10 px-2.5 py-2.5 md:grid-cols-2 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)_minmax(0,0.95fr)_minmax(0,0.95fr)_minmax(0,0.8fr)_auto]"
        >
          <div>
            <div class="mb-1 text-[11px] font-medium text-muted-foreground">
              {{ $t('admin.system.codegen.basic.resource') }}
            </div>
            <Input
              ref="resourceInputRef"
              :model-value="resource"
              :placeholder="$t('admin.system.codegen.basic.resource')"
              @update:model-value="onResourceChange"
            />
          </div>
          <div>
            <div
              class="mb-1 flex items-center gap-1 text-[11px] font-medium text-muted-foreground"
            >
              <span>{{ $t('admin.system.codegen.basic.module') }}</span>
              <Tooltip>
                <template #title>
                  <div class="max-w-[240px] text-xs leading-5">
                    <div>
                      {{ $t('admin.system.codegen.basic.moduleHelpDesc') }}
                    </div>
                    <div
                      v-if="moduleVal === 'business'"
                      class="mt-1 text-muted-foreground"
                    >
                      {{
                        $t(
                          'admin.system.codegen.basic.moduleHelpCurrentBusinessShort',
                        )
                      }}
                    </div>
                  </div>
                </template>
                <span
                  class="inline-flex size-4 cursor-help items-center justify-center rounded-full border border-border text-[10px] text-muted-foreground"
                >
                  ?
                </span>
              </Tooltip>
            </div>
            <Select
              v-model:value="moduleVal"
              class="w-full"
              :options="normalizedModuleOptions"
              :placeholder="$t('admin.system.codegen.basic.placeholder.module')"
              option-filter-prop="label"
              show-search
              style="width: 100%"
            />
            <div class="mt-1.5 flex flex-wrap items-center gap-1">
              <button
                v-for="item in commonModuleOptions"
                :key="item.value"
                type="button"
                class="rounded-full border px-2 py-0.5 text-[10px] transition-colors"
                :class="
                  moduleVal === item.value
                    ? 'border-primary bg-primary/5 text-primary'
                    : 'border-border bg-background text-muted-foreground hover:border-primary/30 hover:text-foreground'
                "
                @click="moduleVal = item.value"
              >
                {{ item.label }}
              </button>
            </div>
          </div>
          <div>
            <div class="mb-1 text-[11px] font-medium text-muted-foreground">
              {{ $t('admin.system.codegen.basic.displayName') }}
            </div>
            <Input
              v-model:value="displayName"
              :placeholder="$t('admin.system.codegen.basic.displayName')"
            />
          </div>
          <div>
            <div class="mb-1 text-[11px] font-medium text-muted-foreground">
              {{ $t('admin.system.codegen.basic.displayNameEn') }}
            </div>
            <Input
              v-model:value="displayNameEn"
              :placeholder="$t('admin.system.codegen.basic.displayNameEn')"
            />
          </div>
          <div>
            <div class="mb-1 text-[11px] font-medium text-muted-foreground">
              {{ $t('admin.system.codegen.basic.placeholder.resourcePlural') }}
            </div>
            <Input
              v-model:value="resourcePlural"
              :placeholder="
                $t('admin.system.codegen.basic.placeholder.resourcePlural')
              "
            />
          </div>

          <div
            class="flex min-w-0 flex-wrap items-center gap-3 rounded-xl border border-border/70 bg-background px-2.5 py-2"
          >
            <div>
              <div class="mb-1 text-[10px] font-medium text-muted-foreground">
                {{ $t('admin.system.codegen.builder.basicsEntryTitle') }}
              </div>
              <div class="flex flex-wrap gap-2">
                <Checkbox
                  :checked="hasAdmin"
                  @change="
                    (event) => onAdminChange(extractCheckboxChecked(event))
                  "
                >
                  {{ $t('admin.system.codegen.enum.admin') }}
                </Checkbox>
                <Checkbox
                  :checked="hasTenant"
                  @change="
                    (event) => onTenantChange(extractCheckboxChecked(event))
                  "
                >
                  {{ $t('admin.system.codegen.enum.tenant') }}
                </Checkbox>
              </div>
            </div>

            <div class="h-7 w-px bg-border/70"></div>

            <div>
              <div class="mb-1 text-[10px] font-medium text-muted-foreground">
                {{ $t('admin.system.codegen.builder.basicsViewTitle') }}
              </div>
              <Radio.Group v-model:value="feMode" size="small">
                <Radio value="table">
                  {{ $t('admin.system.codegen.frontend.table') }}
                </Radio>
                <Radio value="card">
                  {{ $t('admin.system.codegen.frontend.card') }}
                </Radio>
              </Radio.Group>
            </div>
          </div>
        </div>
      </div>
    </Card>

    <div
      v-if="validationErrors.length > 0"
      class="rounded-xl border border-amber-200 bg-amber-50/70 px-3 py-1.5"
    >
      <div class="mb-1.5 flex items-start justify-between gap-3">
        <div>
          <div
            class="flex items-center gap-2 text-sm font-semibold text-amber-800"
          >
            <IconifyIcon icon="lucide:triangle-alert" class="size-4" />
            <span>{{
              $t('admin.system.codegen.generate.validationErrors')
            }}</span>
          </div>
          <div class="mt-1 text-xs leading-5 text-amber-700/90">
            {{ $t('admin.system.codegen.builder.validationListHint') }}
          </div>
        </div>
        <Tag color="warning" class="!mr-0">
          {{ validationErrors.length }}
        </Tag>
      </div>

      <div class="grid max-h-36 gap-1.5 overflow-y-auto pr-1">
        <div
          v-for="(item, index) in validationErrors"
          :key="`${item.path}-${item.field}-${index}`"
          class="flex flex-col gap-2 rounded-lg border border-amber-200/80 bg-background/85 px-3 py-2 md:flex-row md:items-center md:justify-between"
        >
          <div class="min-w-0 flex-1">
            <div class="text-sm font-medium text-foreground">
              {{ item.message }}
            </div>
            <div
              class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground"
            >
              <span v-if="item.path">{{ item.path }}</span>
              <span v-if="item.field">{{ item.field }}</span>
            </div>
          </div>
          <Button size="small" @click="locateValidationIssue(item)">
            <IconifyIcon icon="lucide:locate-fixed" class="mr-1 size-4" />
            {{ $t('admin.system.codegen.builder.locateIssue') }}
          </Button>
        </div>
      </div>
    </div>

    <div
      class="grid gap-2.5 xl:grid-cols-[232px_minmax(0,1fr)_272px] 2xl:grid-cols-[244px_minmax(0,1fr)_288px]"
    >
      <div class="flex min-w-0 flex-col gap-3">
        <ComponentPalette @add="onPaletteAdd" />
      </div>

      <Card class="min-w-0" :body-style="{ padding: '0' }">
        <WysiwygCenter ref="wysiwygRef" class="min-w-0" />
      </Card>

      <Card class="min-w-0" :body-style="{ padding: '0' }">
        <template v-if="store.selectedFieldKey">
          <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
            <div
              class="shrink-0 border-b border-border px-3 py-2 text-xs font-medium text-muted-foreground"
            >
              {{ $t('admin.system.codegen.property.title') }}
            </div>
            <FieldPropertyPanel class="min-h-0 flex-1 overflow-y-auto" />
          </div>
        </template>
        <CodegenValidationPanel
          v-else
          :display-name="displayName"
          :expert-item-count="store.expertItemCount"
          :fe-mode="feMode"
          :field-count="store.fieldCount"
          :has-admin="hasAdmin"
          :has-tenant="hasTenant"
          :is-dirty="store.isDirty"
          :module-name="moduleVal"
          :preview-conflicts="previewConflictCount"
          :preview-summary="previewSummary"
          :preview-warnings="previewWarningCount"
          :resource="resource"
          :resource-plural="resourcePlural"
          :scope-count="scopeCount"
          :validation-error-count="validationErrors.length"
          @jump-errors="focusBuilderTop"
          @open-db-import="dbImportOpen = true"
          @open-expert="expertModalOpen = true"
          @open-import-yaml="onImportYaml"
          @open-preview="codePreviewOpen = true"
        />
      </Card>
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
          :placeholder="
            $t('admin.system.codegen.builder.importYamlPlaceholder')
          "
          :rows="12"
          class="font-mono text-sm"
        />
        <label
          class="inline-flex cursor-pointer items-center gap-1 text-sm text-muted-foreground underline"
        >
          <input
            type="file"
            accept=".yaml,.yml"
            class="sr-only"
            @change="onImportYamlFile"
          />
          <IconifyIcon icon="lucide:upload" class="size-4" />
          <span>{{
            $t('admin.system.codegen.builder.importYamlSelectFile')
          }}</span>
        </label>
      </div>
    </Modal>

    <Modal
      v-model:open="versionHistoryVisible"
      :title="$t('admin.system.codegen.builder.versionHistoryTitle')"
      :footer="null"
      width="520"
    >
      <div
        v-if="!isVersionLoading && versionList.length === 0"
        class="py-8 text-center text-muted-foreground"
      >
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
              <span class="text-sm">{{
                formatVersionTime(item.created_at)
              }}</span>
              <span v-if="item.note" class="text-xs text-muted-foreground">{{
                item.note
              }}</span>
            </div>
            <div class="flex gap-0">
              <Button
                type="link"
                size="small"
                :loading="versionPreviewLoadingIds.has(item.id)"
                @click="onPreviewVersion(item)"
              >
                {{ $t('admin.system.codegen.builder.versionPreview') }}
              </Button>
              <Button
                type="link"
                size="small"
                :loading="isRestoring"
                @click="onRestoreVersion(item)"
              >
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
      <div
        v-if="versionPreviewLoadingIds.size > 0"
        class="py-8 text-center text-muted-foreground"
      >
        {{ $t('common.loading') }}
      </div>
      <Input.TextArea
        v-else
        :value="versionPreviewContent"
        readonly
        :rows="18"
        class="font-mono text-sm"
      />
    </Modal>

    <Modal
      v-model:open="resultModalVisible"
      :title="$t('admin.system.codegen.generate.resultTitle')"
      :footer="null"
      width="520"
    >
      <template v-if="lastResult">
        <div
          v-if="lastResult.conflicts?.length && !lastResult.success"
          class="mb-4"
        >
          <Alert
            type="warning"
            show-icon
            :message="$t('admin.system.codegen.generate.partialWriteTitle')"
          >
            <template #description>
              <p class="mb-2">
                {{ $t('admin.system.codegen.generate.partialWriteDesc') }}
              </p>
              <ul class="list-inside list-disc text-sm">
                <li v-for="(c, i) in lastResult.conflicts" :key="i">
                  {{ formatConflictItem(c) }}
                </li>
              </ul>
            </template>
          </Alert>
        </div>
        <div v-if="lastResult.errors?.length" class="mb-4">
          <Alert type="error" :message="lastResult.errors.join(', ')" />
        </div>
        <div v-if="lastResult.migration" class="mb-4">
          <Alert
            :type="lastResult.migration.success ? 'success' : 'error'"
            :message="
              lastResult.migration.success
                ? lastResult.migration.message ||
                  $t('admin.system.codegen.generate.migrationSuccess')
                : lastResult.migration.error ||
                  $t('admin.system.codegen.generate.migrationFailed')
            "
            show-icon
          />
          <p
            v-if="lastResult.migration.migration_path"
            class="mt-1 text-xs text-muted-foreground"
          >
            {{ lastResult.migration.migration_path }}
          </p>
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
              <div
                v-for="p in lastResult.files_created"
                :key="`c-${p}`"
                class="text-green-600"
              >
                + {{ p }}
              </div>
              <div
                v-for="p in lastResult.files_modified"
                :key="`m-${p}`"
                class="text-amber-600"
              >
                ~ {{ p }}
              </div>
            </div>
          </CollapsePanel>
        </Collapse>
        <div class="mt-4 rounded border border-border p-3">
          <h5 class="mb-2 font-medium">
            {{ $t('admin.system.codegen.generate.nextSteps') }}
          </h5>
          <ul class="list-inside list-decimal space-y-1 text-sm">
            <li v-for="step in resultNextSteps" :key="step">
              {{ $t(`admin.system.codegen.generate.${step}`) }}
            </li>
          </ul>
        </div>
        <div class="mt-4 flex justify-end gap-2">
          <Button
            v-if="hasPreviewSnapshot"
            v-access:code="['action.codegen.preview']"
            type="primary"
            ghost
            @click="openPreviewFromResult"
          >
            {{ $t('admin.system.codegen.toolbar.preview') }}
          </Button>
          <Button @click="closeResultModal">
            {{ $t('common.close') }}
          </Button>
        </div>
      </template>
    </Modal>
  </Page>
</template>
