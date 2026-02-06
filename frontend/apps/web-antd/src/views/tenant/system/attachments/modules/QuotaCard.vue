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
    // ignore
  } finally {
    loading.value = false;
  }
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
      <Col :span="6">
        <Statistic
          :title="$t('tenant.system.attachment.quota.spaceUsed')"
          :value="quota.spaceUsed || 0"
        >
          <template #formatter="{ value }">
            {{ formatFileSize(Number(value)) }}
            <span class="text-xs text-muted-foreground">
              /
              {{
                quota?.spaceLimit === 0
                  ? $t('tenant.system.attachment.quota.unlimited')
                  : formatFileSize(quota?.spaceLimit || 0)
              }}
            </span>
          </template>
        </Statistic>
        <Progress
          :percent="Number((quota.spacePercent || 0).toFixed(1))"
          :status="(quota.spacePercent || 0) > 90 ? 'exception' : 'active'"
          size="small"
        />
      </Col>
      <Col :span="6">
        <Statistic
          :title="$t('tenant.system.attachment.quota.fileCount')"
          :value="quota.fileCount || 0"
        >
          <template #suffix>
            <span class="text-xs text-muted-foreground">
              /
              {{
                (quota?.fileCountLimit || 0) === 0
                  ? $t('tenant.system.attachment.quota.unlimited')
                  : quota?.fileCountLimit
              }}
            </span>
          </template>
        </Statistic>
      </Col>
      <Col :span="6">
        <Statistic
          :title="$t('tenant.system.attachment.quota.maxFileSize')"
          :value="quota.maxFileSize || 0"
        >
          <template #formatter="{ value }">
            {{ formatFileSize(Number(value)) }}
          </template>
        </Statistic>
      </Col>
      <Col :span="6">
        <Statistic
          :title="$t('tenant.system.attachment.quota.bandwidthUsed')"
          :value="quota.bandwidthUsed || 0"
        >
          <template #formatter="{ value }">
            {{ formatFileSize(Number(value)) }}
            <span class="text-xs text-muted-foreground">
              /
              {{
                quota?.bandwidthLimit === 0
                  ? $t('tenant.system.attachment.quota.unlimited')
                  : formatFileSize(quota?.bandwidthLimit || 0)
              }}
            </span>
          </template>
        </Statistic>
      </Col>
    </Row>
  </Card>
</template>
