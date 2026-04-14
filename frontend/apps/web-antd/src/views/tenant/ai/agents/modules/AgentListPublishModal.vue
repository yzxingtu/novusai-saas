<script lang="ts" setup>
import { computed } from 'vue';

import { Input, Modal } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'TenantAgentListPublishModal' });

const props = defineProps<{
  changeLog: string;
  confirmLoading: boolean;
  open: boolean;
}>();

const emit = defineEmits<{
  confirm: [];
  'update:changeLog': [value: string];
  'update:open': [value: boolean];
}>();

const modalOpen = computed({
  get: () => props.open,
  set: (value: boolean) => emit('update:open', value),
});

const modalChangeLog = computed({
  get: () => props.changeLog,
  set: (value: string) => emit('update:changeLog', value),
});
</script>

<template>
  <Modal
    v-model:open="modalOpen"
    :title="$t('tenant.ai.agent.version.publishTitle')"
    :confirm-loading="confirmLoading"
    @ok="emit('confirm')"
  >
    <p class="mb-2 text-muted-foreground">
      {{ $t('tenant.ai.agent.version.publishDesc') }}
    </p>
    <Input.TextArea
      v-model:value="modalChangeLog"
      :placeholder="$t('tenant.ai.agent.version.changeLogPlaceholder')"
      :rows="3"
      :maxlength="2000"
      show-count
    />
  </Modal>
</template>
