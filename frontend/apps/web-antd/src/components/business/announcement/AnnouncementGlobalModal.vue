<script lang="ts" setup>
import type { AnnouncementAnswers } from '#/types/announcement';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  message,
  Modal,
  Spin,
  Tag,
  Typography,
} from 'ant-design-vue';

import { $t } from '#/locales';
import { useAnnouncementStore } from '#/store';
import {
  normalizeAnnouncementAnswers,
  validateAnnouncementAnswers,
} from '#/types/announcement';
import { formatDate } from '#/utils/common';

import AnnouncementAnswerForm from './AnnouncementAnswerForm.vue';

defineOptions({ name: 'AnnouncementGlobalModal' });

const announcementStore = useAnnouncementStore();
const answers = ref<AnnouncementAnswers>({});

const requiresResponse = computed(
  () => announcementStore.current?.requireResponse === true,
);
const deliveryStatus = computed(
  () => announcementStore.current?.deliveryStatus ?? 'pending',
);
const canSubmit = computed(
  () => requiresResponse.value && deliveryStatus.value === 'pending',
);
const canMarkRead = computed(
  () => !requiresResponse.value && deliveryStatus.value === 'pending',
);
const readonlyResponse = computed(
  () => requiresResponse.value && deliveryStatus.value !== 'pending',
);
const canClose = computed(
  () => !requiresResponse.value || readonlyResponse.value,
);

watch(
  () => announcementStore.current,
  (item) => {
    answers.value = item
      ? normalizeAnnouncementAnswers(item.formSchema, item.answers)
      : {};
  },
  { immediate: true },
);

async function submitCurrent() {
  const current = announcementStore.current;
  if (!current || !canSubmit.value) {
    return;
  }

  const errors = validateAnnouncementAnswers(current.formSchema, answers.value);
  if (errors.length > 0) {
    message.warning($t('common.announcement.answerRequired'));
    return;
  }

  await announcementStore.submitCurrent(answers.value);
  if (announcementStore.pendingCount === 0) {
    message.success($t('common.announcement.submitSuccess'));
  }
}

async function closeCurrent() {
  if (!announcementStore.current || !canClose.value) {
    return;
  }
  if (!canMarkRead.value) {
    announcementStore.dismissCurrent();
    return;
  }
  await announcementStore.markCurrentRead();
  if (announcementStore.pendingCount === 0) {
    message.success($t('common.announcement.markReadSuccess'));
  }
}
</script>

<template>
  <Modal
    :open="announcementStore.visible"
    :closable="canClose"
    :footer="null"
    :keyboard="canClose"
    :mask-closable="false"
    :title="
      requiresResponse
        ? $t('common.announcement.requiredModalTitle')
        : $t('common.announcement.globalModalTitle')
    "
    centered
    width="680px"
    @cancel="closeCurrent"
  >
    <Spin :spinning="announcementStore.loading">
      <div v-if="announcementStore.current" class="space-y-5">
        <Alert
          :message="
            requiresResponse
              ? canSubmit
                ? $t('common.announcement.requiredModalHint')
                : $t('common.announcement.responseReadonlyHint')
              : $t('common.announcement.globalModalHint')
          "
          show-icon
          :type="requiresResponse ? 'warning' : 'info'"
        />

        <div class="space-y-2">
          <div class="flex flex-wrap items-center gap-2">
            <Tag :color="requiresResponse ? 'orange' : 'blue'">
              {{
                readonlyResponse
                  ? $t('common.announcement.submittedReadOnly')
                  : requiresResponse
                    ? $t('common.announcement.requiresResponse')
                    : $t('common.announcement.globalAnnouncement')
              }}
            </Tag>
            <span class="text-xs text-muted-foreground">
              {{
                $t('common.announcement.modalQueueProgress', {
                  count: announcementStore.pendingCount,
                })
              }}
            </span>
          </div>
          <Typography.Title :level="4" class="!mb-0">
            {{ announcementStore.current.title }}
          </Typography.Title>
          <span class="text-xs text-muted-foreground">
            {{
              $t('common.announcement.publishedAtWithValue', {
                value: formatDate(announcementStore.current.publishedAt),
              })
            }}
          </span>
        </div>

        <Typography.Paragraph class="whitespace-pre-wrap">
          {{ announcementStore.current.content || '-' }}
        </Typography.Paragraph>

        <AnnouncementAnswerForm
          v-if="requiresResponse"
          v-model="answers"
          :readonly="readonlyResponse"
          :schema="announcementStore.current.formSchema"
        />

        <div class="flex justify-end gap-2">
          <Button
            v-if="canMarkRead"
            :loading="announcementStore.submitting"
            @click="closeCurrent"
          >
            <template #icon>
              <IconifyIcon icon="lucide:check-check" class="size-4" />
            </template>
            {{ $t('common.announcement.markReadAndClose') }}
          </Button>
          <Button
            v-else-if="canSubmit"
            :loading="announcementStore.submitting"
            type="primary"
            @click="submitCurrent"
          >
            <template #icon>
              <IconifyIcon icon="lucide:check" class="size-4" />
            </template>
            {{ $t('common.submit') }}
          </Button>
          <Button v-else @click="closeCurrent">
            <template #icon>
              <IconifyIcon icon="lucide:x" class="size-4" />
            </template>
            {{ $t('common.close') }}
          </Button>
        </div>
      </div>
    </Spin>
  </Modal>
</template>
