<script setup lang="ts">
import type { IdentityDetail, IdentityDetailRequest } from './identity-detail';
import type { IdentityDisplayModel } from './types';

import { computed } from 'vue';

import { Button } from 'ant-design-vue';

import { $t } from '#/locales';

import IdentitySummaryCard from './IdentitySummaryCard.vue';
import {
  createIdentityDetailPreview,
  mergeIdentityDetailFallbacks,
} from './identity-detail';
import { openIdentityDetailDialog } from './use-identity-detail-dialog';

defineOptions({ name: 'IdentityQuickCard' });

const props = withDefaults(
  defineProps<{
    detailRequest?: IdentityDetailRequest | null;
    model: IdentityDetail | IdentityDisplayModel;
    showDetailAction?: boolean;
  }>(),
  {
    detailRequest: null,
    showDetailAction: true,
  },
);

const previewDetail = computed<IdentityDetail>(() =>
  createIdentityDetailPreview({
    ...(props.detailRequest ?? {}),
    fallback: mergeIdentityDetailFallbacks(
      props.detailRequest?.fallback,
      props.model,
    ),
    id: props.model.id,
  }),
);

const canOpenDetail = computed(
  () =>
    props.showDetailAction &&
    (Boolean(props.detailRequest?.scope) || !props.detailRequest?.disableFetch),
);

async function handleOpenDetail() {
  await openIdentityDetailDialog({
    ...(props.detailRequest ?? {}),
    fallback: mergeIdentityDetailFallbacks(
      props.detailRequest?.fallback,
      previewDetail.value,
    ),
    id: previewDetail.value.id,
  });
}
</script>

<template>
  <div class="identity-quick-card">
    <IdentitySummaryCard
      :detail-request="detailRequest"
      :model="model"
      mode="quick"
    />

    <div v-if="canOpenDetail" class="identity-quick-card__actions">
      <Button block size="small" type="default" @click="handleOpenDetail">
        {{ $t('shared.identity.action.viewDetail') }}
      </Button>
    </div>
  </div>
</template>

<style scoped>
.identity-quick-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 300px;
}

.identity-quick-card__actions {
  display: flex;
  justify-content: flex-start;
}
</style>
