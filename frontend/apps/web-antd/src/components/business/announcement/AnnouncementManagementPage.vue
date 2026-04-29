<script lang="ts" setup>
import type { TableColumnsType, TablePaginationConfig } from 'ant-design-vue';

import type {
  AnnouncementAnswers,
  AnnouncementDelivery,
  AnnouncementInfo,
  AnnouncementManagementApi,
  AnnouncementPayload,
  AnnouncementPriority,
} from '#/types/announcement';

import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Card,
  Descriptions,
  Input,
  message,
  Modal,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'ant-design-vue';

import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import AnnouncementAnswerForm from './AnnouncementAnswerForm.vue';
import AnnouncementFormEditor from './AnnouncementFormEditor.vue';

defineOptions({ name: 'AnnouncementManagementPage' });

const props = defineProps<{
  accessPrefix?: string;
  api: AnnouncementManagementApi;
  i18nPrefix: string;
}>();

const route = useRoute();

const accessPrefix = computed(() => props.accessPrefix ?? 'announcement');
const createAccess = computed(() => [`${accessPrefix.value}:create`]);
const updateAccess = computed(() => [`${accessPrefix.value}:update`]);
const deleteAccess = computed(() => [`${accessPrefix.value}:delete`]);
const readAccess = computed(() => [`${accessPrefix.value}:list`]);

const items = ref<AnnouncementInfo[]>([]);
const loading = ref(false);
const currentPage = ref(1);
const pageSize = ref(20);
const total = ref(0);
const searchKeyword = ref('');

const editorOpen = ref(false);
const editorSaving = ref(false);
const editingId = ref<null | number>(null);
const editingStatus = ref<AnnouncementInfo['status']>('draft');
const formModel = ref<AnnouncementPayload>(createDefaultPayload());

const detailOpen = ref(false);
const detailLoading = ref(false);
const detailItem = ref<AnnouncementInfo | null>(null);
const readonlyAnswers = ref<AnnouncementAnswers>({});
const lastQueryDetailId = ref<null | number>(null);

const responsesOpen = ref(false);
const responsesLoading = ref(false);
const responses = ref<AnnouncementDelivery[]>([]);

const columns = computed<TableColumnsType<AnnouncementInfo>>(() => [
  {
    dataIndex: 'title',
    key: 'title',
    title: $t('common.announcement.title'),
  },
  {
    dataIndex: 'status',
    key: 'status',
    title: $t('common.status'),
    width: 120,
  },
  {
    dataIndex: 'priority',
    key: 'priority',
    title: $t('common.announcement.priorityLabel'),
    width: 120,
  },
  {
    dataIndex: 'requireResponse',
    key: 'requireResponse',
    title: $t('common.announcement.requireResponse'),
    width: 130,
  },
  {
    dataIndex: 'recipientCount',
    key: 'recipientCount',
    title: $t('common.announcement.recipientCount'),
    width: 120,
  },
  {
    dataIndex: 'responseCount',
    key: 'responseCount',
    title: $t('common.announcement.responseCount'),
    width: 120,
  },
  {
    dataIndex: 'publishedAt',
    key: 'publishedAt',
    title: $t('common.announcement.publishedAt'),
    width: 180,
  },
  {
    key: 'operation',
    title: $t('common.operation'),
    width: 280,
  },
]);

const responseColumns = computed<TableColumnsType<AnnouncementDelivery>>(() => [
  {
    dataIndex: 'recipientType',
    key: 'recipientType',
    title: $t('common.announcement.recipientType'),
    width: 140,
  },
  {
    dataIndex: 'recipientId',
    key: 'recipientId',
    title: $t('common.announcement.recipientId'),
    width: 120,
  },
  {
    dataIndex: 'status',
    key: 'status',
    title: $t('common.status'),
    width: 120,
  },
  {
    dataIndex: 'submittedAt',
    key: 'submittedAt',
    title: $t('common.announcement.submittedAt'),
    width: 180,
  },
  {
    dataIndex: 'answers',
    key: 'answers',
    title: $t('common.announcement.answers'),
  },
]);

const pagination = computed<TablePaginationConfig>(() => ({
  current: currentPage.value,
  pageSize: pageSize.value,
  showSizeChanger: true,
  showTotal: (count) => $t('common.totalCount', { count }),
  total: total.value,
}));

