<script lang="ts" setup>
import { computed } from 'vue';

import IdentityDisplay from '#/components/business/identity-display/IdentityDisplay.vue';
import { IdentityProfileTrigger } from '#/components/business/identity-display';
import type { IdentityDisplayModel } from '#/components/business/identity-display';

import {
  createIdentityDetailRequest,
  type IdentityDetailMeta,
} from './identity-interactions';

const props = withDefaults(
  defineProps<{
    avatarSize?: number;
    context?: string;
    meta?: IdentityDetailMeta;
    model: IdentityDisplayModel;
    quickCard?: boolean;
    showOrgLine?: boolean;
    showStatusBadge?: boolean;
  }>(),
  {
    avatarSize: 36,
    context: undefined,
    meta: undefined,
    quickCard: true,
    showOrgLine: true,
    showStatusBadge: true,
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
    <IdentityDisplay
      :avatar-size="avatarSize"
      :model="model"
      :show-org-line="showOrgLine"
      :show-status-badge="showStatusBadge"
    />
  </IdentityProfileTrigger>
</template>
