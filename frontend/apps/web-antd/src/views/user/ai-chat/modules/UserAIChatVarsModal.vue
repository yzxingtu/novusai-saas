<script lang="ts" setup>
import { Input, Modal } from 'ant-design-vue';

import { $t } from '#/locales';

import { useUserAIChatContext } from './ai-chat-context';

const {
  varsModalVisible,
  varsModalAgent,
  varsFormValues,
  varsPersist,
  onVarsConfirm,
  onVarsCancel,
} = useUserAIChatContext();
</script>

<template>
  <Modal
    v-model:open="varsModalVisible"
    :title="
      $t('user.aiChat.varsModal.title', {
        name: varsModalAgent?.name ?? '',
      })
    "
    :mask-closable="false"
    :ok-text="$t('user.aiChat.varsModal.confirm')"
    :cancel-text="$t('common.cancel')"
    @ok="onVarsConfirm"
    @cancel="onVarsCancel"
  >
    <p class="mb-4 text-sm text-muted-foreground">
      {{ $t('user.aiChat.varsModal.desc') }}
    </p>
    <div v-if="varsModalAgent" class="space-y-4">
      <div
        v-for="v in varsModalAgent.vars"
        :key="v.name"
        class="flex flex-col gap-1"
      >
        <label class="text-sm font-medium">
          {{ v.label || v.name }}
          <span v-if="v.required" class="ml-0.5 text-destructive">*</span>
        </label>
        <Input
          v-model:value="varsFormValues[v.name]"
          :placeholder="v.default || v.label || v.name"
          allow-clear
        />
      </div>
      <label
        class="flex cursor-pointer items-center gap-2 pt-1 text-xs text-muted-foreground"
      >
        <input
          v-model="varsPersist"
          type="checkbox"
          class="size-3.5 cursor-pointer rounded accent-primary"
        />
        <span class="font-medium text-foreground/70">{{
          $t('user.aiChat.varsModal.persistLabel')
        }}</span>
        <span class="text-[11px]">{{
          $t('user.aiChat.varsModal.persistHint')
        }}</span>
      </label>
    </div>
  </Modal>
</template>
