<script lang="ts" setup>
import type { BindingRecord } from '../../../types';

const props = defineProps<{
  bindingColumns: Array<{ key: string; title: string }>;
  bindings: BindingRecord[];
  canConfigureAdmin: boolean;
  hasVisibleProviders: boolean;
  openCreate: () => void;
  openEdit: (record: BindingRecord) => void;
  prettyStatus: (status: string) => string;
  providerLabel: (code: BindingRecord['provider_code']) => string;
  revalidateBinding: (record: BindingRecord) => void;
  scopeValue: (record: BindingRecord) => string;
  statusColor: (status: string) => string;
}>();
</script>

<template>
  <Card :title="$t('plugin.storage-billing.admin.bindings.title')" class="block">
    <template #extra>
      <Button
        v-if="props.canConfigureAdmin"
        :disabled="!props.hasVisibleProviders"
        type="primary"
        @click="props.openCreate"
      >
        {{ $t('plugin.storage-billing.admin.bindings.add') }}
      </Button>
    </template>
    <div class="section-subtitle">{{ $t('plugin.storage-billing.admin.bindings.subtitle') }}</div>
    <Table
      :columns="props.bindingColumns"
      :data-source="props.bindings"
      :locale="{ emptyText: $t('plugin.storage-billing.admin.bindings.empty') }"
      :pagination="false"
      row-key="id"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'tenant'">#{{ record.tenant_id }}</template>
        <template v-else-if="column.key === 'provider'">{{ props.providerLabel(record.provider_code) }}</template>
        <template v-else-if="column.key === 'mode'">{{ $t(`plugin.storage-billing.admin.bindings.mode.${record.billing_mode}`) }}</template>
        <template v-else-if="column.key === 'scope'">
          <Space wrap>
            <Tag color="blue">{{ $t(`plugin.storage-billing.admin.bindings.scope.${record.scope_type}`) }}</Tag>
            <span>{{ props.scopeValue(record) }}</span>
          </Space>
        </template>
        <template v-else-if="column.key === 'status'">
          <Tag :color="props.statusColor(record.validation_status)">{{ props.prettyStatus(record.validation_status) }}</Tag>
        </template>
        <template v-else-if="column.key === 'message'">
          <span class="muted">{{ record.validation_message || '-' }}</span>
        </template>
        <template v-else-if="column.key === 'actions'">
          <Space v-if="props.canConfigureAdmin" wrap>
            <Button size="small" @click="props.openEdit(record)">{{ $t('plugin.storage-billing.admin.bindings.edit') }}</Button>
            <Button size="small" @click="props.revalidateBinding(record)">{{ $t('plugin.storage-billing.admin.bindings.revalidate') }}</Button>
          </Space>
        </template>
      </template>
    </Table>
    <div v-if="!props.bindings.length" class="empty">
      <Empty :description="$t('plugin.storage-billing.admin.bindings.empty')" />
    </div>
  </Card>
</template>
