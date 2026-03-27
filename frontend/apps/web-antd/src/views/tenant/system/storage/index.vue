<script lang="ts" setup>
/**
 * Tenant storage configuration page
 * 企业端存储配置页面
 *
 * Displays tenant's current storage status, supports three modes:
 * 展示企业当前存储状态，支持三种模式：
 * - Mode 1 (platform): use platform global storage (readonly)
 * - 模式 1 (platform): 使用平台全局存储（只读展示）
 * - Mode 2 (admin_override): admin-specified storage (readonly)
 * - 模式 2 (admin_override): 管理端指定存储（只读展示）
 * - Mode 3 (custom): tenant self-configured cloud storage (editable)
 * - 模式 3 (custom): 企业自主配置云存储（可编辑）
 */
import type { StorageDriverInfo, TenantStorageStatus } from '#/types/storage';

import { computed, onActivated, onMounted, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Card,
  Descriptions,
  DescriptionsItem,
  Divider,
  message,
  Spin,
  Tag,
} from 'ant-design-vue';

import {
  getTenantStorageDriversApi,
  getTenantStorageStatusApi,
  saveTenantStorageConfigApi,
  testTenantStorageConnectionApi,
} from '#/api/tenant/configs';
import {
  StorageCredentialForm,
  StorageDriverSelector,
} from '#/components/business/storage-config';
import {
  createRefreshPageOperation,
  createSavePageOperation,
  createSimplePageOperation,
} from '#/composables/use-page-ai-operation-helpers';
import {
  usePageAIContext,
  usePageAIOperations,
} from '#/composables/use-page-ai-registration';
import { $t } from '#/locales';
import { showRequestError } from '#/utils/error-helpers';

defineOptions({ name: 'TenantStorageConfig' });
const AI_PAGE_KEY = 'tenant.system.storage';

const loading = ref(false);
const saving = ref(false);
const testing = ref(false);

const status = ref<null | TenantStorageStatus>(null);
const drivers = ref<StorageDriverInfo[]>([]);

const selectedDriver = ref<string | undefined>(undefined);
const credentials = ref({
  root_path: '',
  base_url: '',
  options: {} as Record<string, unknown>,
});
const credentialsVersion = ref(0);

/** Whether self-config is allowed (both mode 3 switches are on) / 是否可以自主配置（模式 3 的两个开关都打开） */
const canSelfConfig = computed(() => status.value?.can_self_config ?? false);

/** Current effective storage mode / 当前生效的存储模式 */
const effectiveMode = computed(
  () => status.value?.effective_mode ?? 'platform',
);

/** Current effective driver / 当前生效的驱动 */
const effectiveDriver = computed(
  () => status.value?.effective_driver ?? 'local',
);

/** Mode tag color / 模式标签颜色 */
function getModeColor(mode: string): string {
  switch (mode) {
    case 'admin_override': {
      return 'orange';
    }
    case 'custom': {
      return 'green';
    }
    case 'platform': {
      return 'blue';
    }
    default: {
      return 'default';
    }
  }
}

/** Mode display text / 模式显示文本 */
function getModeText(mode: string): string {
  switch (mode) {
    case 'admin_override': {
      return $t('shared.storage.mode.adminOverride');
    }
    case 'custom': {
      return $t('shared.storage.mode.custom');
    }
    case 'platform': {
      return $t('shared.storage.mode.platform');
    }
    default: {
      return mode;
    }
  }
}

/** Driver name translation (same as StorageDriverSelector logic) / 驱动名称翻译（同 StorageDriverSelector 逻辑） */
function getDriverDisplayName(name: string): string {
  if (!name) return '-';
  if (name.startsWith('storage.driver.')) {
    return $t(`shared.${name}`);
  }
  // Driver code name (e.g. qiniu-kodo) → try translating / 驱动代码名（如 qiniu-kodo）→ 尝试翻译
  const key = `shared.storage.driver.${name.replaceAll('-', '_')}`;
  const result = $t(key);
  return result === key ? name : result;
}