function createDefaultPayload(): AnnouncementPayload {
  return {
    content: '',
    form_schema: [],
    priority: 'normal',
    require_response: false,
    sort_order: 0,
    title: '',
  };
}

function toPayload(item: AnnouncementInfo): AnnouncementPayload {
  return {
    content: item.content ?? '',
    form_schema: item.formSchema,
    priority: item.priority as AnnouncementPriority,
    require_response: item.requireResponse,
    sort_order: item.sortOrder,
    title: item.title,
  };
}

function statusColor(status: string): string {
  if (status === 'published') {
    return 'green';
  }
  return 'default';
}

function priorityColor(priority: string): string {
  const map: Record<string, string> = {
    high: 'orange',
    low: 'default',
    normal: 'blue',
    urgent: 'red',
  };
  return map[priority] ?? 'default';
}

function buildListParams(): Record<string, unknown> {
  const params: Record<string, unknown> = {
    'page[number]': currentPage.value,
    'page[size]': pageSize.value,
    sort: '-created_at',
  };
  const keyword = searchKeyword.value.trim();
  if (keyword) {
    params['filter[title][ilike]'] = keyword;
  }
  return params;
}

async function loadList() {
  loading.value = true;
  try {
    const response = await props.api.list(buildListParams());
    items.value = response.items;
    total.value = response.total;
  } finally {
    loading.value = false;
  }
}

function handleTableChange(pager: TablePaginationConfig) {
  currentPage.value = pager.current ?? 1;
  pageSize.value = pager.pageSize ?? pageSize.value;
  void loadList();
}

function openCreate() {
  editingId.value = null;
  editingStatus.value = 'draft';
  formModel.value = createDefaultPayload();
  editorOpen.value = true;
}

function openEdit(item: AnnouncementInfo) {
  editingId.value = item.id;
  editingStatus.value = item.status;
  formModel.value = toPayload(item);
  editorOpen.value = true;
}

async function saveDraft() {
  if (!formModel.value.title.trim()) {
    message.warning($t('common.announcement.titleRequired'));
    return;
  }
  if (
    formModel.value.require_response &&
    formModel.value.form_schema.length === 0
  ) {
    message.warning($t('common.announcement.formSchemaRequired'));
    return;
  }

  editorSaving.value = true;
  try {
    await (editingId.value
      ? props.api.update(editingId.value, formModel.value)
      : props.api.create(formModel.value));
    message.success($t('common.saveSuccess'));
    editorOpen.value = false;
    await loadList();
  } finally {
    editorSaving.value = false;
  }
}

function confirmPublish(item: AnnouncementInfo) {
  Modal.confirm({
    content: $t('common.announcement.publishConfirmContent', {
      title: item.title,
    }),
    okText: $t('common.announcement.publish'),
    onOk: async () => {
      await props.api.publish(item.id);
      message.success($t('common.announcement.publishSuccess'));
      await loadList();
    },
    title: $t('common.announcement.publishConfirmTitle'),
  });
}

function confirmDelete(item: AnnouncementInfo) {
  Modal.confirm({
    content: $t('common.deleteConfirm', { name: item.title }),
    okText: $t('common.delete'),
    okType: 'danger',
    onOk: async () => {
      await props.api.delete(item.id);
      message.success($t('common.deleteSuccess'));
      await loadList();
    },
    title: $t('common.deleteTitle'),
  });
}

async function openDetail(itemOrId: AnnouncementInfo | number) {
  detailOpen.value = true;
  detailLoading.value = true;
  try {
    detailItem.value =
      typeof itemOrId === 'number' ? await props.api.get(itemOrId) : itemOrId;
    readonlyAnswers.value = {};
  } finally {
    detailLoading.value = false;
  }
}

async function openResponses(item: AnnouncementInfo) {
  responsesOpen.value = true;
  responsesLoading.value = true;
  try {
    responses.value = await props.api.getResponses(item.id);
  } finally {
    responsesLoading.value = false;
  }
}

function onSearch() {
  currentPage.value = 1;
  void loadList();
}

function onResetSearch() {
  searchKeyword.value = '';
  currentPage.value = 1;
  void loadList();
}

