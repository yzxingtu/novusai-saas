<script lang="ts" setup>
import type { NccField, NccRecord, NccTableSchema } from '../types';

import { computed, nextTick, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Checkbox,
  DatePicker,
  Empty,
  Input,
  InputNumber,
  Modal,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Textarea,
  message,
} from 'ant-design-vue';

import {
  aiChatApi,
  bulkDeleteRecordsApi,
  createRecordApi,
  deleteRecordApi,
  getSchemaApi,
  listRecordsApi,
  updateRecordApi,
} from '../api';
import { FIELD_TYPE_COLORS, t } from '../data';

defineOptions({ name: 'NccDataGrid' });

const route = useRoute();
const router = useRouter();

const projectId = ref(0);
const schemaId = ref(0);
const schema = ref<NccTableSchema | null>(null);
const records = ref<NccRecord[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(50);
const loading = ref(false);
const saving = ref(false);
const searchText = ref('');
const showEditModal = ref(false);
const editRecord = ref<Record<string, unknown>>({});
const editRecordId = ref<number | null>(null);
const selectedRowKeys = ref<number[]>([]);
const showAiPanel = ref(false);
const aiLoading = ref(false);
const aiMessage = ref('');
const aiFeature = ref<'analytics' | 'query' | 'write'>('query');
const aiHistory = ref<{ role: 'user' | 'ai'; text: string }[]>([]);
const aiMessagesRef = ref<HTMLElement | null>(null);

const fields = computed<NccField[]>(() => schema.value?.schema_config?.fields ?? []);

const tableColumns = computed(() => {
  return [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 70, fixed: 'left' as const, sorter: (a: Record<string, number>, b: Record<string, number>) => a.id - b.id },
    ...fields.value.map((f: NccField) => ({
      title: f.label || f.name,
      dataIndex: f.name,
      key: f.name,
      ellipsis: true,
      _fieldType: f.type,
    })),
    { title: t('common.actions'), key: 'actions', width: 110, fixed: 'right' as const },
  ];
});

const tableData = computed(() => {
  const raw = records.value.map((r) => ({ id: r.id, ...r.data, _record: r }));
  if (!searchText.value.trim()) return raw;
  const q = searchText.value.toLowerCase();
  return raw.filter((row) =>
    Object.entries(row).some(([k, v]) => k !== '_record' && v !== null && v !== undefined && String(v).toLowerCase().includes(q)),
  );
});

const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: number[]) => { selectedRowKeys.value = keys; },
}));

async function loadData() {
  projectId.value = Number(route.params.projectId) || 0;
  schemaId.value = Number(route.params.schemaId) || 0;
  if (!projectId.value || !schemaId.value) return;
  loading.value = true;
  try {
    const [s, r] = await Promise.all([
      getSchemaApi(projectId.value, schemaId.value),
      listRecordsApi(projectId.value, schemaId.value, currentPage.value, pageSize.value),
    ]);
    schema.value = s;
    records.value = r.items ?? [];
    total.value = r.total ?? 0;
  } catch {
    // handled
  } finally {
    loading.value = false;
  }
}

async function handlePageChange(p: number, ps: number) {
  currentPage.value = p;
  pageSize.value = ps;
  await loadData();
}

function goBack() {
  router.push(`/admin/plugins/novus-crud-code/projects/${projectId.value}`);
}

function openCreate() {
  editRecordId.value = null;
  editRecord.value = {};
  fields.value.forEach((f: NccField) => {
    editRecord.value[f.name] = f.default ?? (f.type === 'boolean' ? false : f.type === 'integer' ? 0 : '');
  });
  showEditModal.value = true;
}

function openEdit(record: NccRecord) {
  editRecordId.value = record.id;
  editRecord.value = { ...record.data };
  showEditModal.value = true;
}

async function saveRecord() {
  saving.value = true;
  try {
    if (editRecordId.value) {
      await updateRecordApi(projectId.value, schemaId.value, editRecordId.value, editRecord.value);
    } else {
      await createRecordApi(projectId.value, schemaId.value, editRecord.value);
    }
    showEditModal.value = false;
    await loadData();
  } catch {
    // handled
  } finally {
    saving.value = false;
  }
}

function confirmDelete(id: number) {
  Modal.confirm({
    title: t('record.confirmDelete'),
    okType: 'danger',
    okText: t('common.delete'),
    cancelText: t('common.cancel'),
    onOk: async () => {
      try {
        await deleteRecordApi(projectId.value, schemaId.value, id);
        message.success(t('common.delete'));
        await loadData();
      } catch {
        // handled
      }
    },
  });
}

