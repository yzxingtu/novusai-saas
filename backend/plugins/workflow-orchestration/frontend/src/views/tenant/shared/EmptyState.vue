<script lang="ts" setup>
const props = withDefaults(
  defineProps<{
    title: string;
    description?: string;
  }>(),
  {
    description: '',
  },
);
</script>

<template>
  <div class="rounded-3xl border border-dashed border-slate-200 bg-white/80 px-6 py-10 text-center shadow-sm">
    <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-500">
      <svg
        class="h-6 w-6"
        fill="none"
        stroke="currentColor"
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="1.8"
        viewBox="0 0 24 24"
      >
        <path d="M12 5v14" />
        <path d="M5 12h14" />
      </svg>
    </div>
    <h3 class="mt-4 text-base font-semibold text-slate-900">
      {{ props.title }}
    </h3>
    <p
      v-if="props.description"
      class="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-500"
    >
      {{ props.description }}
    </p>
    <div class="mt-4 flex justify-center">
      <slot />
    </div>
  </div>
</template>
