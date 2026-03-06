<script setup lang="ts">
import type { ConfigGroupListItemMeta, ConfigItemMeta } from '#/types/config';

import { computed, onBeforeUnmount, onMounted, onUnmounted, ref } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Button, Card, Empty, Modal, Spin } from 'ant-design-vue';

import {
  getTenantConfigGroupDetailApi,
  getTenantConfigGroupsApi,
  updateTenantConfigGroupApi,
} from '#/api/tenant/configs';
import { ConfigForm } from '#/components';
import PluginSettingsTabs from '#/components/business/plugin-slots/PluginSettingsTabs.vue';
import { $t as t } from '#/locales';

// 存储配置专用页面（懒加载）
import TenantStoragePanel from '../storage/index.vue';

defineOptions({ name: 'TenantConfigList' });

const groups = ref<ConfigGroupListItemMeta[]>([]);
const activeGroup = ref<string>('');
const configs = ref<ConfigItemMeta[]>([]);
const loading = ref(false);
const groupLoading = ref(false);
const saving = ref(false);
const formRef = ref<any>();

// 当前选中的分组数据
const activeGroupData = computed(() =>
  groups.value.find((g) => g.code === activeGroup.value),
);

// 获取分组名称（优先使用 name，其次 name_key 翻译，最后 fallback 到 code）
function getGroupName(g: ConfigGroupListItemMeta): string {
  if (g.name) return g.name;
  if (g.name_key) {
    const translated = t(g.name_key);
    if (translated !== g.name_key) return translated;
  }
  const fallbackKey = `shared.config.group.${g.code}`;
  const fallbackTranslated = t(fallbackKey);
  if (fallbackTranslated !== fallbackKey) return fallbackTranslated;
  return g.code;
}

// 获取分组描述
function getGroupDesc(g: ConfigGroupListItemMeta): string {
  if (g.description) return g.description;
  if (g.description_key) {
    const translated = t(g.description_key);
    if (translated !== g.description_key) return translated;
  }
  const fallbackKey = `shared.config.group.${g.code}.desc`;
  const fallbackTranslated = t(fallbackKey);
  if (fallbackTranslated !== fallbackKey) return fallbackTranslated;
  return '';
}

// 按 sort_order 排序的分组列表
const sortedGroups = computed(() =>
  groups.value.toSorted((a, b) => (a.sort_order || 0) - (b.sort_order || 0)),
);

async function loadGroups() {
  groupLoading.value = true;
  try {
    groups.value = await getTenantConfigGroupsApi();
    if (groups.value.length > 0) {
      // 按 sort_order 取第一个组
      const sorted = groups.value.toSorted(
        (a, b) => (a.sort_order || 0) - (b.sort_order || 0),
      );
      const firstGroup = sorted[0];
      if (!firstGroup) return;
      activeGroup.value = firstGroup.code;
      // tenant_storage 组用专用面板，不需要加载配置详情
      if (activeGroup.value !== 'tenant_storage') {
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
    const detail = await getTenantConfigGroupDetailApi(code);
    configs.value = (detail.configs || []).toSorted(
      (a, b) => (a.sort_order || 0) - (b.sort_order || 0),
    );
  } finally {
    loading.value = false;
  }
}

async function onSelectGroup(code: string) {
  if (code === activeGroup.value) return;
  // 检查表单是否有修改
  if (formRef.value?.isDirty?.()) {
    Modal.confirm({
      title: t('shared.config.page.unsaved_title'),
      content: t('shared.config.page.unsaved_content'),
      okText: t('shared.common.confirm'),
      cancelText: t('shared.common.cancel'),
      onOk: async () => {
        activeGroup.value = code;
        // tenant_storage 组用专用面板，不需要加载配置详情
        if (code !== 'tenant_storage') {
          await loadGroupDetail(code);
        }
      },
    });
  } else {
    activeGroup.value = code;
    // tenant_storage 组用专用面板，不需要加载配置详情
    if (code !== 'tenant_storage') {
      await loadGroupDetail(code);
    }
  }
}

async function onSave() {
  if (!activeGroup.value) return;
  try {
    await formRef.value?.validate();
  } catch {
    // 表单验证失败，不继续提交
    return;
  }
  const payload = formRef.value?.prepareSubmitData();
  saving.value = true;
  try {
    await updateTenantConfigGroupApi(activeGroup.value, payload, {
      showSuccessMessage: true,
    });
    await loadGroupDetail(activeGroup.value);
  } catch {
    // 错误已经由 request 拦截器处理并显示
  } finally {
    saving.value = false;
  }
}

function beforeUnloadHandler(e: BeforeUnloadEvent) {
  if (formRef.value?.isDirty?.()) {
    e.preventDefault();
    e.returnValue = '';
  }
}
onMounted(() => {
  loadGroups();
  window.addEventListener('beforeunload', beforeUnloadHandler);
});
onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', beforeUnloadHandler);
});

const cleanupPageContext = registerPageContext('tenant/system/configs', () => ({
  page_key: 'tenant.system.configs',
  page_title: t('tenant.system.config.name'),
  page_data: {
    resource: '/tenant/system/configs',
    total_groups: groups.value.length,
  },
}));

onUnmounted(cleanupPageContext);
</script>

<template>
  <Page auto-content-height>
    <div class="flex h-full flex-col gap-4 overflow-hidden md:flex-row">
      <!-- 左侧：配置分组列表 -->
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

      <!-- 右侧：配置表单 -->
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
          <!-- 存储配置组的保存按钮在存储组件内部管理，此处隐藏 -->
          <Button
            v-if="activeGroup !== 'tenant_storage'"
            type="primary"
            v-access:code="['tenant_config:update']"
            :loading="saving"
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
          <!-- tenant_storage 分组使用专用存储配置组件 -->
          <TenantStoragePanel v-if="activeGroup === 'tenant_storage'" />
          <div v-else-if="activeGroup" class="max-w-[800px]">
            <ConfigForm ref="formRef" :configs="configs" />
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