function confirmBulkDelete() {
  Modal.confirm({
    title: t('record.confirmBulkDelete'),
    content: `${selectedRowKeys.value.length} ${t('record.total')}`,
    okType: 'danger',
    okText: t('common.delete'),
    cancelText: t('common.cancel'),
    onOk: async () => {
      try {
        await bulkDeleteRecordsApi(projectId.value, schemaId.value, selectedRowKeys.value);
        selectedRowKeys.value = [];
        message.success(t('common.delete'));
        await loadData();
      } catch {
        // handled
      }
    },
  });
}

function clearAiHistory() {
  aiHistory.value = [];
}

function scrollToBottom() {
  nextTick(() => {
    if (aiMessagesRef.value) {
      aiMessagesRef.value.scrollTop = aiMessagesRef.value.scrollHeight;
    }
  });
}

async function sendAiMessage() {
  if (!aiMessage.value.trim() || aiLoading.value) return;
  const msg = aiMessage.value.trim();
  aiHistory.value.push({ role: 'user', text: msg });
  aiMessage.value = '';
  scrollToBottom();
  aiLoading.value = true;
  try {
    const featureMap = { query: 'data_query', write: 'data_write', analytics: 'data_analytics' };
    const res = await aiChatApi(projectId.value, msg, featureMap[aiFeature.value]);
    aiHistory.value.push({ role: 'ai', text: res.reply || '' });
  } catch (e: unknown) {
    aiHistory.value.push({ role: 'ai', text: String(e) });
  } finally {
    aiLoading.value = false;
    scrollToBottom();
  }
}

onMounted(() => loadData());
</script>

