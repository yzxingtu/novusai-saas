<script setup lang="ts">
/**
 * Admin — System Agent Assignment Management — useCrudList + 配置面板
 *
 * useCrudList(keyField='feature_code') 管理列表数据，自定义 inline 编辑。
 */
import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Button, Card, Popconfirm, Select, Switch, Table, Tag, message } from 'ant-design-vue';

import type { AgentAssignmentItem } from '#/api/shared/agent-assignments';

import {
  getAgentAssignmentListApi,
  getPublishedAgentsApi,
  updateAgentAssignmentApi,
} from '#/api/shared/agent-assignments';
import { useCrudList } from '#/composables';
import { $t } from '#/locales';
import { preferences } from '@vben/preferences';

// ========== 声明式列表管理 ==========
const {
  list: assignments, loading, loadList,
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
interface AgentOption { label: string; value: number }
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
const saving = ref<string | null>(null);

async function updateAssignment(featureCode: string, agentId: number | null) {
  saving.value = featureCode;
  try {
    await updateAgentAssignmentApi('/admin', featureCode, { agent_id: agentId });
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
    await updateAgentAssignmentApi('/admin', featureCode, { is_active: isActive });
    await loadList();
  } catch {
    // handled by interceptor
  } finally {
    saving.value = null;
  }
}

// ========== 辅助 ==========
const currentLocale = computed(() => preferences.app.locale);

function pickLocale(dict: Record<string, string> | undefined): string | undefined {
  if (!dict) return undefined;
  const locale = currentLocale.value;
  return dict[locale] ?? dict['zh-CN'] ?? dict['en'] ?? Object.values(dict)[0];
}

function featureName(record: AgentAssignmentItem): string {
  const fromApi = pickLocale(record.display_name);
  if (fromApi) return fromApi;
  // 插件功能不走静态 i18n，直接用 DB 字段
  if (record.feature_code.startsWith('plugin.')) {
    return record.feature_name;
  }
  const key = `admin.ai.agentAssignment.features.${record.feature_code}.name`;
  const val = $t(key);
  return val === key ? record.feature_name : val;
}

function featureDesc(record: AgentAssignmentItem): string {
  const fromApi = pickLocale(record.description_i18n);
  if (fromApi) return fromApi;
  // 插件功能不走静态 i18n，直接用 DB 字段
  if (record.feature_code.startsWith('plugin.')) {
    return record.description || '';
  }
  const key = `admin.ai.agentAssignment.features.${record.feature_code}.description`;
  const val = $t(key);
  return val === key ? (record.description || '') : val;
}

const columns = [
  {
    title: $t('admin.ai.agentAssignment.columns.featureName'),
    dataIndex: 'feature_name',
    key: 'feature_name',
    width: 280,
  },
  {
    title: $t('admin.ai.agentAssignment.columns.featureCode'),
    dataIndex: 'feature_code',
    key: 'feature_code',
    width: 160,
  },
  {
    title: $t('admin.ai.agentAssignment.columns.agent'),
    dataIndex: 'agent_id',
    key: 'agent_id',
    width: 260,
  },
  {
    title: $t('admin.ai.agentAssignment.columns.status'),
    dataIndex: 'is_active',
    key: 'is_active',
    width: 100,
    align: 'center' as const,
  },
];
</script>

<template>
  <Page :title="$t('admin.ai.agentAssignment.title')">
    <Card>
      <template #extra>
        <Button size="small" @click="loadList">
          <template #icon>
            <IconifyIcon icon="lucide:refresh-cw" class="size-3.5" />
          </template>
          {{ $t('common.refresh') }}
        </Button>
      </template>

      <Table
        :columns="columns"
        :data-source="assignments"
        :loading="loading"
        :pagination="false"
        row-key="feature_code"
        size="middle"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'feature_name'">
            <div class="flex items-center gap-2">
              <IconifyIcon icon="lucide:plug" class="text-primary size-4" />
              <span class="font-medium">{{ featureName(record as AgentAssignmentItem) }}</span>
            </div>
            <div class="text-muted-foreground mt-0.5 text-xs">
              {{ featureDesc(record as AgentAssignmentItem) }}
            </div>
          </template>

          <template v-else-if="column.key === 'feature_code'">
            <Tag color="blue">{{ record.feature_code }}</Tag>
          </template>

          <template v-else-if="column.key === 'agent_id'">
            <Select
              :value="record.agent_id"
              :options="agentOptions"
              :loading="saving === record.feature_code"
              :placeholder="$t('admin.ai.agentAssignment.selectAgent')"
              allow-clear
              style="width: 220px"
              @change="(val: unknown) => updateAssignment(record.feature_code, (val as number) ?? null)"
            />
          </template>

          <template v-else-if="column.key === 'is_active'">
            <Popconfirm
              :title="$t('admin.ai.agentAssignment.toggleActiveConfirm', { action: record.is_active ? $t('common.disable') : $t('common.enable') })"
              @confirm="toggleActive(record.feature_code, !record.is_active)"
            >
              <Switch
                :checked="record.is_active"
                :loading="saving === record.feature_code"
                size="small"
              />
            </Popconfirm>
          </template>
        </template>
      </Table>
    </Card>
  </Page>
</template>
