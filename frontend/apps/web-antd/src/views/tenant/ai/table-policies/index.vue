<script lang="ts" setup>
/**
 * 企业端 AI 数据访问策略页面
 *
 * 展示有效策略列表（全局 + 企业覆盖合并），支持编辑覆盖和恢复默认。
 */
import type {
  EffectiveTablePolicy,
  TablePolicyOverrideRequest,
} from '#/api/tenant/ai';

import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  Badge,
  Button,
  Card,
  Drawer,
  Form,
  InputNumber,
  message,
  Modal,
  Spin,
  Switch,
  Table,
  Tag,
} from 'ant-design-vue';

import {
  getTenantTablePoliciesApi,
  removeTablePolicyOverrideApi,
  upsertTablePolicyOverrideApi,
} from '#/api/tenant/ai';
import { $t } from '#/locales';

defineOptions({ name: 'TenantAITablePolicies' });

// ============ State ============

const loading = ref(false);
const policies = ref<EffectiveTablePolicy[]>([]);
const searchText = ref('');

const filteredPolicies = computed(() => {
  if (!searchText.value) return policies.value;
  const q = searchText.value.toLowerCase();
  return policies.value.filter(
    (p) =>
      p.table_name.toLowerCase().includes(q) ||
      (p.label && p.label.toLowerCase().includes(q)),
  );
});

async function loadPolicies() {
  loading.value = true;
  try {
    const res = await getTenantTablePoliciesApi();
    policies.value = res || [];
  } catch {
    message.error($t('common.requestFailed'));
  } finally {
    loading.value = false;
  }
}

onMounted(loadPolicies);

// ============ Override Drawer ============

const drawerVisible = ref(false);
const editingPolicy = ref<EffectiveTablePolicy | null>(null);
const overrideForm = ref<TablePolicyOverrideRequest>({});
const saving = ref(false);

function openOverrideDrawer(policy: EffectiveTablePolicy) {
  editingPolicy.value = policy;
  overrideForm.value = {
    allow_read: policy.has_override ? policy.allow_read : undefined,
    allow_create: policy.has_override ? policy.allow_create : undefined,
    allow_update: policy.has_override ? policy.allow_update : undefined,
    allow_delete: policy.has_override ? policy.allow_delete : undefined,
    max_rows: policy.has_override ? policy.max_rows : undefined,
    is_active: policy.has_override ? policy.is_active : undefined,
  };
  drawerVisible.value = true;
}

async function saveOverride() {
  if (!editingPolicy.value) return;
  saving.value = true;
  try {
    await upsertTablePolicyOverrideApi(
      editingPolicy.value.id,
      overrideForm.value,
    );
    message.success($t('tenant.ai.tablePolicy.messages.overrideSuccess'));
    drawerVisible.value = false;
    await loadPolicies();
  } catch {
    message.error($t('common.requestFailed'));
  } finally {
    saving.value = false;
  }
}

async function resetOverride(policy: EffectiveTablePolicy) {
  Modal.confirm({
    title: $t('tenant.ai.tablePolicy.resetOverride'),
    content: $t('tenant.ai.tablePolicy.resetConfirm'),
    async onOk() {
      try {
        await removeTablePolicyOverrideApi(policy.id);
        message.success($t('tenant.ai.tablePolicy.messages.resetSuccess'));
        await loadPolicies();
      } catch {
        message.error($t('common.requestFailed'));
      }
    },
  });
}

// ============ Table Columns ============

