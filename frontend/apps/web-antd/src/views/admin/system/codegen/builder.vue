<script lang="ts" setup>
/**
 * 代码生成器三栏可视化构建器 / Codegen Visual Builder
 *
 * 三栏布局: 组件面板 | 字段卡片列表 | 属性面板 + 表单预览
 */
import type { CodegenConfigInfo, PreviewResult } from '#/api/admin/codegen';

import { computed, defineAsyncComponent, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Badge,
  Button,
  Card,
  Checkbox,
  Dropdown,
  Input,
  Menu,
  MenuItem,
  Radio,
  Select,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { getCodegenConfigDetailApi } from '#/api/admin/codegen';
import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';

import { useCodegenBuilderFieldWorkspace } from './composables/use-codegen-builder-field-workspace';
import { useCodegenBuilderPage } from './composables/use-codegen-builder-page';
import { useCodegenBuilderScope } from './composables/use-codegen-builder-scope';
import { useCodegenBuilderWorkflows } from './composables/use-codegen-builder-workflows';
import BuilderValidationBanner from './sections/BuilderValidationBanner.vue';
import BuilderWorkflowDialogs from './sections/BuilderWorkflowDialogs.vue';

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

const expertModalOpen = ref(false);
const dbImportOpen = ref(false);
const validationErrors = ref<
  Array<{ code: string; field: string; message: string; path: string }>
>([]);
const configMeta = ref<CodegenConfigInfo | null>(null);

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

const {
  commonModuleOptions,
  displayName,
  displayNameEn,
  feMode,
  hasAdmin,
  hasTenant,
  loadModules,
  moduleVal,
  normalizedModuleOptions,
  onAdminChange,
  onResourceChange,
  onTenantChange,
  resource,
  resourcePlural,
  scopeCount,
} = useCodegenBuilderScope();

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

function extractCheckboxChecked(event: unknown): boolean {
  return Boolean(
    (event as { target?: { checked?: boolean } })?.target?.checked ?? false,
  );
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

const {
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
} = useCodegenBuilderWorkflows({
  configId,
  configMeta,
  refreshConfigMeta,
  router,
  setPreviewSnapshot,
  store,
  validationErrors,
});

const presetQuery = computed(() => route.query.preset as string | undefined);
const watchedRouteId = computed(() => route.params.id);

const { fields } = useCodegenBuilderPage({
  configId,
  configMeta,
  isNewMode,
  loadModules,
  onSave,
  resourceInputRef,
  routeId: watchedRouteId,
  router,
  store,
  watchPresetQuery: presetQuery,
});

const { focusBuilderTop, locateValidationIssue, onDbImported, onPaletteAdd } =
  useCodegenBuilderFieldWorkspace({
    builderTopRef,
    dbImportOpen,
    fields,
    resourceInputRef,
    store,
    wysiwygRef,
  });
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

    <BuilderValidationBanner
      :validation-errors="validationErrors"
      @locate="locateValidationIssue"
    />

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
    <BuilderWorkflowDialogs
      :close-result-modal="closeResultModal"
      :format-conflict-item="formatConflictItem"
      :format-version-time="formatVersionTime"
      :has-preview-snapshot="hasPreviewSnapshot"
      :import-yaml-text="importYamlText"
      :import-yaml-visible="importYamlVisible"
      :is-importing="isImporting"
      :is-restoring="isRestoring"
      :is-version-loading="isVersionLoading"
      :last-result="lastResult"
      :on-confirm-import-yaml="onConfirmImportYaml"
      :on-import-yaml-file="onImportYamlFile"
      :on-preview-version="onPreviewVersion"
      :on-restore-version="onRestoreVersion"
      :open-preview-from-result="openPreviewFromResult"
      :result-modal-visible="resultModalVisible"
      :result-next-steps="resultNextSteps"
      :version-history-visible="versionHistoryVisible"
      :version-list="versionList"
      :version-preview-content="versionPreviewContent"
      :version-preview-loading-ids="versionPreviewLoadingIds"
      :version-preview-note="versionPreviewNote"
      :version-preview-visible="versionPreviewVisible"
      @update:import-yaml-text="importYamlText = $event"
      @update:import-yaml-visible="importYamlVisible = $event"
      @update:result-modal-visible="resultModalVisible = $event"
      @update:version-history-visible="versionHistoryVisible = $event"
      @update:version-preview-visible="versionPreviewVisible = $event"
    />
  </Page>
</template>