/** Load data / 加载数据 */
async function loadData() {
  loading.value = true;
  try {
    let driversData: StorageDriverInfo[] = [];
    try {
      driversData = await getTenantStorageDriversApi();
    } catch (error) {
      console.error(
        '[TenantStorage] getTenantStorageDriversApi failed:',
        error,
      );
    }
    drivers.value = driversData;

    const statusData = await getTenantStorageStatusApi();
    status.value = statusData;

    // Custom mode: backfill non-sensitive fields (driver/bucket/domain), but start secrets from blank
    // custom 模式回填非敏感字段（驱动/Bucket/域名），但密钥从空白开始
    // Backend returns desensitized options (e.g. AK****CD), cannot backfill to password inputs
    // 后端返回的 options 是脱敏的（如 AK****CD），不能回填到密码输入框
    if (
      statusData.effective_mode === 'custom' &&
      statusData.tenant_storage_driver
    ) {
      selectedDriver.value = statusData.tenant_storage_driver;
      credentials.value = {
        root_path: statusData.tenant_storage_root_path || '',
        base_url: statusData.tenant_storage_base_url || '',
        options: {}, // Don't backfill secrets, start from blank / 密钥不回填，从空白开始
      };
    } else {
      // Non-custom mode (platform/admin_override): display-only, no form backfill needed / 非 custom 模式（platform/admin_override）: 仅用于状态展示，不需要回填表单
      selectedDriver.value = undefined;
      credentials.value = { root_path: '', base_url: '', options: {} };
    }
    credentialsVersion.value++;
  } finally {
    loading.value = false;
  }
}

/** Save custom storage config / 保存自定义存储配置 */
async function onSave() {
  if (!canSelfConfig.value) {
    return {
      success: false,
      message: $t('shared.storage.status.selfConfigNotAllowed'),
    };
  }
  if (!selectedDriver.value) {
    message.warning($t('shared.storage.selectDriver'));
    return {
      success: false,
      message: $t('shared.storage.selectDriver'),
    };
  }
  if (!credentials.value.root_path?.trim()) {
    const messageText = `${$t('shared.storage.field.bucket')} ${$t('shared.storage.required')}`;
    message.warning(messageText);
    return {
      success: false,
      message: messageText,
    };
  }
  saving.value = true;
  try {
    // Build save data: skip empty options to avoid overwriting backend secrets
    // 构建保存数据：如果 options 为空对象则不发送，避免覆盖后端已有的密钥
    // (loadData doesn't backfill desensitized options, so don't overwrite if tenant didn't re-enter secrets)
    // （因为 loadData 时不回填脱敏的 options，如果企业没重新填写密钥就不应覆盖）
    const saveData: Record<string, unknown> = {
      tenant_storage_mode: 'custom',
      tenant_storage_driver: selectedDriver.value,
      tenant_storage_root_path: credentials.value.root_path,
      tenant_storage_base_url: credentials.value.base_url,
    };
    const opts = credentials.value.options;
    if (opts && Object.keys(opts).length > 0) {
      saveData.tenant_storage_options = opts;
    }
    await saveTenantStorageConfigApi(saveData, { showSuccessMessage: true });
    await loadData();
  } finally {
    saving.value = false;
  }
}

/** Test connection / 测试连接 */
async function onTestConnection() {
  if (!canSelfConfig.value) {
    return {
      success: false,
      message: $t('shared.storage.status.selfConfigNotAllowed'),
    };
  }
  if (!selectedDriver.value) {
    return {
      success: false,
      message: $t('shared.storage.selectDriver'),
    };
  }
  testing.value = true;
  try {
    const result = await testTenantStorageConnectionApi({
      driver: selectedDriver.value,
      root_path: credentials.value.root_path,
      base_url: credentials.value.base_url,
      config: credentials.value.options,
    });
    if (result.success) {
      message.success($t('shared.storage.testSuccess'));
      return {
        success: true,
        message: $t('shared.storage.testSuccess'),
      };
    } else {
      const messageText = result.errors?.[0] || $t('shared.storage.testFailed');
      message.error(messageText);
      return {
        success: false,
        message: messageText,
      };
    }
  } catch (error) {
    showRequestError(error, 'shared.storage.testFailed');
    return {
      success: false,
      message: $t('shared.storage.testFailed'),
    };
  } finally {
    testing.value = false;
  }
}

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

usePageAIContext({
  pageKey: AI_PAGE_KEY,
  title: () => $t('tenant.system.storage.name'),
  resource: '/tenant/system/storage',
  data: () => ({
    can_self_config: canSelfConfig.value,
    current_form_driver: selectedDriver.value ?? null,
    drivers_total: drivers.value.length,
    effective_driver: effectiveDriver.value,
    effective_mode: status.value?.effective_mode ?? 'unknown',
  }),
});

usePageAIOperations({
  pageKey: AI_PAGE_KEY,
  operationStrategy: 'append',
  operations: [
    createRefreshPageOperation({
      name: 'refresh_status',
      action: loadData,
      description: 'Reload storage status and driver list',
    }),
    createSavePageOperation({
      name: 'save_config',
      label: $t('shared.pageOperation.saveConfig'),
      description:
        'Save the current storage configuration (only available in custom mode)',
      action: onSave,
    }),
    createSimplePageOperation({
      name: 'test_connection',
      label: $t('shared.storage.testConnection'),
      description:
        'Test the current storage connection with the selected driver and credentials / 使用当前所选驱动与凭证测试存储连接',
      readonly: false,
      action: onTestConnection,
    }),
  ],
});
</script>

