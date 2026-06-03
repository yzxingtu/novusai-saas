<script lang="ts" setup>
/**
 * Admin Platform Storage Configuration Panel
 * 管理端平台存储配置面板
 *
 * Replaces ConfigForm for platform_storage group, providing:
 * 替代 ConfigForm 渲染 platform_storage 分组，提供：
 * - Driver selector (aware of plugin enable status) / 驱动选择器
 * - Credential form (dynamically switches by driver) / 凭证表单
 * - Connection test button / 连接测试按钮
 * - General storage params (visibility/chunking/limits/extensions, still uses ConfigForm) / 通用存储参数
 *
 * Note: Tenant self-config is now per-tenant (in TenantStorageDrawer), no global switch.
 * 注意：企业自主配置权限改为逐企业控制，不再有全局开关。
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

// Driver list / 驱动列表
const drivers = ref<StorageDriverInfo[]>([]);
// Currently selected driver / 当前选中的驱动
const selectedDriver = ref<string | undefined>(undefined);
// Credentials / 凭证
const credentials = ref({
  root_path: '',
  base_url: '',
  options: {} as Record<string, unknown>,
});
const credentialsVersion = ref(0);

// Impact analysis modal / 影响分析弹窗
const impactModalRef = ref<InstanceType<typeof StorageSwitchImpactModal>>();
const originalDriver = ref<string | undefined>(undefined);

// General storage params (rendered by ConfigForm) / 通用存储参数
const generalConfigs = ref<ConfigItemMeta[]>([]);
const generalFormRef = ref<InstanceType<typeof ConfigForm>>();

/** Load data / 加载数据 */
async function loadData() {
  loading.value = true;
  try {
    // Load driver list and config details independently / 分别加载驱动列表和配置详情
    let driversData: StorageDriverInfo[] = [];
    try {
      driversData = await getStorageDriversApi();
    } catch (error) {
      console.error('[StoragePanel] getStorageDriversApi failed:', error);
    }
    drivers.value = driversData;

    const groupDetail = await getAdminConfigGroupDetailApi('platform_storage');

    // Extract current values from config details / 从配置详情中提取当前值
    const configs = groupDetail.configs || [];
    const configMap = new Map<string, ConfigItemMeta>();
    for (const c of configs) {
      configMap.set(c.key, c);
    }

    // Driver / 驱动
    const driverConfig = configMap.get('platform_storage_driver');
    selectedDriver.value = (driverConfig?.value as string) || 'local';
    originalDriver.value = selectedDriver.value;

    // Credentials / 凭证
    const rootPath = configMap.get('platform_storage_root_path');
    const baseUrl = configMap.get('platform_storage_base_url');
    const options = configMap.get('platform_storage_options');
    credentials.value = {
      root_path: (rootPath?.value as string) || '',
      base_url: (baseUrl?.value as string) || '',
      options: (options?.value as Record<string, unknown>) || {},
    };
    credentialsVersion.value++;

    // General params (exclude driver/credential keys + deprecated global switch, rest for ConfigForm) / 通用参数
    const excludeKeys = new Set([
      'platform_storage_base_url',
      'platform_storage_driver',
      'platform_storage_options',
      'platform_storage_root_path',
      // Self-config permission now per-tenant, global switch no longer used / 自主配置权限逐企业控制
      'platform_tenant_storage_self_config_enabled',
    ]);
    generalConfigs.value = configs
      .filter((c) => !excludeKeys.has(c.key))
      .toSorted((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
  } finally {
    loading.value = false;
  }
}

/** Save all config (show impact analysis on driver change) / 保存全部配置 */
async function onSave() {
  // Non-local driver requires Bucket / 非 local 驱动必须填 Bucket
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

  // Driver changed → show impact analysis first / 驱动变更先展示影响分析
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

/** Confirm switch after impact analysis / 影响分析后确认切换 */
function onConfirmSwitch() {
  doSave();
}

/** Navigate to migration management page / 跳转到迁移管理页 */
function onGoMigrate(source: string, target: string) {
  router.push({
    path: '/admin/plugins/storage-migration',
    query: { source, target },
  });
}

/** Actual save logic / 实际保存逻辑 */
async function doSave() {
  saving.value = true;
  try {
    // Collect general params / 收集通用参数
    let generalPayload: Record<string, unknown> = {};
    if (generalFormRef.value?.prepareSubmitData) {
      generalPayload = generalFormRef.value.prepareSubmitData();
    }

    // Merge driver + credentials / 合并驱动 + 凭证
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

/** Test connection / 测试连接 */
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

/** Hide credential form when driver is local / 驱动为 local 时不显示凭证表单 */
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
      <!-- Driver selection / 驱动选择 -->
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

      <!-- Credential form (shown when not local) / 凭证表单 -->
      <template v-if="showCredentials">
        <Divider />
        <StorageCredentialForm
          :key="credentialsVersion"
          v-model:value="credentials"
          :driver="selectedDriver || null"
        />
        <!-- Test connection / 测试连接 -->
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

      <!-- Local mode hint / local 提示 -->
      <Alert
        v-if="selectedDriver === 'local'"
        type="info"
        show-icon
        :message="$t('shared.storage.modeDesc.platform')"
      />

      <!-- General storage params / 通用存储参数 -->
      <template v-if="generalConfigs.length > 0">
        <Divider />
        <ConfigForm ref="generalFormRef" :configs="generalConfigs" />
      </template>
    </div>

    <!-- Storage switch impact analysis modal / 存储切换影响分析弹窗 -->
    <StorageSwitchImpactModal
      ref="impactModalRef"
      @confirm-switch="onConfirmSwitch"
      @go-migrate="onGoMigrate"
    />
  </Spin>
</template>
