<script lang="ts" setup>
import type {
  RichTextAIApplyMode,
  RichTextAIApplyTarget,
  RichTextAITask,
  RichTextDraftRuntimeState,
} from './types';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

const props = withDefaults(
  defineProps<{
    compact?: boolean;
    state?: null | RichTextDraftRuntimeState;
    task: RichTextAITask;
  }>(),
  {
    compact: false,
    state: null,
  },
);

const emit = defineEmits<{
  apply: [target: RichTextAIApplyTarget, mode: RichTextAIApplyMode];
  copy: [mode: RichTextAIApplyMode];
  discard: [];
  undo: [];
}>();

const modeLabels: Record<RichTextAIApplyMode, string> = {
  formatted: $t('common.aiWithFormat'),
  plain: $t('common.aiPlainText'),
};

const targetLabels: Record<RichTextAIApplyTarget, string> = {
  append_to_end: $t('common.appendContent'),
  insert_after_selection: $t('common.richTextInsertAfterSelection'),
  replace_selection: $t('common.richTextReplaceSelection'),
};

const stateLabels: Record<RichTextAITask['state'], string> = {
  applied: $t('common.richTextDraftStateApplied'),
  queued: $t('common.richTextDraftStateQueued'),
  ready: $t('common.richTextDraftStateReady'),
  undone: $t('common.richTextDraftStateUndone'),
};

const availableModes = computed<RichTextAIApplyMode[]>(() => {
  const modes: RichTextAIApplyMode[] =
    props.task.availableModes.length > 0
      ? props.task.availableModes
      : ['plain', 'formatted'];
  const normalized: RichTextAIApplyMode[] = [];
  for (const mode of modes) {
    if (!normalized.includes(mode)) {
      normalized.push(mode);
    }
  }
  return normalized;
});

const lastAppliedMode = computed(
  () => props.state?.lastApplyMode ?? props.task.lastAppliedMode ?? null,
);
const lastAppliedTarget = computed(
  () => props.state?.lastApplyTarget ?? props.task.lastAppliedTarget ?? null,
);

function resolveSelectedMode() {
  const preferredMode =
    lastAppliedMode.value ?? props.task.preferredApplyMode ?? 'plain';
  if (availableModes.value.includes(preferredMode)) {
    return preferredMode;
  }
  return availableModes.value[0] ?? 'plain';
}

const selectedMode = ref<RichTextAIApplyMode>(resolveSelectedMode());

watch(
  () =>
    [
      availableModes.value.join('|'),
      props.state?.lastApplyMode,
      props.task.lastAppliedMode,
      props.task.preferredApplyMode,
      props.task.taskId,
    ] as const,
  (nextValue, previousValue) => {
    const shouldResync =
      !previousValue ||
      nextValue[0] !== previousValue[0] ||
      nextValue[1] !== previousValue[1] ||
      nextValue[2] !== previousValue[2] ||
      nextValue[3] !== previousValue[3] ||
      nextValue[4] !== previousValue[4];
    if (shouldResync || !availableModes.value.includes(selectedMode.value)) {
      selectedMode.value = resolveSelectedMode();
    }
  },
  { immediate: true },
);

const modeOptions = computed(() =>
  availableModes.value.map((mode) => ({
    label: modeLabels[mode],
    value: mode,
  })),
);

const isInteractive = computed(() => !!props.state);

const applyActions = computed(() =>
  (
    [
      'replace_selection',
      'insert_after_selection',
      'append_to_end',
    ] satisfies RichTextAIApplyTarget[]
  ).map((target) => ({
    disabled: !canApply(target),
    hint: getApplyHint(target),
    label: targetLabels[target],
    target,
  })),
);

const statusDetail = computed(() => {
  const parts: string[] = [];
  if (props.task.state === 'applied' || props.task.state === 'undone') {
    if (lastAppliedTarget.value) {
      parts.push(targetLabels[lastAppliedTarget.value]);
    }
    if (lastAppliedMode.value) {
      parts.push(modeLabels[lastAppliedMode.value]);
    }
  } else {
    parts.push(modeLabels[selectedMode.value]);
  }
  return parts.join(' / ');
});

const hasDisabledApplyAction = computed(() =>
  applyActions.value.some((action) => action.disabled),
);

function getStateLabel() {
  return stateLabels[props.task.state];
}

function getApplyHint(target: RichTextAIApplyTarget) {
  if (canApply(target)) {
    return '';
  }
  return props.state?.helperText?.trim() ?? '';
}

function onCopy() {
  emit('copy', selectedMode.value);
}

