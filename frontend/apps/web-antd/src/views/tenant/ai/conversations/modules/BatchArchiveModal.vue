<script lang="ts" setup>
defineOptions({ name: 'TenantBatchArchiveModal' });
/**
 * 批量归档对话弹窗
 * 支持按天数归档过期对话
 */
import { ref } from 'vue';

import { message, Modal, Select } from 'ant-design-vue';

import { batchArchiveConversationsApi } from '#/api/tenant/conversations';
import { $t } from '#/locales';

const props = defineProps<{
  open: boolean;
}>();

const emits = defineEmits<{
  success: [];
  'update:open': [value: boolean];
}>();

const loading = ref(false);
const beforeDays = ref<number>(30);

const daysOptions = [
  { label: $t('tenant.ai.conversation.batchArchiveOptions.days7'), value: 7 },
  { label: $t('tenant.ai.conversation.batchArchiveOptions.days14'), value: 14 },
  { label: $t('tenant.ai.conversation.batchArchiveOptions.days30'), value: 30 },
  { label: $t('tenant.ai.conversation.batchArchiveOptions.days60'), value: 60 },
  { label: $t('tenant.ai.conversation.batchArchiveOptions.days90'), value: 90 },
];

async function onOk() {
  loading.value = true;
  try {
    const result = await batchArchiveConversationsApi({
      before_days: beforeDays.value,
    });
    message.success(
      $t('tenant.ai.conversation.messages.batchArchiveSuccess', {
        count: result.archived_count,
      }),
    );
    emits('update:open', false);
    emits('success');
  } catch {
    message.error($t('tenant.common.failed'));
  } finally {
    loading.value = false;
  }
}

function onCancel() {
  emits('update:open', false);
}
</script>

<template>
  <Modal
    :open="props.open"
    :title="$t('tenant.ai.conversation.batchArchive')"
    :confirm-loading="loading"
    @ok="onOk"
    @cancel="onCancel"
  >
    <div class="flex flex-col gap-4 py-4">
      <div>
        <label class="mb-1.5 block text-sm font-medium text-foreground">
          {{ $t('tenant.ai.conversation.archiveBeforeDays') }}
        </label>
        <Select
          v-model:value="beforeDays"
          :options="daysOptions"
          class="w-full"
        />
      </div>
      <div class="rounded-lg bg-warning/10 p-3 text-sm text-warning">
        {{ $t('tenant.ai.conversation.batchArchiveWarning') }}
      </div>
    </div>
  </Modal>
</template>
