<script setup lang="ts">
import type { IdentityDetailRequest } from './identity-detail';
import type { IdentityDisplayModel } from './types';

import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import { Popover } from 'ant-design-vue';

import { $t } from '#/locales';

import IdentityDisplay from './IdentityDisplay.vue';
import IdentityQuickCard from './IdentityQuickCard.vue';
import { mergeIdentityDetailFallbacks } from './identity-detail';
import { resolveIdentityDisplayTitle } from './types';
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

const supportsHoverQuickCard = ref(false);
const mediaCleanups: Array<() => void> = [];

const mergedDetailRequest = computed<IdentityDetailRequest>(() => ({
  ...(props.detailRequest ?? {}),
  fallback: mergeIdentityDetailFallbacks(
    props.detailRequest?.fallback,
    props.model,
  ),
  id: props.model.id,
}));

const quickCardEnabled = computed(
  () => props.showQuickCard && !props.disabled && supportsHoverQuickCard.value,
);

const triggerAriaLabel = computed(
  () =>
    `${$t('shared.identity.action.openDialogAria')} ${resolveIdentityDisplayTitle(props.model)}`,
);

function bindMediaQuery(query: string, onChange: () => void) {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return;
  }

  const mediaQuery = window.matchMedia(query);
  const listener = () => onChange();

  if (typeof mediaQuery.addEventListener === 'function') {
    mediaQuery.addEventListener('change', listener);
    mediaCleanups.push(() => mediaQuery.removeEventListener('change', listener));
  } else if (typeof mediaQuery.addListener === 'function') {
    mediaQuery.addListener(listener);
    mediaCleanups.push(() => mediaQuery.removeListener(listener));
  }
}

function updateHoverSupport() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    supportsHoverQuickCard.value = false;
    return;
  }

  supportsHoverQuickCard.value =
    window.matchMedia('(hover: hover)').matches &&
    window.matchMedia('(pointer: fine)').matches;
}

async function handleOpenDetail() {
  if (props.disabled) {
    return;
  }
  await openIdentityDetailDialog(mergedDetailRequest.value);
}

async function handleKeyboardOpen(event: KeyboardEvent) {
  if (event.key !== 'Enter' && event.key !== ' ') {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  await handleOpenDetail();
}

onMounted(() => {
  updateHoverSupport();
  bindMediaQuery('(hover: hover)', updateHoverSupport);
  bindMediaQuery('(pointer: fine)', updateHoverSupport);
});

onBeforeUnmount(() => {
  mediaCleanups.splice(0).forEach((cleanup) => cleanup());
});
</script>

<template>
  <Popover
    v-if="quickCardEnabled"
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
      aria-haspopup="dialog"
      :aria-label="triggerAriaLabel"
      class="identity-profile-trigger"
      :disabled="disabled"
      type="button"
      @click.stop="handleOpenDetail"
      @keydown="handleKeyboardOpen"
    >
      <slot>
        <IdentityDisplay :model="model" />
      </slot>
    </button>
  </Popover>

  <button
    v-else
    aria-haspopup="dialog"
    :aria-label="triggerAriaLabel"
    class="identity-profile-trigger"
    :disabled="disabled"
    type="button"
    @click.stop="handleOpenDetail"
    @keydown="handleKeyboardOpen"
  >
    <slot>
      <IdentityDisplay :model="model" />
    </slot>
  </button>
</template>

<style scoped>
.identity-profile-trigger {
  display: inline-flex;
  width: 100%;
  min-width: 0;
  padding: 0;
  text-align: left;
  cursor: pointer;
  background: transparent;
  border: none;
  justify-content: flex-start;
  align-items: stretch;
  appearance: none;
}

.identity-profile-trigger:disabled {
  cursor: default;
  opacity: 0.82;
}

.identity-profile-trigger:focus-visible {
  outline: 2px solid rgb(14 165 233 / 0.4);
  outline-offset: 3px;
  border-radius: 18px;
}
</style>