<template>
  <div class="flex h-full flex-col overflow-hidden">
    <!-- Toolbar -->
    <div class="flex shrink-0 items-center gap-3 border-b bg-card px-5 py-2.5">
      <button
        class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        @click="goBack"
      >
        <IconifyIcon icon="lucide:arrow-left" class="h-3.5 w-3.5" />
        {{ t('record.backToProject') }}
      </button>
      <span class="text-border">|</span>
      <span class="inline-flex items-center gap-1.5 text-sm font-bold text-foreground">
        <IconifyIcon icon="lucide:table" class="h-4 w-4 text-primary" />
        {{ schema?.display_name || schema?.name || '...' }}
      </span>
      <span class="text-xs text-muted-foreground">{{ total }} {{ t('record.total') }}</span>
      <div class="ml-auto flex items-center gap-2">
        <Input
          v-model:value="searchText"
          :placeholder="t('record.search')"
          allow-clear
          size="small"
          class="w-48"
        >
          <template #prefix>
            <IconifyIcon icon="lucide:search" class="h-3.5 w-3.5 text-muted-foreground" />
          </template>
        </Input>
        <Button
          v-if="selectedRowKeys.length > 0"
          danger
          size="small"
          @click="confirmBulkDelete"
        >
          <template #icon><IconifyIcon icon="lucide:trash-2" /></template>
          {{ t('record.deleteSelected') }} ({{ selectedRowKeys.length }})
        </Button>
        <Button
          size="small"
          :type="showAiPanel ? 'primary' : 'default'"
          @click="showAiPanel = !showAiPanel"
        >
          <template #icon><IconifyIcon icon="lucide:bot" /></template>
          AI
        </Button>
        <Button type="primary" size="small" @click="openCreate">
          <template #icon><IconifyIcon icon="lucide:plus" /></template>
          {{ t('record.create') }}
        </Button>
      </div>
    </div>

    <!-- Main content area -->
    <div class="flex flex-1 overflow-hidden">
      <!-- Data Table -->
      <div class="flex min-w-0 flex-1 flex-col overflow-hidden">
        <Table
          :row-selection="rowSelection"
          :columns="tableColumns"
          :data-source="tableData"
          :loading="loading"
          :pagination="{
            current: currentPage,
            pageSize,
            total,
            showSizeChanger: true,
            size: 'small',
            showTotal: (t2: number) => `${t2} ${t('record.total')}`,
            onChange: handlePageChange,
          }"
          row-key="id"
          size="small"
          :scroll="{ x: 'max-content' }"
          class="flex-1"
        >
          <template #bodyCell="{ column, record, text }">
            <template v-if="column.key === 'actions'">
              <Space :size="4">
                <button
                  class="inline-flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary"
                  @click="openEdit((record as Record<string, unknown>)._record as NccRecord)"
                >
                  <IconifyIcon icon="lucide:pencil" class="h-3.5 w-3.5" />
                </button>
                <button
                  class="inline-flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                  @click="confirmDelete((record as Record<string, unknown>).id as number)"
                >
                  <IconifyIcon icon="lucide:trash-2" class="h-3.5 w-3.5" />
                </button>
              </Space>
            </template>
            <template v-else-if="(column as Record<string, unknown>)._fieldType === 'boolean'">
              <Tag :color="text ? 'success' : 'error'" class="!m-0">
                {{ text ? t('record.true') : t('record.false') }}
              </Tag>
            </template>
            <template v-else-if="(column as Record<string, unknown>)._fieldType === 'datetime'">
              <span class="text-xs text-muted-foreground">
                {{ text ? new Date(String(text)).toLocaleString() : '' }}
              </span>
            </template>
            <template v-else-if="(column as Record<string, unknown>)._fieldType === 'json'">
              <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px] text-foreground">
                {{ typeof text === 'object' ? JSON.stringify(text) : text }}
              </code>
            </template>
            <template v-else>{{ text }}</template>
          </template>

          <template #emptyText>
            <Empty :description="t('record.noData')" class="py-8">
              <Button type="primary" size="small" @click="openCreate">
                <template #icon><IconifyIcon icon="lucide:plus" /></template>
                {{ t('record.addFirst') }}
              </Button>
            </Empty>
          </template>
        </Table>
      </div>

      <!-- AI Chat Panel -->
      <div
        v-if="showAiPanel"
        class="flex w-[360px] shrink-0 flex-col overflow-hidden border-l bg-card"
      >
        <!-- AI Header -->
        <div class="flex items-center justify-between border-b px-4 py-2.5">
          <span class="inline-flex items-center gap-1.5 text-sm font-semibold text-foreground">
            <IconifyIcon icon="lucide:bot" class="h-4 w-4 text-primary" />
            {{ t('ai.title') }}
            <span class="ml-1 inline-flex items-center gap-1 rounded-full bg-success/10 px-1.5 py-0.5 text-[10px] font-medium text-success">
              <span class="h-1.5 w-1.5 rounded-full bg-success" />
              {{ t('ai.online') }}
            </span>
          </span>
          <div class="flex items-center gap-1">
            <button
              v-if="aiHistory.length > 0"
              class="inline-flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              :title="t('ai.clear')"
              @click="clearAiHistory"
            >
              <IconifyIcon icon="lucide:trash" class="h-3.5 w-3.5" />
            </button>
            <button
              class="inline-flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              @click="showAiPanel = false"
            >
              <IconifyIcon icon="lucide:x" class="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        <!-- Feature Tabs -->
        <div class="flex border-b bg-muted/30 px-2">
          <button
            v-for="feat in (['query', 'write', 'analytics'] as const)"
            :key="feat"
            class="flex-1 px-2 py-2 text-center text-xs font-medium transition-colors"
            :class="aiFeature === feat
              ? 'border-b-2 border-primary text-primary'
              : 'text-muted-foreground hover:text-foreground'"
            @click="aiFeature = feat"
          >
            <IconifyIcon
              :icon="feat === 'query' ? 'lucide:search' : feat === 'write' ? 'lucide:pen-line' : 'lucide:bar-chart-3'"
              class="mr-1 inline h-3 w-3"
            />
            {{ t(`ai.feature.${feat}`) }}
          </button>
        </div>

        <!-- Messages -->
        <div ref="aiMessagesRef" class="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto p-3">
          <!-- Welcome message -->
          <div v-if="aiHistory.length === 0" class="space-y-3 py-3">
            <div class="flex items-start gap-2.5">
              <div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                <IconifyIcon icon="lucide:bot" class="h-4 w-4 text-primary" />
              </div>
              <div class="rounded-xl rounded-bl-sm bg-muted px-3 py-2 text-sm leading-relaxed text-foreground">
                {{ t('ai.welcome') }}
              </div>
            </div>
            <div v-if="aiFeature === 'write'" class="mx-2 flex items-center gap-1.5 rounded-md bg-warning/10 px-3 py-2 text-xs text-warning">
              <IconifyIcon icon="lucide:alert-triangle" class="h-3.5 w-3.5 shrink-0" />
              {{ t('ai.writeWarning') }}
            </div>
          </div>

          <!-- Chat messages -->
          <div
            v-for="(msg, i) in aiHistory"
            :key="i"
            class="flex gap-2.5"
            :class="msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'"
          >
            <div class="flex h-6 w-6 shrink-0 items-center justify-center rounded-md" :class="msg.role === 'user' ? 'bg-primary/10' : 'bg-muted'">
              <IconifyIcon
                :icon="msg.role === 'user' ? 'lucide:user' : 'lucide:bot'"
                class="h-3.5 w-3.5"
                :class="msg.role === 'user' ? 'text-primary' : 'text-muted-foreground'"
              />
            </div>
            <div
              class="max-w-[80%] rounded-xl px-3 py-2 text-sm leading-relaxed"
              :class="msg.role === 'user'
                ? 'rounded-br-sm bg-primary text-primary-foreground'
                : 'rounded-bl-sm bg-muted text-foreground'"
            >
              <pre v-if="msg.role === 'ai'" class="whitespace-pre-wrap break-words font-sans">{{ msg.text }}</pre>
              <span v-else>{{ msg.text }}</span>
            </div>
          </div>

          <!-- Loading indicator -->
          <div v-if="aiLoading" class="flex gap-2.5">
            <div class="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-muted">
              <IconifyIcon icon="lucide:bot" class="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <div class="rounded-xl rounded-bl-sm bg-muted px-3 py-2.5 text-sm">
              <div class="flex gap-1">
                <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/50 [animation-delay:-0.3s]" />
                <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/50 [animation-delay:-0.15s]" />
                <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/50" />
              </div>
            </div>
          </div>
        </div>

        <!-- Input -->
        <div class="flex gap-1.5 border-t p-2.5">
          <Input
            v-model:value="aiMessage"
            :placeholder="t('ai.inputPlaceholder')"
            class="flex-1"
            size="small"
            @press-enter="sendAiMessage"
          />
          <Button type="primary" size="small" :loading="aiLoading" :disabled="!aiMessage.trim()" @click="sendAiMessage">
            <template #icon><IconifyIcon icon="lucide:send" /></template>
          </Button>
        </div>
      </div>
    </div>

    <!-- Create/Edit Modal -->
    <Modal
      v-model:open="showEditModal"
      :title="editRecordId ? t('record.edit') : t('record.create')"
      :confirm-loading="saving"
      :ok-text="t('common.save')"
      :cancel-text="t('common.cancel')"
      width="560px"
      @ok="saveRecord"
    >
      <div class="max-h-[60vh] space-y-4 overflow-y-auto pt-2">
        <div v-for="f in fields" :key="f.name" class="rounded-lg border bg-card p-3">
          <div class="mb-2 flex items-center justify-between">
            <span class="text-sm font-medium text-foreground">
              {{ f.label || f.name }}
              <span v-if="f.required" class="ml-0.5 text-destructive">*</span>
            </span>
            <span
              class="rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold"
              :class="FIELD_TYPE_COLORS[f.type] ?? 'bg-muted text-muted-foreground'"
            >{{ f.type }}</span>
          </div>
          <Textarea
            v-if="f.type === 'text'"
            v-model:value="(editRecord as Record<string, string>)[f.name]"
            :rows="3"
            :placeholder="f.label || f.name"
          />
          <div v-else-if="f.type === 'boolean'" class="flex items-center gap-2 py-1">
            <Switch v-model:checked="(editRecord as Record<string, boolean>)[f.name]" />
            <span class="text-sm text-muted-foreground">{{ f.label || f.name }}</span>
          </div>
          <InputNumber
            v-else-if="f.type === 'integer'"
            v-model:value="(editRecord as Record<string, number>)[f.name]"
            class="w-full"
            :placeholder="f.label || f.name"
          />
          <DatePicker
            v-else-if="f.type === 'datetime'"
            :value="undefined"
            show-time
            class="w-full"
            :placeholder="f.label || f.name"
            @change="(_: unknown, ds: string) => { editRecord[f.name] = ds; }"
          />
          <Textarea
            v-else-if="f.type === 'json'"
            :value="typeof editRecord[f.name] === 'object' ? JSON.stringify(editRecord[f.name], null, 2) : String(editRecord[f.name] ?? '{}')"
            :rows="4"
            class="font-mono text-xs"
            @change="(e: Event) => { try { editRecord[f.name] = JSON.parse((e.target as HTMLTextAreaElement).value); } catch { editRecord[f.name] = (e.target as HTMLTextAreaElement).value; } }"
          />
          <Input v-else v-model:value="(editRecord as Record<string, string>)[f.name]" :placeholder="f.label || f.name" />
        </div>
      </div>
    </Modal>
  </div>
</template>
