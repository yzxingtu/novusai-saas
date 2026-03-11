<script setup lang="ts">
import type { ConfigGroupListItemMeta, ConfigItemMeta } from '#/types/config';

import { computed, onActivated, onBeforeUnmount, onMounted, onUnmounted, ref } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';
import { registerPageOperations } from '#/components/business/ai-slide-panel/page-operation-registry';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Button, Card, Empty, Modal, Spin } from 'ant-design-vue';

import {
  generateFernetKeyApi,
  getAdminConfigGroupDetailApi,
  getAdminConfigGroupsApi,
  updateAdminConfigGroupApi,
} from '#/api/admin/configs';
import { ConfigForm } from '#/components';
import PluginSettingsTabs from '#/components/business/plugin-slots/PluginSettingsTabs.vue';
import { $t, $t as t } from '#/locales';

// Platform storage config dedicated panel / 平台存储配置专用面板
import PlatformStoragePanel from './modules/PlatformStoragePanel.vue';

defineOptions({ name: 'SystemConfigList' });

const generatingKey = ref(false);
async function onGenerateFernetKey(setValue: (v: string) => void) {
  generatingKey.value = true;
  try {
    const result = await generateFernetKeyApi();
    setValue(result.key);
  } catch {
  } finally {
    generatingKey.value = false;
  }
}

const groups = ref<ConfigGroupListItemMeta[]>([]);
const activeGroup = ref<string>('');
const configs = ref<ConfigItemMeta[]>([]);
const loading = ref(false);
const groupLoading = ref(false);
const saving = ref(false);
const formRef = ref<any>();
const storagePanelRef = ref<{
  onSave: () => Promise<void>;
  saving: { value: boolean };
}>();

// Currently selected group data / 当前选中的分组数据
const activeGroupData = computed(() =>
  groups.value.find((g) => g.code === activeGroup.value),
);

// Get group name (prefer name, then name_key translation, fallback to code) / 获取分组名称
function getGroupName(g: ConfigGroupListItemMeta): string {
  // 1. Use name field directly / 直接使用 name 字段
  if (g.name) return g.name;
  // 2. Use name_key translation / 使用 name_key 翻译
  if (g.name_key) {
    const translated = t(g.name_key);
    if (translated !== g.name_key) return translated;
  }
  // 3. Fallback: try shared.config.group.{code} format / 尝试使用此格式
  const fallbackKey = `shared.config.group.${g.code}`;
  const fallbackTranslated = t(fallbackKey);
  if (fallbackTranslated !== fallbackKey) return fallbackTranslated;
  // 4. Final fallback to code / 最后 fallback 到 code
  return g.code;
}

// Get group description / 获取分组描述
function getGroupDesc(g: ConfigGroupListItemMeta): string {
  // 1. Use description field directly / 直接使用 description 字段
  if (g.description) return g.description;
  // 2. Use description_key translation / 使用 description_key 翻译
  if (g.description_key) {
    const translated = t(g.description_key);
    if (translated !== g.description_key) return translated;
  }
  // 3. Fallback: try shared.config.group_desc.{code} format / 尝试使用此格式
  const fallbackKey = `shared.config.group_desc.${g.code}`;
  const fallbackTranslated = t(fallbackKey);
  if (fallbackTranslated !== fallbackKey) return fallbackTranslated;
  return '';
}

// Groups sorted by sort_order / 按 sort_order 排序的分组列表
const sortedGroups = computed(() =>
  groups.value.toSorted((a, b) => (a.sort_order || 0) - (b.sort_order || 0)),
);

async function loadGroups() {
  groupLoading.value = true;
  try {
    groups.value = await getAdminConfigGroupsApi();
    if (groups.value.length > 0) {
      // Pick first group by sort_order / 按 sort_order 取第一个组
      const sorted = groups.value.toSorted(
        (a, b) => (a.sort_order || 0) - (b.sort_order || 0),
      );
      const firstGroup = sorted[0];
      if (!firstGroup) return;
      activeGroup.value = firstGroup.code;
      // platform_storage uses dedicated panel, no need to load config detail / 专用面板无需加载配置详情
      if (activeGroup.value !== 'platform_storage') {
        await loadGroupDetail(activeGroup.value);
      }
    }
  } finally {
    groupLoading.value = false;
  }
}

async function loadGroupDetail(code: string) {
  loading.value = true;
  try {
    const detail = await getAdminConfigGroupDetailApi(code);
    configs.value = (detail.configs || []).toSorted(
      (a, b) => (a.sort_order || 0) - (b.sort_order || 0),
    );
  } finally {
    loading.value = false;
  }
}

async function onSelectGroup(code: string) {
  if (code === activeGroup.value) return;
  // Check if form has modifications / 检查表单是否有修改
  if (formRef.value?.isDirty?.()) {
    Modal.confirm({
      title: t('shared.config.page.unsaved_title'),
      content: t('shared.config.page.unsaved_content'),
      okText: t('shared.common.confirm'),
      cancelText: t('shared.common.cancel'),
      onOk: async () => {
        activeGroup.value = code;
        // platform_storage uses dedicated panel / 专用面板
        if (code !== 'platform_storage') {
          await loadGroupDetail(code);
        }
      },
    });
  } else {
    activeGroup.value = code;
    // platform_storage uses dedicated panel / 专用面板
    if (code !== 'platform_storage') {
      await loadGroupDetail(code);
    }
  }
}

