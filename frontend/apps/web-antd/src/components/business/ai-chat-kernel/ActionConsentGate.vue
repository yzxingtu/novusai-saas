<script lang="ts" setup>
import type { KernelPendingActionState } from './TurnFlowState';

import type {
  ToolApprovalPresentation,
  ToolApprovalPresentationDetail,
  ToolApprovalPresentationTarget,
} from '#/types/ai-chat';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { $t } from '#/locales';

const props = withDefaults(
  defineProps<{
    action?: KernelPendingActionState | null;
    compact?: boolean;
  }>(),
  {
    action: null,
    compact: false,
  },
);

const emit = defineEmits<{
  approve: [];
  reject: [];
}>();

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function hasEntries(value: unknown): value is Record<string, unknown> {
  return isRecord(value) && Object.keys(value).length > 0;
}

function stringFromAliases(
  value: Record<string, unknown> | undefined,
  aliases: string[],
): string | undefined {
  if (!value) {
    return undefined;
  }
  for (const alias of aliases) {
    const raw = value[alias];
    if (typeof raw === 'string') {
      const trimmed = raw.trim();
      if (trimmed.length > 0) {
        return trimmed;
      }
    }
    if (typeof raw === 'number' || typeof raw === 'boolean') {
      return String(raw);
    }
  }
  return undefined;
}

