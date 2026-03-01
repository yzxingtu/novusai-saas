<script lang="ts" setup>
/**
 * 管理端租户存储配置抽屉
 *
 * 允许管理员为单个租户配置存储，三种模式互斥：
 * - 使用平台存储：租户使用全局存储，无需任何配置
 * - 管理员帮配：管理员填写云存储凭证，租户只读
 * - 允许租户自定义：租户可在自己的配置页面自行配置（从空白开始）
 *
 * 三个模式是纯 Radio 三选一，不存在独立开关。
 * 选「允许租户自定义」时 selfConfigEnabled 自动为 true，其他两个自动为 false。
 */
import type { StorageDriverInfo } from '#/types/storage';

import { ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Drawer,
  Form,
  FormItem,
  message,
  Radio,
  RadioGroup,
  Spin,
} from 'ant-design-vue';

import {
  getStorageDriversApi,
  getTenantStorageConfigApi,
  testTenantStorageConnectionApi,
  updateTenantStorageConfigApi,
} from '#/api/admin/configs';
import {
  StorageCredentialForm,
  StorageDriverSelector,
} from '#/components/business/storage-config';
import { $t } from '#/locales';

defineOptions({ name: 'TenantStorageDrawer' });

const visible = ref(false);
const loading = ref(false);
const saving = ref(false);
const testing = ref(false);

const tenantId = ref<number>(0);
const tenantName = ref('');

const drivers = ref<StorageDriverInfo[]>([]);
const storageMode = ref<string>('platform');
const selectedDriver = ref<string | undefined>(undefined);
const credentials = ref({
  root_path: '',
  base_url: '',
  options: {} as Record<string, unknown>,
});
const credentialsVersion = ref(0);

function open(tenant: { id: number; name: string }) {
  tenantId.value = tenant.id;
  tenantName.value = tenant.name;
  visible.value = true;
  loadData();
}

async function loadData() {
  loading.value = true;
  try {
    let driversData: StorageDriverInfo[] = [];
    try {
      driversData = await getStorageDriversApi();
    } catch (e) {
      console.error('[TenantStorageDrawer] getStorageDriversApi failed:', e);
    }
    drivers.value = driversData;

    const configData = await getTenantStorageConfigApi(tenantId.value);

    storageMode.value = (configData.tenant_storage_mode as string) || 'platform';
    const savedDriver = (configData.tenant_storage_driver as string) || undefined;

    // If saved driver's plugin is not available, clear selection
    const driverInfo = driversData.find((d: StorageDriverInfo) => d.name === savedDriver);
    selectedDriver.value = (driverInfo && driverInfo.is_available) ? savedDriver : undefined;

    credentials.value = {
      root_path: (configData.tenant_storage_root_path as string) || '',
      base_url: (configData.tenant_storage_base_url as string) || '',
      options: (configData.tenant_storage_options as Record<string, unknown>) || {},
    };
    credentialsVersion.value++;
  } finally {
    loading.value = false;
  }
}

async function onSave() {
  // admin_override 模式必填校验
  if (storageMode.value === 'admin_override') {
    if (!selectedDriver.value) {
      message.warning($t('shared.storage.selectDriver'));
      return;
    }
    if (!credentials.value.root_path?.trim()) {
      message.warning($t('shared.storage.field.bucket') + ' ' + $t('shared.storage.required'));
      return;
    }
  }
  saving.value = true;
  try {
    // selfConfigEnabled 由模式自动决定：custom=true，其他=false
    const isSelfConfig = storageMode.value === 'custom';
    await updateTenantStorageConfigApi(tenantId.value, {
      tenant_storage_mode: storageMode.value,
      tenant_storage_driver: storageMode.value === 'admin_override' ? (selectedDriver.value || null) : null,
      tenant_storage_root_path: storageMode.value === 'admin_override' ? credentials.value.root_path : '',
      tenant_storage_base_url: storageMode.value === 'admin_override' ? credentials.value.base_url : '',
      tenant_storage_options: storageMode.value === 'admin_override' ? credentials.value.options : {},
      tenant_storage_self_config_enabled: isSelfConfig,
    }, { showSuccessMessage: true });
  } finally {
    saving.value = false;
  }
}

async function onTestConnection() {
  if (!selectedDriver.value) return;
  testing.value = true;
  try {
    const result = await testTenantStorageConnectionApi(tenantId.value, {
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

defineExpose({ open });
</script>

<template>
  <Drawer
    v-model:open="visible"
    :title="`${$t('shared.storage.adminTab.title')} - ${tenantName}`"
    :width="560"
    :destroy-on-close="true"
  >
    <Spin :spinning="loading">
      <Form layout="vertical">
        <!-- 存储模式三选一 -->
        <FormItem :label="$t('shared.storage.adminTab.modeLabel')">
          <RadioGroup v-model:value="storageMode">
            <div class="flex flex-col gap-3">
              <Radio value="platform">
                <div>
                  <div class="font-medium">{{ $t('shared.storage.mode.platform') }}</div>
                  <div class="text-xs text-muted-foreground">{{ $t('shared.storage.modeDesc.platform') }}</div>
                </div>
              </Radio>
              <Radio value="admin_override">
                <div>
                  <div class="font-medium">{{ $t('shared.storage.mode.adminOverride') }}</div>
                  <div class="text-xs text-muted-foreground">{{ $t('shared.storage.modeDesc.adminOverride') }}</div>
                </div>
              </Radio>
              <Radio value="custom">
                <div>
                  <div class="font-medium">{{ $t('shared.storage.mode.custom') }}</div>
                  <div class="text-xs text-muted-foreground">{{ $t('shared.storage.modeDesc.custom') }}</div>
                </div>
              </Radio>
            </div>
          </RadioGroup>
        </FormItem>

        <!-- 管理员帮配模式：驱动选择 + 凭证表单 -->
        <template v-if="storageMode === 'admin_override'">
          <FormItem :label="$t('shared.storage.selectDriver')">
            <StorageDriverSelector
              v-model:value="selectedDriver"
              :drivers="drivers"
              :show-local="false"
            />
          </FormItem>

          <StorageCredentialForm
            :key="credentialsVersion"
            v-model:value="credentials"
            :driver="selectedDriver || null"
          />

          <!-- 测试连接 -->
          <div class="mt-4 flex gap-3">
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
          </div>
        </template>

        <!-- 使用平台存储提示 -->
        <Alert
          v-if="storageMode === 'platform'"
          type="info"
          show-icon
          :message="$t('shared.storage.modeDesc.platform')"
          class="mt-2"
        />

        <!-- 允许租户自定义提示 -->
        <Alert
          v-if="storageMode === 'custom'"
          type="success"
          show-icon
          :message="$t('shared.storage.adminTab.customHint')"
          class="mt-2"
        />
      </Form>
    </Spin>

    <template #footer>
      <div class="flex justify-end gap-3">
        <Button @click="visible = false">
          {{ $t('shared.common.cancel') }}
        </Button>
        <Button
          type="primary"
          :loading="saving"
          @click="onSave"
        >
          {{ $t('shared.storage.save') }}
        </Button>
      </div>
    </template>
  </Drawer>
</template>
