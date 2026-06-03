<script lang="ts" setup>
/**
 * Storage Driver Selector
 * 存储驱动选择器
 *
 * Displays all available storage drivers, marks plugin activation status.
 * 展示所有可用存储驱动，标记插件启用状态。
 * Disabled plugin drivers show "unavailable" tag and cannot be selected.
 * 未启用的插件驱动显示「不可用」标签且禁止选择。
 * Shared between admin and tenant storage config pages.
 * 管理端和企业端存储配置页面共用。
 */
import type { StorageDriverInfo } from '#/types/storage';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Select, Tag, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'StorageDriverSelector' });

const props = withDefaults(
  defineProps<{
    disabled?: boolean;
    drivers: StorageDriverInfo[];
    showLocal?: boolean;
  }>(),
  {
    disabled: false,
    showLocal: true,
  },
);

const modelValue = defineModel<string | undefined>('value', {
  default: undefined,
});

const filteredDrivers = computed(() => {
  if (props.showLocal) return props.drivers;
  return props.drivers.filter((d) => d.name !== 'local');
});

const driverIconMap: Record<string, string> = {
  local: 'lucide:hard-drive',
  s3: 'lucide:cloud',
  'aliyun-oss': 'lucide:cloud',
  'qiniu-kodo': 'lucide:cloud',
  'tencent-cos': 'lucide:cloud',
};

function getDriverIcon(name: string): string {
  return driverIconMap[name] || 'lucide:database';
}

/**
 * Driver display name translation
 * 驱动显示名称翻译
 *
 * Backend display_name has two formats:
 * 后端返回的 display_name 有两种情况：
 * 1. i18n key like "storage.driver.local" → convert to "shared.storage.driver.local" for translation
 *    i18n key 格式如 "storage.driver.local" → 转换为 "shared.storage.driver.local" 翻译
 * 2. Unregistered driver returns text directly like "七牛云 Kodo" → return as-is
 *    未注册驱动直接返回中文文本如 "七牛云 Kodo" → 原样返回
 *
 * Note: Only call keys that are known to exist, to avoid intlify Not found warnings.
 * 注意：只调用确定存在的 key，避免 intlify Not found 警告。
 */
function getDriverDisplayName(displayName: string): string {
  if (!displayName) return '';
  // Backend i18n key format "storage.driver.xxx" → frontend "shared.storage.driver.xxx" / 后端 i18n key 格式 "storage.driver.xxx" → 前端 "shared.storage.driver.xxx"
  if (displayName.startsWith('storage.driver.')) {
    return $t(`shared.${displayName}`);
  }
  // Not an i18n key (direct text), return as-is / 非 i18n key（直接中文/英文文本），原样返回
  return displayName;
}
</script>

<template>
  <Select
    v-model:value="modelValue"
    :placeholder="$t('shared.storage.selectDriver')"
    :disabled="disabled"
    class="w-full"
  >
    <Select.Option
      v-for="driver in filteredDrivers"
      :key="driver.name"
      :value="driver.name"
      :disabled="!driver.is_available"
    >
      <div class="flex items-center gap-2">
        <IconifyIcon
          :icon="getDriverIcon(driver.name)"
          class="h-4 w-4 flex-shrink-0"
        />
        <span>{{ getDriverDisplayName(driver.display_name) }}</span>
        <Tag v-if="driver.is_builtin" color="blue" class="ml-auto text-xs">
          {{ $t('shared.storage.builtin') }}
        </Tag>
        <Tooltip
          v-else-if="!driver.is_available"
          :title="$t('shared.storage.pluginNotEnabled')"
        >
          <Tag color="red" class="ml-auto text-xs">
            {{ $t('shared.storage.unavailable') }}
          </Tag>
        </Tooltip>
        <Tag
          v-else-if="driver.plugin_name"
          color="green"
          class="ml-auto text-xs"
        >
          {{ $t('shared.storage.plugin') }}
        </Tag>
      </div>
    </Select.Option>
  </Select>
</template>
