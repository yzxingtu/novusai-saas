<script lang="ts" setup>
/**
 * 邮件内容预览抽屉
 */
import type { EmailLogDetail } from '#/api/admin/email-log';

import { ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Descriptions, Empty, Spin, Tag } from 'ant-design-vue';

import { getEmailLogDetailApi } from '#/api/admin/email-log';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import { getStatusColor, getTriggerColor } from '../data';

const [Drawer, drawerApi] = useVbenDrawer({
  onOpenChange(isOpen: boolean) {
    if (isOpen) {
      const data = drawerApi.getData<{ id: number }>();
      if (data?.id) {
        loadDetail(data.id);
      }
    }
  },
});

const loading = ref(false);
const detail = ref<EmailLogDetail | null>(null);

async function loadDetail(id: number) {
  loading.value = true;
  detail.value = null;
  try {
    detail.value = await getEmailLogDetailApi(id);
  } catch {
    // handled by interceptor
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <Drawer
    :title="$t('admin.system.emailLog.preview.title')"
    class="w-[680px]"
  >
    <Spin :spinning="loading">
      <template v-if="detail">
        <!-- 基本信息 -->
        <Descriptions
          :column="2"
          bordered
          size="small"
          class="mb-4"
        >
          <Descriptions.Item :label="$t('admin.system.emailLog.toAddress')" :span="2">
            {{ detail.toAddress }}
          </Descriptions.Item>
          <Descriptions.Item v-if="detail.cc" :label="'CC'" :span="2">
            {{ detail.cc }}
          </Descriptions.Item>
          <Descriptions.Item v-if="detail.bcc" :label="'BCC'" :span="2">
            {{ detail.bcc }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.system.emailLog.subject')" :span="2">
            <span class="font-medium">{{ detail.subject }}</span>
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.system.emailLog.statusLabel')" :span="1">
            <Tag :color="getStatusColor(detail.status)">
              {{ $t(`admin.system.emailLog.status.${detail.status}`) }}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.system.emailLog.triggeredBy')" :span="1">
            <Tag :color="getTriggerColor(detail.triggeredBy)">
              {{ $t(`admin.system.emailLog.trigger.${detail.triggeredBy}`) }}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.system.emailLog.createdAt')" :span="1">
            {{ detail.createdAt ? formatDate(detail.createdAt) : '-' }}
          </Descriptions.Item>
          <Descriptions.Item v-if="detail.errorMessage" :label="$t('admin.system.emailLog.errorMessage')" :span="2">
            <span class="text-destructive">{{ detail.errorMessage }}</span>
          </Descriptions.Item>
        </Descriptions>

        <!-- 邮件内容 -->
        <div class="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
          <IconifyIcon icon="lucide:file-text" class="size-4" />
          {{ $t('admin.system.emailLog.preview.content') }}
        </div>

        <div v-if="detail.htmlBody" class="rounded-lg border border-border bg-background">
          <iframe
            :srcdoc="detail.htmlBody"
            class="h-[400px] w-full rounded-lg"
            sandbox="allow-same-origin"
            frameborder="0"
          />
        </div>
        <div v-else-if="detail.textBody" class="rounded-lg border border-border bg-muted/30 p-4">
          <pre class="whitespace-pre-wrap text-sm text-foreground">{{ detail.textBody }}</pre>
        </div>
        <Empty
          v-else
          :description="$t('admin.system.emailLog.preview.noContent')"
          class="py-8"
        />
      </template>
    </Spin>
  </Drawer>
</template>
