<script setup lang="ts">
import { computed } from 'vue';

import { Alert, Drawer, Empty, Spin, Switch } from 'ant-design-vue';

import { $t } from '#/locales';

import {
  getIdentityApprovalStatusLabel,
  getIdentityStatusLabel,
} from './identity-detail';
import {
  formatIdentityDateTime,
  resolveIdentityPrimaryContextLabel,
  resolveIdentityPrimaryContextValue,
  shouldShowIdentityOrganization,
  shouldShowIdentityRole,
  usesRoleAsPrimaryIdentityContext,
} from './detail-presentation';
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

interface DetailRow {
  checked?: boolean;
  key: string;
  label: string;
  type?: 'switch' | 'text';
  value: string;
}

const basicRows = computed(() => {
  if (!detail.value) {
    return [];
  }
  const current = detail.value;
  const rows: DetailRow[] = [
    {
      key: 'username',
      label: $t('shared.identity.field.username'),
      value: current.username || $t('shared.identity.field.empty'),
    },
    {
      key: 'context',
      label: resolveIdentityPrimaryContextLabel(current),
      value: resolveIdentityPrimaryContextValue(current),
    },
  ];

  if (current.tenantName?.trim()) {
    rows.push({
      key: 'tenant',
      label: $t('shared.identity.field.tenant'),
      value: current.tenantName.trim(),
    });
  }

  if (shouldShowIdentityOrganization(current)) {
    rows.push({
      key: 'organization',
      label: $t('shared.identity.field.organization'),
      value: current.orgNodeName!.trim(),
    });
  }

  if (
    !usesRoleAsPrimaryIdentityContext(current) &&
    shouldShowIdentityRole(current)
  ) {
    rows.push({
      key: 'role',
      label: $t('shared.identity.field.role'),
      value: current.roleName!.trim(),
    });
  }

  rows.push(
    {
      key: 'status',
      label: $t('shared.identity.field.status'),
      checked: current.isActive !== false,
      type: 'switch',
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
  );

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
      value: formatIdentityDateTime(current.createdAt),
    },
    {
      key: 'updatedAt',
      label: $t('shared.identity.field.updatedAt'),
      value: formatIdentityDateTime(current.updatedAt),
    },
    {
      key: 'lastLoginAt',
      label: $t('shared.identity.field.lastLoginAt'),
      value: formatIdentityDateTime(current.lastLoginAt),
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
              <dd class="identity-detail-drawer__value">
                <div
                  v-if="item.type === 'switch'"
                  class="identity-detail-drawer__switch-value"
                >
                  <Switch
                    :checked="item.checked"
                    disabled
                    size="small"
                  />
                  <span>{{ item.value }}</span>
                </div>
                <template v-else>
                  {{ item.value }}
                </template>
              </dd>
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

.identity-detail-drawer__switch-value {
  align-items: center;
  display: inline-flex;
  gap: 10px;
  justify-content: flex-start;
  min-width: 0;
}

.dark .identity-detail-drawer__section-title,
.dark .identity-detail-drawer__value {
  color: rgb(243 244 246);
}

.dark .identity-detail-drawer__label {
  color: rgb(156 163 175);
}
</style>
