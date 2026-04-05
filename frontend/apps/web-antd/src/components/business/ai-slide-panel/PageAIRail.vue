<script lang="ts" setup>
import type { PageOperation } from './page-operation-registry';
import type {
  PageAIDiagnostics,
  PageAIStatBadge,
} from './use-page-ai-capability';

import { IconifyIcon } from '@vben/icons';

import { Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

const props = withDefaults(
  defineProps<{
    detailsExpanded?: boolean;
    diagnostics?: null | PageAIDiagnostics;
    fallbackOnly?: boolean;
    hasExpandableDetails?: boolean;
    hasPageAI?: boolean;
    operationCount?: number;
    pageAIRailTooltip?: string;
    pageAIRemainingOperationCount?: number;
    pageAIStatBadges?: PageAIStatBadge[];
    pageAISummary?: string;
    pageAIVisibleOperations?: PageOperation[];
    resolvedPageAITitle?: string;
  }>(),
  {
    detailsExpanded: false,
    diagnostics: null,
    fallbackOnly: false,
    hasExpandableDetails: false,
    hasPageAI: false,
    operationCount: 0,
    pageAIRailTooltip: '',
    pageAIRemainingOperationCount: 0,
    pageAIStatBadges: () => [],
    pageAISummary: '',
    pageAIVisibleOperations: () => [],
    resolvedPageAITitle: '',
  },
);

const emit = defineEmits<{
  expandAllOperations: [];
  toggleDetails: [];
}>();

function onToggleDetails() {
  if (!props.hasExpandableDetails) {
    return;
  }
  emit('toggleDetails');
}
</script>

<template>
  <div v-if="hasPageAI" class="flex w-full min-w-0 flex-col gap-2">
    <div
      data-testid="ai-panel-page-ai-card"
      class="relative flex min-h-9 w-full min-w-0 items-center overflow-hidden rounded-xl border border-primary/15 bg-gradient-to-r from-primary/[0.08] via-background to-primary/[0.02] px-2 py-1"
    >
      <div class="flex min-w-0 flex-1 items-center justify-between gap-1.5">
        <Tooltip :title="pageAIRailTooltip">
          <div
            data-testid="ai-panel-page-ai-trigger"
            class="flex min-w-0 flex-1 items-center gap-1.5 rounded-lg pr-1 transition-colors"
            :class="
              hasExpandableDetails
                ? 'cursor-pointer hover:bg-primary/[0.05]'
                : ''
            "
            :aria-expanded="hasExpandableDetails ? detailsExpanded : undefined"
            :aria-label="hasExpandableDetails ? pageAIRailTooltip : undefined"
            :role="hasExpandableDetails ? 'button' : undefined"
            :tabindex="hasExpandableDetails ? 0 : undefined"
            @click="onToggleDetails"
            @keydown.enter.prevent="onToggleDetails"
            @keydown.space.prevent="onToggleDetails"
          >
            <div
              class="bg-primary/12 flex size-6 shrink-0 items-center justify-center rounded-lg text-primary"
            >
              <IconifyIcon icon="lucide:cpu" class="size-3" />
            </div>
            <span
              class="truncate text-[10px] font-semibold uppercase tracking-[0.14em] text-primary/75"
            >
              {{ $t('common.aiPanel.pageAiSupported') }}
            </span>
            <span
              v-if="fallbackOnly"
              class="inline-flex shrink-0 items-center rounded-full bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700"
            >
              {{ $t('common.aiPanel.pageAiFallbackBadge') }}
            </span>
            <span
              v-if="operationCount > 0"
              class="inline-flex shrink-0 items-center rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold text-primary"
            >
              {{ operationCount }}
            </span>
          </div>
        </Tooltip>
        <div
          class="flex shrink-0 items-center gap-1"
          @click.stop
          @keydown.enter.stop
          @keydown.space.stop
        >
          <slot name="actions"></slot>
          <Tooltip
            v-if="hasExpandableDetails"
            :title="
              detailsExpanded
                ? $t('common.aiPanel.pageAiCollapse')
                : $t('common.aiPanel.pageAiExpand')
            "
          >
            <button
              data-testid="ai-panel-page-ai-toggle"
              class="inline-flex size-7 shrink-0 items-center justify-center rounded-lg border border-border/45 bg-background/85 text-foreground transition-colors hover:border-primary/20 hover:bg-primary/[0.05]"
              :aria-expanded="detailsExpanded"
              :aria-label="
                detailsExpanded
                  ? $t('common.aiPanel.pageAiCollapse')
                  : $t('common.aiPanel.pageAiExpand')
              "
              type="button"
              @click.stop="emit('toggleDetails')"
            >
              <IconifyIcon
                icon="lucide:chevron-down"
                class="size-3 transition-transform duration-200"
                :class="detailsExpanded ? 'rotate-180' : ''"
              />
            </button>
          </Tooltip>
        </div>
      </div>
    </div>

    <Transition name="page-ai-details">
      <div
        v-if="detailsExpanded && hasExpandableDetails"
        data-testid="ai-panel-page-ai-details"
        class="w-full rounded-xl border border-primary/15 bg-background/85 px-2.5 py-2"
      >
        <div class="flex flex-col gap-2">
          <div class="flex min-w-0 items-start justify-between gap-2">
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-1.5">
                <span
                  class="text-[10px] font-semibold uppercase tracking-[0.14em] text-primary/75"
                >
                  {{ $t('common.aiPanel.pageAiSupported') }}
                </span>
                <span
                  v-if="fallbackOnly"
                  class="inline-flex items-center rounded-full bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700"
                >
                  {{ $t('common.aiPanel.pageAiFallbackBadge') }}
                </span>
                <span
                  v-if="operationCount > 0"
                  class="inline-flex items-center rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold text-primary"
                >
                  {{ operationCount }}
                </span>
              </div>
              <Tooltip :title="resolvedPageAITitle">
                <div
                  class="mt-1 truncate text-[11px] font-medium text-foreground"
                  :title="resolvedPageAITitle"
                >
                  {{ resolvedPageAITitle }}
                </div>
              </Tooltip>
              <Tooltip :title="pageAISummary">
                <div
                  class="mt-0.5 truncate text-[10px] leading-4 text-muted-foreground"
                  :title="pageAISummary"
                >
                  {{ pageAISummary }}
                </div>
              </Tooltip>
            </div>
          </div>

          <div
            v-if="pageAIStatBadges.length > 0"
            class="flex flex-wrap gap-1.5"
          >
            <span
              v-for="badge in pageAIStatBadges"
              :key="badge.key"
              class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium"
              :class="badge.className"
            >
              {{ badge.label }}
            </span>
          </div>

          <div
            v-if="diagnostics"
            data-testid="ai-panel-page-ai-diagnostics"
            class="rounded-lg border border-dashed border-border/60 bg-muted/20 px-2.5 py-2"
          >
            <div
              class="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground"
            >
              {{ $t('common.aiPanel.pageAiDiagnostics') }}
            </div>
            <div
              class="mt-1 space-y-1 text-[10px] leading-4 text-muted-foreground"
            >
              <div>
                {{
                  $t('common.aiPanel.pageAiDiagSource', {
                    source: diagnostics.source,
                  })
                }}
              </div>
              <div>
                {{
                  $t('common.aiPanel.pageAiDiagBudget', {
                    final: diagnostics.finalBytes,
                    hard: diagnostics.hardLimitBytes,
                    raw: diagnostics.rawBytes,
                    soft: diagnostics.softLimitBytes,
                  })
                }}
              </div>
              <div>
                {{
                  $t('common.aiPanel.pageAiDiagOps', {
                    current: diagnostics.finalOperationCount,
                    raw: diagnostics.rawOperationCount,
                  })
                }}
              </div>
              <div>
                {{
                  diagnostics.compressed
                    ? $t('common.aiPanel.pageAiDiagCompressionOn')
                    : $t('common.aiPanel.pageAiDiagCompressionOff')
                }}
              </div>
            </div>
          </div>

          <div
            v-if="pageAIVisibleOperations.length > 0"
            class="max-h-[208px] overflow-y-auto pr-1"
          >
            <div class="grid gap-1.5 sm:grid-cols-2">
              <div
                v-for="operation in pageAIVisibleOperations"
                :key="operation.name"
                data-testid="ai-panel-page-ai-preview-item"
                class="bg-background/78 rounded-lg border border-border/45 px-2.5 py-2 shadow-sm shadow-black/[0.03]"
              >
                <div class="flex items-start justify-between gap-2">
                  <div class="min-w-0 flex-1">
                    <Tooltip :title="operation.label">
                      <div
                        class="truncate text-[11px] font-medium text-foreground"
                        :title="operation.label"
                      >
                        {{ operation.label }}
                      </div>
                    </Tooltip>
                    <Tooltip :title="operation.description || operation.name">
                      <div
                        class="mt-0.5 truncate text-[10px] leading-4 text-muted-foreground"
                        :title="operation.description || operation.name"
                      >
                        {{ operation.description || operation.name }}
                      </div>
                    </Tooltip>
                  </div>
                  <span
                    class="shrink-0 rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em]"
                    :class="
                      operation.readonly
                        ? 'bg-blue-500/10 text-blue-700'
                        : 'bg-amber-500/10 text-amber-700'
                    "
                  >
                    {{
                      operation.readonly
                        ? $t('common.aiPanel.pageAiReadonlyLabel')
                        : $t('common.aiPanel.pageAiWritableLabel')
                    }}
                  </span>
                </div>
              </div>
              <button
                v-if="pageAIRemainingOperationCount > 0"
                data-testid="ai-panel-page-ai-more"
                class="flex min-h-[64px] items-center justify-center rounded-lg border border-dashed border-primary/20 bg-primary/[0.04] px-3 py-2 text-center transition-colors hover:border-primary/35 hover:bg-primary/[0.08]"
                type="button"
                @click.stop="emit('expandAllOperations')"
              >
                <div>
                  <div class="text-sm font-semibold leading-none text-primary">
                    +{{ pageAIRemainingOperationCount }}
                  </div>
                  <div
                    class="mt-1 text-[10px] font-medium uppercase tracking-[0.14em] text-primary/70"
                  >
                    {{ $t('common.aiPanel.pageAiPreviewMore') }}
                  </div>
                </div>
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.page-ai-details-enter-active,
.page-ai-details-leave-active {
  overflow: hidden;
  transition:
    opacity 0.22s ease,
    max-height 0.28s ease,
    transform 0.28s ease;
}

.page-ai-details-enter-from,
.page-ai-details-leave-to {
  max-height: 0;
  opacity: 0;
  transform: translateY(-6px);
}

.page-ai-details-enter-to,
.page-ai-details-leave-from {
  max-height: 320px;
  opacity: 1;
  transform: translateY(0);
}
</style>
