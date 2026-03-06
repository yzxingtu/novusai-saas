<script lang="ts" setup>
/**
 * 管理端通知模板管理页面
 */
import type { NotificationTemplateInfo } from '#/api/admin/notification-templates';

import { onUnmounted, ref } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';
import { registerPageOperations } from '#/components/business/ai-slide-panel/page-operation-registry';

import { Page } from '@vben/common-ui';

import {
  Button,
  Card,
  Checkbox,
  Drawer,
  Form,
  Input,
  message,
  Select,
  Tag,
} from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  getNotificationTemplateListApi,
  testNotificationTemplateApi,
  updateNotificationTemplateApi,
} from '#/api/admin/notification-templates';
import { $t } from '#/locales';

import {
  getCategoryColor,
  getChannelColor,
  getChannelLabel,
  getPriorityColor,
  useColumns,
  useGridFormSchema,
} from './data';

defineOptions({ name: 'AdminNotificationTemplates' });

const editOpen = ref(false);
const editLoading = ref(false);
const editForm = ref<{
  body_template: string;
  channels: string[];
  code: string;
  id: number;
  priority: string;
  title_template: string;
}>({
  id: 0,
  code: '',
  channels: [],
  priority: 'normal',
  title_template: '',
  body_template: '',
});

const CHANNEL_OPTIONS = [
  { label: $t('admin.system.notificationTemplate.channelWs'), value: 'ws' },
  {
    label: $t('admin.system.notificationTemplate.channelInbox'),
    value: 'inbox',
  },
  {
    label: $t('admin.system.notificationTemplate.channelEmail'),
    value: 'email',
  },
  {
    label: $t('admin.system.notificationTemplate.channelWebhook'),
    value: 'webhook',
  },
];

const PRIORITY_OPTIONS = [
  {
    label: $t('admin.system.notificationTemplate.priority_options.low'),
    value: 'low',
  },
  {
    label: $t('admin.system.notificationTemplate.priority_options.normal'),
    value: 'normal',
  },
  {
    label: $t('admin.system.notificationTemplate.priority_options.high'),
    value: 'high',
  },
  {
    label: $t('admin.system.notificationTemplate.priority_options.urgent'),
    value: 'urgent',
  },
];

async function onTest(row: NotificationTemplateInfo) {
  try {
    await testNotificationTemplateApi(row.id);
    message.success(
      $t('admin.system.notificationTemplate.messages.testSuccess'),
    );
  } catch {
    message.error($t('admin.system.notificationTemplate.messages.testFailed'));
  }
}

function onEdit(row: NotificationTemplateInfo) {
  editForm.value = {
    id: row.id,
    code: row.code,
    channels: row.channels || [],
    priority: row.priority,
    title_template: row.title_template,
    body_template: row.body_template || '',
  };
  editOpen.value = true;
}

async function handleSave() {
  editLoading.value = true;
  try {
    await updateNotificationTemplateApi(editForm.value.id, {
      channels: editForm.value.channels,
      priority: editForm.value.priority,
      title_template: editForm.value.title_template,
      body_template: editForm.value.body_template || undefined,
    });
    message.success(
      $t('admin.system.notificationTemplate.messages.updateSuccess'),
    );
    editOpen.value = false;
    gridReload();
  } catch {
    message.error(
      $t('admin.system.notificationTemplate.messages.updateFailed'),
    );
  } finally {
    editLoading.value = false;
  }
}

