<script lang="ts" setup>
import type { PageOperation } from './page-operation-types';
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
  <div v-if="hasPageAI" class="flex w-full min-w-0 flex-col gap-1.5">
    <div
      data-testid="ai-panel-page-ai-card"
      class="page-ai-card border-border/18 relative flex min-h-[46px] w-full min-w-0 items-center overflow-hidden rounded-[20px] border px-2.5 py-1.5"
    >
      <div class="flex min-w-0 flex-1 items-center justify-between gap-1.5">
        <Tooltip :title="pageAIRailTooltip">
          <div
            data-testid="ai-panel-page-ai-trigger"
            class="flex min-w-0 flex-1 items-center gap-2 rounded-[16px] pr-1 transition-colors"
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
              class="flex size-[26px] shrink-0 items-center justify-center rounded-[14px] bg-primary/[0.07] text-primary ring-1 ring-primary/10"
            >
              <IconifyIcon icon="lucide:cpu" class="size-[11px] shrink-0" />
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex min-w-0 flex-wrap items-center gap-1">
                <span
                  class="text-muted-foreground/64 inline-flex shrink-0 items-center text-[8.5px] font-medium uppercase tracking-[0.1em]"
                >
                  {{ $t('common.aiPanel.pageAiSupported') }}
                </span>
                <span
                  v-if="fallbackOnly"
                  class="inline-flex shrink-0 items-center rounded-full bg-amber-500/10 px-1.5 py-[2px] text-[8px] font-semibold text-amber-700"
                >
                  {{ $t('common.aiPanel.pageAiFallbackBadge') }}
                </span>
                <span
                  v-if="operationCount > 0"
                  class="text-muted-foreground/74 inline-flex shrink-0 items-center rounded-full bg-muted/60 px-1.5 py-[2px] text-[8px] font-medium"
                >
                  {{ operationCount }}
                </span>
              </div>
              <div
                class="text-foreground/84 mt-0.5 truncate text-[10.75px] font-medium"
              >
                {{
                  resolvedPageAITitle || $t('common.aiPanel.pageAiSupported')
                }}
              </div>
              <div
                v-if="pageAISummary"
                class="text-muted-foreground/62 mt-0.5 truncate text-[9.5px]"
              >
                {{ pageAISummary }}
              </div>
            </div>
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
              class="text-foreground/68 border-border/24 bg-background/88 hover:border-border/42 inline-flex size-[26px] shrink-0 items-center justify-center rounded-[14px] border transition-colors hover:bg-muted/70"
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
        class="border-border/22 bg-background/96 w-full rounded-[20px] border px-2.5 py-2.5"
      >
        <div class="flex flex-col gap-2">
          <Tooltip v-if="pageAISummary" :title="pageAISummary">
            <div
              class="text-muted-foreground/66 whitespace-pre-wrap break-words text-[9.75px] leading-5"
              :title="pageAISummary"
            >
              {{ pageAISummary }}
            </div>
          </Tooltip>

          <div v-if="pageAIStatBadges.length > 0" class="flex flex-wrap gap-1">
            <span
              v-for="badge in pageAIStatBadges"
              :key="badge.key"
              class="inline-flex items-center rounded-full px-2 py-[2px] text-[9.5px] font-medium"
              :class="badge.className"
            >
              {{ badge.label }}
            </span>
          </div>

          <div
            v-if="diagnostics"
            data-testid="ai-panel-page-ai-diagnostics"
            class="rounded-[16px] border border-dashed border-border/30 bg-muted/[0.06] px-2.5 py-2"
          >
            <div class="text-[9.75px] font-medium text-muted-foreground">
              {{ $t('common.aiPanel.pageAiDiagnostics') }}
            </div>
            <div
              class="mt-1 space-y-1 text-[9.5px] leading-5 text-muted-foreground"
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
                  })
                }}
              </div>
              <div>
                {{
                  $t('common.aiPanel.pageAiDiagOps', {
                    current: diagnostics.interactablesCount,
                  })
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
                class="border-border/22 rounded-[16px] border bg-background px-2.5 py-2"
              >
                <div class="flex items-start justify-between gap-2">
                  <div class="min-w-0 flex-1">
                    <Tooltip :title="operation.label">
                      <div
                        class="truncate text-[10px] font-medium text-foreground"
                        :title="operation.label"
                      >
                        {{ operation.label }}
                      </div>
                    </Tooltip>
                    <Tooltip :title="operation.description || operation.name">
                      <div
                        class="text-muted-foreground/66 mt-0.5 truncate text-[9.5px] leading-5"
                        :title="operation.description || operation.name"
                      >
                        {{ operation.description || operation.name }}
                      </div>
                    </Tooltip>
                  </div>
                  <span
                    class="shrink-0 rounded-full px-2 py-[2px] text-[8px] font-semibold uppercase tracking-[0.12em]"
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
                class="border-border/36 flex min-h-[58px] items-center justify-center rounded-[16px] border border-dashed bg-muted/[0.08] px-3 py-2 text-center transition-colors hover:border-border hover:bg-muted/[0.16]"
                type="button"
                @click.stop="emit('expandAllOperations')"
              >
                <div>
                  <div
                    class="text-foreground/72 text-[12px] font-semibold leading-none"
                  >
                    +{{ pageAIRemainingOperationCount }}
                  </div>
                  <div
                    class="text-muted-foreground/68 mt-1 text-[9.5px] font-medium"
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
.page-ai-card {
  background: hsl(var(--background) / 0.985);
  box-shadow: 0 14px 28px -32px hsl(var(--foreground) / 0.12);
}

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
