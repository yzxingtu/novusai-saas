<script lang="ts" setup>
import type {
  MonitoringConversationDetail,
  MonitoringProviderEvent,
  MonitoringRetryEvent,
  MonitoringRuntimeDiagnostics,
} from '../../api';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Card, Empty, Tag } from 'ant-design-vue';

import { getTurnFlowForDisplay } from '#/components/business/ai-chat-panel/chat-message-turn-flow';
import { $t } from '#/locales';
import {
  containsRetiredRuntimeDiagnosticValue,
  visibleRuntimeDiagnosticTokens,
} from '#/utils/ai-runtime-diagnostics';

import {
  asRecord,
  asRecordArray,
  asString,
  formatTagValue,
  formatTokens,
  hasEntries,
} from './helpers';
import { toMonitoringChatMessage } from './monitoring-chat-message-adapter';

defineOptions({ name: 'MonitoringConversationDiagnosticsCard' });

const props = defineProps<{
  detail: MonitoringConversationDetail;
  i18nPrefix: string;
}>();

function asOptionalString(value: unknown): string | undefined {
  const normalized = asString(value);
  return normalized || undefined;
}

function visibleDiagnosticTokens(value: unknown): string[] {
  return visibleRuntimeDiagnosticTokens(value);
}

function visibleDiagnosticText(value: unknown): string {
  return asString(value);
}

function formatVisibleTagValue(...values: unknown[]): string {
  const visibleValue = values.map((value) => asString(value)).find(Boolean);
  return visibleValue ? formatTagValue(visibleValue) : '';
}

