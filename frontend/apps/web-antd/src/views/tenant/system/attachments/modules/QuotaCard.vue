<script setup lang="ts">
import type { StorageQuotaInfo } from '#/types/attachment';

import { onMounted, ref } from 'vue';

import { Card, Col, Progress, Row, Statistic } from 'ant-design-vue';

import { getStorageQuotaApi } from '#/api/tenant/attachment';
import { $t } from '#/locales';

import { formatFileSize } from '../data';

defineOptions({ name: 'QuotaCard' });

const loading = ref(false);
const quota = ref<null | StorageQuotaInfo>(null);

async function loadQuota() {
  loading.value = true;
  try {
    quota.value = await getStorageQuotaApi();
  } catch {
    // ignore / 忽略非关键错误
  } finally {
    loading.value = false;
  }
}

function formatQuotaLimit(currentQuota: null | StorageQuotaInfo) {
  if (!currentQuota?.planAvailable) {
    return $t('tenant.system.attachment.quota.unavailable');
  }
  if (currentQuota.unlimited) {
    return $t('tenant.system.attachment.quota.unlimited');
  }
  return formatFileSize(currentQuota.limitBytes || 0);
}

function formatMaxFileSize(value: number | string) {
  if (quota.value?.planAvailable === false) {
    return $t('tenant.system.attachment.quota.unavailable');
  }
  return Number(value) === 0
    ? $t('tenant.system.attachment.quota.unlimited')
    : `${value} MB`;
}

onMounted(() => {
  loadQuota();
});

defineExpose({ refresh: loadQuota });
</script>

<template>
  <Card v-if="quota" :loading="loading" :bordered="false" class="mb-4">
    <template #title>
      <span class="font-medium">{{
        $t('tenant.system.attachment.quota.title')
      }}</span>
    </template>
    <Row :gutter="24">
      <Col :span="8">
        <Statistic
          :title="$t('tenant.system.attachment.quota.spaceUsed')"
          :value="quota.usedBytes || 0"
        >
          <template #formatter="{ value }">
            {{ formatFileSize(Number(value)) }}
            <span class="text-xs text-muted-foreground">
              / {{ formatQuotaLimit(quota) }}
            </span>
          </template>
        </Statistic>
        <Progress
          :percent="Number((quota.usagePercent || 0).toFixed(1))"
          :status="(quota.usagePercent || 0) > 90 ? 'exception' : 'active'"
          size="small"
        />
      </Col>
      <Col :span="8">
        <Statistic
          :title="$t('tenant.system.attachment.quota.fileCount')"
          :value="quota.totalCount || 0"
        />
      </Col>
      <Col :span="8">
        <Statistic
          :title="$t('tenant.system.attachment.quota.maxFileSize')"
          :value="quota.maxFileSizeMb || 0"
        >
          <template #formatter="{ value }">
            {{ formatMaxFileSize(value) }}
          </template>
        </Statistic>
      </Col>
    </Row>
  </Card>
</template>
