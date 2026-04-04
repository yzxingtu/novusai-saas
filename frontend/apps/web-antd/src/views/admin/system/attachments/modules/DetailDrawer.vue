<script lang="ts" setup>
import type { AttachmentDetailSection } from '#/components/business/attachment-detail';
/**
 * 附件详情抽屉
 */
import type { AttachmentInfo } from '#/types/attachment';

import { computed } from 'vue';

import { getAttachmentDetailApi } from '#/api/admin/attachment';
import { AttachmentDetailDescriptions } from '#/components/business/attachment-detail';
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

const sections = computed<AttachmentDetailSection[]>(() => {
  if (!detail.value) return [];
  return [
    {
      fields: [
        { label: $t('admin.system.attachment.name'), value: detail.value.name },
        {
          label: $t('admin.system.attachment.path'),
          value: detail.value.path,
          kind: 'code',
        },
        {
          label: $t('admin.system.attachment.mimeType'),
          value: detail.value.mimeType,
        },
        {
          label: $t('admin.system.attachment.size'),
          value: formatFileSize(detail.value.size),
        },
        {
          label: $t('admin.system.attachment.category'),
          value: getCategoryText(detail.value.category),
          kind: 'tag',
          color: getCategoryColor(detail.value.category),
        },
        {
          label: $t('admin.system.attachment.visibility'),
          value: getVisibilityText(detail.value.visibility),
          kind: 'tag',
          color: getVisibilityColor(detail.value.visibility),
        },
        {
          label: $t('admin.system.attachment.driver'),
          value: detail.value.driver,
          kind: 'tag',
          color: 'blue',
        },
        {
          label: $t('admin.system.attachment.hash'),
          value: detail.value.hash,
          kind: 'code',
        },
        {
          label: $t('admin.system.attachment.tenantId'),
          value: detail.value.tenantId,
          show: Boolean(detail.value.tenantId),
        },
        {
          label: $t('admin.system.attachment.businessType'),
          value: detail.value.businessType,
          show: Boolean(detail.value.businessType),
        },
        {
          label: $t('admin.system.attachment.businessId'),
          value: detail.value.businessId,
          show: Boolean(detail.value.businessId),
        },
        {
          label: $t('admin.system.attachment.uploadedAt'),
          value: formatDate(detail.value.createdAt),
        },
      ],
    },
  ];
});
</script>

<template>
  <Drawer :title="$t('admin.system.attachment.detail')">
    <template v-if="detail">
      <AttachmentDetailDescriptions :sections="sections" />
    </template>
  </Drawer>
</template>