function formatDiagnosticJson(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

function translateOption(
  group: string,
  value: null | string | undefined,
): string {
  const raw = asString(value);
  if (!raw) {
    return '-';
  }
  const key = `${props.i18nPrefix}.${group}.${raw}`;
  const translated = $t(key);
  return translated === key ? raw : translated;
}

const canonicalTurnFlowDiagnostics = computed(() => {
  for (
    let index = props.detail.message_list.length - 1;
    index >= 0;
    index -= 1
  ) {
    const normalizedMessage = toMonitoringChatMessage(
      props.detail.message_list[index]!,
    );
    if (!normalizedMessage.turnFlow) {
      continue;
    }
    const flow = getTurnFlowForDisplay(normalizedMessage);
    if (flow.timeline.length === 0) {
      continue;
    }
    const terminalStage = flow.timeline[flow.timeline.length - 1];
    const canonicalFailureKind =
      asOptionalString(flow.failureKind) ||
      ((flow.finalStageStatus === 'error' || flow.turnOutcome === 'failed') &&
      asOptionalString(flow.completionReason)
        ? asOptionalString(flow.completionReason)
        : undefined);
    return {
      completion_reason: asOptionalString(flow.completionReason),
      failure_kind: canonicalFailureKind,
      final_stage_status:
        asOptionalString(flow.finalStageStatus) ||
        asOptionalString(terminalStage?.status),
      turn_flow_complete:
        typeof flow.turnFlowComplete === 'boolean'
          ? flow.turnFlowComplete
          : undefined,
      turn_outcome: asOptionalString(flow.turnOutcome),
    };
  }
  return null;
});

const runtimeDiagnostics = computed<MonitoringRuntimeDiagnostics | null>(() => {
  const metadata = asRecord(props.detail.metadata);
  const contextDiagnostics =
    asRecord(props.detail.context_diagnostics) ||
    asRecord(metadata?.context_diagnostics);
  const lastRunSummary =
    asRecord(props.detail.last_run_summary) ||
    asRecord(metadata?.last_run_summary);
  const merged = {
    ...contextDiagnostics,
    ...lastRunSummary,
  } as MonitoringRuntimeDiagnostics;
  const canonical = canonicalTurnFlowDiagnostics.value;
  if (canonical?.failure_kind) {
    merged.failure_kind = canonical.failure_kind;
  }
  if (canonical?.completion_reason) {
    merged.partial_exit_reason = canonical.completion_reason;
  }
  if (canonical?.final_stage_status) {
    merged.final_stage_status = canonical.final_stage_status;
  }
  if (canonical?.turn_outcome) {
    merged.turn_outcome = canonical.turn_outcome;
  }
  if (typeof canonical?.turn_flow_complete === 'boolean') {
    merged.turn_flow_complete = canonical.turn_flow_complete;
  }
  return hasEntries(merged) ? merged : null;
});

const providerEvents = computed<MonitoringProviderEvent[]>(() =>
  asRecordArray<MonitoringProviderEvent>(
    runtimeDiagnostics.value?.provider_events,
  ).filter((event) => !containsRetiredRuntimeDiagnosticValue(event)),
);

const retryEvents = computed<MonitoringRetryEvent[]>(() =>
  asRecordArray<MonitoringRetryEvent>(runtimeDiagnostics.value?.retry_events),
);

const candidateToolNames = computed(() =>
  visibleDiagnosticTokens(runtimeDiagnostics.value?.candidate_tool_names),
);

const diagnosticsSummary = computed(() => {
  const diagnostics = runtimeDiagnostics.value;
  if (!diagnostics) {
    return [];
  }
  const summaryItems = [
    {
      key: 'path',
      label: $t(`${props.i18nPrefix}.executionPath`),
      value: translateOption(
        'executionPathOptions',
        diagnostics.execution_path,
      ),
    },
    {
      key: 'failure',
      label: $t(`${props.i18nPrefix}.failureKind`),
      value: translateOption('failureKindOptions', diagnostics.failure_kind),
    },
    {
      key: 'budget',
      label: $t(`${props.i18nPrefix}.budgetStatus`),
      value: translateOption('budgetStatusOptions', diagnostics.budget_status),
    },
    {
      key: 'budgetExitReason',
      label: $t(`${props.i18nPrefix}.budgetExitReason`),
      value: visibleDiagnosticText(diagnostics.budget_exit_reason),
    },
    {
      key: 'providerEvents',
      label: $t(`${props.i18nPrefix}.providerEvents`),
      value: formatTokens(providerEvents.value.length),
    },
    {
      key: 'retryEvents',
      label: $t(`${props.i18nPrefix}.retryEvents`),
      value: formatTokens(retryEvents.value.length),
    },
  ];
  return summaryItems.filter((item) => item.value && item.value !== '-');
});

const diagnosticsDetailRows = computed(() => {
  const diagnostics = runtimeDiagnostics.value;
  if (!diagnostics) {
    return [];
  }
  return [
    {
      key: 'budgetExitReason',
      label: $t(`${props.i18nPrefix}.budgetExitReason`),
      value: visibleDiagnosticText(diagnostics.budget_exit_reason),
    },
    {
      key: 'partialExitReason',
      label: $t(`${props.i18nPrefix}.partialExitReason`),
      value: visibleDiagnosticText(diagnostics.partial_exit_reason),
    },
  ].filter((item) => item.value);
});
</script>

<template>
  <Card class="monitoring-card mt-4" :bordered="false">
    <template #title>
      <div class="monitoring-card__title">
        <IconifyIcon class="size-4" icon="lucide:workflow" />
        <span>{{ $t(`${i18nPrefix}.runtimeDiagnostics`) }}</span>
      </div>
    </template>

    <Empty
      v-if="!runtimeDiagnostics"
      :description="$t(`${i18nPrefix}.diagnosticsEmpty`)"
    />

    <template v-else>
      <div class="monitoring-diagnostics-summary">
        <article
          v-for="item in diagnosticsSummary"
          :key="item.key"
          class="monitoring-diagnostics-summary__item"
        >
          <div class="monitoring-overview-label">{{ item.label }}</div>
          <div class="monitoring-overview-value">{{ item.value }}</div>
        </article>
      </div>

      <div v-if="diagnosticsDetailRows.length > 0" class="mt-4">
        <div class="monitoring-card__subtitle">
          {{ $t(`${i18nPrefix}.diagnosticNotes`) }}
        </div>
        <div class="monitoring-overview-grid mt-3">
          <div
            v-for="item in diagnosticsDetailRows"
            :key="item.key"
            class="monitoring-overview-item"
          >
            <div class="monitoring-overview-label">{{ item.label }}</div>
            <div class="monitoring-overview-value">{{ item.value }}</div>
          </div>
        </div>
      </div>

      <div class="mt-4">
        <section class="monitoring-diagnostics-panel">
          <div class="monitoring-card__subtitle">
            {{ $t(`${i18nPrefix}.candidateTools`) }}
          </div>
          <div
            v-if="candidateToolNames.length > 0"
            class="monitoring-tag-list mt-3"
          >
            <Tag v-for="tool in candidateToolNames" :key="tool" color="purple">
              {{ tool }}
            </Tag>
          </div>
          <Empty
            v-else
            class="mt-3"
            :description="$t(`${i18nPrefix}.diagnosticsEmpty`)"
          />

          <div class="monitoring-card__subtitle mt-5">
            {{ $t(`${i18nPrefix}.providerEvents`) }}
          </div>
          <Empty
            v-if="providerEvents.length === 0"
            class="mt-3"
            :description="$t(`${i18nPrefix}.diagnosticsEmpty`)"
          />
          <div v-else class="mt-3 space-y-3">
            <article
              v-for="(event, index) in providerEvents"
              :key="`${event.kind || 'provider'}-${index}`"
              class="monitoring-diagnostics-event"
            >
              <div class="monitoring-diagnostics-intent__head">
                <Tag
                  v-if="
                    formatVisibleTagValue(
                      event.kind,
                      event.provider_failure_kind,
                    )
                  "
                  color="orange"
                >
                  {{
                    formatVisibleTagValue(
                      event.kind,
                      event.provider_failure_kind,
                    )
                  }}
                </Tag>
                <span
                  v-if="visibleDiagnosticText(event.stage)"
                  class="text-xs text-muted-foreground"
                >
                  {{ visibleDiagnosticText(event.stage) }}
                </span>
              </div>
              <pre class="monitoring-diagnostics-json">{{
                formatDiagnosticJson(event)
              }}</pre>
            </article>
          </div>

          <div class="monitoring-card__subtitle mt-5">
            {{ $t(`${i18nPrefix}.retryEvents`) }}
          </div>
          <Empty
            v-if="retryEvents.length === 0"
            class="mt-3"
            :description="$t(`${i18nPrefix}.diagnosticsEmpty`)"
          />
          <div v-else class="mt-3 space-y-3">
            <article
              v-for="(event, index) in retryEvents"
              :key="`${event.kind || 'retry'}-${index}`"
              class="monitoring-diagnostics-event"
            >
              <div class="monitoring-diagnostics-intent__head">
                <Tag
                  v-if="formatVisibleTagValue(event.kind, event.reason)"
                  color="gold"
                >
                  {{ formatVisibleTagValue(event.kind, event.reason) }}
                </Tag>
                <span
                  v-if="event.attempt != null"
                  class="text-xs text-muted-foreground"
                >
                  #{{ event.attempt }}
                </span>
              </div>
              <pre class="monitoring-diagnostics-json">{{
                formatDiagnosticJson(event)
              }}</pre>
            </article>
          </div>
        </section>
      </div>
    </template>
  </Card>
</template>
