<script setup lang="ts">
import type {
  ConfigGroupListItemMeta,
  ConfigItemMeta,
  ConfigSubmitPayload,
} from '#/types/config';
import type { AdminSslDnsReadiness } from '#/api/admin/configs';

import {
  computed,
  nextTick,
  onActivated,
  onBeforeUnmount,
  onMounted,
  ref,
} from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Alert, Button, Card, Empty, Modal, Spin } from 'ant-design-vue';

import {
  generateFernetKeyApi,
  getAdminConfigGroupDetailApi,
  getAdminConfigGroupsApi,
  getAdminSslDnsReadinessApi,
  updateAdminConfigGroupApi,
} from '#/api/admin/configs';
import { ConfigForm } from '#/components';
import { usePageAIRegistration } from '#/composables/use-page-ai-registration';
import PluginSettingsTabs from '#/components/business/plugin-slots/PluginSettingsTabs.vue';
import { $t, $t as t } from '#/locales';

// Platform storage config dedicated panel / 平台存储配置专用面板
import PlatformStoragePanel from './modules/PlatformStoragePanel.vue';

defineOptions({ name: 'SystemConfigList' });

const route = useRoute();
const router = useRouter();

const CONFIG_GROUP_QUERY_KEY = 'group';
const CONFIG_ITEM_QUERY_KEY = 'config';
const DEFAULT_PAGE_CONTEXT_MAX_BYTES = 8192;
const PAGE_CONTEXT_GROUP_CODE = 'platform_ai_toolkit';
const PAGE_CONTEXT_CONFIG_KEY = 'ai_page_context_max_bytes';
const PLATFORM_SSL_GROUP_CODE = 'platform_ssl';

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
const dnsReadiness = ref<AdminSslDnsReadiness | null>(null);
const loading = ref(false);
const groupLoading = ref(false);
const saving = ref(false);
interface ConfigFormExpose {
  isDirty: () => boolean;
  prepareSubmitData: () => ConfigSubmitPayload;
  validate: () => Promise<void>;
}

const formRef = ref<ConfigFormExpose>();
const storagePanelRef = ref<{
  onSave: () => Promise<void>;
  saving: { value: boolean };
}>();

function getQueryStringParam(key: string): string {
  const value = route.query[key];
  if (Array.isArray(value)) {
    return typeof value[0] === 'string' ? value[0] : '';
  }
  return typeof value === 'string' ? value : '';
}

function getRequestedGroupCode(): string {
  return getQueryStringParam(CONFIG_GROUP_QUERY_KEY);
}

function getRequestedConfigKey(): string {
  return getQueryStringParam(CONFIG_ITEM_QUERY_KEY);
}

function getResolvedRequestedGroupCode(): string | undefined {
  const requestedGroupCode = getRequestedGroupCode();
  if (!requestedGroupCode) return undefined;
  return groups.value.some((group) => group.code === requestedGroupCode)
    ? requestedGroupCode
    : undefined;
}

async function syncRouteSelection(groupCode: string, configKey?: string) {
  const currentGroupCode = getRequestedGroupCode();
  const currentConfigKey = getRequestedConfigKey();
  const nextConfigKey = configKey ?? '';
  if (
    currentGroupCode === groupCode &&
    currentConfigKey === nextConfigKey
  ) {
    return;
  }

  const nextQuery: Record<string, string> = {};
  for (const [key, value] of Object.entries(route.query)) {
    if (Array.isArray(value)) {
      if (typeof value[0] === 'string') {
        nextQuery[key] = value[0];
      }
      continue;
    }
    if (typeof value === 'string') {
      nextQuery[key] = value;
    }
  }
  nextQuery[CONFIG_GROUP_QUERY_KEY] = groupCode;
  if (configKey) {
    nextQuery[CONFIG_ITEM_QUERY_KEY] = configKey;
  } else {
    delete nextQuery[CONFIG_ITEM_QUERY_KEY];
  }
  await router.replace({ path: route.path, query: nextQuery });
}

async function scrollToConfigItem(configKey: string) {
  await nextTick();
  const target = document.getElementById(`config-item-${configKey}`);
  target?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

async function focusRequestedConfig(groupCode: string) {
  const requestedConfigKey = getRequestedConfigKey();
  if (
    !requestedConfigKey ||
    groupCode !== getRequestedGroupCode() ||
    !configs.value.some((cfg) => cfg.key === requestedConfigKey)
  ) {
    return;
  }
  await scrollToConfigItem(requestedConfigKey);
}

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

async function activateGroup(
  code: string,
  options?: { configKey?: string; syncRoute?: boolean },
) {
  activeGroup.value = code;
  if (options?.syncRoute !== false) {
    await syncRouteSelection(code, options?.configKey);
  }
  if (code === 'platform_storage') {
    configs.value = [];
    dnsReadiness.value = null;
    return;
  }
  await loadGroupDetail(code);
}

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
      const requestedGroupCode = getResolvedRequestedGroupCode();
      const initialGroupCode = requestedGroupCode || firstGroup.code;
      await activateGroup(initialGroupCode, {
        configKey:
          requestedGroupCode === initialGroupCode
            ? getRequestedConfigKey() || undefined
            : undefined,
      });
    }
  } finally {
    groupLoading.value = false;
  }
}