function formatDisplayValue(value: unknown): string {
  if (value === null || value === undefined) {
    return '';
  }
  if (typeof value === 'string') {
    return value.trim();
  }
  if (
    typeof value === 'number' ||
    typeof value === 'boolean' ||
    typeof value === 'bigint'
  ) {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function collectDetails(
  presentation: ToolApprovalPresentation,
): ToolApprovalPresentationDetail[] {
  const rawDetails =
    [
      presentation.safeDetails,
      presentation.safe_details,
      presentation.details,
      presentation.detailFields,
      presentation.detail_fields,
    ].find((items) => Array.isArray(items) && items.length > 0) || [];
  if (!Array.isArray(rawDetails)) {
    return [];
  }
  return rawDetails.filter((item): item is ToolApprovalPresentationDetail => {
    return isRecord(item) && item.sensitive !== true;
  });
}

const presentation = computed(() => {
  return props.action?.kind === 'confirmation'
    ? props.action.approvalPresentation
    : undefined;
});

const presentationRecord = computed(() => {
  return isRecord(presentation.value)
    ? (presentation.value as Record<string, unknown>)
    : undefined;
});

const presentationTitle = computed(() => {
  return stringFromAliases(presentationRecord.value, [
    'title',
    'actionLabel',
    'action_label',
  ]);
});

const presentationSummary = computed(() => {
  return stringFromAliases(presentationRecord.value, ['summary']);
});

const actionLabel = computed(() => {
  if (presentationTitle.value) {
    return presentationTitle.value;
  }
  if (props.action?.operationLabel) {
    return props.action.operationLabel;
  }
  if (props.action?.toolName) {
    return props.action.toolName;
  }
  return props.action?.action || props.action?.table || '';
});

const actionDescription = computed(() => {
  if (presentationSummary.value) {
    return presentationSummary.value;
  }
  if (props.action?.operationDescription) {
    return props.action.operationDescription;
  }
  if (props.action?.table && props.action?.action) {
    return `${props.action.table} · ${props.action.action}`;
  }
  return props.action?.table || '';
});

const presentationMetaItems = computed(() => {
  const record = presentationRecord.value;
  if (!record) {
    return [];
  }
  const riskLevel =
    stringFromAliases(record, ['riskLevel', 'risk_level'])?.toLowerCase() ||
    undefined;
  return [
    {
      key: 'operation',
      label: $t('common.globalAiChat.approvalOperationType'),
      value: stringFromAliases(record, ['operationType', 'operation_type']),
    },
    {
      key: 'business',
      label: $t('common.globalAiChat.approvalBusinessArea'),
      value: stringFromAliases(record, [
        'businessAreaLabel',
        'business_area_label',
        'businessArea',
        'business_area',
      ]),
    },
    {
      key: 'menu',
      label: $t('common.globalAiChat.approvalMenu'),
      value: stringFromAliases(record, ['menuLabel', 'menu_label']),
    },
    {
      key: 'permission',
      label: $t('common.globalAiChat.approvalPermissionCode'),
      value: stringFromAliases(record, ['permissionCode', 'permission_code']),
    },
    {
      key: 'risk',
      label: $t('common.globalAiChat.approvalRiskLevel'),
      tone: riskLevel,
      value:
        stringFromAliases(record, ['riskLabel', 'risk_label']) ||
        stringFromAliases(record, ['riskLevel', 'risk_level']),
    },
  ].filter((item) => item.value);
});

const riskToneClass = (tone?: string) => {
  if (tone === 'high') {
    return 'border-red-500/25 bg-red-500/10 text-red-600 dark:text-red-400';
  }
  if (tone === 'medium') {
    return 'border-amber-500/25 bg-amber-500/10 text-amber-600 dark:text-amber-400';
  }
  if (tone === 'low') {
    return 'border-emerald-500/25 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400';
  }
  return 'border-border/40 bg-accent/40 text-muted-foreground';
};

const presentationTarget = computed(() => {
  const explicitTarget =
    stringFromAliases(presentationRecord.value, [
      'targetText',
      'target_text',
    ]) ||
    stringFromAliases(presentationRecord.value, [
      'targetLabel',
      'target_label',
    ]);
  if (explicitTarget) {
    return explicitTarget;
  }
  const rawTarget = presentation.value?.target;
  if (typeof rawTarget === 'string') {
    return rawTarget.trim();
  }
  if (!isRecord(rawTarget)) {
    return '';
  }
  const target = rawTarget as ToolApprovalPresentationTarget;
  const targetType = stringFromAliases(target, ['type', 'kind']);
  const targetName =
    stringFromAliases(target, ['name', 'label', 'value', 'id']) ||
    formatDisplayValue(target);
  if (targetType && targetName) {
    return `${targetType} · ${targetName}`;
  }
  return targetName;
});

const presentationDetails = computed(() => {
  if (!presentation.value) {
    return [];
  }
  return collectDetails(presentation.value)
    .map((item, index) => {
      const label =
        stringFromAliases(item, ['label', 'name', 'key']) ||
        `${$t('common.globalAiChat.approvalDetail')} ${index + 1}`;
      const value = formatDisplayValue(
        item.valueText ??
          item.value_text ??
          item.displayValue ??
          item.display_value ??
          item.value,
      );
      return { key: `${label}-${index}`, label, value };
    })
    .filter((item) => item.label && item.value);
});

const fallbackPreviewEntries = computed(() => {
  if (presentation.value || !hasEntries(props.action?.preview)) {
    return [];
  }
  return Object.entries(props.action.preview);
});

const technicalPayload = computed(() => {
  const candidate =
    presentation.value?.technical ||
    presentation.value?.technicalDetails ||
    presentation.value?.technical_details;
  if (hasEntries(candidate)) {
    return candidate;
  }
  return presentation.value && hasEntries(props.action?.preview)
    ? props.action.preview
    : undefined;
});

const consentArguments = computed(() => {
  return hasEntries(props.action?.arguments)
    ? props.action.arguments
    : undefined;
});

const titleKey = computed(() =>
  props.action?.kind === 'confirmation'
    ? 'common.globalAiChat.confirmationTitle'
    : 'common.globalAiChat.consentTitle',
);

const approveKey = computed(() =>
  props.action?.kind === 'confirmation'
    ? 'common.globalAiChat.confirmBtn'
    : 'common.globalAiChat.consentAllow',
);

const rejectKey = computed(() =>
  props.action?.kind === 'confirmation'
    ? 'common.globalAiChat.rejectBtn'
    : 'common.globalAiChat.consentDeny',
);

const resolvedLabel = computed(() => {
  if (!props.action?.resolved) {
    return '';
  }
  if (props.action.kind === 'confirmation') {
    return $t('common.globalAiChat.confirmationResolved');
  }
  if (props.action.rejected) {
    return $t('common.globalAiChat.consentRejected');
  }
  if (props.action.autoApproved) {
    return $t('common.globalAiChat.consentAutoApproved');
  }
  return $t('common.globalAiChat.consentApproved');
});
</script>

<template>
  <div
    v-if="action"
    data-testid="chat-message-kernel-consent"
    class="overflow-hidden rounded-lg border"
    :class="[
      compact ? 'mb-1.5' : 'mb-2',
      action.resolved
        ? 'border-border/20 bg-accent/10'
        : 'border-warning/30 bg-warning/5',
    ]"
  >
    <div
      class="flex min-w-0 items-center gap-1.5 border-b border-border/20 text-muted-foreground"
      :class="compact ? 'px-2.5 py-1.5 text-[11px]' : 'px-3 py-2 text-xs'"
    >
      <IconifyIcon
        :icon="
          action.kind === 'confirmation'
            ? 'lucide:shield-question'
            : action.resolved
              ? 'lucide:shield-check'
              : 'lucide:shield-alert'
        "
        class="shrink-0"
        :class="compact ? 'size-3' : 'size-3.5'"
      />
      <span class="min-w-0 break-words font-medium">{{ $t(titleKey) }}</span>
      <span
        v-if="action.resolved"
        class="ml-auto inline-flex shrink-0 items-center rounded-full px-1.5 py-[1px] text-[10px] font-medium"
        :class="
          action.rejected
            ? 'bg-red-500/10 text-red-500'
            : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
        "
      >
        {{ resolvedLabel }}
      </span>
    </div>

    <div :class="compact ? 'space-y-2 px-2.5 py-2' : 'space-y-2.5 px-3 py-2.5'">
      <div class="min-w-0 space-y-1">
        <p
          v-if="actionLabel"
          class="break-words font-medium text-foreground/90"
          :class="compact ? 'text-[11px]' : 'text-xs'"
        >
          {{ actionLabel }}
        </p>
        <p
          v-if="actionDescription"
          class="break-words text-muted-foreground/80"
          :class="compact ? 'text-[11px]' : 'text-xs'"
        >
          {{ actionDescription }}
        </p>
        <p
          v-if="action.skillName"
          class="text-muted-foreground/75"
          :class="compact ? 'text-[10px]' : 'text-[11px]'"
        >
          {{ action.skillName }}
        </p>
      </div>

      <div
        v-if="presentationMetaItems.length > 0"
        data-testid="approval-presentation-meta"
        class="flex min-w-0 flex-wrap gap-1.5"
      >
        <span
          v-for="item in presentationMetaItems"
          :key="item.key"
          class="inline-flex min-w-0 max-w-full items-center gap-1 rounded-md border px-1.5 py-0.5"
          :class="[
            compact ? 'text-[10px]' : 'text-[11px]',
            item.key === 'risk'
              ? riskToneClass(item.tone)
              : 'border-border/40 bg-accent/40 text-muted-foreground',
          ]"
        >
          <span class="shrink-0 text-muted-foreground/70">
            {{ item.label }}
          </span>
          <span class="min-w-0 break-words font-medium text-foreground/80">
            {{ item.value }}
          </span>
        </span>
      </div>

      <div
        v-if="presentationTarget"
        data-testid="approval-presentation-target"
        class="min-w-0 rounded-md border border-border/40 bg-accent/30 px-2 py-1.5"
        :class="compact ? 'text-[10px]' : 'text-[11px]'"
      >
        <span class="text-muted-foreground/70">
          {{ $t('common.globalAiChat.approvalTarget') }}
        </span>
        <span class="ml-1 break-words font-medium text-foreground/80">
          {{ presentationTarget }}
        </span>
      </div>

      <dl
        v-if="presentationDetails.length > 0"
        data-testid="approval-presentation-details"
        class="min-w-0 divide-y divide-border/30 overflow-hidden rounded-md border border-border/40 bg-accent/30"
        :class="compact ? 'text-[10px]' : 'text-[11px]'"
      >
        <div
          v-for="item in presentationDetails"
          :key="item.key"
          class="grid min-w-0 grid-cols-[minmax(0,0.42fr)_minmax(0,0.58fr)] gap-2 px-2 py-1.5"
        >
          <dt class="min-w-0 break-words font-medium text-foreground/70">
            {{ item.label }}
          </dt>
          <dd class="min-w-0 break-words text-muted-foreground">
            {{ item.value }}
          </dd>
        </div>
      </dl>

      <div
        v-if="fallbackPreviewEntries.length > 0"
        data-testid="approval-fallback-preview"
        class="overflow-y-auto rounded-md bg-accent/50"
        :class="
          compact
            ? 'max-h-32 px-2 py-1.5 text-[10px]'
            : 'max-h-40 px-3 py-2 text-xs'
        "
      >
        <table class="w-full table-fixed text-left">
          <tr
            v-for="[key, value] in fallbackPreviewEntries"
            :key="String(key)"
            class="border-b border-border/30 last:border-0"
          >
            <td
              class="w-[38%] break-words py-0.5 pr-3 align-top font-medium text-foreground/70"
            >
              {{ key }}
            </td>
            <td class="break-words py-0.5 text-muted-foreground">
              {{ typeof value === 'object' ? JSON.stringify(value) : value }}
            </td>
          </tr>
        </table>
      </div>

      <details
        v-if="technicalPayload"
        data-testid="approval-technical-details"
        class="[&>summary::-webkit-details-marker]:hidden [&>summary]:list-none"
      >
        <summary
          class="flex cursor-pointer items-center gap-1 text-muted-foreground/70 hover:text-muted-foreground"
          :class="compact ? 'text-[10px]' : 'text-[11px]'"
        >
          <IconifyIcon icon="lucide:code" class="size-3" />
          {{ $t('common.globalAiChat.approvalTechnicalDetails') }}
        </summary>
        <pre
          class="mt-1 max-h-24 overflow-y-auto whitespace-pre-wrap rounded bg-accent/40 px-1.5 py-1 font-mono text-[10px] text-muted-foreground"
          >{{ JSON.stringify(technicalPayload, null, 2) }}</pre
        >
      </details>

      <details
        v-if="consentArguments"
        class="[&>summary::-webkit-details-marker]:hidden [&>summary]:list-none"
      >
        <summary
          class="flex cursor-pointer items-center gap-1 text-muted-foreground/70 hover:text-muted-foreground"
          :class="compact ? 'text-[10px]' : 'text-[11px]'"
        >
          <IconifyIcon icon="lucide:code" class="size-3" />
          {{ $t('common.globalAiChat.consentShowArgs') }}
        </summary>
        <pre
          class="mt-1 max-h-24 overflow-y-auto whitespace-pre-wrap rounded bg-accent/40 px-1.5 py-1 font-mono text-[10px] text-muted-foreground"
          >{{ JSON.stringify(consentArguments, null, 2) }}</pre
        >
      </details>

      <div v-if="!action.resolved" class="flex items-center gap-2">
        <button
          class="inline-flex items-center gap-1 rounded-md bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
          @click="emit('approve')"
        >
          <IconifyIcon icon="lucide:check" class="size-3" />
          {{ $t(approveKey) }}
        </button>
        <button
          class="inline-flex items-center gap-1 rounded-md border border-border/60 px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive"
          @click="emit('reject')"
        >
          <IconifyIcon icon="lucide:x" class="size-3" />
          {{ $t(rejectKey) }}
        </button>
      </div>
    </div>
  </div>
</template>
