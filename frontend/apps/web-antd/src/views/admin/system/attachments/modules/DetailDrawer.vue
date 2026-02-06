<script lang="ts" setup>
/**
 * 附件详情抽屉
 */
import type { AttachmentInfo } from '#/types/attachment';

import { Descriptions, DescriptionsItem, Tag } from 'ant-design-vue';

import { getAttachmentDetailApi } from '#/api/admin/attachment';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import {
  formatFileSize,
  getCategoryColor,
  getCategoryText,
  getVisibilityColor,
  getVisibilityText,
} from '../data';

defineOptions({ name: 'AttachmentDetailDrawer' });

const { Drawer, detailData: detail } = useCrudDrawer<AttachmentInfo>({
  detailApi: (id) => getAttachmentDetailApi(id as number),
});
</script>

<template>
  <Drawer :title="$t('admin.system.attachment.detail')">
    <template v-if="detail">
      <Descriptions :column="1" bordered size="small">
        <DescriptionsItem :label="$t('admin.system.attachment.name')">
          {{ detail.name }}
        </DescriptionsItem>
        <DescriptionsItem :label="$t('admin.system.attachment.path')">
          <code class="rounded bg-accent px-1 py-0.5 text-xs">
            {{ detail.path }}
          </code>
        </DescriptionsItem>
        <DescriptionsItem :label="$t('admin.system.attachment.mimeType')">
          {{ detail.mimeType }}
        </DescriptionsItem>
        <DescriptionsItem :label="$t('admin.system.attachment.size')">
          {{ formatFileSize(detail.size) }}
        </DescriptionsItem>
        <DescriptionsItem :label="$t('admin.system.attachment.category')">
          <Tag :color="getCategoryColor(detail.category)">
            {{ getCategoryText(detail.category) }}
          </Tag>
        </DescriptionsItem>
        <DescriptionsItem :label="$t('admin.system.attachment.visibility')">
          <Tag :color="getVisibilityColor(detail.visibility)">
            {{ getVisibilityText(detail.visibility) }}
          </Tag>
        </DescriptionsItem>
        <DescriptionsItem :label="$t('admin.system.attachment.driver')">
          <Tag color="blue">{{ detail.driver }}</Tag>
        </DescriptionsItem>
        <DescriptionsItem :label="$t('admin.system.attachment.hash')">
          <code class="rounded bg-accent px-1 py-0.5 text-xs">
            {{ detail.hash }}
          </code>
        </DescriptionsItem>
        <DescriptionsItem
          v-if="detail.tenantId"
          :label="$t('admin.system.attachment.tenantId')"
        >
          {{ detail.tenantId }}
        </DescriptionsItem>
        <DescriptionsItem
          v-if="detail.refType"
          :label="$t('admin.system.attachment.refType')"
        >
          {{ detail.refType }}
        </DescriptionsItem>
        <DescriptionsItem
          v-if="detail.refId"
          :label="$t('admin.system.attachment.refId')"
        >
          {{ detail.refId }}
        </DescriptionsItem>
        <DescriptionsItem :label="$t('admin.system.attachment.uploadedAt')">
          {{ formatDate(detail.uploadedAt) }}
        </DescriptionsItem>
        <DescriptionsItem :label="$t('admin.system.attachment.createdAt')">
          {{ formatDate(detail.createdAt) }}
        </DescriptionsItem>
      </Descriptions>
    </template>
  </Drawer>
</template>