const { Grid, onRefresh: gridReload, gridApi } = useCrudPage<NotificationTemplateInfo>({
  api: {
    list: getNotificationTemplateListApi,
    resource: '/admin/notification-templates',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  i18nPrefix: 'admin.system.notificationTemplate',
  defaultSort: 'category',
  customActions: {
    test: onTest,
    edit: onEdit,
  },
});

const cleanupPageContext = registerPageContext('admin/system/notification-templates', () => ({
  page_key: 'admin.system.notification-templates',
  page_title: $t('admin.system.notificationTemplate.name'),
  page_data: {
    resource: '/admin/notification-templates',
  },
}));

const cleanupPageOps = registerPageOperations('admin.system.notification-templates', [
  {
    name: 'search_templates',
    label: $t('shared.pageOperation.searchByKeyword'),
    description: 'Search notification templates by code',
    readonly: true,
    params: {
      keyword: { type: 'string', description: 'Template code keyword' },
    },
    handler: async (params) => {
      const keyword = (params?.keyword as string) || '';
      gridApi.formApi?.setValues({ 'filter[code][ilike]': keyword });
      gridApi.reload({ page: 1 });
      return { success: true, message: `Searched for: ${keyword}` };
    },
  },
  {
    name: 'refresh_list',
    label: $t('shared.pageOperation.refreshList'),
    description: 'Reload the notification template list',
    readonly: true,
    handler: async () => {
      gridReload();
      return { success: true, message: 'Notification template list refreshed' };
    },
  },
]);

onUnmounted(() => {
  cleanupPageContext();
  cleanupPageOps();
});
</script>

<template>
  <Page
    auto-content-height
    :description="$t('admin.system.notificationTemplate.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <!-- 编辑抽屉 -->
    <Drawer
      v-model:open="editOpen"
      :title="$t('admin.system.notificationTemplate.editTitle')"
      width="500"
    >
      <Form layout="vertical">
        <Form.Item :label="$t('admin.system.notificationTemplate.code')">
          <Input :value="editForm.code" disabled />
        </Form.Item>
        <Form.Item :label="$t('admin.system.notificationTemplate.channels')">
          <Checkbox.Group
            v-model:value="editForm.channels"
            :options="CHANNEL_OPTIONS"
          />
        </Form.Item>
        <Form.Item :label="$t('admin.system.notificationTemplate.priority')">
          <Select
            v-model:value="editForm.priority"
            :options="PRIORITY_OPTIONS"
          />
        </Form.Item>
        <Form.Item
          :label="$t('admin.system.notificationTemplate.titleTemplate')"
        >
          <Input v-model:value="editForm.title_template" />
        </Form.Item>
        <Form.Item
          :label="$t('admin.system.notificationTemplate.bodyTemplate')"
        >
          <Input.TextArea v-model:value="editForm.body_template" :rows="4" />
        </Form.Item>
        <Form.Item>
          <Button type="primary" :loading="editLoading" @click="handleSave">
            {{ $t('common.save') }}
          </Button>
        </Form.Item>
      </Form>
    </Drawer>

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 编码列 -->
        <template #code_cell="{ row }">
          <span class="font-mono text-xs text-muted-foreground">{{
            row.code
          }}</span>
        </template>

        <!-- 标题模板列 -->
        <template #title_cell="{ row }">
          <span class="text-sm text-foreground">{{ row.title_template }}</span>
        </template>

        <!-- 正文模板列 -->
        <template #body_cell="{ row }">
          <span
            v-if="row.body_template"
            class="line-clamp-2 text-xs text-muted-foreground"
          >
            {{ row.body_template }}
          </span>
          <span v-else class="text-xs text-muted-foreground">-</span>
        </template>

        <!-- 分类列 -->
        <template #category_cell="{ row }">
          <Tag :color="getCategoryColor(row.category)">
            {{
              $t(
                `admin.system.notificationTemplate.category_options.${row.category}`,
              )
            }}
          </Tag>
        </template>

        <!-- 渠道列 -->
        <template #channels_cell="{ row }">
          <div class="flex flex-wrap gap-1">
            <Tag
              v-for="ch in row.channels || []"
              :key="ch"
              :color="getChannelColor(ch)"
              size="small"
            >
              {{ getChannelLabel(ch) }}
            </Tag>
          </div>
        </template>

        <!-- 优先级列 -->
        <template #priority_cell="{ row }">
          <Tag :color="getPriorityColor(row.priority)">
            {{
              $t(
                `admin.system.notificationTemplate.priority_options.${row.priority}`,
              )
            }}
          </Tag>
        </template>

        <!-- 系统内置列 -->
        <template #isSystem_cell="{ row }">
          <Tag :color="row.is_system ? 'blue' : 'default'">
            {{
              row.is_system
                ? $t('admin.system.notificationTemplate.systemBuiltin')
                : $t('admin.system.notificationTemplate.custom')
            }}
          </Tag>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
