<script setup lang="ts">
/**
 * Admin — System Agent Assignment Management
 *
 * Table view of feature_code → agent bindings.
 * Allows changing the bound agent via inline Select dropdown.
 */
import { onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Button, Card, Select, Switch, Table, Tag, message } from 'ant-design-vue';

import type { AgentAssignmentItem } from '#/api/shared/agent-assignments';

import { $t } from '#/locales';
import { requestClient } from '#/utils/request';

import { getAgentAssignmentListApi } from '#/api/shared/agent-assignments';

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
    const data = await getAgentAssignmentListApi('/admin');
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
    }>('/admin/ai/agents', {
      params: { 'filter[status][eq]': 'published', 'page[size]': 100 },
    });
    agentOptions.value = res.items.map((a) => ({ label: a.name, value: a.id }));
  } catch {
    // handled by interceptor
  }
}

async function updateAssignment(featureCode: string, agentId: number | null) {
  saving.value = featureCode;
  try {
    await requestClient.put(`/admin/ai/agent-assignments/${featureCode}`, {
      agent_id: agentId,
    });
    message.success($t('admin.ai.agentAssignment.saveSuccess'));
    await loadAssignments();
  } catch {
    // handled by interceptor
  } finally {
    saving.value = null;
  }
}

async function toggleActive(featureCode: string, isActive: boolean) {
  saving.value = featureCode;
  try {
    await requestClient.put(`/admin/ai/agent-assignments/${featureCode}`, {
      is_active: isActive,
    });
    await loadAssignments();
  } catch {
    // handled by interceptor
  } finally {
    saving.value = null;
  }
}

function featureName(featureCode: string, fallback: string): string {
  const key = `admin.ai.agentAssignment.features.${featureCode}.name`;
  const val = $t(key);
  return val === key ? fallback : val;
}

function featureDesc(featureCode: string, fallback: string): string {
  const key = `admin.ai.agentAssignment.features.${featureCode}.description`;
  const val = $t(key);
  return val === key ? fallback : val;
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

onMounted(() => {
  loadAssignments();
  loadAgentOptions();
});
</script>

<template>
  <Page :title="$t('admin.ai.agentAssignment.title')">
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
              <span class="font-medium">{{ featureName(record.feature_code, record.feature_name) }}</span>
            </div>
            <div class="text-muted-foreground mt-0.5 text-xs">
              {{ featureDesc(record.feature_code, record.description || '') }}
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
            <Switch
              :checked="record.is_active"
              :loading="saving === record.feature_code"
              size="small"
              @change="(val: unknown) => toggleActive(record.feature_code, val as boolean)"
            />
          </template>
        </template>
      </Table>
    </Card>
  </Page>
</template>
