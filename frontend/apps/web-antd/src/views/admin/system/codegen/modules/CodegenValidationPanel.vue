<script lang="ts" setup>
/**
 * Codegen builder empty-side panel / Codegen 构建器空状态检查面板
 *
 * 当未选中字段时，用于展示当前配置摘要、预览摘要与下一步动作。
 */
const props = defineProps<{
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
    <div class="border-b border-border px-4 py-3">
      <div class="flex items-center justify-between gap-2">
        <div class="text-sm font-semibold text-foreground">
          {{ $t('admin.system.codegen.builder.panelTitle') }}
        </div>
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
      </div>
      <div class="mt-2 flex flex-wrap gap-1.5">
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
          {{ $t('admin.system.codegen.builder.metricFields') }} {{ fieldCount }}
        </span>
        <span
          class="rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground"
        >
          {{ $t('admin.system.codegen.builder.metricScopes') }} {{ scopeCount }}
        </span>
        <span
          class="rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground"
        >
          {{ $t('admin.system.codegen.builder.metricAdvanced') }}
          {{ expertItemCount }}
        </span>
        <span
          class="rounded-full px-2 py-0.5 text-[11px] font-medium"
          :class="
            validationErrorCount > 0
              ? 'bg-amber-100 text-amber-700'
              : 'bg-muted text-muted-foreground'
          "
        >
          {{ $t('admin.system.codegen.builder.metricErrors') }}
          {{ validationErrorCount }}
        </span>
      </div>
    </div>

    <div class="flex flex-col gap-3 p-3">
      <section class="rounded-xl border border-border/70 bg-muted/10 px-3 py-3">
        <div
          class="mb-2 text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground"
        >
          {{ $t('admin.system.codegen.builder.panelConfigTitle') }}
        </div>
        <div class="grid gap-2 text-sm">
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

      <section class="rounded-xl border border-border/70 bg-muted/10 px-3 py-3">
        <div class="mb-3 flex items-center justify-between">
          <div class="text-sm font-medium text-foreground">
            {{ $t('admin.system.codegen.builder.panelPreviewTitle') }}
          </div>
          <button
            type="button"
            class="text-xs font-medium text-primary transition-colors hover:text-primary/80"
            @click="emit('openPreview')"
          >
            {{ $t('admin.system.codegen.toolbar.preview') }}
          </button>
        </div>

        <div v-if="previewSummary" class="grid grid-cols-2 gap-2">
          <div class="rounded-lg bg-background px-3 py-2.5">
            <div class="text-[11px] text-muted-foreground">
              {{ $t('admin.system.codegen.builder.previewCreateFiles') }}
            </div>
            <div class="mt-1 text-base font-semibold text-foreground">
              {{ previewSummary.create_count }}
            </div>
          </div>
          <div class="rounded-lg bg-background px-3 py-2.5">
            <div class="text-[11px] text-muted-foreground">
              {{ $t('admin.system.codegen.builder.previewModifyFiles') }}
            </div>
            <div class="mt-1 text-base font-semibold text-foreground">
              {{ previewSummary.modify_count }}
            </div>
          </div>
          <div class="rounded-lg bg-background px-3 py-2.5">
            <div class="text-[11px] text-muted-foreground">
              {{ $t('admin.system.codegen.preview.filterBackend') }}
            </div>
            <div class="mt-1 text-base font-semibold text-foreground">
              {{ previewSummary.backend_files }}
            </div>
          </div>
          <div class="rounded-lg bg-background px-3 py-2.5">
            <div class="text-[11px] text-muted-foreground">
              {{ $t('admin.system.codegen.preview.filterFrontend') }}
            </div>
            <div class="mt-1 text-base font-semibold text-foreground">
              {{ previewSummary.frontend_files }}
            </div>
          </div>
          <div class="rounded-lg bg-background px-3 py-2.5">
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
          <div class="rounded-lg bg-background px-3 py-2.5">
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
        <div
          v-else
          class="rounded-lg border border-dashed border-border bg-background px-3 py-4 text-center text-xs leading-5 text-muted-foreground"
        >
          {{ $t('admin.system.codegen.builder.panelPreviewEmpty') }}
        </div>
      </section>

      <section class="grid gap-2">
        <div
          class="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground"
        >
          {{ $t('admin.system.codegen.builder.panelActionsTitle') }}
        </div>
        <div class="grid gap-2">
          <button
            type="button"
            class="flex items-center justify-between rounded-xl border border-border bg-muted/10 px-3 py-2.5 text-left transition-colors hover:bg-muted/50"
            @click="emit('openExpert')"
          >
            <span class="text-sm font-medium text-foreground">
              {{ $t('admin.system.codegen.advanced.button') }}
            </span>
            <span class="text-sm font-semibold text-foreground">
              {{ expertItemCount }}
            </span>
          </button>

          <button
            type="button"
            class="flex items-center justify-between rounded-xl border border-border bg-muted/10 px-3 py-2.5 text-left transition-colors hover:bg-muted/50"
            @click="emit('openDbImport')"
          >
            <span class="text-sm font-medium text-foreground">
              {{ $t('admin.system.codegen.builder.dbImportBtn') }}
            </span>
          </button>

          <button
            type="button"
            class="flex items-center justify-between rounded-xl border border-border bg-muted/10 px-3 py-2.5 text-left transition-colors hover:bg-muted/50"
            @click="emit('openImportYaml')"
          >
            <span class="text-sm font-medium text-foreground">
              {{ $t('admin.system.codegen.builder.importYaml') }}
            </span>
          </button>

          <button
            v-if="validationErrorCount > 0"
            type="button"
            class="flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50/70 px-3 py-2.5 text-left transition-colors hover:bg-amber-50"
            @click="emit('jumpErrors')"
          >
            <span class="text-sm font-medium text-amber-800">
              {{ $t('admin.system.codegen.generate.validationErrors') }}
            </span>
            <span class="text-sm font-semibold text-amber-800">
              {{ validationErrorCount }}
            </span>
          </button>
        </div>
      </section>
    </div>
  </div>
</template>
