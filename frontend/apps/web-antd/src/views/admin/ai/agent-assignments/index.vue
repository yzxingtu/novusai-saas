<script setup lang="ts">
import type { AgentAssignmentItem } from '#/api/shared/agent-assignments';

/**
 * Admin — System Agent Assignment Management — useCrudList + 卡片行配置面板
 * 管理端 — 系统智能体分配管理 — useCrudList + 卡片行配置
 *
 * useCrudList(keyField='feature_code') 管理列表数据，自定义 inline 编辑。
 */
import { computed, onMounted, ref, watchEffect } from 'vue';

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

import AIPageHeroCard from '../_shared/AIPageHeroCard.vue';

// ========== 声明式列表管理 / declarative CRUD list ==========
const assignmentSummary = ref({ active: 0, assigned: 0 });

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
  ai: {
    entityName: $t('admin.ai.agentAssignment.title'),
    entityDescription: $t('admin.ai.agentAssignments.entityDescription'),
    contextExtras: () => ({
      active: assignmentSummary.value.active,
      assigned: assignmentSummary.value.assigned,
    }),
  },
});

// ========== Agent 选项 / agent select options ==========
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
    // handled by interceptor / 错误由请求拦截器处理
  }
}

onMounted(loadAgentOptions);

// ========== 自定义操作 / custom row actions ==========
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
    // handled by interceptor / 错误由请求拦截器处理
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
    // handled by interceptor / 错误由请求拦截器处理
  } finally {
    saving.value = null;
  }
}

// ========== 辅助 / helpers ==========
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

// ========== 功能图标映射 / capability icon map ==========
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

// ========== 统计 / stats ==========
watchEffect(() => {
  assignmentSummary.value = {
    active: assignments.value.filter((item) => item.is_active).length,
    assigned: assignments.value.filter((item) => item.agent_id !== null).length,
  };
});

const assignmentStats = computed(() => {
  const items = assignments.value;
  const total = items.length;
  const active = items.filter((item) => item.is_active).length;
  const assigned = items.filter((item) => item.agent_id !== null).length;
  const plugins = items.filter((item) =>
    item.feature_code.startsWith('plugin.'),
  ).length;

  return {
    active,
    assigned,
    plugins,
    publishedAgents: agentOptions.value.length,
    total,
    unassigned: total - assigned,
  };
});

const heroMetrics = computed(() => [
  {
    key: 'features',
    label: $t('admin.ai.agentAssignment.hero.metrics.features'),
    value: assignmentStats.value.total,
  },
  {
    key: 'publishedAgents',
    label: $t('admin.ai.agentAssignment.hero.metrics.publishedAgents'),
    value: assignmentStats.value.publishedAgents,
  },
  {
    key: 'enabled',
    label: $t('admin.ai.agentAssignment.hero.metrics.enabled'),
    value: assignmentStats.value.active,
  },
  {
    key: 'assigned',
    label: $t('admin.ai.agentAssignment.hero.metrics.assigned'),
    value: assignmentStats.value.assigned,
  },
]);

const heroChips = computed(() => {
  const chips = [
    {
      key: 'scope',
      icon: 'lucide:globe-2',
      className: 'bg-primary/10 text-primary',
      text: $t('admin.ai.agentAssignment.hero.chips.scope'),
    },
    {
      key: 'publishedAgents',
      icon: 'lucide:bot',
      className: 'bg-background/90 text-foreground',
      text: $t('admin.ai.agentAssignment.hero.chips.publishedAgents', {
        count: assignmentStats.value.publishedAgents,
      }),
    },
  ];

  if (assignmentStats.value.plugins > 0) {
    chips.push({
      key: 'plugins',
      icon: 'lucide:puzzle',
      className: 'bg-violet-500/10 text-violet-700 dark:text-violet-200',
      text: $t('admin.ai.agentAssignment.hero.chips.plugins', {
        count: assignmentStats.value.plugins,
      }),
    });
  }

  chips.push(
    assignmentStats.value.unassigned > 0
      ? {
          key: 'pending',
          icon: 'lucide:badge-alert',
          className: 'bg-amber-500/10 text-amber-700 dark:text-amber-200',
          text: $t('admin.ai.agentAssignment.hero.chips.pending', {
            count: assignmentStats.value.unassigned,
          }),
        }
      : {
          key: 'ready',
          icon: 'lucide:badge-check',
          className: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-200',
          text: $t('admin.ai.agentAssignment.hero.chips.ready'),
        },
  );

  return chips;
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <AIPageHeroCard
      :chips="heroChips"
      :description="$t('admin.ai.agentAssignment.hero.description')"
      icon="lucide:cpu"
      icon-wrap-class="bg-primary/10 text-primary"
      :metrics="heroMetrics"
      :title="$t('admin.ai.agentAssignment.title')"
    >
      <template #actions>
        <Button :loading="loading" @click="loadList">
          <template #icon>
            <IconifyIcon icon="lucide:refresh-cw" class="size-3.5" />
          </template>
          {{ $t('common.refresh') }}
        </Button>
      </template>
    </AIPageHeroCard>

    <!-- ==================== 功能绑定卡片列表 ==================== -->
    <Spin :spinning="loading && assignments.length === 0">
      <div class="flex flex-col gap-3">
        <div
          v-for="item in assignments"
          :key="item.feature_code"
          class="rounded-2xl border border-border/70 bg-card/95 px-5 py-4 shadow-sm transition-all duration-200 hover:border-primary/20 hover:shadow-[0_10px_30px_-24px_hsl(var(--primary))]"
          :class="
            item.is_active ? '' : 'border-border/50 opacity-60'
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
