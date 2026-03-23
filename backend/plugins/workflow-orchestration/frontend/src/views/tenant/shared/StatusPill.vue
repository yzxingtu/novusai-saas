<script lang="ts" setup>
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    label: string;
    tone?: string;
  }>(),
  {
    tone: 'neutral',
  },
);

const toneClassMap: Record<string, string> = {
  danger:
    'border-rose-200 bg-rose-50 text-rose-700',
  info:
    'border-sky-200 bg-sky-50 text-sky-700',
  neutral:
    'border-slate-200 bg-slate-100 text-slate-700',
  success:
    'border-emerald-200 bg-emerald-50 text-emerald-700',
  warning:
    'border-amber-200 bg-amber-50 text-amber-700',
};

const classes = computed(() => {
  return (
    toneClassMap[props.tone] ??
    toneClassMap.neutral
  );
});
</script>

<template>
  <span
    class="inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium"
    :class="classes"
  >
    {{ props.label }}
  </span>
</template>
