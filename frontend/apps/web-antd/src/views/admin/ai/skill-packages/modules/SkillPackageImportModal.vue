<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { Modal, Select, Upload } from 'ant-design-vue';

import { $t } from '#/locales';

interface Props {
  conflictMode: 'rename' | 'skip';
  importing: boolean;
  onImportFile: (file: File) => Promise<boolean>;
  open: boolean;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  'update:conflictMode': [value: 'rename' | 'skip'];
  'update:open': [value: boolean];
}>();

function updateOpen(value: boolean) {
  emit('update:open', value);
}

function updateConflictMode(value: 'rename' | 'skip') {
  emit('update:conflictMode', value);
}
</script>

<template>
  <Modal
    :open="props.open"
    :title="$t('admin.ai.skillPackage.importBtn')"
    :footer="null"
    :destroy-on-close="true"
    width="520px"
    @update:open="updateOpen"
  >
    <div class="flex flex-col gap-3 py-2">
      <div class="flex gap-4">
        <div class="flex flex-1 flex-col gap-1">
          <span class="text-xs font-medium text-muted-foreground">
            {{ $t('admin.ai.skillPackage.importConflictMode') }}
          </span>
          <Select
            :value="props.conflictMode"
            size="small"
            :options="[
              {
                label: $t('admin.ai.skillPackage.importConflictRename'),
                value: 'rename',
              },
              {
                label: $t('admin.ai.skillPackage.importConflictSkip'),
                value: 'skip',
              },
            ]"
            @update:value="
              (value) =>
                updateConflictMode((value ?? 'rename') as 'rename' | 'skip')
            "
          />
        </div>
      </div>
      <Upload.Dragger
        :before-upload="props.onImportFile"
        accept=".json"
        :multiple="false"
        :show-upload-list="false"
        :disabled="props.importing"
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
              :icon="props.importing ? 'lucide:loader-2' : 'lucide:file-input'"
              class="size-8 text-white"
              :class="{ 'animate-spin': props.importing }"
            />
          </div>
          <div class="flex flex-col items-center gap-1">
            <span class="text-sm font-semibold text-foreground">
              {{
                props.importing
                  ? $t('admin.ai.skillPackage.messages.uploading')
                  : $t('admin.ai.skillPackage.importDragText')
              }}
            </span>
            <span class="text-xs text-muted-foreground">
              {{ $t('admin.ai.skillPackage.importDesc') }}
            </span>
          </div>
        </div>
      </Upload.Dragger>
    </div>
  </Modal>
</template>
