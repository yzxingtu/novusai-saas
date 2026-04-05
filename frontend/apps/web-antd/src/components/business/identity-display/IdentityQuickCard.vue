<script setup lang="ts">
import type { IdentityDetail, IdentityDetailRequest } from './identity-detail';
import type { IdentityDisplayModel } from './types';

import { computed } from 'vue';

import { Button, Switch } from 'ant-design-vue';

import { $t } from '#/locales';

import { shouldShowIdentityRole } from './detail-presentation';
import {
  createIdentityDetailPreview,
  getIdentityApprovalStatusLabel,
  getIdentityStatusLabel,
  toIdentityDetailFallback,
} from './identity-detail';
import IdentityDisplay from './IdentityDisplay.vue';
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
    ...props.detailRequest,
    fallback: {
      ...toIdentityDetailFallback(props.detailRequest?.fallback),
      ...toIdentityDetailFallback(props.model),
    },
    id: props.model.id,
  }),
);

const metaRows = computed(() => {
  const detail = previewDetail.value;
  const rows = [
    {
      key: 'username',
      label: $t('shared.identity.field.username'),
      value: detail.username || $t('shared.identity.field.empty'),
    },
    {
      key: 'organization',
      label: $t('shared.identity.field.organization'),
      value: detail.orgNodeName || $t('shared.identity.unassignedArchitecture'),
    },
    {
      key: 'status',
      label: $t('shared.identity.field.status'),
      checked: detail.isActive !== false,
      type: 'switch' as const,
      value: getIdentityStatusLabel(detail.isActive),
    },
  ];

  if (detail.tenantName?.trim()) {
    rows.splice(2, 0, {
      key: 'tenant',
      label: $t('shared.identity.field.tenant'),
      value: detail.tenantName.trim(),
    });
  }

  if (shouldShowIdentityRole(detail)) {
    rows.splice(3, 0, {
      key: 'role',
      label: $t('shared.identity.field.role'),
      value: detail.roleName!.trim(),
    });
  }

  if (detail.email?.trim()) {
    rows.push({
      key: 'email',
      label: $t('shared.identity.field.email'),
      value: detail.email.trim(),
    });
  }

  if (detail.phone?.trim()) {
    rows.push({
      key: 'phone',
      label: $t('shared.identity.field.phone'),
      value: detail.phone.trim(),
    });
  }

  if (detail.approvalStatus?.trim()) {
    rows.push({
      key: 'approval',
      label: $t('shared.identity.field.approvalStatus'),
      value: getIdentityApprovalStatusLabel(detail.approvalStatus),
    });
  }

  return rows;
});

const canOpenDetail = computed(
  () =>
    props.showDetailAction &&
    (Boolean(props.detailRequest?.scope) || !props.detailRequest?.disableFetch),
);

async function handleOpenDetail() {
  await openIdentityDetailDialog({
    ...props.detailRequest,
    fallback: {
      ...props.detailRequest?.fallback,
      ...previewDetail.value,
    },
    id: previewDetail.value.id,
  });
}
</script>

<template>
  <div class="identity-quick-card">
    <IdentityDisplay
      :avatar-size="44"
      :model="previewDetail"
      :show-status-badge="true"
      vertical-align="center"
    />

    <dl class="identity-quick-card__meta-list">
      <div
        v-for="item in metaRows"
        :key="item.key"
        class="identity-quick-card__meta-row"
      >
        <dt class="identity-quick-card__meta-label">
          {{ item.label }}
        </dt>
        <dd class="identity-quick-card__meta-value">
          <div
            v-if="item.type === 'switch'"
            class="identity-quick-card__switch-value"
          >
            <Switch :checked="item.checked" disabled size="small" />
            <span>{{ item.value }}</span>
          </div>
          <template v-else>
            {{ item.value }}
          </template>
        </dd>
      </div>
    </dl>

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
  min-width: 280px;
  text-align: left;
}

.identity-quick-card__meta-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
}

.identity-quick-card__meta-row {
  align-items: flex-start;
  display: grid;
  gap: 10px;
  grid-template-columns: minmax(78px, 92px) minmax(0, 1fr);
  text-align: left;
}

.identity-quick-card__meta-label {
  color: rgb(107 114 128);
  font-size: 12px;
  line-height: 1.45;
  margin: 0;
  text-align: left;
}

.identity-quick-card__meta-value {
  color: rgb(17 24 39);
  font-size: 12px;
  font-weight: 500;
  line-height: 1.45;
  margin: 0;
  min-width: 0;
  overflow-wrap: anywhere;
  text-align: left;
}

.identity-quick-card__switch-value {
  align-items: center;
  display: inline-flex;
  gap: 8px;
  justify-content: flex-start;
  min-width: 0;
}

.identity-quick-card__actions {
  display: flex;
  justify-content: flex-start;
  padding-top: 2px;
}

.dark .identity-quick-card__meta-label {
  color: rgb(156 163 175);
}

.dark .identity-quick-card__meta-value {
  color: rgb(243 244 246);
}
</style>
