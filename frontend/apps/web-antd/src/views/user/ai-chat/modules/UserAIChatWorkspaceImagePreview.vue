<script lang="ts" setup>
import { Modal } from 'ant-design-vue';

import { useUserAIChatWorkspaceContext } from './user-ai-chat-workspace-context';

const { previewImageUrl, previewImageVisible } =
  useUserAIChatWorkspaceContext();
</script>

<template>
  <Modal
    v-model:open="previewImageVisible"
    :footer="null"
    width="auto"
    :style="{ maxWidth: '90vw' }"
    centered
    destroy-on-close
  >
    <img
      :src="previewImageUrl"
      alt=""
      class="max-h-[80vh] max-w-full object-contain"
    />
  </Modal>
</template>
