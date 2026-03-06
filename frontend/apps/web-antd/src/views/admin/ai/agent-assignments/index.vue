<script setup lang="ts">
import type { AgentAssignmentItem } from '#/api/shared/agent-assignments';

/**
 * Admin — System Agent Assignment Management — useCrudList + 卡片行配置面板
 *
 * 设计规范：detail-page-patterns.md（信息摘要栏 + 卡片行替代平表格）
 * useCrudList(keyField='feature_code') 管理列表数据，自定义 inline 编辑。
 */
import { computed, onMounted, onUnmounted, ref } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';
import { preferences } from '@vben/preferences';

import {
  Button,
  Empty,
  message,
  Popconfirm,
  Select,
  Spin,
  Switch,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import {
  getAgentAssignmentListApi,
  getPublishedAgentsApi,
  updateAgentAssignmentApi,
} from '#/api/shared/agent-assignments';
import { useCrudList } from '#/composables';
import { $t } from '#/locales';

// ========== 声明式列表管理 ==========
const {
  list: assignments,
  loading,
  loadList,
} = useCrudList<AgentAssignmentItem>({
  api: {
    list: () => getAgentAssignmentListApi('/admin'),
    resource: '/admin/ai/agent-assignments',
  },
  keyField: 'feature_code',
  i18nPrefix: 'admin.ai.agentAssignment',
  nameField: 'feature_name',
  pager: false,
});

// ========== Agent 选项 ==========
interface AgentOption {
  label: string;
  value: number;
}
const agentOptions = ref<AgentOption[]>([]);

async function loadAgentOptions() {
  try {
    const res = await getPublishedAgentsApi('/admin');
    agentOptions.value = res.items.map((a) => ({ label: a.name, value: a.id }));
  } catch {
    // handled by interceptor
  }
}

onMounted(loadAgentOptions);

// ========== 自定义操作 ==========
const saving = ref<null | string>(null);

async function updateAssignment(featureCode: string, agentId: null | number) {
  saving.value = featureCode;
  try {
    await updateAgentAssignmentApi('/admin', featureCode, {
      agent_id: agentId,
    });
    message.success($t('admin.ai.agentAssignment.saveSuccess'));
    await loadList();
  } catch {
    // handled by interceptor
  } finally {
    saving.value = null;
  }
}

async function toggleActive(featureCode: string, isActive: boolean) {
  saving.value = featureCode;
  try {
    await updateAgentAssignmentApi('/admin', featureCode, {
      is_active: isActive,
    });
    await loadList();
  } catch {
    // handled by interceptor
  } finally {
    saving.value = null;
  }
}

// ========== 辅助 ==========
const currentLocale = computed(() => preferences.app.locale);

function pickLocale(
  dict: Record<string, string> | undefined,
): string | undefined {
  if (!dict) return undefined;
  const locale = currentLocale.value;
  return dict[locale] ?? dict['zh-CN'] ?? dict.en ?? Object.values(dict)[0];
}

function featureName(record: AgentAssignmentItem): string {
  const fromApi = pickLocale(record.display_name);
  if (fromApi) return fromApi;
  if (record.feature_code.startsWith('plugin.')) return record.feature_name;
  const key = `admin.ai.agentAssignment.features.${record.feature_code}.name`;
  const val = $t(key);
  return val === key ? record.feature_name : val;
}

function featureDesc(record: AgentAssignmentItem): string {
  const fromApi = pickLocale(record.description_i18n);
  if (fromApi) return fromApi;
  if (record.feature_code.startsWith('plugin.'))
    return record.description || '';
  const key = `admin.ai.agentAssignment.features.${record.feature_code}.description`;
  const val = $t(key);
  return val === key ? record.description || '' : val;
}

// ========== 功能图标映射 ==========
interface FeatureIconConfig {
  icon: string;
  bgClass: string;
  iconClass: string;
}

function getFeatureIcon(featureCode: string): FeatureIconConfig {
  if (featureCode.startsWith('plugin.')) {
    return {
      icon: 'lucide:puzzle',
      bgClass: 'bg-purple-500/10',
      iconClass: 'text-purple-500',
    };
  }
  switch (featureCode) {
    case 'data_analysis': {
      return {
        icon: 'lucide:bar-chart-2',
        bgClass: 'bg-green-500/10',
        iconClass: 'text-green-500',
      };
    }
    case 'general_chat': {
      return {
        icon: 'lucide:message-circle',
        bgClass: 'bg-blue-500/10',
        iconClass: 'text-blue-500',
      };
    }
    case 'knowledge_base': {
      return {
        icon: 'lucide:database',
        bgClass: 'bg-amber-500/10',
        iconClass: 'text-amber-500',
      };
    }
    case 'translation': {
      return {
        icon: 'lucide:languages',
        bgClass: 'bg-cyan-500/10',
        iconClass: 'text-cyan-500',
      };
    }
    default: {
      return {
        icon: 'lucide:cpu',
        bgClass: 'bg-primary/10',
        iconClass: 'text-primary',
      };
    }
  }
}

// ========== 统计 ==========
const stats = computed(() => ({
  total: assignments.value.length,
  active: assignments.value.filter((a) => a.is_active).length,
  assigned: assignments.value.filter((a) => a.agent_id !== null).length,
}));

const cleanupPageContext = registerPageContext('admin/ai/agent-assignments', () => ({
  page_key: 'admin.ai.agent-assignments',
  page_title: $t('admin.ai.agentAssignment.title'),
  page_data: {
    resource: '/admin/ai/agent-assignments',
    total: stats.value.total,
    active: stats.value.active,
    assigned: stats.value.assigned,
  },
}));

onUnmounted(cleanupPageContext);
</script>

<template>
  <Page
    :title="$t('admin.ai.agentAssignment.title')"
    content-class="flex flex-col gap-4"
  >
    <!-- ==================== 信息摘要栏 ==================== -->
    <div class="relative overflow-hidden rounded-xl border bg-card shadow-sm">
      <div
        class="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-transparent"
      ></div>
      <div class="relative flex flex-wrap items-center gap-5 p-5">
        <!-- 功能图标 -->
        <div
          class="flex size-14 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-sm ring-2 ring-primary/20 ring-offset-2 ring-offset-card"
        >
          <IconifyIcon icon="lucide:cpu" class="size-7" />
        </div>

        <!-- 说明文字 -->
        <div class="flex-1">
          <h2 class="mb-1 text-base font-bold text-foreground">
            {{ $t('admin.ai.agentAssignment.title') }}
          </h2>
          <p class="text-sm text-muted-foreground">
            {{ $t('admin.ai.agentAssignment.pageDesc') }}
          </p>
          <!-- 统计行 -->
          <div
            class="mt-3 flex flex-wrap items-center gap-4 text-xs text-muted-foreground"
          >
            <div class="flex items-center gap-1.5">
              <span class="inline-block size-2 rounded-full bg-border"></span>
              <span>{{
                $t('admin.ai.agentAssignment.stats.total', {
                  count: stats.total,
                })
              }}</span>
            </div>
            <div class="flex items-center gap-1.5">
              <span
                class="inline-block size-2 rounded-full bg-green-500"
              ></span>
              <span>{{
                $t('admin.ai.agentAssignment.stats.active', {
                  count: stats.active,
                })
              }}</span>
            </div>
            <div class="flex items-center gap-1.5">
              <IconifyIcon icon="lucide:link" class="size-3" />
              <span>{{
                $t('admin.ai.agentAssignment.stats.assigned', {
                  count: stats.assigned,
                })
              }}</span>
            </div>
          </div>
        </div>

        <!-- 刷新按钮 -->
        <Button size="small" :loading="loading" @click="loadList">
          <template #icon>
            <IconifyIcon icon="lucide:refresh-cw" class="size-3.5" />
          </template>
          {{ $t('common.refresh') }}
        </Button>
      </div>
    </div>

    <!-- ==================== 功能绑定卡片列表 ==================== -->
    <Spin :spinning="loading && assignments.length === 0">
      <div class="flex flex-col gap-3">
        <div
          v-for="item in assignments"
          :key="item.feature_code"
          class="rounded-xl border bg-card px-5 py-4 transition-all duration-200"
          :class="
            item.is_active ? 'border-border' : 'border-border/50 opacity-60'
          "
        >
          <div class="flex flex-wrap items-center gap-4">
            <!-- 功能图标 -->
            <div
              class="flex size-10 shrink-0 items-center justify-center rounded-xl"
              :class="getFeatureIcon(item.feature_code).bgClass"
            >
              <IconifyIcon
                :icon="getFeatureIcon(item.feature_code).icon"
                class="size-5"
                :class="getFeatureIcon(item.feature_code).iconClass"
              />
            </div>

            <!-- 功能信息 -->
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-sm font-semibold text-foreground">{{
                  featureName(item)
                }}</span>
                <Tag
                  color="blue"
                  class="!mr-0 !text-[10px]"
                  style="padding: 0 5px"
                >
                  {{ item.feature_code }}
                </Tag>
                <Tag
                  v-if="item.feature_code.startsWith('plugin.')"
                  color="purple"
                  class="!mr-0 !text-[10px]"
                  style="padding: 0 5px"
                >
                  {{ $t('admin.ai.agentAssignment.typePlugin') }}
                </Tag>
              </div>
              <p
                v-if="featureDesc(item)"
                class="mt-0.5 truncate text-xs text-muted-foreground"
              >
                {{ featureDesc(item) }}
              </p>
            </div>

            <!-- 右侧：全局默认提示 + Agent 选择器 + 开关 -->
            <div class="flex shrink-0 items-center gap-4">
              <!-- 全局默认 hint（未覆盖时显示） -->
              <Tooltip
                v-if="!item.agent_id && item.global_agent_name"
                :title="
                  $t('admin.ai.agentAssignment.globalDefault', {
                    name: item.global_agent_name,
                  })
                "
              >
                <div
                  class="flex items-center gap-1 rounded-lg border border-border/50 bg-accent/50 px-2.5 py-1 text-xs text-muted-foreground"
                >
                  <IconifyIcon icon="lucide:globe" class="size-3" />
                  <span class="max-w-[80px] truncate">{{
                    item.global_agent_name
                  }}</span>
                </div>
              </Tooltip>

              <!-- Agent 选择器 -->
              <Select
                :value="item.agent_id ?? undefined"
                :options="agentOptions"
                :loading="saving === item.feature_code"
                :placeholder="$t('admin.ai.agentAssignment.selectAgent')"
                allow-clear
                class="!w-52"
                @change="
                  (val: unknown) =>
                    updateAssignment(item.feature_code, (val as number) ?? null)
                "
              />

              <!-- 启用开关 -->
              <Popconfirm
                :title="
                  $t('admin.ai.agentAssignment.toggleActiveConfirm', {
                    action: item.is_active
                      ? $t('common.disable')
                      : $t('common.enable'),
                  })
                "
                @confirm="toggleActive(item.feature_code, !item.is_active)"
              >
                <div
                  class="flex items-center gap-1.5 text-xs text-muted-foreground"
                >
                  <Switch
                    :checked="item.is_active"
                    :loading="saving === item.feature_code"
                    size="small"
                  />
                  <span class="hidden md:inline">{{
                    item.is_active
                      ? $t('common.enabled')
                      : $t('common.disabled')
                  }}</span>
                </div>
              </Popconfirm>
            </div>
          </div>
        </div>

        <!-- 空状态 -->
        <div
          v-if="assignments.length === 0 && !loading"
          class="flex items-center justify-center py-16"
        >
          <Empty :description="$t('common.noData')" />
        </div>
      </div>
    </Spin>
  </Page>
</template>
