<script setup lang="ts">
import type { IdentityDetailRequest } from './identity-detail';
import type { IdentityDisplayModel } from './types';

import { computed } from 'vue';

import { Popover } from 'ant-design-vue';

import IdentityDisplay from './IdentityDisplay.vue';
import IdentityQuickCard from './IdentityQuickCard.vue';
import { toIdentityDetailFallback } from './identity-detail';
import { openIdentityDetailDialog } from './use-identity-detail-dialog';

defineOptions({ name: 'IdentityProfileTrigger' });

const props = withDefaults(
  defineProps<{
    detailRequest?: IdentityDetailRequest | null;
    disabled?: boolean;
    model: IdentityDisplayModel;
    placement?:
      | 'bottom'
      | 'bottomLeft'
      | 'bottomRight'
      | 'left'
      | 'leftBottom'
      | 'leftTop'
      | 'right'
      | 'rightBottom'
      | 'rightTop'
      | 'top'
      | 'topLeft'
      | 'topRight';
    showQuickCard?: boolean;
  }>(),
  {
    detailRequest: null,
    disabled: false,
    placement: 'rightTop',
    showQuickCard: true,
  },
);

const mergedDetailRequest = computed<IdentityDetailRequest>(() => ({
  ...(props.detailRequest ?? {}),
  fallback: {
    ...(toIdentityDetailFallback(props.detailRequest?.fallback) ?? {}),
    ...(toIdentityDetailFallback(props.model) ?? {}),
  },
  id: props.model.id,
}));

async function handleClick() {
  if (props.disabled) {
    return;
  }
  await openIdentityDetailDialog(mergedDetailRequest.value);
}
</script>

<template>
  <Popover
    v-if="showQuickCard"
    :placement="placement"
    :trigger="['hover']"
    overlay-class-name="identity-profile-trigger__popover"
  >
    <template #content>
      <IdentityQuickCard
        :detail-request="mergedDetailRequest"
        :model="model"
      />
    </template>

    <button
      class="identity-profile-trigger"
      type="button"
      @click.stop="handleClick"
    >
      <slot>
        <IdentityDisplay :model="model" />
      </slot>
    </button>
  </Popover>

  <button
    v-else
    class="identity-profile-trigger"
    type="button"
    @click.stop="handleClick"
  >
    <slot>
      <IdentityDisplay :model="model" />
    </slot>
  </button>
</template>

<style scoped>
.identity-profile-trigger {
  align-items: stretch;
  appearance: none;
  background: transparent;
  border: none;
  cursor: pointer;
  display: inline-flex;
  justify-content: flex-start;
  padding: 0;
  text-align: left;
  width: 100%;
}

.identity-profile-trigger:focus-visible {
  border-radius: 14px;
  outline: 2px solid rgb(59 130 246 / 0.28);
  outline-offset: 2px;
}
</style>
