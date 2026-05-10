<script lang="ts" setup>
/**
 * 管理端通知模板管理页面
 */
import type {
  NotificationTemplateInfo,
  NotificationTemplateLockedField,
  UpdateNotificationTemplateParams,
} from '#/api/admin/notification-templates';

import { computed, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  Button,
  Card,
  Checkbox,
  Descriptions,
  Drawer,
  Form,
  Input,
  message,
  Modal,
  Select,
  Switch,
  Tag,
} from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  getNotificationTemplateListApi,
  getNotificationTemplatePreviewApi,
  restoreNotificationTemplateDefaultApi,
  testNotificationTemplateApi,
  updateNotificationTemplateApi,
} from '#/api/admin/notification-templates';
import { $t } from '#/locales';

import {
  getCategoryColor,
  getChannelColor,
  getChannelLabel,
  getOverrideLabel,
  getPriorityColor,
  getScopeLabel,
  getSourceLabel,
  useColumns,
  useGridFormSchema,
} from './data';

defineOptions({ name: 'AdminNotificationTemplates' });

const editOpen = ref(false);
const editLoading = ref(false);
const previewOpen = ref(false);
const previewLoading = ref(false);
const previewData = ref<NotificationTemplateInfo['effectivePreview'] | null>(
  null,
);
const previewRecord = ref<NotificationTemplateInfo | null>(null);
const editForm = ref<{
  bodyTemplate: string;
  channels: string[];
  code: string;
  enabled: boolean;
  id: number;
  isOverride: boolean;
  lockedFields: NotificationTemplateLockedField[];
  pluginName: null | string;
  priority: string;
  scope: null | string;
  source: null | string;
  tenantName: null | string;
  titleTemplate: string;
}>({
  id: 0,
  code: '',
  scope: null,
  tenantName: null,
  pluginName: null,
  source: null,
  isOverride: false,
  lockedFields: [],
  enabled: true,
  channels: [],
  priority: 'normal',
  titleTemplate: '',
  bodyTemplate: '',
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

const LOCKABLE_TEMPLATE_FIELDS = [
  'channels',
  'priority',
  'title_template',
  'body_template',
  'is_enabled',
] as const;

type LockableTemplateField = (typeof LOCKABLE_TEMPLATE_FIELDS)[number];

const LOCKED_FIELD_LABEL_KEYS: Record<LockableTemplateField, string> = {
  body_template: 'bodyTemplate',
  channels: 'channels',
  is_enabled: 'enabled',
  priority: 'priority',
  title_template: 'titleTemplate',
};

function isKnownLockableField(
  field: NotificationTemplateLockedField,
): field is LockableTemplateField {
  return (LOCKABLE_TEMPLATE_FIELDS as readonly string[]).includes(field);
}

function getLockedFieldLabel(field: NotificationTemplateLockedField) {
  if (!isKnownLockableField(field)) {
    return field;
  }
  return $t(
    `admin.system.notificationTemplate.${LOCKED_FIELD_LABEL_KEYS[field]}`,
  );
}

function getLockedFieldLabels(
  fields: NotificationTemplateLockedField[] | null | undefined,
) {
  return (fields ?? []).map((field) => getLockedFieldLabel(field));
}

function isLockedField(field: LockableTemplateField) {
  return editForm.value.lockedFields.includes(field);
}

const canSaveEdit = computed(() =>
  LOCKABLE_TEMPLATE_FIELDS.some((field) => !isLockedField(field)),
);

const editLockedFieldLabels = computed(() =>
  getLockedFieldLabels(editForm.value.lockedFields),
);

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
    scope: row.scope,
    tenantName: row.tenantName,
    pluginName: row.pluginName,
    source: row.source,
    isOverride: row.isOverride,
    lockedFields: row.lockedFields,
    enabled: row.enabled,
    channels: row.channels || [],
    priority: row.priority,
    titleTemplate: row.titleTemplate,
    bodyTemplate: row.bodyTemplate || '',
  };
  editOpen.value = true;
}

function buildUpdatePayload(): UpdateNotificationTemplateParams {
  const payload: UpdateNotificationTemplateParams = {};
  if (!isLockedField('channels')) {
    payload.channels = editForm.value.channels;
  }
  if (!isLockedField('priority')) {
    payload.priority = editForm.value.priority;
  }
  if (!isLockedField('is_enabled')) {
    payload.enabled = editForm.value.enabled;
  }
  if (!isLockedField('title_template')) {
    payload.titleTemplate = editForm.value.titleTemplate;
  }
  if (!isLockedField('body_template')) {
    payload.bodyTemplate = editForm.value.bodyTemplate || null;
  }
  return payload;
}

