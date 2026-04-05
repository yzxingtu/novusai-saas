<script setup lang="ts">
import { computed } from 'vue';

import { Alert, Drawer, Empty, Spin } from 'ant-design-vue';

import { $t } from '#/locales';

import {
  getIdentityApprovalStatusLabel,
  getIdentityDetailTypeLabel,
  getIdentityStatusLabel,
} from './identity-detail';
import IdentityDisplay from './IdentityDisplay.vue';
import { useIdentityDetailDialog } from './use-identity-detail-dialog';

defineOptions({ name: 'IdentityDetailDrawer' });

const { closeIdentityDetailDialog, identityDetailDialogState } =
  useIdentityDetailDialog();

const open = computed({
  get: () => identityDetailDialogState.open,
  set: (value: boolean) => {
    if (!value) {
      closeIdentityDetailDialog();
    }
  },
});

const detail = computed(() => identityDetailDialogState.detail);

const basicRows = computed(() => {
  if (!detail.value) {
    return [];
  }
  const current = detail.value;
  const rows = [
    {
      key: 'username',
      label: $t('shared.identity.field.username'),
      value: current.username || $t('shared.identity.field.empty'),
    },
    {
      key: 'userType',
      label: $t('shared.identity.field.userType'),
      value: getIdentityDetailTypeLabel(current.userType),
    },
    {
      key: 'organization',
      label: $t('shared.identity.field.organization'),
      value:
        current.orgNodeName || $t('shared.identity.unassignedArchitecture'),
    },
    {
      key: 'role',
      label: $t('shared.identity.field.role'),
      value: current.roleName || $t('shared.identity.field.empty'),
    },
    {
      key: 'status',
      label: $t('shared.identity.field.status'),
      value: getIdentityStatusLabel(current.isActive),
    },
    {
      key: 'owner',
      label: $t('shared.identity.field.owner'),
      value: current.isOwner ? $t('shared.common.yes') : $t('shared.common.no'),
    },
    {
      key: 'leader',
      label: $t('shared.identity.field.leader'),
      value: current.isLeader ? $t('shared.common.yes') : $t('shared.common.no'),
    },
  ];

  if (current.tenantName?.trim()) {
    rows.splice(2, 0, {
      key: 'tenant',
      label: $t('shared.identity.field.tenant'),
      value: current.tenantName.trim(),
    });
  }

  if (current.email?.trim()) {
    rows.push({
      key: 'email',
      label: $t('shared.identity.field.email'),
      value: current.email.trim(),
    });
  }

  if (current.phone?.trim()) {
    rows.push({
      key: 'phone',
      label: $t('shared.identity.field.phone'),
      value: current.phone.trim(),
    });
  }

  if (current.approvalStatus?.trim()) {
    rows.push({
      key: 'approvalStatus',
      label: $t('shared.identity.field.approvalStatus'),
      value: getIdentityApprovalStatusLabel(current.approvalStatus),
    });
  }

  if (current.isSuper) {
    rows.push({
      key: 'super',
      label: $t('shared.identity.field.superAdmin'),
      value: $t('shared.common.yes'),
    });
  }

  return rows;
});

const activityRows = computed(() => {
  if (!detail.value) {
    return [];
  }
  const current = detail.value;
  return [
    {
      key: 'createdAt',
      label: $t('shared.identity.field.createdAt'),
      value: current.createdAt || $t('shared.identity.field.empty'),
    },
    {
      key: 'updatedAt',
      label: $t('shared.identity.field.updatedAt'),
      value: current.updatedAt || $t('shared.identity.field.empty'),
    },
    {
      key: 'lastLoginAt',
      label: $t('shared.identity.field.lastLoginAt'),
      value: current.lastLoginAt || $t('shared.identity.field.empty'),
    },
    {
      key: 'lastLoginIp',
      label: $t('shared.identity.field.lastLoginIp'),
      value: current.lastLoginIp || $t('shared.identity.field.empty'),
    },
  ];
});
</script>

<template>
  <Drawer
    v-model:open="open"
    :title="$t('shared.identity.detail.title')"
    :width="420"
    placement="right"
  >
    <Spin :spinning="identityDetailDialogState.loading">
      <div v-if="detail" class="identity-detail-drawer">
        <IdentityDisplay
          :avatar-size="56"
          :model="detail"
          :show-status-badge="true"
        />

        <Alert
          v-if="identityDetailDialogState.error"
          show-icon
          type="warning"
          :message="identityDetailDialogState.error"
        />

        <section class="identity-detail-drawer__section">
          <h4 class="identity-detail-drawer__section-title">
            {{ $t('shared.identity.detail.basicSection') }}
          </h4>
          <dl class="identity-detail-drawer__list">
            <div
              v-for="item in basicRows"
              :key="item.key"
              class="identity-detail-drawer__row"
            >
              <dt class="identity-detail-drawer__label">{{ item.label }}</dt>
              <dd class="identity-detail-drawer__value">{{ item.value }}</dd>
            </div>
          </dl>
        </section>

        <section class="identity-detail-drawer__section">
          <h4 class="identity-detail-drawer__section-title">
            {{ $t('shared.identity.detail.activitySection') }}
          </h4>
          <dl class="identity-detail-drawer__list">
            <div
              v-for="item in activityRows"
              :key="item.key"
              class="identity-detail-drawer__row"
            >
              <dt class="identity-detail-drawer__label">{{ item.label }}</dt>
              <dd class="identity-detail-drawer__value">{{ item.value }}</dd>
            </div>
          </dl>
        </section>
      </div>

      <Empty
        v-else
        :description="$t('shared.identity.detail.emptyDescription')"
      />
    </Spin>
  </Drawer>
</template>

<style scoped>
.identity-detail-drawer {
  display: flex;
  flex-direction: column;
  gap: 18px;
  text-align: left;
}

.identity-detail-drawer__section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  text-align: left;
}

.identity-detail-drawer__section-title {
  color: rgb(17 24 39);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
  margin: 0;
  text-align: left;
}

.identity-detail-drawer__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0;
}

.identity-detail-drawer__row {
  align-items: flex-start;
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(88px, 108px) minmax(0, 1fr);
  text-align: left;
}

.identity-detail-drawer__label {
  color: rgb(107 114 128);
  font-size: 12px;
  line-height: 1.45;
  margin: 0;
  text-align: left;
}

.identity-detail-drawer__value {
  color: rgb(17 24 39);
  font-size: 12px;
  font-weight: 500;
  line-height: 1.5;
  margin: 0;
  overflow-wrap: anywhere;
  text-align: left;
}

.dark .identity-detail-drawer__section-title,
.dark .identity-detail-drawer__value {
  color: rgb(243 244 246);
}

.dark .identity-detail-drawer__label {
  color: rgb(156 163 175);
}
</style>
