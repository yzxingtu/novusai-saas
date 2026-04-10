import type { Ref } from 'vue';
import type { Router } from 'vue-router';

import type {
  CodegenConfigInfo,
  CodegenVersionItem,
  PreviewResult,
} from '#/api/admin/codegen';

import { computed, h, ref } from 'vue';

import { Checkbox, message, Modal } from 'ant-design-vue';
import yaml from 'js-yaml';

import {
  createCodegenConfigApi,
  downloadCodegenPreviewZipApi,
  getCodegenConfigVersionApi,
  getCodegenConfigVersionsApi,
  postCodegenConfigRestoreVersionApi,
  postCodegenGenerateApi,
  postCodegenPreviewApi,
  postCodegenValidateApi,
  updateCodegenConfigApi,
} from '#/api/admin/codegen';
import { $t } from '#/locales';
import { formatRelativeTime } from '#/utils/common';
import { downloadText } from '#/utils/download';

type ValidationErrorItem = {
  code: string;
  field: string;
  message: string;
  path: string;
};

export type GenerateResultPayload = {
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
};

type GenerateNextStepKey =
  | 'checkMigration'
  | 'migrationAlreadyApplied'
  | 'migrationNoChanges'
  | 'restartIfNeeded'
  | 'reviewCode'
  | 'runMigration';

type BuilderStoreLike = {
  configId: null | number;
  configJson: Record<string, unknown>;
  fieldCount: number;
  loadConfig: (id: null | number, json: Record<string, unknown>) => void;
  saveConfig: (id: number, json: Record<string, unknown>) => void;
};

type UseCodegenBuilderWorkflowsOptions = {
  configId: Ref<null | number>;
  configMeta: Ref<CodegenConfigInfo | null>;
  refreshConfigMeta: (targetId?: null | number) => Promise<void>;
  router: Router;
  setPreviewSnapshot: (preview: PreviewResult) => void;
  store: BuilderStoreLike;
  validationErrors: Ref<ValidationErrorItem[]>;
};

function extractCheckboxChecked(event: unknown): boolean {
  return Boolean(
    (event as { target?: { checked?: boolean } })?.target?.checked,
  );
}