async function onPreview(row: NotificationTemplateInfo) {
  previewRecord.value = row;
  previewData.value = row.effectivePreview;
  previewOpen.value = true;
  previewLoading.value = true;
  try {
    previewData.value = await getNotificationTemplatePreviewApi(row.id);
  } finally {
    previewLoading.value = false;
  }
}

function onRestore(row: NotificationTemplateInfo) {
  Modal.confirm({
    title: $t('admin.system.notificationTemplate.restoreConfirmTitle'),
    content: $t('admin.system.notificationTemplate.restoreConfirmContent', {
      code: row.code,
    }),
    okText: $t('admin.system.notificationTemplate.restoreDefault'),
    cancelText: $t('common.cancel'),
    async onOk() {
      await restoreNotificationTemplateDefaultApi(row.id);
      message.success(
        $t('admin.system.notificationTemplate.messages.restoreSuccess'),
      );
      gridReload();
    },
  });
}

async function handleSave() {
  const payload = buildUpdatePayload();
  if (Object.keys(payload).length === 0) {
    return;
  }

  editLoading.value = true;
  try {
    await updateNotificationTemplateApi(editForm.value.id, payload);
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

const { Grid, onRefresh: gridReload } = useCrudPage<NotificationTemplateInfo>({
  api: {
    list: getNotificationTemplateListApi,
    resource: '/admin/notification-templates',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  i18nPrefix: 'admin.system.notificationTemplate',
  defaultSort: 'category',
  customActions: {
    preview: onPreview,
    restore: onRestore,
    test: onTest,
    edit: onEdit,
  },
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
        <Form.Item :label="$t('admin.system.notificationTemplate.scope')">
          <Input :value="getScopeLabel(editForm.scope)" disabled />
        </Form.Item>
        <Form.Item :label="$t('admin.system.notificationTemplate.tenant')">
          <Input
            :value="
              editForm.tenantName ||
              $t('admin.system.notificationTemplate.platformDefault')
            "
            disabled
          />
        </Form.Item>
        <Form.Item :label="$t('admin.system.notificationTemplate.plugin')">
          <Input
            :value="
              editForm.pluginName ||
              $t('admin.system.notificationTemplate.noPlugin')
            "
            disabled
          />
        </Form.Item>
        <Form.Item :label="$t('admin.system.notificationTemplate.source')">
          <Input :value="getSourceLabel(editForm.source)" disabled />
        </Form.Item>
        <Form.Item :label="$t('admin.system.notificationTemplate.override')">
          <Input :value="getOverrideLabel(editForm.isOverride)" disabled />
        </Form.Item>
        <Form.Item
          :label="$t('admin.system.notificationTemplate.lockedFields')"
        >
          <div
            v-if="editLockedFieldLabels.length > 0"
            class="flex flex-wrap gap-1"
          >
            <Tag
              v-for="label in editLockedFieldLabels"
              :key="label"
              color="orange"
            >
              {{ label }}
            </Tag>
          </div>
          <span v-else class="text-xs text-muted-foreground">
            {{ $t('admin.system.notificationTemplate.noLockedFields') }}
          </span>
        </Form.Item>
        <Form.Item :label="$t('admin.system.notificationTemplate.enabled')">
          <Switch
            v-model:checked="editForm.enabled"
            :disabled="isLockedField('is_enabled')"
          />
        </Form.Item>
        <Form.Item :label="$t('admin.system.notificationTemplate.channels')">
          <Checkbox.Group
            v-model:value="editForm.channels"
            :disabled="isLockedField('channels')"
            :options="CHANNEL_OPTIONS"
          />
        </Form.Item>
        <Form.Item :label="$t('admin.system.notificationTemplate.priority')">
          <Select
            v-model:value="editForm.priority"
            :disabled="isLockedField('priority')"
            :options="PRIORITY_OPTIONS"
          />
        </Form.Item>
        <Form.Item
          :label="$t('admin.system.notificationTemplate.titleTemplate')"
        >
          <Input
            v-model:value="editForm.titleTemplate"
            :disabled="isLockedField('title_template')"
          />
        </Form.Item>
        <Form.Item
          :label="$t('admin.system.notificationTemplate.bodyTemplate')"
        >
          <Input.TextArea
            v-model:value="editForm.bodyTemplate"
            :disabled="isLockedField('body_template')"
            :rows="4"
          />
        </Form.Item>
        <Form.Item>
          <Button
            type="primary"
            :disabled="!canSaveEdit"
            :loading="editLoading"
            @click="handleSave"
          >
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
          <span class="text-sm text-foreground">{{ row.titleTemplate }}</span>
        </template>

        <!-- 正文模板列 -->
        <template #body_cell="{ row }">
          <span
            v-if="row.bodyTemplate"
            class="line-clamp-2 text-xs text-muted-foreground"
          >
            {{ row.bodyTemplate }}
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

        <template #scope_cell="{ row }">
          <Tag color="blue">{{ getScopeLabel(row.scope) }}</Tag>
        </template>

        <template #tenant_cell="{ row }">
          <span v-if="row.tenantName" class="text-xs text-foreground">
            {{ row.tenantName }}
          </span>
          <Tag v-else color="default" class="!m-0">
            {{ $t('admin.system.notificationTemplate.platformDefault') }}
          </Tag>
        </template>

        <template #plugin_cell="{ row }">
          <Tag v-if="row.pluginName" color="purple" class="!m-0">
            {{ row.pluginName }}
          </Tag>
          <span v-else class="text-xs text-muted-foreground">
            {{ $t('admin.system.notificationTemplate.noPlugin') }}
          </span>
        </template>

        <template #source_cell="{ row }">
          <span class="text-xs text-muted-foreground">
            {{ getSourceLabel(row.source) }}
          </span>
        </template>

        <template #override_cell="{ row }">
          <Tag :color="row.isOverride ? 'orange' : 'default'">
            {{ getOverrideLabel(row.isOverride) }}
          </Tag>
        </template>

        <template #enabled_cell="{ row }">
          <Tag :color="row.enabled ? 'green' : 'red'">
            {{
              row.enabled
                ? $t('admin.system.notificationTemplate.enabled')
                : $t('admin.system.notificationTemplate.disabled')
            }}
          </Tag>
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
          <Tag :color="row.isSystem ? 'blue' : 'default'">
            {{
              row.isSystem
                ? $t('admin.system.notificationTemplate.systemBuiltin')
                : $t('admin.system.notificationTemplate.custom')
            }}
          </Tag>
        </template>
      </Grid>
    </Card>

    <Drawer
      v-model:open="previewOpen"
      :title="$t('admin.system.notificationTemplate.previewTitle')"
      width="560"
    >
      <div class="flex flex-col gap-4">
        <Card>
          <Descriptions :column="1" size="small">
            <Descriptions.Item
              :label="$t('admin.system.notificationTemplate.code')"
            >
              {{ previewRecord?.code || '-' }}
            </Descriptions.Item>
            <Descriptions.Item
              :label="$t('admin.system.notificationTemplate.scope')"
            >
              {{ getScopeLabel(previewRecord?.scope) }}
            </Descriptions.Item>
            <Descriptions.Item
              :label="$t('admin.system.notificationTemplate.tenant')"
            >
              {{
                previewRecord?.tenantName ||
                $t('admin.system.notificationTemplate.platformDefault')
              }}
            </Descriptions.Item>
            <Descriptions.Item
              :label="$t('admin.system.notificationTemplate.plugin')"
            >
              {{
                previewRecord?.pluginName ||
                $t('admin.system.notificationTemplate.noPlugin')
              }}
            </Descriptions.Item>
            <Descriptions.Item
              :label="$t('admin.system.notificationTemplate.source')"
            >
              {{ getSourceLabel(previewRecord?.source) }}
            </Descriptions.Item>
            <Descriptions.Item
              :label="$t('admin.system.notificationTemplate.override')"
            >
              {{ getOverrideLabel(previewRecord?.isOverride || false) }}
            </Descriptions.Item>
            <Descriptions.Item
              :label="$t('admin.system.notificationTemplate.lockedFields')"
            >
              <div
                v-if="previewRecord?.lockedFields.length"
                class="flex flex-wrap gap-1"
              >
                <Tag
                  v-for="label in getLockedFieldLabels(
                    previewRecord?.lockedFields,
                  )"
                  :key="label"
                  color="orange"
                >
                  {{ label }}
                </Tag>
              </div>
              <span v-else>-</span>
            </Descriptions.Item>
            <Descriptions.Item
              :label="$t('admin.system.notificationTemplate.enabled')"
            >
              {{
                previewRecord?.enabled
                  ? $t('admin.system.notificationTemplate.enabled')
                  : $t('admin.system.notificationTemplate.disabled')
              }}
            </Descriptions.Item>
          </Descriptions>
        </Card>

        <Card :loading="previewLoading">
          <div
            class="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400"
          >
            {{ $t('admin.system.notificationTemplate.previewEffective') }}
          </div>
          <div class="mt-3 text-sm font-medium text-slate-900">
            {{ previewData?.titleTemplate || '-' }}
          </div>
          <div
            class="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-600"
          >
            {{ previewData?.bodyTemplate || '-' }}
          </div>
        </Card>
      </div>
    </Drawer>
  </Page>
</template>
