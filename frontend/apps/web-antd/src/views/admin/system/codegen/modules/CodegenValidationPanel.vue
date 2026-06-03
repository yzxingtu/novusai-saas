<script lang="ts" setup>
/**
 * Codegen builder empty-side panel / Codegen 构建器空状态检查面板
 *
 * 当未选中字段时，用于展示当前配置摘要、预览摘要与下一步动作。
 */
import { IconifyIcon } from '@vben/icons';

defineProps<{
  displayName?: string;
  expertItemCount: number;
  feMode: string;
  fieldCount: number;
  hasAdmin: boolean;
  hasTenant: boolean;
  isDirty: boolean;
  moduleName?: string;
  previewConflicts: number;
  previewSummary?: null | {
    backend_files: number;
    create_count: number;
    frontend_files: number;
    modify_count: number;
    total_lines: number;
  };
  previewWarnings: number;
  resource?: string;
  resourcePlural?: string;
  scopeCount: number;
  validationErrorCount: number;
}>();

const emit = defineEmits<{
  jumpErrors: [];
  openDbImport: [];
  openExpert: [];
  openImportYaml: [];
  openPreview: [];
}>();
</script>

<template>
  <div class="flex h-full flex-col overflow-y-auto bg-background">
    <div class="border-b border-border px-3 py-2">
      <div class="flex items-center justify-between gap-2">
        <div class="flex flex-wrap items-center gap-1.5">
          <span
            class="rounded-full px-2 py-0.5 text-[11px] font-medium"
            :class="
              isDirty
                ? 'bg-amber-100 text-amber-700'
                : 'bg-emerald-100 text-emerald-700'
            "
          >
            {{
              isDirty
                ? $t('admin.system.codegen.builder.unsavedChanges')
                : $t('admin.system.codegen.builder.savedState')
            }}
          </span>
          <span
            class="rounded-full px-2 py-0.5 text-[11px] font-medium"
            :class="
              hasAdmin
                ? 'bg-sky-100 text-sky-700'
                : 'bg-muted text-muted-foreground'
            "
          >
            {{ $t('admin.system.codegen.enum.admin') }}
          </span>
          <span
            class="rounded-full px-2 py-0.5 text-[11px] font-medium"
            :class="
              hasTenant
                ? 'bg-emerald-100 text-emerald-700'
                : 'bg-muted text-muted-foreground'
            "
          >
            {{ $t('admin.system.codegen.enum.tenant') }}
          </span>
          <span
            class="rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground"
          >
            {{
              feMode === 'card'
                ? $t('admin.system.codegen.frontend.card')
                : $t('admin.system.codegen.frontend.table')
            }}
          </span>
          <span
            class="rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground"
          >
            {{ $t('admin.system.codegen.builder.metricFields') }}
            {{ fieldCount }}
          </span>
          <span
            class="rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground"
          >
            {{ $t('admin.system.codegen.builder.metricAdvanced') }}
            {{ expertItemCount }}
          </span>
          <span
            v-if="validationErrorCount > 0"
            class="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-700"
          >
            {{ $t('admin.system.codegen.builder.metricErrors') }}
            {{ validationErrorCount }}
          </span>
        </div>
        <button
          type="button"
          class="shrink-0 text-xs font-medium text-primary transition-colors hover:text-primary/80"
          @click="emit('openPreview')"
        >
          {{ $t('admin.system.codegen.toolbar.preview') }}
        </button>
      </div>
    </div>

    <div class="flex flex-col gap-2 p-2.5">
      <section
        class="rounded-xl border border-border/70 bg-muted/10 px-3 py-2.5"
      >
        <div class="grid gap-1.5 text-sm">
          <div class="grid grid-cols-[84px_minmax(0,1fr)] items-center gap-2">
            <span class="text-xs text-muted-foreground">
              {{ $t('admin.system.codegen.builder.panelResource') }}
            </span>
            <span class="truncate font-mono text-foreground">
              {{ resource || '—' }}
            </span>
          </div>
          <div class="grid grid-cols-[84px_minmax(0,1fr)] items-center gap-2">
            <span class="text-xs text-muted-foreground">
              {{ $t('admin.system.codegen.builder.panelDisplayName') }}
            </span>
            <span class="truncate text-foreground">{{
              displayName || '—'
            }}</span>
          </div>
          <div class="grid grid-cols-[84px_minmax(0,1fr)] items-center gap-2">
            <span class="text-xs text-muted-foreground">
              {{ $t('admin.system.codegen.builder.panelModule') }}
            </span>
            <span class="truncate text-foreground">{{
              moduleName || '—'
            }}</span>
          </div>
          <div class="grid grid-cols-[84px_minmax(0,1fr)] items-center gap-2">
            <span class="text-xs text-muted-foreground">
              {{ $t('admin.system.codegen.builder.panelResourcePlural') }}
            </span>
            <span class="truncate text-foreground">
              {{ resourcePlural || '—' }}
            </span>
          </div>
        </div>
      </section>

      <section
        v-if="previewSummary || previewWarnings > 0 || previewConflicts > 0"
        class="rounded-xl border border-border/70 bg-muted/10 px-3 py-2.5"
      >
        <div class="mb-2 text-[11px] font-medium text-muted-foreground">
          {{ $t('admin.system.codegen.builder.panelPreviewTitle') }}
        </div>
        <div class="grid grid-cols-2 gap-2">
          <div v-if="previewSummary" class="rounded-lg bg-background px-3 py-2">
            <div class="text-[11px] text-muted-foreground">
              {{ $t('admin.system.codegen.builder.previewCreateFiles') }}
            </div>
            <div class="mt-1 text-base font-semibold text-foreground">
              {{ previewSummary.create_count }}
            </div>
          </div>
          <div v-if="previewSummary" class="rounded-lg bg-background px-3 py-2">
            <div class="text-[11px] text-muted-foreground">
              {{ $t('admin.system.codegen.builder.previewModifyFiles') }}
            </div>
            <div class="mt-1 text-base font-semibold text-foreground">
              {{ previewSummary.modify_count }}
            </div>
          </div>
          <div v-if="previewSummary" class="rounded-lg bg-background px-3 py-2">
            <div class="text-[11px] text-muted-foreground">
              {{ $t('admin.system.codegen.preview.filterBackend') }}
            </div>
            <div class="mt-1 text-base font-semibold text-foreground">
              {{ previewSummary.backend_files }}
            </div>
          </div>
          <div v-if="previewSummary" class="rounded-lg bg-background px-3 py-2">
            <div class="text-[11px] text-muted-foreground">
              {{ $t('admin.system.codegen.preview.filterFrontend') }}
            </div>
            <div class="mt-1 text-base font-semibold text-foreground">
              {{ previewSummary.frontend_files }}
            </div>
          </div>
          <div class="rounded-lg bg-background px-3 py-2">
            <div class="text-[11px] text-muted-foreground">
              {{ $t('admin.system.codegen.preview.warnings') }}
            </div>
            <div
              class="mt-1 text-base font-semibold"
              :class="
                previewWarnings > 0 ? 'text-amber-600' : 'text-foreground'
              "
            >
              {{ previewWarnings }}
            </div>
          </div>
          <div class="rounded-lg bg-background px-3 py-2">
            <div class="text-[11px] text-muted-foreground">
              {{ $t('admin.system.codegen.preview.filterConflicts') }}
            </div>
            <div
              class="mt-1 text-base font-semibold"
              :class="
                previewConflicts > 0 ? 'text-rose-600' : 'text-foreground'
              "
            >
              {{ previewConflicts }}
            </div>
          </div>
        </div>
      </section>

      <section
        class="rounded-xl border border-border/70 bg-muted/10 px-3 py-2.5"
      >
        <div class="mb-2 text-[11px] font-medium text-muted-foreground">
          {{ $t('admin.system.codegen.builder.panelActionsTitle') }}
        </div>
        <div class="grid gap-1.5">
          <button
            type="button"
            class="flex items-center justify-between rounded-lg border border-border bg-background px-3 py-2 text-left transition-colors hover:border-primary/30 hover:bg-primary/5"
            @click="emit('openExpert')"
          >
            <span class="flex min-w-0 items-center gap-2">
              <IconifyIcon
                icon="lucide:settings-2"
                class="size-4 text-muted-foreground"
              />
              <span class="text-sm font-medium text-foreground">
                {{ $t('admin.system.codegen.advanced.button') }}
              </span>
            </span>
            <span class="text-xs text-muted-foreground">
              {{ expertItemCount }}
            </span>
          </button>

          <button
            type="button"
            class="flex items-center justify-between rounded-lg border border-border bg-background px-3 py-2 text-left transition-colors hover:border-primary/30 hover:bg-primary/5"
            @click="emit('openDbImport')"
          >
            <span class="flex min-w-0 items-center gap-2">
              <IconifyIcon
                icon="lucide:database"
                class="size-4 text-muted-foreground"
              />
              <span class="text-sm font-medium text-foreground">
                {{ $t('admin.system.codegen.builder.dbImportBtn') }}
              </span>
            </span>
          </button>

          <button
            type="button"
            class="flex items-center justify-between rounded-lg border border-border bg-background px-3 py-2 text-left transition-colors hover:border-primary/30 hover:bg-primary/5"
            @click="emit('openImportYaml')"
          >
            <span class="flex min-w-0 items-center gap-2">
              <IconifyIcon
                icon="lucide:upload"
                class="size-4 text-muted-foreground"
              />
              <span class="text-sm font-medium text-foreground">
                {{ $t('admin.system.codegen.builder.importYaml') }}
              </span>
            </span>
          </button>

          <button
            v-if="validationErrorCount > 0"
            type="button"
            class="flex items-center justify-between rounded-lg border border-amber-200 bg-amber-50/70 px-3 py-2 text-left transition-colors hover:bg-amber-50"
            @click="emit('jumpErrors')"
          >
            <span class="flex min-w-0 items-center gap-2">
              <IconifyIcon
                icon="lucide:triangle-alert"
                class="size-4 text-amber-700"
              />
              <span class="text-sm font-medium text-amber-800">
                {{ $t('admin.system.codegen.generate.validationErrors') }}
              </span>
            </span>
            <span class="text-xs font-semibold text-amber-800">
              {{ validationErrorCount }}
            </span>
          </button>
        </div>
      </section>
    </div>
  </div>
</template>
