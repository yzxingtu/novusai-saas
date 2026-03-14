<script setup lang="ts">
import type { AgentAssignmentItem } from '#/api/shared/agent-assignments';

/**
 * Tenant — System Agent Assignment Management — useCrudList + 配置面板
 *
 * useCrudList(keyField='feature_code') 管理列表数据，自定义覆盖/恢复操作。
 */
import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';
import { preferences } from '@vben/preferences';

import {
  Button,
  Card,
  message,
  Popconfirm,
  Select,
  Table,
  Tag,
} from 'ant-design-vue';

import {
  deleteAgentAssignmentApi,
  getAgentAssignmentListApi,
  getPublishedAgentsApi,
  updateAgentAssignmentApi,
} from '#/api/shared/agent-assignments';
import { useCrudList } from '#/composables';
import { $t } from '#/locales';

const T = 'tenant.ai.agentAssignment';

// ========== 声明式列表管理 ==========
const {
  list: assignments,
  loading,
  loadList,
} = useCrudList<AgentAssignmentItem>({
  api: {
    list: () => getAgentAssignmentListApi('/tenant'),
    resource: '/tenant/ai/agent-assignments',
  },
  keyField: 'feature_code',
  i18nPrefix: 'tenant.ai.agentAssignment',
  nameField: 'feature_name',
  pager: false,
  ai: {},
});

// ========== Agent 选项 ==========
interface AgentOption {
  label: string;
  value: number;
}
const agentOptions = ref<AgentOption[]>([]);

async function loadAgentOptions() {
  try {
    const res = await getPublishedAgentsApi('/tenant');
    agentOptions.value = res.items.map((a) => ({ label: a.name, value: a.id }));
  } catch {
    // handled by interceptor / 错误由请求拦截器处理
  }
}

onMounted(loadAgentOptions);

// ========== 自定义操作 ==========
const saving = ref<null | string>(null);

async function setOverride(featureCode: string, agentId: null | number) {
  saving.value = featureCode;
  try {
    await updateAgentAssignmentApi('/tenant', featureCode, {
      agent_id: agentId,
    });
    message.success($t(`${T}.saveSuccess`));
    await loadList();
  } catch {
    // handled by interceptor / 错误由请求拦截器处理
  } finally {
    saving.value = null;
  }
}

async function restoreDefault(featureCode: string) {
  saving.value = featureCode;
  try {
    await deleteAgentAssignmentApi('/tenant', featureCode);
    message.success($t(`${T}.restoreSuccess`));
    await loadList();
  } catch {
    // handled by interceptor / 错误由请求拦截器处理
  } finally {
    saving.value = null;
  }
}

// ========== 辅助：多语言 ==========
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
  return record.feature_name;
}

function featureDesc(record: AgentAssignmentItem): string {
  const fromApi = pickLocale(record.description_i18n);
  if (fromApi) return fromApi;
  return record.description || '';
}

const columns = [
  {
    title: $t(`${T}.columns.featureName`),
    dataIndex: 'feature_name',
    key: 'feature_name',
    width: 200,
  },
  {
    title: $t(`${T}.columns.featureCode`),
    dataIndex: 'feature_code',
    key: 'feature_code',
    width: 140,
  },
  {
    title: $t(`${T}.columns.globalDefault`),
    key: 'global_default',
    width: 160,
  },
  {
    title: $t(`${T}.columns.currentAgent`),
    key: 'current_agent',
    width: 260,
  },
  {
    title: $t(`${T}.columns.status`),
    key: 'override_status',
    width: 120,
    align: 'center' as const,
  },
  {
    title: $t(`${T}.columns.actions`),
    key: 'actions',
    width: 120,
    align: 'center' as const,
  },
];
</script>

<template>
  <Page :title="$t(`${T}.title`)">
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
              <IconifyIcon icon="lucide:plug" class="size-4 text-primary" />
              <span class="font-medium">{{
                featureName(record as AgentAssignmentItem)
              }}</span>
            </div>
            <div
              v-if="featureDesc(record as AgentAssignmentItem)"
              class="mt-0.5 text-xs text-muted-foreground"
            >
              {{ featureDesc(record as AgentAssignmentItem) }}
            </div>
          </template>

          <template v-else-if="column.key === 'feature_code'">
            <Tag color="blue">{{ record.feature_code }}</Tag>
          </template>

          <template v-else-if="column.key === 'global_default'">
            <span class="text-sm text-muted-foreground">
              {{ record.global_agent_name || record.agent_name || '-' }}
            </span>
          </template>

          <template v-else-if="column.key === 'current_agent'">
            <Select
              :value="record.agent_id"
              :options="agentOptions"
              :loading="saving === record.feature_code"
              :placeholder="$t(`${T}.selectAgent`)"
              allow-clear
              style="width: 220px"
              @change="
                (val: unknown) =>
                  setOverride(record.feature_code, (val as number) ?? null)
              "
            />
          </template>

          <template v-else-if="column.key === 'override_status'">
            <Tag v-if="record.is_override" color="orange">
              {{ $t(`${T}.overridden`) }}
            </Tag>
            <Tag v-else color="green">
              {{ $t(`${T}.inherited`) }}
            </Tag>
          </template>

          <template v-else-if="column.key === 'actions'">
            <Popconfirm
              v-if="record.is_override"
              :title="$t(`${T}.restoreConfirm`)"
              @confirm="restoreDefault(record.feature_code)"
            >
              <Button
                size="small"
                type="link"
                danger
                :loading="saving === record.feature_code"
              >
                {{ $t(`${T}.restoreDefault`) }}
              </Button>
            </Popconfirm>
            <span v-else class="text-xs text-muted-foreground">-</span>
          </template>
        </template>
      </Table>
    </Card>
  </Page>
</template>
