<script setup lang="ts">
/**
 * Tenant — System Agent Assignment Management
 *
 * Shows all feature bindings with global defaults vs tenant overrides.
 * Allows tenant to override agent bindings or restore to global default.
 */
import { onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Button, Card, Popconfirm, Select, Table, Tag, message } from 'ant-design-vue';

import type { AgentAssignmentItem } from '#/api/shared/agent-assignments';

import { $t } from '#/locales';
import { requestClient } from '#/utils/request';

import { getAgentAssignmentListApi } from '#/api/shared/agent-assignments';

const T = 'tenant.ai.agentAssignment';

interface AgentOption {
  label: string;
  value: number;
}

const loading = ref(false);
const saving = ref<string | null>(null);
const assignments = ref<AgentAssignmentItem[]>([]);
const agentOptions = ref<AgentOption[]>([]);

async function loadAssignments() {
  loading.value = true;
  try {
    const data = await getAgentAssignmentListApi('/tenant');
    assignments.value = data;
  } catch {
    // handled by interceptor
  } finally {
    loading.value = false;
  }
}

async function loadAgentOptions() {
  try {
    const res = await requestClient.get<{
      items: Array<{ id: number; name: string; status: string }>;
    }>('/tenant/ai/agents', {
      params: { 'filter[status][eq]': 'published', 'page[size]': 100 },
    });
    agentOptions.value = res.items.map((a) => ({ label: a.name, value: a.id }));
  } catch {
    // handled by interceptor
  }
}

async function setOverride(featureCode: string, agentId: number | null) {
  saving.value = featureCode;
  try {
    await requestClient.put(`/tenant/ai/agent-assignments/${featureCode}`, {
      agent_id: agentId,
    });
    message.success($t(`${T}.saveSuccess`));
    await loadAssignments();
  } catch {
    // handled by interceptor
  } finally {
    saving.value = null;
  }
}

async function restoreDefault(featureCode: string) {
  saving.value = featureCode;
  try {
    await requestClient.delete(`/tenant/ai/agent-assignments/${featureCode}`);
    message.success($t(`${T}.restoreSuccess`));
    await loadAssignments();
  } catch {
    // handled by interceptor
  } finally {
    saving.value = null;
  }
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

onMounted(() => {
  loadAssignments();
  loadAgentOptions();
});
</script>

<template>
  <Page :title="$t(`${T}.title`)">
    <Card>
      <template #extra>
        <Button size="small" @click="loadAssignments">
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
              <span class="font-medium">{{ record.feature_name }}</span>
            </div>
            <div v-if="record.description" class="text-muted-foreground mt-0.5 text-xs">
              {{ record.description }}
            </div>
          </template>

          <template v-else-if="column.key === 'feature_code'">
            <Tag color="blue">{{ record.feature_code }}</Tag>
          </template>

          <template v-else-if="column.key === 'global_default'">
            <span class="text-muted-foreground text-sm">
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
              @change="(val: unknown) => setOverride(record.feature_code, (val as number) ?? null)"
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
            <span v-else class="text-muted-foreground text-xs">-</span>
          </template>
        </template>
      </Table>
    </Card>
  </Page>
</template>