function formatAnswers(answers: null | Record<string, unknown> | undefined) {
  if (!answers) {
    return '-';
  }
  return JSON.stringify(answers, null, 2);
}

function resolveAnnouncementRecord(record: unknown): AnnouncementInfo | null {
  if (!record || typeof record !== 'object') {
    return null;
  }
  const candidate = record as Partial<AnnouncementInfo>;
  if (typeof candidate.id !== 'number' || typeof candidate.title !== 'string') {
    return null;
  }
  return candidate as AnnouncementInfo;
}

function openDetailRecord(record: unknown) {
  const item = resolveAnnouncementRecord(record);
  if (item) {
    void openDetail(item);
  }
}

function openEditRecord(record: unknown) {
  const item = resolveAnnouncementRecord(record);
  if (item) {
    openEdit(item);
  }
}

function confirmPublishRecord(record: unknown) {
  const item = resolveAnnouncementRecord(record);
  if (item) {
    confirmPublish(item);
  }
}

function confirmDeleteRecord(record: unknown) {
  const item = resolveAnnouncementRecord(record);
  if (item) {
    confirmDelete(item);
  }
}

function openResponsesRecord(record: unknown) {
  const item = resolveAnnouncementRecord(record);
  if (item) {
    void openResponses(item);
  }
}

watch(
  () => route.query.announcement_id,
  (value) => {
    const id = Number(value);
    if (!Number.isFinite(id) || id <= 0 || lastQueryDetailId.value === id) {
      return;
    }
    lastQueryDetailId.value = id;
    void openDetail(id);
  },
  { immediate: true },
);

