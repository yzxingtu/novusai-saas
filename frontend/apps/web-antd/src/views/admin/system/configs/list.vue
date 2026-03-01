<script setup lang="ts">
import type { ConfigGroupListItemMeta, ConfigItemMeta } from '#/types/config';

import { computed, onActivated, onBeforeUnmount, onMounted, ref } from 'vue';

defineOptions({ name: 'SystemConfigList' });

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
import { $t as t } from '#/locales';

// 平台存储配置专用面板
import PlatformStoragePanel from './modules/PlatformStoragePanel.vue';

const generatingKey = ref(false);
async function onGenerateFernetKey(setValue: (v: string) => void) {
  generatingKey.value = true;
  try {
    const result = await generateFernetKeyApi();
    setValue(result.key);
  } catch {} finally {
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
const storagePanelRef = ref<{ onSave: () => Promise<void>; saving: { value: boolean } }>();

// 当前选中的分组数据
const activeGroupData = computed(() =>
  groups.value.find((g) => g.code === activeGroup.value),
);

// 获取分组名称（优先使用 name，其次 name_key 翻译，最后 fallback 到 code）
function getGroupName(g: ConfigGroupListItemMeta): string {
  // 1. 直接使用 name 字段
  if (g.name) return g.name;
  // 2. 使用 name_key 翻译
  if (g.name_key) {
    const translated = t(g.name_key);
    if (translated !== g.name_key) return translated;
  }
  // 3. fallback: 尝试使用 shared.config.group.{code} 格式
  const fallbackKey = `shared.config.group.${g.code}`;
  const fallbackTranslated = t(fallbackKey);
  if (fallbackTranslated !== fallbackKey) return fallbackTranslated;
  // 4. 最后 fallback 到 code
  return g.code;
}

// 获取分组描述
function getGroupDesc(g: ConfigGroupListItemMeta): string {
  // 1. 直接使用 description 字段
  if (g.description) return g.description;
  // 2. 使用 description_key 翻译
  if (g.description_key) {
    const translated = t(g.description_key);
    if (translated !== g.description_key) return translated;
  }
  // 3. fallback: 尝试使用 shared.config.group_desc.{code} 格式
  const fallbackKey = `shared.config.group_desc.${g.code}`;
  const fallbackTranslated = t(fallbackKey);
  if (fallbackTranslated !== fallbackKey) return fallbackTranslated;
  return '';
}

// 按 sort_order 排序的分组列表
const sortedGroups = computed(() =>
  [...groups.value].sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0)),
);

async function loadGroups() {
  groupLoading.value = true;
  try {
    groups.value = await getAdminConfigGroupsApi();
    if (groups.value.length > 0) {
      // 按 sort_order 取第一个组
      const sorted = [...groups.value].sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
      activeGroup.value = sorted[0]!.code;
      // platform_storage 组用专用面板，不需要加载配置详情
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
    configs.value = (detail.configs || []).sort(
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
        // platform_storage 组用专用面板，不需要加载配置详情
        if (code !== 'platform_storage') {
          await loadGroupDetail(code);
        }
      },
    });
  } else {
    activeGroup.value = code;
    // platform_storage 组用专用面板，不需要加载配置详情
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
    // 表单验证失败，不继续提交
    return;
  }
  const payload = formRef.value?.prepareSubmitData();
  saving.value = true;
  try {
    await updateAdminConfigGroupApi(activeGroup.value, payload, {
      showSuccessMessage: true,
    });
    // 重新加载以反显最新值
    await loadGroupDetail(activeGroup.value);
  } catch {
    // 错误已经由 request 拦截器处理并显示
  } finally {
    saving.value = false;
  }
}

// 浏览器关闭/刷新提醒
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
</script>

<template>
  <Page auto-content-height>
    <div class="relative z-0 flex h-full flex-col gap-4 overflow-hidden md:flex-row">
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
          <Button
            type="primary"
            v-access:code="['platform_config:update']"
            :loading="activeGroup === 'platform_storage' ? storagePanelRef?.saving?.value : saving"
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
          <!-- platform_storage 分组使用专用存储配置面板 -->
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
