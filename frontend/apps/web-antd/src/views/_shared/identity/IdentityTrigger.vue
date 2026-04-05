<script lang="ts" setup>
import type { IdentityDetailMeta } from './identity-interactions';

import type { IdentityDisplayModel } from '#/components/business/identity-display';

import { computed } from 'vue';

import { IdentityProfileTrigger } from '#/components/business/identity-display';
import IdentityDisplay from '#/components/business/identity-display/IdentityDisplay.vue';

import { createIdentityDetailRequest } from './identity-interactions';

const props = withDefaults(
  defineProps<{
    avatarSize?: number;
    badgeWrap?: 'nowrap' | 'wrap';
    context?: string;
    meta?: IdentityDetailMeta;
    model: IdentityDisplayModel;
    quickCard?: boolean;
    showOrgLine?: boolean;
    showSecondaryText?: boolean;
    showStatusBadge?: boolean;
    verticalAlign?: 'center' | 'start';
  }>(),
  {
    avatarSize: 36,
    badgeWrap: 'wrap',
    context: undefined,
    meta: undefined,
    quickCard: true,
    showOrgLine: true,
    showSecondaryText: true,
    showStatusBadge: true,
    verticalAlign: 'start',
  },
);

const detailRequest = computed(() =>
  createIdentityDetailRequest({
    context: props.context,
    meta: props.meta,
    model: props.model,
  }),
);
</script>

<template>
  <IdentityProfileTrigger
    :detail-request="detailRequest"
    :model="model"
    :show-quick-card="quickCard"
  >
    <slot :detail-request="detailRequest" :model="model">
      <IdentityDisplay
        :avatar-size="avatarSize"
        :badge-wrap="badgeWrap"
        :model="model"
        :show-org-line="showOrgLine"
        :show-secondary-text="showSecondaryText"
        :show-status-badge="showStatusBadge"
        :vertical-align="verticalAlign"
      />
    </slot>
  </IdentityProfileTrigger>
</template>
