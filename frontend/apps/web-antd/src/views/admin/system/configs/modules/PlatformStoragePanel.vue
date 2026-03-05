<script lang="ts" setup>
/**
 * 管理端平台存储配置面板
 *
 * 替代 ConfigForm 渲染 platform_storage 分组，提供：
 * - 驱动选择器（感知插件启用状态）
 * - 凭证表单（根据驱动动态切换）
 * - 连接测试按钮
 * - 通用存储参数（可见性/分片/限制/扩展名/允许的自定义驱动等，仍用 ConfigForm）
 *
 * 注意：租户自主配置权限改为逐租户控制（在 TenantStorageDrawer 中），不再有全局开关。
 */
import type { ConfigItemMeta } from '#/types/config';
import type { StorageDriverInfo } from '#/types/storage';

import { onActivated, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import { Alert, Button, Divider, message, Spin } from 'ant-design-vue';

import {
  getAdminConfigGroupDetailApi,
  getStorageDriversApi,
  testStorageConnectionApi,
  updateAdminConfigGroupApi,
} from '#/api/admin/configs';
import { ConfigForm } from '#/components';
import {
  StorageCredentialForm,
  StorageDriverSelector,
} from '#/components/business/storage-config';
import StorageSwitchImpactModal from '#/components/business/storage-migration/StorageSwitchImpactModal.vue';
import { $t } from '#/locales';

defineOptions({ name: 'PlatformStoragePanel' });

const router = useRouter();
const loading = ref(false);
const saving = ref(false);
const testing = ref(false);

// 驱动列表
const drivers = ref<StorageDriverInfo[]>([]);
// 当前选中的驱动
const selectedDriver = ref<string | undefined>(undefined);
// 凭证
const credentials = ref({
  root_path: '',
  base_url: '',
  options: {} as Record<string, unknown>,
});
const credentialsVersion = ref(0);

// Impact analysis modal
const impactModalRef = ref<InstanceType<typeof StorageSwitchImpactModal>>();
const originalDriver = ref<string | undefined>(undefined);

// 通用存储参数（由 ConfigForm 渲染）
const generalConfigs = ref<ConfigItemMeta[]>([]);
const generalFormRef = ref<InstanceType<typeof ConfigForm>>();

/** 加载数据 */
async function loadData() {
  loading.value = true;
  try {
    // 分别加载驱动列表和配置详情，互不阻塞
    let driversData: StorageDriverInfo[] = [];
    try {
      driversData = await getStorageDriversApi();
    } catch (error) {
      console.error('[StoragePanel] getStorageDriversApi failed:', error);
    }
    drivers.value = driversData;

    const groupDetail = await getAdminConfigGroupDetailApi('platform_storage');

    // 从配置详情中提取当前值
    const configs = groupDetail.configs || [];
    const configMap = new Map<string, ConfigItemMeta>();
    for (const c of configs) {
      configMap.set(c.key, c);
    }

    // 驱动
    const driverConfig = configMap.get('platform_storage_driver');
    selectedDriver.value = (driverConfig?.value as string) || 'local';
    originalDriver.value = selectedDriver.value;

    // 凭证
    const rootPath = configMap.get('platform_storage_root_path');
    const baseUrl = configMap.get('platform_storage_base_url');
    const options = configMap.get('platform_storage_options');
    credentials.value = {
      root_path: (rootPath?.value as string) || '',
      base_url: (baseUrl?.value as string) || '',
      options: (options?.value as Record<string, unknown>) || {},
    };
    credentialsVersion.value++;

    // 通用参数（排除驱动/凭证相关的 key + 已废弃的全局开关，剩余给 ConfigForm 渲染）
    const excludeKeys = new Set([
      'platform_storage_base_url',
      'platform_storage_driver',
      'platform_storage_options',
      'platform_storage_root_path',
      // 自主配置权限改为逐租户控制，全局开关不再使用
      'platform_tenant_storage_self_config_enabled',
    ]);
    generalConfigs.value = configs
      .filter((c) => !excludeKeys.has(c.key))
      .toSorted((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
  } finally {
    loading.value = false;
  }
}

/** 保存全部配置（驱动变更时先展示影响分析） */
async function onSave() {
  // 非 local 驱动必须填 Bucket
  if (
    selectedDriver.value &&
    selectedDriver.value !== 'local' &&
    !credentials.value.root_path?.trim()
  ) {
    message.warning(
      `${$t('shared.storage.field.bucket')} ${$t('shared.storage.required')}`,
    );
    return;
  }

  // 驱动发生变更 → 先展示影响分析
  if (
    originalDriver.value &&
    selectedDriver.value &&
    originalDriver.value !== selectedDriver.value
  ) {
    impactModalRef.value?.open(originalDriver.value, selectedDriver.value);
    return;
  }

  await doSave();
}

/** 影响分析后确认切换 */
function onConfirmSwitch() {
  doSave();
}

/** 跳转到迁移管理页 */
function onGoMigrate(source: string, target: string) {
  router.push({
    path: '/admin/system/storage-migration',
    query: { source, target },
  });
}

/** 实际保存逻辑 */
async function doSave() {
  saving.value = true;
  try {
    // 收集通用参数
    let generalPayload: Record<string, unknown> = {};
    if (generalFormRef.value?.prepareSubmitData) {
      generalPayload = generalFormRef.value.prepareSubmitData();
    }

    // 合并驱动 + 凭证
    const payload: Record<string, unknown> = {
      ...generalPayload,
      platform_storage_driver: selectedDriver.value || 'local',
      platform_storage_root_path: credentials.value.root_path,
      platform_storage_base_url: credentials.value.base_url,
      platform_storage_options: credentials.value.options,
    };

    await updateAdminConfigGroupApi('platform_storage', payload, {
      showSuccessMessage: true,
    });
    await loadData();
  } finally {
    saving.value = false;
  }
}

/** 测试连接 */
async function onTestConnection() {
  if (!selectedDriver.value || selectedDriver.value === 'local') return;
  testing.value = true;
  try {
    const result = await testStorageConnectionApi({
      driver: selectedDriver.value,
      root_path: credentials.value.root_path,
      base_url: credentials.value.base_url,
      config: credentials.value.options,
    });
    if (result.success) {
      message.success($t('shared.storage.testSuccess'));
    } else {
      message.error(result.errors?.[0] || $t('shared.storage.testFailed'));
    }
  } catch {
    message.error($t('shared.storage.testFailed'));
  } finally {
    testing.value = false;
  }
}

/** 驱动为 local 时不显示凭证表单 */
const showCredentials = ref(false);
watch(
  selectedDriver,
  (d) => {
    showCredentials.value = !!d && d !== 'local';
  },
  { immediate: true },
);

let isInitialMount = true;
onMounted(() => {
  loadData();
});
onActivated(() => {
  if (isInitialMount) {
    isInitialMount = false;
    return;
  }
  loadData();
});

defineExpose({ onSave, saving });
</script>

<template>
  <Spin :spinning="loading">
    <div class="space-y-6">
      <!-- 驱动选择 -->
      <div>
        <div class="mb-2 text-sm font-medium">
          {{ $t('shared.storage.selectDriver') }}
        </div>
        <StorageDriverSelector
          v-model:value="selectedDriver"
          :drivers="drivers"
          :show-local="true"
        />
      </div>

      <!-- 凭证表单（非 local 时显示） -->
      <template v-if="showCredentials">
        <Divider />
        <StorageCredentialForm
          :key="credentialsVersion"
          v-model:value="credentials"
          :driver="selectedDriver || null"
        />
        <!-- 测试连接 -->
        <div class="flex gap-3">
          <Button
            :loading="testing"
            :disabled="!selectedDriver || selectedDriver === 'local'"
            @click="onTestConnection"
          >
            <template #icon>
              <IconifyIcon icon="lucide:wifi" />
            </template>
            {{ $t('shared.storage.testConnection') }}
          </Button>
        </div>
      </template>

      <!-- local 提示 -->
      <Alert
        v-if="selectedDriver === 'local'"
        type="info"
        show-icon
        :message="$t('shared.storage.modeDesc.platform')"
      />

      <!-- 通用存储参数 -->
      <template v-if="generalConfigs.length > 0">
        <Divider />
        <ConfigForm ref="generalFormRef" :configs="generalConfigs" />
      </template>
    </div>

    <!-- 存储切换影响分析弹窗 -->
    <StorageSwitchImpactModal
      ref="impactModalRef"
      @confirm-switch="onConfirmSwitch"
      @go-migrate="onGoMigrate"
    />
  </Spin>
</template>