const columns = [
  {
    title: $t('tenant.ai.tablePolicy.tableName'),
    dataIndex: 'table_name',
    key: 'table_name',
    width: 180,
  },
  {
    title: $t('tenant.ai.tablePolicy.label'),
    dataIndex: 'label',
    key: 'label',
    width: 150,
  },
  {
    title: $t('tenant.ai.tablePolicy.allowRead'),
    dataIndex: 'allow_read',
    key: 'allow_read',
    width: 80,
  },
  {
    title: $t('tenant.ai.tablePolicy.allowCreate'),
    dataIndex: 'allow_create',
    key: 'allow_create',
    width: 80,
  },
  {
    title: $t('tenant.ai.tablePolicy.allowUpdate'),
    dataIndex: 'allow_update',
    key: 'allow_update',
    width: 80,
  },
  {
    title: $t('tenant.ai.tablePolicy.allowDelete'),
    dataIndex: 'allow_delete',
    key: 'allow_delete',
    width: 80,
  },
  {
    title: $t('tenant.ai.tablePolicy.maxRows'),
    dataIndex: 'max_rows',
    key: 'max_rows',
    width: 100,
  },
  {
    title: $t('tenant.ai.tablePolicy.hasOverride'),
    dataIndex: 'has_override',
    key: 'has_override',
    width: 100,
  },
  {
    title: $t('common.action'),
    key: 'action',
    width: 180,
    fixed: 'right' as const,
  },
];
</script>

<template>
  <Page :title="$t('tenant.ai.tablePolicy.title')">
    <template #description>
      {{ $t('tenant.ai.tablePolicy.pageDesc') }}
    </template>

    <Card>
      <Spin :spinning="loading">
        <Table
          :columns="columns"
          :data-source="filteredPolicies"
          :pagination="false"
          :scroll="{ x: 1100 }"
          row-key="id"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template
              v-if="
                column.key === 'allow_read' ||
                column.key === 'allow_create' ||
                column.key === 'allow_update' ||
                column.key === 'allow_delete'
              "
            >
              <Badge :status="record[column.key] ? 'success' : 'default'" />
            </template>
            <template v-else-if="column.key === 'has_override'">
              <Tag v-if="record.has_override" color="blue">
                {{ $t('tenant.ai.tablePolicy.overridden') }}
              </Tag>
              <Tag v-else>
                {{ $t('tenant.ai.tablePolicy.globalDefault') }}
              </Tag>
            </template>
            <template v-else-if="column.key === 'action'">
              <Button
                type="link"
                size="small"
                @click="openOverrideDrawer(record as EffectiveTablePolicy)"
              >
                {{ $t('tenant.ai.tablePolicy.editOverride') }}
              </Button>
              <Button
                v-if="record.has_override"
                type="link"
                danger
                size="small"
                @click="resetOverride(record as EffectiveTablePolicy)"
              >
                {{ $t('tenant.ai.tablePolicy.resetOverride') }}
              </Button>
            </template>
          </template>
        </Table>
      </Spin>
    </Card>

    <!-- Override Drawer -->
    <Drawer
      v-model:open="drawerVisible"
      :title="$t('tenant.ai.tablePolicy.editOverride')"
      width="400"
    >
      <Form layout="vertical">
        <Form.Item :label="$t('tenant.ai.tablePolicy.allowRead')">
          <Switch v-model:checked="overrideForm.allow_read" />
        </Form.Item>
        <Form.Item :label="$t('tenant.ai.tablePolicy.allowCreate')">
          <Switch v-model:checked="overrideForm.allow_create" />
        </Form.Item>
        <Form.Item :label="$t('tenant.ai.tablePolicy.allowUpdate')">
          <Switch v-model:checked="overrideForm.allow_update" />
        </Form.Item>
        <Form.Item :label="$t('tenant.ai.tablePolicy.allowDelete')">
          <Switch v-model:checked="overrideForm.allow_delete" />
        </Form.Item>
        <Form.Item :label="$t('tenant.ai.tablePolicy.maxRows')">
          <InputNumber
            v-model:value="overrideForm.max_rows"
            :min="1"
            :max="editingPolicy?.max_rows ?? 1000"
            style="width: 100%"
          />
        </Form.Item>
      </Form>
      <template #footer>
        <div class="flex justify-end gap-2">
          <Button @click="drawerVisible = false">
            {{ $t('common.cancel') }}
          </Button>
          <Button type="primary" :loading="saving" @click="saveOverride">
            {{ $t('common.save') }}
          </Button>
        </div>
      </template>
    </Drawer>
  </Page>
</template>
