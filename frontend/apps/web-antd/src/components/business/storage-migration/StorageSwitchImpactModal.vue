<script lang="ts" setup>
/**
 * Storage Switch Impact Analysis Modal
 *
 * Shows impact analysis when admin switches storage driver.
 * Displays file counts, sizes, and visibility breakdown.
 * Provides "Switch Anyway" and "Migrate First" actions.
 */
import type { ImpactAnalysis } from '#/api/admin/storage-migration';

import { computed, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Descriptions,
  DescriptionsItem,
  Modal,
  Spin,
  Statistic,
  Tag,
} from 'ant-design-vue';

import { getImpactAnalysisApi } from '#/api/admin/storage-migration';
import { $t } from '#/locales';

const emit = defineEmits<{
  (e: 'confirmSwitch'): void;
  (e: 'goMigrate', source: string, target: string): void;
}>();

const visible = ref(false);
const loading = ref(false);
const analysis = ref<ImpactAnalysis | null>(null);
const sourceDriver = ref('');
const targetDriver = ref('');

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / 1024 ** i).toFixed(1)} ${units[i]}`;
}

const hasPrivateFiles = computed(
  () => (analysis.value?.private_files ?? 0) > 0,
);
const hasPublicFiles = computed(() => (analysis.value?.public_files ?? 0) > 0);
const hasFiles = computed(() => (analysis.value?.total_files ?? 0) > 0);

async function open(source: string, target: string) {
  sourceDriver.value = source;
  targetDriver.value = target;
  visible.value = true;
  loading.value = true;
  analysis.value = null;

  try {
    analysis.value = await getImpactAnalysisApi(source, target);
  } catch {
    // handled by request interceptor / 错误由请求拦截器处理
  } finally {
    loading.value = false;
  }
}

function onConfirmSwitch() {
  visible.value = false;
  emit('confirmSwitch');
}

function onGoMigrate() {
  visible.value = false;
  emit('goMigrate', sourceDriver.value, targetDriver.value);
}

defineExpose({ open });
</script>

<template>
  <Modal
    v-model:open="visible"
    :title="$t('admin.storageMigration.switchWarning.title')"
    :footer="null"
    :width="600"
    destroy-on-close
  >
    <Spin :spinning="loading">
      <div v-if="analysis" class="space-y-4">
        <!-- Description -->
        <Alert
          type="warning"
          show-icon
          :message="$t('admin.storageMigration.switchWarning.description')"
        />

        <!-- Stats -->
        <div class="grid grid-cols-3 gap-4">
          <div class="rounded-lg border p-3 text-center">
            <Statistic
              :title="$t('admin.storageMigration.impactAnalysis.totalFiles')"
              :value="analysis.total_files"
            />
          </div>
          <div class="rounded-lg border p-3 text-center">
            <Statistic
              :title="$t('admin.storageMigration.impactAnalysis.privateFiles')"
              :value="analysis.private_files"
              :value-style="{
                color: analysis.private_files > 0 ? '#cf1322' : undefined,
              }"
            />
          </div>
          <div class="rounded-lg border p-3 text-center">
            <Statistic
              :title="$t('admin.storageMigration.impactAnalysis.publicFiles')"
              :value="analysis.public_files"
            />
          </div>
        </div>

        <!-- Size info -->
        <Descriptions :column="2" bordered size="small">
          <DescriptionsItem
            :label="$t('admin.storageMigration.impactAnalysis.totalSize')"
          >
            {{ formatBytes(analysis.total_size_bytes) }}
          </DescriptionsItem>
          <DescriptionsItem
            :label="$t('admin.storageMigration.impactAnalysis.sourceDriver')"
          >
            <Tag color="blue">{{ analysis.source_driver }}</Tag>
          </DescriptionsItem>
          <DescriptionsItem
            :label="$t('admin.storageMigration.impactAnalysis.targetDriver')"
          >
            <Tag color="green">{{ analysis.target_driver }}</Tag>
          </DescriptionsItem>
        </Descriptions>

        <!-- Warnings -->
        <div v-if="hasFiles" class="space-y-2">
          <Alert
            v-if="hasPrivateFiles"
            type="error"
            show-icon
            :message="
              $t('admin.storageMigration.switchWarning.privateWarning', {
                count: analysis.private_files,
              })
            "
          />
          <Alert
            v-if="hasPublicFiles"
            type="info"
            show-icon
            :message="
              $t('admin.storageMigration.switchWarning.publicWarning', {
                count: analysis.public_files,
              })
            "
          />
        </div>

        <!-- No files -->
        <Alert
          v-if="!hasFiles"
          type="success"
          show-icon
          :message="$t('admin.storageMigration.impactAnalysis.noFiles')"
        />

        <!-- Actions -->
        <div class="flex justify-end gap-3 pt-2">
          <Button v-if="hasFiles" type="primary" @click="onGoMigrate">
            <template #icon>
              <IconifyIcon icon="lucide:hard-drive-download" />
            </template>
            {{ $t('admin.storageMigration.switchWarning.btnMigrate') }}
          </Button>
          <Button
            :type="hasFiles ? 'default' : 'primary'"
            :danger="hasPrivateFiles"
            @click="onConfirmSwitch"
          >
            {{ $t('admin.storageMigration.switchWarning.btnSwitch') }}
          </Button>
        </div>
      </div>
    </Spin>
  </Modal>
</template>