async function loadGroupDetail(code: string) {
  loading.value = true;
  try {
    const detailPromise = getAdminConfigGroupDetailApi(code);
    const readinessPromise =
      code === PLATFORM_SSL_GROUP_CODE
        ? getAdminSslDnsReadinessApi({
            showCodeMessage: false,
            showErrorMessage: false,
          }).catch(() => null)
        : Promise.resolve(null);
    const [detail, readiness] = await Promise.all([
      detailPromise,
      readinessPromise,
    ]);
    configs.value = (detail.configs || []).toSorted(
      (a, b) => (a.sort_order || 0) - (b.sort_order || 0),
    );
    dnsReadiness.value = readiness;
    await focusRequestedConfig(code);
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
        await activateGroup(code);
      },
    });
  } else {
    await activateGroup(code);
  }
}

async function onLocatePageContextLimit() {
  if (activeGroup.value !== PAGE_CONTEXT_GROUP_CODE) {
    await activateGroup(PAGE_CONTEXT_GROUP_CODE, {
      configKey: PAGE_CONTEXT_CONFIG_KEY,
    });
    return;
  }
  await syncRouteSelection(PAGE_CONTEXT_GROUP_CODE, PAGE_CONTEXT_CONFIG_KEY);
  await scrollToConfigItem(PAGE_CONTEXT_CONFIG_KEY);
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
  if (!payload) return;
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
  const requestedGroupCode = getResolvedRequestedGroupCode();
  if (requestedGroupCode) {
    activateGroup(requestedGroupCode, {
      configKey: getRequestedConfigKey() || undefined,
      syncRoute: false,
    });
    return;
  }
  if (activeGroup.value && activeGroup.value !== 'platform_storage') {
    loadGroupDetail(activeGroup.value);
  }
});
onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', beforeUnloadHandler);
});

usePageAIRegistration({
  pageKey: 'admin.system.configs',
  title: () => $t('admin.system.config.title'),
  resource: '/admin/system/configs',
  data: () => ({
    active_group: activeGroup.value,
  }),
  operations: [
    {
      name: 'refresh_configs',
      label: $t('shared.pageOperation.refreshConfig'),
      description: $t('shared.pageOperation.refreshConfig'),
      readonly: true,
      handler: async () => {
        await loadGroups();
        return {
          success: true,
          message: $t('shared.pageOperation.msg.detailRefreshed'),
        };
      },
    },
    {
      name: 'save_config',
      label: $t('shared.pageOperation.saveConfig'),
      description: $t('shared.pageOperation.saveConfig'),
      readonly: false,
      handler: async () => {
        await onSave();
        return {
          success: true,
          message: $t('shared.pageOperation.msg.formSubmittedSuccess'),
        };
      },
    },
  ],
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
            <Alert
              v-if="activeGroup === PAGE_CONTEXT_GROUP_CODE"
              class="mb-4"
              type="info"
              show-icon
              :message="t('shared.config.page.page_context_limit_title')"
              :description="
                t('shared.config.page.page_context_limit_desc', {
                  configKey: PAGE_CONTEXT_CONFIG_KEY,
                  defaultValue: DEFAULT_PAGE_CONTEXT_MAX_BYTES,
                })
              "
            >
              <template #action>
                <Button size="small" @click="onLocatePageContextLimit">
                  {{ t('shared.config.page.locate_page_context_limit') }}
                </Button>
              </template>
            </Alert>
            <Alert
              v-if="activeGroup === PLATFORM_SSL_GROUP_CODE && dnsReadiness"
              class="mb-4"
              :type="dnsReadiness.ready ? 'success' : 'warning'"
              show-icon
              :message="dnsReadiness.summary"
            >
              <template
                v-if="dnsReadiness.issues.length > 0"
                #description
              >
                <ul class="mb-0 pl-5">
                  <li
                    v-for="issue in dnsReadiness.issues"
                    :key="issue.code"
                    class="leading-6"
                  >
                    {{ issue.message }}
                  </li>
                </ul>
              </template>
            </Alert>
            <ConfigForm
              ref="formRef"
              :configs="configs"
            >
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
