<script lang="ts" setup>
import type { DashboardActivityEntry } from './types';

import { computed } from 'vue';

import { IdentityDisplay } from '#/components/business/identity-display';
import { formatDate } from '#/utils/common';
import IdentityTrigger from '#/views/_shared/identity/IdentityTrigger.vue';

const props = withDefaults(
  defineProps<{
    columns?: 1 | 2;
    emptyHeight?: string;
    emptyText: string;
    items: DashboardActivityEntry[];
    maxHeight?: string;
  }>(),
  {
    columns: 1,
    emptyHeight: '320px',
    maxHeight: undefined,
  },
);

const listClass = computed(() =>
  props.columns === 2 ? 'mt-5 grid gap-3 lg:grid-cols-2' : 'mt-5 space-y-3',
);

const wrapperClass = computed(() =>
  props.maxHeight ? 'overflow-y-auto pr-1' : '',
);

const wrapperStyle = computed(() =>
  props.maxHeight ? { maxHeight: props.maxHeight } : {},
);
</script>

<template>
  <div v-if="items.length > 0" :class="wrapperClass" :style="wrapperStyle">
    <div :class="listClass">
      <div
        v-for="activity in items"
        :key="activity.id"
        class="rounded-[22px] border border-border/60 bg-background/80 p-4"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="flex min-w-0 flex-1 items-start gap-3">
            <span
              class="inline-flex shrink-0 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary"
            >
              {{ activity.method }}
            </span>
            <div class="min-w-0 flex-1">
              <IdentityTrigger
                v-if="activity.actor.interactive"
                :avatar-size="34"
                :meta="activity.actor.meta"
                :model="activity.actor.model"
                class="max-w-full"
              />
              <IdentityDisplay
                v-else
                :avatar-size="34"
                :model="activity.actor.model"
                class="max-w-full"
              />
            </div>
          </div>
          <span class="shrink-0 pt-1 text-xs text-muted-foreground">
            {{ formatDate(activity.createdAt, 'YYYY-MM-DD HH:mm') }}
          </span>
        </div>
        <p class="mt-3 text-sm text-muted-foreground">
          {{ activity.detail }}
        </p>
        <p class="mt-2 text-sm font-medium text-foreground">
          {{ activity.path }}
        </p>
      </div>
    </div>
  </div>

  <div
    v-else
    class="mt-5 flex items-center justify-center rounded-[22px] border border-dashed border-border/70 bg-background/60 text-sm text-muted-foreground"
    :style="{ height: emptyHeight }"
  >
    {{ emptyText }}
  </div>
</template>