export function useCodegenBuilderWorkflows(
  options: UseCodegenBuilderWorkflowsOptions,
) {
  const codePreviewOpen = ref(false);
  const importYamlVisible = ref(false);
  const importYamlText = ref('');
  const isGenerating = ref(false);
  const isImporting = ref(false);
  const isPreparingGenerate = ref(false);
  const isRestoring = ref(false);
  const isSaving = ref(false);
  const isVersionLoading = ref(false);
  const lastResult = ref<GenerateResultPayload | null>(null);
  const resultModalVisible = ref(false);
  const versionHistoryVisible = ref(false);
  const versionList = ref<CodegenVersionItem[]>([]);
  const versionPreviewContent = ref('');
  const versionPreviewLoadingIds = ref<Set<number>>(new Set());
  const versionPreviewNote = ref('');
  const versionPreviewVisible = ref(false);

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

  async function buildGeneratePreviewSnapshot() {
    const preview = await postCodegenPreviewApi({
      config_json: options.store.configJson,
    });
    options.setPreviewSnapshot(preview);
    return preview;
  }

  async function onSave() {
    const json = options.store.configJson;
    const resource = (json.resource as string) || '';
    const module = (json.module as string) || '';
    const displayName = (json.display_name as string) || '';
    if (!resource.trim()) {
      message.warning($t('admin.system.codegen.validation.resource_required'));
      return;
    }
    if (!module.trim()) {
      message.warning($t('admin.system.codegen.validation.module_required'));
      return;
    }
    if (!displayName.trim()) {
      message.warning(
        $t('admin.system.codegen.validation.display_name_required'),
      );
      return;
    }

    try {
      const validation = await postCodegenValidateApi({
        config_json: json,
        mode: 'draft',
      });
      if (!validation.valid) {
        options.validationErrors.value = validation.errors ?? [];
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
      const displayNameEn = (json.display_name_en as string) || resource;

      if (
        options.store.configId !== null &&
        options.store.configId !== undefined
      ) {
        const updated = await updateCodegenConfigApi(options.store.configId, {
          config_json: json,
          display_name: displayName,
          display_name_en: displayNameEn,
          module,
          name,
          resource,
        });
        options.store.saveConfig(options.store.configId, json);
        options.configMeta.value = updated;
        options.validationErrors.value = [];
        message.success($t('admin.system.codegen.messages.saveSuccess'));
        return;
      }

      const created = await createCodegenConfigApi({
        config_json: json,
        display_name: displayName,
        display_name_en: displayNameEn,
        module,
        name,
        resource,
      });
      options.store.saveConfig(created.id, created.config_json || json);
      options.configMeta.value = created;
      options.validationErrors.value = [];
      message.success($t('admin.system.codegen.messages.saveSuccess'));
      await options.router.replace(`/admin/system/codegen/${created.id}/edit`);
    } catch {
      message.error($t('common.failed'));
    } finally {
      isSaving.value = false;
    }
  }

  async function doGenerate(force = false) {
    options.validationErrors.value = [];
    try {
      const validation = await postCodegenValidateApi({
        config_json: options.store.configJson,
        mode: 'generate',
      });
      if (!validation.valid) {
        options.validationErrors.value = validation.errors ?? [];
        message.warning($t('admin.system.codegen.generate.validateFirst'));
        return;
      }

      const payload =
        options.store.configId === null || options.store.configId === undefined
          ? { auto_migrate: true, config_json: options.store.configJson, force }
          : { auto_migrate: true, config_id: options.store.configId, force };
      const result = await postCodegenGenerateApi(payload);
      lastResult.value = result;
      resultModalVisible.value = true;

      if (
        (options.store.configId === null ||
          options.store.configId === undefined) &&
        result.config_id !== null &&
        result.config_id !== undefined
      ) {
        options.store.loadConfig(result.config_id, options.store.configJson);
        await options.router.replace(
          `/admin/system/codegen/${result.config_id}/edit`,
        );
      }

      await options.refreshConfigMeta(
        result.config_id ?? options.store.configId ?? options.configId.value,
      );

      if (result.success) {
        message.success($t('admin.system.codegen.messages.generateSuccess'));
      } else if (result.errors?.length) {
        message.error(result.errors.join('; '));
      }
    } catch (error) {
      message.error(
        error instanceof Error ? error.message : $t('common.failed'),
      );
    } finally {
      isGenerating.value = false;
    }
  }

  async function onGenerate() {
    const resource = (options.store.configJson.resource as string) || '';
    const forceGenerate = ref(false);
    isPreparingGenerate.value = true;
    try {
      const preview = await buildGeneratePreviewSnapshot();
      const summary = preview.summary ?? {
        backend_files: 0,
        create_count: 0,
        frontend_files: 0,
        modify_count: 0,
        total_lines: 0,
      };
      const conflicts = preview.conflicts?.length ?? 0;
      const warnings = preview.warnings?.length ?? 0;

      Modal.confirm({
        content: h('div', { class: 'flex flex-col gap-3' }, [
          h(
            'p',
            { class: 'm-0 text-sm text-muted-foreground' },
            $t('admin.system.codegen.builder.generateConfirmContent', {
              resource,
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
                h('div', { class: 'font-mono font-medium' }, resource || '-'),
              ]),
              h('div', [
                h(
                  'div',
                  { class: 'text-xs text-muted-foreground' },
                  $t('admin.system.codegen.builder.metricFields'),
                ),
                h(
                  'div',
                  { class: 'font-medium' },
                  String(options.store.fieldCount),
                ),
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
                      warnings > 0
                        ? 'font-medium text-amber-600'
                        : 'font-medium',
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
        okType: conflicts > 0 ? 'danger' : 'primary',
        onOk: async () => {
          isGenerating.value = true;
          await doGenerate(forceGenerate.value);
        },
        title: $t('admin.system.codegen.builder.generateConfirmTitle'),
        width: 560,
      });
    } catch {
      Modal.confirm({
        content: h('div', { class: 'flex flex-col gap-3' }, [
          h(
            'p',
            { class: 'm-0 text-sm text-muted-foreground' },
            $t('admin.system.codegen.builder.generateConfirmContent', {
              resource,
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
        title: $t('admin.system.codegen.builder.generateConfirmTitle'),
      });
    } finally {
      isPreparingGenerate.value = false;
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

  function onExportYaml() {
    const json = options.store.configJson;
    if (!json || Object.keys(json).length === 0) {
      message.warning($t('admin.system.codegen.builder.exportEmpty'));
      return;
    }
    const content = yaml.dump(json, { indent: 2, lineWidth: -1 });
    const name = (json.resource as string) || 'codegen';
    downloadText(content, {
      filename: `${name}.yaml`,
      mimeType: 'text/x-yaml',
    });
    message.success($t('shared.common.exportSuccess'));
  }

  function onImportYaml() {
    importYamlText.value = '';
    importYamlVisible.value = true;
  }

  function onImportYamlFile(event: Event) {
    const input = event.target as HTMLInputElement;
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
    if (
      typeof parsed !== 'object' ||
      parsed === null ||
      Array.isArray(parsed)
    ) {
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
        const msgs = (result.errors ?? [])
          .map((item) => item.message)
          .filter(Boolean);
        message.error(
          msgs.join('; ') ||
            $t('admin.system.codegen.builder.importYamlValidateError'),
        );
        return;
      }
      options.configMeta.value = null;
      options.store.loadConfig(null, parsed);
      options.validationErrors.value = [];
      importYamlVisible.value = false;
      message.success($t('admin.system.codegen.builder.importYamlSuccess'));
    } catch {
      message.error($t('common.failed'));
    } finally {
      isImporting.value = false;
    }
  }

  async function onOpenVersionHistory() {
    const id = options.configId.value;
    if (!id) return;
    versionHistoryVisible.value = true;
    isVersionLoading.value = true;
    try {
      versionList.value = await getCodegenConfigVersionsApi(id);
    } catch {
      message.error($t('common.failed'));
      versionHistoryVisible.value = false;
    } finally {
      isVersionLoading.value = false;
    }
  }

  async function onRestoreVersion(version: CodegenVersionItem) {
    const id = options.configId.value;
    if (!id || !version.id) return;
    Modal.confirm({
      onOk: async () => {
        isRestoring.value = true;
        try {
          const restored = await postCodegenConfigRestoreVersionApi(
            id,
            version.id,
          );
          options.store.loadConfig(restored.id, restored.config_json || {});
          options.validationErrors.value = [];
          versionHistoryVisible.value = false;
          message.success(
            $t('admin.system.codegen.builder.versionRestoreSuccess'),
          );
          message.info(
            $t('admin.system.codegen.builder.versionRestoreUndoCleared'),
          );
        } catch {
          message.error($t('common.failed'));
        } finally {
          isRestoring.value = false;
        }
      },
      title: $t('admin.system.codegen.builder.versionRestoreConfirm'),
    });
  }

  function formatVersionTime(iso: null | string) {
    return formatRelativeTime(iso) ?? '-';
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

  async function onPreviewVersion(version: CodegenVersionItem) {
    const id = options.configId.value;
    if (!id || !version.id) return;
    versionPreviewVisible.value = true;
    versionPreviewNote.value =
      version.note || formatVersionTime(version.created_at) || '';
    versionPreviewLoadingIds.value = new Set([
      version.id,
      ...versionPreviewLoadingIds.value,
    ]);
    versionPreviewContent.value = '';
    try {
      const result = await getCodegenConfigVersionApi(id, version.id);
      const json = result?.config_json ?? {};
      versionPreviewContent.value = yaml.dump(json, {
        indent: 2,
        lineWidth: -1,
      });
    } catch {
      message.error($t('common.failed'));
      versionPreviewVisible.value = false;
    } finally {
      versionPreviewLoadingIds.value = new Set(
        [...versionPreviewLoadingIds.value].filter(
          (item) => item !== version.id,
        ),
      );
    }
  }

  async function onDownloadZip() {
    try {
      await downloadCodegenPreviewZipApi(
        { config_json: options.store.configJson },
        { step: undefined },
      );
      message.success($t('admin.system.codegen.messages.downloadSuccess'));
    } catch (error) {
      const detail = (
        error as {
          response?: { data?: { detail?: string | { error?: string } } };
        }
      )?.response?.data?.detail;
      const msg =
        (typeof detail === 'object' && detail?.error) ||
        (typeof detail === 'string' ? detail : null) ||
        $t('admin.system.codegen.messages.downloadFail');
      message.error(msg);
    }
  }

  return {
    closeResultModal,
    codePreviewOpen,
    formatConflictItem,
    formatVersionTime,
    importYamlText,
    importYamlVisible,
    isGenerating,
    isImporting,
    isPreparingGenerate,
    isRestoring,
    isSaving,
    isVersionLoading,
    lastResult,
    onConfirmImportYaml,
    onDownloadZip,
    onExportYaml,
    onGenerate,
    onImportYaml,
    onImportYamlFile,
    onOpenVersionHistory,
    onPreviewVersion,
    onRestoreVersion,
    onSave,
    openPreviewFromResult,
    resultModalVisible,
    resultNextSteps,
    versionHistoryVisible,
    versionList,
    versionPreviewContent,
    versionPreviewLoadingIds,
    versionPreviewNote,
    versionPreviewVisible,
  };
}