function getModeButtonType(mode: RichTextAIApplyMode) {
  if (selectedMode.value !== mode) {
    return 'text';
  }
  return mode === 'formatted' ? 'primary' : 'default';
}

function canApply(target: RichTextAIApplyTarget) {
  if (!isInteractive.value) {
    return false;
  }
  const targetStateMap: Record<RichTextAIApplyTarget, boolean> = {
    append_to_end: props.state?.canAppendToEnd ?? false,
    insert_after_selection: props.state?.canInsertAfterSelection ?? false,
    replace_selection: props.state?.canReplaceSelection ?? false,
  };
  return targetStateMap[target];
}
</script>

<template>
  <div
    data-testid="rich-text-draft-card"
    class="overflow-hidden rounded-lg border border-primary/20 bg-primary/5"
    :class="compact ? 'mt-1.5' : 'mt-2'"
  >
    <div
      class="flex items-start gap-2 border-b border-primary/10 px-3 py-2"
      :class="compact ? 'text-[11px]' : 'text-xs'"
    >
      <IconifyIcon
        icon="lucide:file-pen-line"
        class="mt-0.5 size-3.5 shrink-0 text-primary"
      />
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2">
          <span class="truncate font-medium text-foreground">
            {{ task.title || $t('common.richTextEditor') }}
          </span>
          <span
            class="shrink-0 rounded-full bg-primary/10 px-1.5 py-px text-[10px] font-medium text-primary"
          >
            {{ getStateLabel() }}
          </span>
        </div>
        <p v-if="statusDetail" class="mt-0.5 text-[10px] text-primary/75">
          {{ statusDetail }}
        </p>
        <p
          v-if="task.summary"
          class="mt-0.5 line-clamp-2 text-muted-foreground/80"
        >
          {{ task.summary }}
        </p>
        <p
          v-if="task.selectionLabel"
          class="mt-0.5 text-[10px] text-muted-foreground/70"
        >
          {{ task.selectionLabel }}
        </p>
        <p
          v-if="state?.helperText && hasDisabledApplyAction"
          class="mt-1 text-[10px] text-muted-foreground/70"
        >
          {{ state.helperText }}
        </p>
      </div>
    </div>

    <div class="px-3 py-2.5">
      <div
        v-if="modeOptions.length > 0"
        class="grid gap-2"
        :class="compact ? 'grid-cols-2 text-[11px]' : 'grid-cols-2 text-xs'"
      >
        <Button
          v-for="mode in modeOptions"
          :key="mode.value"
          size="small"
          :block="compact"
          :type="getModeButtonType(mode.value)"
          :data-testid="`rich-text-mode-${mode.value}`"
          @click="selectedMode = mode.value"
        >
          {{ mode.label }}
        </Button>
      </div>

      <div
        class="mt-2"
        :class="
          compact ? 'grid gap-1.5 text-[11px]' : 'flex flex-wrap gap-2 text-xs'
        "
      >
        <template v-for="action in applyActions" :key="action.target">
          <Tooltip v-if="action.hint" :title="action.hint">
            <span :class="compact ? 'w-full' : 'inline-flex'">
              <Button
                size="small"
                :block="compact"
                :disabled="action.disabled"
                :data-testid="`rich-text-apply-${action.target}`"
                @click="emit('apply', action.target, selectedMode)"
              >
                {{ action.label }}
              </Button>
            </span>
          </Tooltip>
          <Button
            v-else
            size="small"
            :block="compact"
            :disabled="action.disabled"
            :data-testid="`rich-text-apply-${action.target}`"
            @click="emit('apply', action.target, selectedMode)"
          >
            {{ action.label }}
          </Button>
        </template>
      </div>

      <div
        class="mt-2"
        :class="
          compact
            ? 'grid grid-cols-3 gap-1.5 text-[11px]'
            : 'flex flex-wrap gap-2 text-xs'
        "
      >
        <Button
          size="small"
          :block="compact"
          :disabled="!state?.canUndo"
          data-testid="rich-text-undo"
          @click="emit('undo')"
        >
          {{ $t('common.undo') }}
        </Button>
        <Button
          size="small"
          :block="compact"
          :disabled="state ? !state.canCopy : false"
          data-testid="rich-text-copy"
          @click="onCopy"
        >
          {{ $t('common.copy') }}
        </Button>
        <Button
          size="small"
          :block="compact"
          :disabled="!isInteractive"
          data-testid="rich-text-discard"
          @click="emit('discard')"
        >
          {{ $t('common.discard') }}
        </Button>
      </div>
    </div>
  </div>
</template>