<template>
  <Spin :spinning="loading">
    <div class="mx-auto max-w-[800px] space-y-6 py-2">
      <!-- Current storage status card / 当前存储状态卡片 -->
      <Card>
        <template #title>
          <div class="flex items-center gap-2">
            <IconifyIcon icon="lucide:database" class="h-5 w-5 text-primary" />
            <span>{{ $t('shared.storage.status.title') }}</span>
          </div>
        </template>

        <Descriptions :column="2" bordered size="small">
          <DescriptionsItem :label="$t('shared.storage.status.currentMode')">
            <Tag :color="getModeColor(effectiveMode)">
              {{ getModeText(effectiveMode) }}
            </Tag>
          </DescriptionsItem>
          <DescriptionsItem :label="$t('shared.storage.status.currentDriver')">
            <Tag color="default">
              {{ getDriverDisplayName(effectiveDriver) }}
            </Tag>
          </DescriptionsItem>
        </Descriptions>

        <!-- Readonly hint: mode 1 or mode 2 / 只读提示：模式 1 或模式 2 -->
        <Alert
          v-if="
            effectiveMode === 'platform' || effectiveMode === 'admin_override'
          "
          type="info"
          show-icon
          :message="$t('shared.storage.status.readonlyHint')"
          class="mt-4"
        />

        <!-- Self-config not allowed hint / 未开放自主配置提示 -->
        <Alert
          v-if="effectiveMode === 'platform' && !canSelfConfig"
          type="warning"
          show-icon
          :message="$t('shared.storage.status.selfConfigNotAllowed')"
          class="mt-4"
        />
      </Card>

      <!-- Admin override mode: show desensitized config info (readonly) / 管理员帮配模式：展示脱敏后的配置信息（只读） -->
      <Card v-if="effectiveMode === 'admin_override' && status">
        <template #title>
          <div class="flex items-center gap-2">
            <IconifyIcon
              icon="lucide:shield-check"
              class="h-5 w-5 text-primary"
            />
            <span>{{ $t('shared.storage.adminOverrideDetail.title') }}</span>
          </div>
        </template>

        <Descriptions :column="1" bordered size="small">
          <DescriptionsItem
            :label="$t('shared.storage.adminOverrideDetail.driver')"
          >
            <Tag color="blue">
              {{ getDriverDisplayName(status.tenant_storage_driver || '') }}
            </Tag>
          </DescriptionsItem>
          <DescriptionsItem :label="$t('shared.storage.field.bucket')">
            {{ status.tenant_storage_root_path || '-' }}
          </DescriptionsItem>
          <DescriptionsItem :label="$t('shared.storage.field.baseUrl')">
            {{ status.tenant_storage_base_url || '-' }}
          </DescriptionsItem>
          <template v-if="status.tenant_storage_options">
            <DescriptionsItem
              v-for="(val, key) in status.tenant_storage_options"
              :key="key"
              :label="String(key)"
            >
              <span class="font-mono text-xs">{{ val }}</span>
            </DescriptionsItem>
          </template>
        </Descriptions>
      </Card>

      <!-- Self-config form (only shown when mode 3 is enabled) / 自主配置表单（仅模式 3 开放时显示） -->
      <Card v-if="canSelfConfig">
        <template #title>
          <div class="flex items-center gap-2">
            <IconifyIcon icon="lucide:cloud" class="h-5 w-5 text-primary" />
            <span>{{ $t('shared.storage.mode.custom') }}</span>
          </div>
        </template>
        <template #extra>
          <div class="flex gap-2">
            <Button
              :loading="testing"
              :disabled="!selectedDriver"
              @click="onTestConnection"
            >
              <template #icon>
                <IconifyIcon icon="lucide:wifi" />
              </template>
              {{ $t('shared.storage.testConnection') }}
            </Button>
            <Button type="primary" :loading="saving" @click="onSave">
              <template #icon>
                <IconifyIcon icon="lucide:save" />
              </template>
              {{ $t('shared.storage.save') }}
            </Button>
          </div>
        </template>

        <Alert
          type="info"
          show-icon
          :message="$t('shared.storage.status.selfConfigEnabled')"
          class="mb-4"
        />

        <!-- Driver selection / 驱动选择 -->
        <div class="mb-4">
          <div class="mb-2 text-sm font-medium">
            {{ $t('shared.storage.selectDriver') }}
          </div>
          <StorageDriverSelector
            v-model:value="selectedDriver"
            :drivers="drivers"
            :show-local="false"
          />
        </div>

        <Divider />

        <!-- Credential form / 凭证表单 -->
        <StorageCredentialForm
          :key="credentialsVersion"
          v-model:value="credentials"
          :driver="selectedDriver || null"
        />
      </Card>
    </div>
  </Spin>
</template>
