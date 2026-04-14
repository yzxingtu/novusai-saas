<script lang="ts" setup>
import type { UploadRequestOption } from 'ant-design-vue/es/vc-upload/interface';

import { IconifyIcon } from '@vben/icons';

import { Modal, Upload } from 'ant-design-vue';

import { $t } from '#/locales';

interface Props {
  onUpload: (options: UploadRequestOption) => Promise<void>;
  open: boolean;
  uploading: boolean;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  'update:open': [value: boolean];
}>();

function updateOpen(value: boolean) {
  emit('update:open', value);
}
</script>

<template>
  <Modal
    :open="props.open"
    :title="$t('admin.ai.skillPackage.uploadZip')"
    :footer="null"
    :destroy-on-close="true"
    width="520px"
    @update:open="updateOpen"
  >
    <div class="py-2">
      <Upload.Dragger
        :custom-request="props.onUpload"
        accept=".zip"
        :multiple="false"
        :show-upload-list="false"
        :disabled="props.uploading"
      >
        <div class="flex flex-col items-center gap-4 py-8">
          <div
            class="flex size-14 items-center justify-center rounded-2xl"
            :style="{
              background:
                'linear-gradient(135deg, hsl(var(--primary)) 0%, hsl(var(--primary) / 75%) 100%)',
            }"
          >
            <IconifyIcon
              :icon="
                props.uploading ? 'lucide:loader-2' : 'lucide:cloud-upload'
              "
              class="size-8 text-white"
              :class="{ 'animate-spin': props.uploading }"
            />
          </div>
          <div class="flex flex-col items-center gap-1">
            <span class="text-sm font-semibold text-foreground">
              {{
                props.uploading
                  ? $t('admin.ai.skillPackage.messages.uploading')
                  : $t('admin.ai.skillPackage.uploadDragText')
              }}
            </span>
            <span class="text-xs text-muted-foreground">
              {{ $t('admin.ai.skillPackage.uploadDesc') }}
            </span>
          </div>
        </div>
      </Upload.Dragger>
    </div>
  </Modal>
</template>
