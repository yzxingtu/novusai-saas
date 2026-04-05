<script setup lang="ts">
import { computed } from 'vue';

import { Alert, Drawer, Empty, Spin } from 'ant-design-vue';

import { $t } from '#/locales';

import {
  buildIdentityActivityRows,
  buildIdentitySummaryRows,
} from './detail-presentation';
import IdentitySummaryCard from './IdentitySummaryCard.vue';
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

const sections = computed(() => {
  if (!detail.value) {
    return [];
  }

  return [
    {
      key: 'overview',
      title: $t('shared.identity.detail.overviewSection'),
      rows: buildIdentitySummaryRows(detail.value, 'detail-overview'),
    },
    {
      key: 'account',
      title: $t('shared.identity.detail.accountSection'),
      rows: buildIdentitySummaryRows(detail.value, 'detail-account'),
    },
    {
      key: 'activity',
      title: $t('shared.identity.detail.activitySection'),
      rows: buildIdentityActivityRows(detail.value),
    },
  ];
});
</script>

<template>
  <Drawer
    v-model:open="open"
    :title="$t('shared.identity.detail.title')"
    :width="440"
    placement="right"
  >
    <Spin :spinning="identityDetailDialogState.loading">
      <div class="identity-detail-drawer">
        <IdentitySummaryCard
          v-if="detail"
          :detail-request="identityDetailDialogState.request"
          :model="detail"
          mode="embedded"
          :show-rows="false"
        />

        <Alert
          v-if="identityDetailDialogState.error"
          show-icon
          type="warning"
          :message="identityDetailDialogState.error"
        />

        <template v-if="detail">
          <section
            v-for="section in sections"
            :key="section.key"
            class="identity-detail-drawer__section"
            :data-section="section.key"
          >
            <h4 class="identity-detail-drawer__section-title">
              {{ section.title }}
            </h4>
            <dl class="identity-detail-drawer__list">
              <div
                v-for="item in section.rows"
                :key="item.key"
                class="identity-detail-drawer__row"
              >
                <dt class="identity-detail-drawer__label">{{ item.label }}</dt>
                <dd class="identity-detail-drawer__value">{{ item.value }}</dd>
              </div>
            </dl>
          </section>
        </template>

        <Empty
          v-else
          :description="$t('shared.identity.detail.emptyDescription')"
        />
      </div>
    </Spin>
  </Drawer>
</template>

<style scoped>
.identity-detail-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
  text-align: left;
}

.identity-detail-drawer__section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  background: hsl(var(--card));
  border: 1px solid hsl(var(--border) / 72%);
  border-radius: 18px;
}

.identity-detail-drawer__section-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
  color: hsl(var(--foreground));
}

.identity-detail-drawer__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0;
}

.identity-detail-drawer__row {
  display: grid;
  grid-template-columns: minmax(88px, 112px) minmax(0, 1fr);
  gap: 12px;
  align-items: flex-start;
}

.identity-detail-drawer__label {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  color: hsl(var(--muted-foreground));
}

.identity-detail-drawer__value {
  margin: 0;
  overflow-wrap: anywhere;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.5;
  color: hsl(var(--foreground));
}
</style>