async function onSave() {
  if (!activeGroup.value) return;
  if (activeGroup.value === 'platform_storage') {
    await storagePanelRef.value?.onSave();
    return;
  }
  try {
    await formRef.value?.validate();
  } catch {
    // Form validation failed, do not submit / 表单验证失败
    return;
  }
  const payload = formRef.value?.prepareSubmitData();
  saving.value = true;
  try {
    await updateAdminConfigGroupApi(activeGroup.value, payload, {
      showSuccessMessage: true,
    });
    // Reload to reflect latest values / 重新加载以反显最新值
    await loadGroupDetail(activeGroup.value);
  } catch {
    // Error already handled and displayed by request interceptor / 错误已由拦截器处理
  } finally {
    saving.value = false;
  }
}

// Browser close/refresh reminder / 浏览器关闭刷新提醒
function beforeUnloadHandler(e: BeforeUnloadEvent) {
  if (formRef.value?.isDirty?.()) {
    e.preventDefault();
    e.returnValue = '';
  }
}
let isInitialMount = true;
onMounted(() => {
  loadGroups();
  window.addEventListener('beforeunload', beforeUnloadHandler);
});
onActivated(() => {
  if (isInitialMount) {
    isInitialMount = false;
    return;
  }
  if (activeGroup.value && activeGroup.value !== 'platform_storage') {
    loadGroupDetail(activeGroup.value);
  }
});
onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', beforeUnloadHandler);
});

const cleanupPageContext = registerPageContext('admin/system/configs', () => ({
  page_key: 'admin.system.configs',
  page_title: $t('admin.system.config.title'),
  page_data: {
    resource: '/admin/system/configs',
    active_group: activeGroup.value,
  },
}));

const cleanupPageOps = registerPageOperations('admin.system.configs', [
  {
    name: 'refresh_configs',
    label: $t('shared.pageOperation.refreshConfig'),
    description: 'Reload config groups and current group detail',
    readonly: true,
    handler: async () => {
      await loadGroups();
      return { success: true, message: 'Config groups refreshed' };
    },
  },
  {
    name: 'save_config',
    label: $t('shared.pageOperation.saveConfig'),
    description: 'Save the current config group settings',
    readonly: false,
    handler: async () => {
      await onSave();
      return { success: true, message: 'Config saved' };
    },
  },
]);

onUnmounted(() => {
  cleanupPageContext();
  cleanupPageOps();
});
</script>

<template>
  <Page auto-content-height>
    <div
      class="relative z-0 flex h-full flex-col gap-4 overflow-hidden md:flex-row"
    >
      <!-- Left: Config group list / 左侧配置分组列表 -->
      <Card
        class="w-full flex-shrink-0 overflow-hidden md:w-[260px]"
        :body-style="{
          padding: 0,
          height: 'calc(100% - 57px)',
          overflow: 'auto',
        }"
      >
        <template #title>
          <div class="flex items-center gap-2">
            <IconifyIcon icon="lucide:settings" class="h-4 w-4 text-primary" />
            <span>{{ t('shared.config.page.title') }}</span>
          </div>
        </template>
        <Spin :spinning="groupLoading" class="h-full">
          <div class="py-2">
            <div
              v-for="g in sortedGroups"
              :key="g.code"
              class="group-item mx-2 mb-1 cursor-pointer rounded-lg px-3 py-2.5 transition-colors"
              :class="[
                g.code === activeGroup
                  ? 'bg-primary/10 text-primary'
                  : 'hover:bg-accent',
              ]"
              @click="onSelectGroup(g.code)"
            >
              <div class="flex items-center gap-2 font-medium">
                <IconifyIcon
                  v-if="g.icon"
                  :icon="g.icon"
                  class="h-4 w-4 flex-shrink-0"
                />
                <span>{{ getGroupName(g) }}</span>
              </div>
              <div
                v-if="getGroupDesc(g)"
                class="mt-0.5 text-xs text-muted-foreground"
                :class="g.icon ? 'ml-6' : ''"
              >
                {{ getGroupDesc(g) }}
              </div>
            </div>
            <Empty
              v-if="!groupLoading && groups.length === 0"
              :description="t('shared.common.noData')"
              class="py-8"
            />
          </div>
        </Spin>
      </Card>

      <!-- Right: Config form / 右侧配置表单 -->
      <Card
        class="min-w-0 flex-1 overflow-hidden"
        :body-style="{
          padding: '16px 24px',
          height: 'calc(100% - 57px)',
          overflow: 'auto',
        }"
      >
        <template #title>
          <span>{{
            activeGroupData ? getGroupName(activeGroupData) : ''
          }}</span>
        </template>
        <template #extra>
          <Button
            type="primary"
            v-access:code="['platform_config:update']"
            :loading="
              activeGroup === 'platform_storage'
                ? storagePanelRef?.saving?.value
                : saving
            "
            :disabled="!activeGroup"
            @click="onSave"
          >
            <template #icon>
              <IconifyIcon icon="lucide:save" />
            </template>
            {{ t('shared.common.save') }}
          </Button>
        </template>

        <Spin :spinning="loading">
          <!-- platform_storage group uses dedicated storage config panel / 专用存储配置面板 -->
          <PlatformStoragePanel
            v-if="activeGroup === 'platform_storage'"
            ref="storagePanelRef"
          />
          <div v-else-if="activeGroup" class="max-w-[800px]">
            <ConfigForm ref="formRef" :configs="configs">
              <template #generate-ssl_private_key_encryption_key="{ setValue }">
                <Button
                  size="small"
                  :loading="generatingKey"
                  @click="onGenerateFernetKey(setValue)"
                >
                  <IconifyIcon icon="lucide:key" class="mr-1 size-3" />
                  {{ t('shared.config.generate_key') }}
                </Button>
              </template>
            </ConfigForm>
            <PluginSettingsTabs />
          </div>
          <Empty
            v-else
            :description="t('shared.config.page.select_group')"
            class="py-16"
          />
        </Spin>
      </Card>
    </div>
  </Page>
</template>

<style scoped>
.group-item.active {
  font-weight: 500;
}
</style>