onMounted(loadList);
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <Card :body-style="{ padding: '16px' }">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 class="m-0 text-lg font-semibold">
            {{ $t(`${i18nPrefix}.title`) }}
          </h2>
          <p class="m-0 mt-1 text-sm text-muted-foreground">
            {{ $t(`${i18nPrefix}.subtitle`) }}
          </p>
        </div>
        <Space wrap>
          <Input.Search
            v-model:value="searchKeyword"
            :placeholder="$t('common.announcement.searchPlaceholder')"
            allow-clear
            class="w-[260px]"
            @search="onSearch"
          />
          <Button @click="onResetSearch">
            <template #icon>
              <IconifyIcon icon="lucide:rotate-ccw" class="size-4" />
            </template>
            {{ $t('common.reset') }}
          </Button>
          <Button @click="loadList">
            <template #icon>
              <IconifyIcon icon="lucide:refresh-cw" class="size-4" />
            </template>
            {{ $t('common.refresh') }}
          </Button>
          <Button
            v-access:code="createAccess"
            type="primary"
            @click="openCreate"
          >
            <template #icon>
              <IconifyIcon icon="lucide:plus" class="size-4" />
            </template>
            {{ $t('common.announcement.createDraft') }}
          </Button>
        </Space>
      </div>
    </Card>

    <Card class="flex-1" :body-style="{ padding: '16px' }">
      <Table
        :columns="columns"
        :data-source="items"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        size="middle"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'title'">
            <Button type="link" class="px-0" @click="openDetailRecord(record)">
              {{ record.title }}
            </Button>
          </template>

          <template v-else-if="column.key === 'status'">
            <Tag :color="statusColor(record.status)">
              {{ $t(`common.announcement.status.${record.status}`) }}
            </Tag>
          </template>

          <template v-else-if="column.key === 'priority'">
            <Tag :color="priorityColor(record.priority)">
              {{ $t(`common.announcement.priority.${record.priority}`) }}
            </Tag>
          </template>

          <template v-else-if="column.key === 'requireResponse'">
            <Tag :color="record.requireResponse ? 'orange' : 'default'">
              {{ record.requireResponse ? $t('common.yes') : $t('common.no') }}
            </Tag>
          </template>

          <template v-else-if="column.key === 'publishedAt'">
            <Tooltip :title="formatDate(record.publishedAt)">
              <span>{{ formatDate(record.publishedAt) }}</span>
            </Tooltip>
          </template>

          <template v-else-if="column.key === 'operation'">
            <Space wrap>
              <Button
                size="small"
                type="link"
                @click="openDetailRecord(record)"
              >
                {{ $t('common.detail') }}
              </Button>
              <Button
                v-access:code="updateAccess"
                size="small"
                type="link"
                @click="openEditRecord(record)"
              >
                {{ $t('common.edit') }}
              </Button>
              <Button
                v-if="record.status === 'draft'"
                v-access:code="updateAccess"
                size="small"
                type="link"
                @click="confirmPublishRecord(record)"
              >
                {{ $t('common.announcement.publish') }}
              </Button>
              <Button
                v-access:code="readAccess"
                size="small"
                type="link"
                @click="openResponsesRecord(record)"
              >
                {{ $t('common.announcement.responses') }}
              </Button>
              <Button
                v-if="record.status === 'draft'"
                v-access:code="deleteAccess"
                danger
                size="small"
                type="link"
                @click="confirmDeleteRecord(record)"
              >
                {{ $t('common.delete') }}
              </Button>
            </Space>
          </template>
        </template>
      </Table>
    </Card>

    <Modal
      v-model:open="editorOpen"
      :title="
        editingId
          ? $t('common.announcement.editDraft')
          : $t('common.announcement.createDraft')
      "
      width="760px"
      centered
      destroy-on-close
    >
      <AnnouncementFormEditor
        v-model="formModel"
        :locked="editingStatus === 'published'"
      />
      <template #footer>
        <div class="flex justify-end gap-2">
          <Button @click="editorOpen = false">
            {{ $t('common.cancel') }}
          </Button>
          <Button
            v-access:code="editingId ? updateAccess : createAccess"
            :loading="editorSaving"
            type="primary"
            @click="saveDraft"
          >
            {{ $t('common.save') }}
          </Button>
        </div>
      </template>
    </Modal>

    <Modal
      v-model:open="detailOpen"
      :title="$t('common.announcement.detail')"
      width="680px"
      :footer="null"
      centered
      destroy-on-close
    >
      <div v-if="detailItem" class="space-y-5">
        <Descriptions :column="1" bordered size="small">
          <Descriptions.Item :label="$t('common.announcement.title')">
            {{ detailItem.title }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('common.status')">
            {{ $t(`common.announcement.status.${detailItem.status}`) }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('common.announcement.priorityLabel')">
            {{ $t(`common.announcement.priority.${detailItem.priority}`) }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('common.announcement.requireResponse')">
            {{
              detailItem.requireResponse ? $t('common.yes') : $t('common.no')
            }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('common.announcement.publishedAt')">
            {{ formatDate(detailItem.publishedAt) }}
          </Descriptions.Item>
        </Descriptions>

        <div>
          <h3 class="mb-2 text-base font-medium">
            {{ $t('common.announcement.content') }}
          </h3>
          <Typography.Paragraph class="whitespace-pre-wrap">
            {{ detailItem.content || '-' }}
          </Typography.Paragraph>
        </div>

        <div v-if="detailItem.requireResponse">
          <h3 class="mb-2 text-base font-medium">
            {{ $t('common.announcement.responseForm') }}
          </h3>
          <AnnouncementAnswerForm
            v-model="readonlyAnswers"
            :schema="detailItem.formSchema"
            readonly
          />
        </div>
      </div>
      <div v-else-if="detailLoading" class="py-8 text-center">
        {{ $t('common.loading') }}
      </div>
    </Modal>

    <Modal
      v-model:open="responsesOpen"
      :title="$t('common.announcement.responses')"
      width="860px"
      :footer="null"
      centered
      destroy-on-close
    >
      <Table
        :columns="responseColumns"
        :data-source="responses"
        :loading="responsesLoading"
        :pagination="false"
        row-key="id"
        size="small"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <Tag :color="record.status === 'submitted' ? 'green' : 'default'">
              {{ $t(`common.announcement.deliveryStatus.${record.status}`) }}
            </Tag>
          </template>
          <template v-else-if="column.key === 'submittedAt'">
            {{ formatDate(record.submittedAt) }}
          </template>
          <template v-else-if="column.key === 'answers'">
            <pre class="m-0 whitespace-pre-wrap text-xs">{{
              formatAnswers(record.answers)
            }}</pre>
          </template>
        </template>
      </Table>
    </Modal>
  </Page>
</template>
