<script lang="ts" setup>
const props = withDefaults(
  defineProps<{
    description?: string;
    eyebrow?: string;
    title: string;
  }>(),
  {
    description: '',
    eyebrow: '',
  },
);
</script>

<template>
  <div class="min-h-full bg-[radial-gradient(circle_at_top_left,_rgba(18,98,194,0.14),_transparent_36%),linear-gradient(180deg,_rgba(248,250,252,0.98),_rgba(241,245,249,0.96))] px-4 py-6 text-foreground sm:px-6 lg:px-8">
    <div class="mx-auto flex w-full max-w-7xl flex-col gap-6">
      <section class="overflow-hidden rounded-3xl border border-white/70 bg-white/90 shadow-[0_24px_80px_-44px_rgba(15,23,42,0.35)] backdrop-blur">
        <div class="grid gap-4 px-6 py-6 sm:px-8 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <div class="space-y-3">
            <p
              v-if="props.eyebrow"
              class="text-xs font-semibold uppercase tracking-[0.24em] text-sky-700"
            >
              {{ props.eyebrow }}
            </p>
            <div class="space-y-2">
              <h1 class="text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">
                {{ props.title }}
              </h1>
              <p
                v-if="props.description"
                class="max-w-3xl text-sm leading-6 text-slate-600 sm:text-base"
              >
                {{ props.description }}
              </p>
            </div>
          </div>
          <div class="flex flex-wrap items-center justify-start gap-3 lg:justify-end">
            <slot name="actions" />
          </div>
        </div>
      </section>

      <slot />
    </div>
  </div>
</template>
