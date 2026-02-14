<script setup lang="ts">
/**
 * ListPreview — 根据 CrudConfig 实时渲染列表预览
 *
 * 支持布局: standard / card_list / tree_table / kanban / timeline / master_detail
 * 支持列渲染预设: tag/switch/money/percent/relative_time/datetime/date/avatar/image/link/copy/progress/badge/icon/color
 */
import { computed, ref } from 'vue';

import {
  Avatar,
  Badge,
  Button,
  Card,
  Empty,
  Input,
  Pagination,
  Progress,
  Space,
  Switch,
  Table,
  Tag,
  Timeline,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { CrudConfig, FieldConfig, ListRenderPreset } from '../types';

/**
 * Locale-aware field label: uses label_en when current UI is English.
 * Falls back to label_zh → field.name.
 */
function fieldLabel(field: FieldConfig): string {
  const isEn = $t('common.locale') === 'en-US';
  if (isEn && field.label_en) return field.label_en;
  return field.label_zh || field.name;
}

function enumLabel(opt: { label_zh: string; label_en?: string }): string {
  const isEn = $t('common.locale') === 'en-US';
  if (isEn && opt.label_en) return opt.label_en;
  return opt.label_zh;
}

import type { MockDataRow } from '../composables/use-mock-data';

const T = 'admin.dev.crudGenerator';

const props = defineProps<{
  config: CrudConfig;
  data: MockDataRow[];
}>();

const emit = defineEmits<{
  (e: 'edit', row: MockDataRow): void;
  (e: 'create'): void;
}>();

// ============================================================
// Pagination
// ============================================================

const currentPage = ref(1);
const pageSize = ref(10);

const pagedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  return props.data.slice(start, start + pageSize.value);
});

// ============================================================
// Columns
// ============================================================

const listFields = computed(() =>
  props.config.fields.filter((f) => f.in_list),
);

const columns = computed(() => {
  const cols: Record<string, unknown>[] = [];

  // Index column
  if (props.config.list_config.show_index) {
    cols.push({
      title: '#',
      key: '_index',
      width: 60,
      align: 'center',
      customRender: ({ index }: { index: number }) =>
        (currentPage.value - 1) * pageSize.value + index + 1,
    });
  }

  // Field columns
  for (const field of listFields.value) {
    cols.push({
      title: fieldLabel(field),
      dataIndex: field.name,
      key: field.name,
      width: field.list_width ?? undefined,
      align: field.list_align || 'left',
      fixed: field.list_fixed ?? undefined,
      sorter: field.list_sortable,
      ellipsis: true,
    });
  }

  // Operations column
  if (props.config.operations.length > 0) {
    cols.push({
      title: $t(`${T}.listPreview.operations`),
      key: '_operations',
      width: 150,
      align: 'center',
      fixed: 'right',
    });
  }

  return cols;
});

// ============================================================
// Layout helpers
// ============================================================

const layoutVariant = computed(() => props.config.layout.variant);
const isStandardTable = computed(() =>
  layoutVariant.value === 'standard' || layoutVariant.value === 'master_detail',
);
const isCardList = computed(() => layoutVariant.value === 'card_list');
const isKanban = computed(() => layoutVariant.value === 'kanban');
const isTimeline = computed(() => layoutVariant.value === 'timeline');

// ============================================================
// Render preset helpers
// ============================================================

function getPreset(field: FieldConfig): ListRenderPreset | null {
  return field.list_render ?? null;
}

function getEnumLabel(fieldName: string, value: unknown): string {
  for (const field of props.config.fields) {
    if (field.name === fieldName && field.enum_ref) {
      const enumDef = props.config.enums.find((e) => e.name === field.enum_ref);
      if (enumDef) {
        const opt = enumDef.values.find((v) => v.value === value);
        const isEn = $t('common.locale') === 'en-US';
        if (opt) return (isEn && opt.label_en) ? opt.label_en : opt.label_zh;
      }
    }
  }
  return String(value ?? '');
}

function getEnumColor(fieldName: string, value: unknown): string {
  for (const field of props.config.fields) {
    if (field.name === fieldName && field.enum_ref) {
      const enumDef = props.config.enums.find((e) => e.name === field.enum_ref);
      if (enumDef) {
        const opt = enumDef.values.find((v) => v.value === value);
        if (opt?.color) return opt.color;
      }
    }
  }
  return 'default';
}

function formatMoney(val: unknown): string {
  const num = Number(val);
  if (Number.isNaN(num)) return String(val ?? '');
  return `¥ ${num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatPercent(val: unknown): string {
  const num = Number(val);
  if (Number.isNaN(num)) return String(val ?? '');
  return `${num.toFixed(1)}%`;
}

function formatRelativeTime(val: unknown): string {
  if (!val) return '-';
  const date = new Date(String(val));
  const now = Date.now();
  const diff = now - date.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return '刚刚';
  if (mins < 60) return `${mins} 分钟前`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} 天前`;
  return String(val).slice(0, 10);
}

function formatDatetime(val: unknown): string {
  if (!val) return '-';
  return String(val).slice(0, 19);
}

function formatDate(val: unknown): string {
  if (!val) return '-';
  return String(val).slice(0, 10);
}

// Kanban grouping
const kanbanGroups = computed(() => {
  const groupField = props.config.layout.kanban_group_field;
  if (!groupField) return [];

  const field = props.config.fields.find((f) => f.name === groupField);
  if (!field?.enum_ref) return [];

  const enumDef = props.config.enums.find((e) => e.name === field.enum_ref);
  if (!enumDef) return [];

  return enumDef.values.map((opt) => ({
    value: opt.value,
    label: enumLabel(opt),
    color: opt.color ?? 'default',
    items: props.data.filter(
      (row) => row[groupField] === opt.value,
    ),
  }));
});

// Timeline date field
const timelineDateField = computed(
  () => props.config.layout.timeline_date_field || 'created_at',
);

// Card display fields
const cardFields = computed(() => {
  const cfgFields = props.config.layout.card_fields;
  if (cfgFields && cfgFields.length > 0) {
    return props.config.fields.filter((f) => cfgFields.includes(f.name));
  }
  return listFields.value.slice(0, 4);
});

const cardCoverField = computed(() => props.config.layout.card_cover_field);
const cardColumns = computed(() => props.config.layout.card_columns || 3);
</script>

<template>
  <div class="list-preview">
    <!-- Empty state -->
    <Empty
      v-if="listFields.length === 0"
      :description="$t(`${T}.listPreview.noFields`)"
      class="py-16"
    />

    <template v-else>
      <!-- Toolbar -->
      <div class="mb-3 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <Button type="primary" size="small" @click="emit('create')">
            <template #icon>
              <span class="icon-[lucide--plus] size-3.5" />
            </template>
            {{ $t(`${T}.listPreview.create`) }}
          </Button>
          <Button v-if="config.import_export?.enable_import" size="small">
            <template #icon>
              <span class="icon-[lucide--upload] size-3.5" />
            </template>
            {{ $t(`${T}.listPreview.import`) }}
          </Button>
          <Button v-if="config.import_export?.enable_export" size="small">
            <template #icon>
              <span class="icon-[lucide--download] size-3.5" />
            </template>
            {{ $t(`${T}.listPreview.export`) }}
          </Button>
        </div>

        <div class="flex items-center gap-2">
          <Input.Search
            v-if="config.list_config.toolbar_search"
            :placeholder="$t(`${T}.listPreview.search`)"
            size="small"
            style="width: 200px"
            allow-clear
          />
        </div>
      </div>

      <!-- ==================== Standard Table ==================== -->
      <Table
        v-if="isStandardTable"
        :columns="columns"
        :data-source="pagedData"
        :pagination="false"
        :row-selection="config.list_config.show_checkbox ? { type: 'checkbox' } : undefined"
        :scroll="{ x: 'max-content' }"
        :stripe="config.list_config.stripe"
        bordered
        row-key="id"
        size="small"
      >
        <!-- Dynamic column slots -->
        <template #bodyCell="{ column, record, text }">
          <!-- Operations column -->
          <template v-if="column.key === '_operations'">
            <Space :size="4">
              <Button
                v-if="config.operations.includes('edit')"
                size="small"
                type="link"
                @click="emit('edit', record as MockDataRow)"
              >
                {{ $t(`${T}.listPreview.edit`) }}
              </Button>
              <Button
                v-if="config.operations.includes('delete')"
                danger
                size="small"
                type="link"
              >
                {{ $t(`${T}.listPreview.delete`) }}
              </Button>
            </Space>
          </template>

          <!-- Render presets for field columns -->
          <template v-else>
            <template v-for="field in listFields" :key="field.name">
              <template v-if="column.dataIndex === field.name">
                <!-- tag -->
                <Tag v-if="getPreset(field) === 'tag'" :color="getEnumColor(field.name, text)">
                  {{ getEnumLabel(field.name, text) }}
                </Tag>

                <!-- badge -->
                <Badge v-else-if="getPreset(field) === 'badge'" :color="getEnumColor(field.name, text)" :text="getEnumLabel(field.name, text)" />

                <!-- switch -->
                <Switch v-else-if="getPreset(field) === 'switch'" :checked="!!text" size="small" />

                <!-- money -->
                <span v-else-if="getPreset(field) === 'money'" class="font-mono tabular-nums">
                  {{ formatMoney(text) }}
                </span>

                <!-- percent -->
                <span v-else-if="getPreset(field) === 'percent'" class="tabular-nums">
                  {{ formatPercent(text) }}
                </span>

                <!-- progress -->
                <Progress
                  v-else-if="getPreset(field) === 'progress'"
                  :percent="Number(text) || 0"
                  :show-info="false"
                  size="small"
                  style="width: 80px"
                />

                <!-- relative_time -->
                <Tooltip v-else-if="getPreset(field) === 'relative_time'" :title="formatDatetime(text)">
                  <span class="text-muted-foreground text-xs">{{ formatRelativeTime(text) }}</span>
                </Tooltip>

                <!-- datetime -->
                <span v-else-if="getPreset(field) === 'datetime'" class="text-muted-foreground text-xs tabular-nums">
                  {{ formatDatetime(text) }}
                </span>

                <!-- date -->
                <span v-else-if="getPreset(field) === 'date'" class="text-muted-foreground text-xs tabular-nums">
                  {{ formatDate(text) }}
                </span>

                <!-- avatar -->
                <div v-else-if="getPreset(field) === 'avatar'" class="flex items-center gap-2">
                  <Avatar :size="24" :src="typeof text === 'string' ? text : undefined">
                    {{ typeof text === 'string' ? text.charAt(0).toUpperCase() : '?' }}
                  </Avatar>
                </div>

                <!-- image -->
                <img
                  v-else-if="getPreset(field) === 'image'"
                  :src="String(text || '')"
                  alt=""
                  class="h-8 w-8 rounded object-cover"
                />

                <!-- link -->
                <a
                  v-else-if="getPreset(field) === 'link'"
                  :href="String(text || '#')"
                  class="text-primary truncate"
                  target="_blank"
                >
                  {{ text }}
                </a>

                <!-- copy -->
                <div v-else-if="getPreset(field) === 'copy'" class="flex items-center gap-1">
                  <span class="truncate">{{ text }}</span>
                  <Tooltip :title="$t(`${T}.preview.copyCode`)">
                    <span class="icon-[lucide--copy] text-muted-foreground size-3 cursor-pointer" />
                  </Tooltip>
                </div>

                <!-- icon -->
                <span v-else-if="getPreset(field) === 'icon'" class="text-lg">
                  {{ text }}
                </span>

                <!-- color -->
                <div v-else-if="getPreset(field) === 'color'" class="flex items-center gap-2">
                  <span
                    :style="{ backgroundColor: String(text || '#ccc') }"
                    class="inline-block size-4 rounded border"
                  />
                  <span class="font-mono text-xs">{{ text }}</span>
                </div>

                <!-- ellipsis (default for text/no preset) -->
                <span v-else-if="getPreset(field) === 'ellipsis'" class="truncate">
                  {{ text }}
                </span>

                <!-- enum with no preset — auto tag -->
                <Tag v-else-if="field.type === 'enum'" :color="getEnumColor(field.name, text)">
                  {{ getEnumLabel(field.name, text) }}
                </Tag>

                <!-- boolean with no preset — auto switch -->
                <Switch v-else-if="field.type === 'boolean'" :checked="!!text" disabled size="small" />

                <!-- default -->
                <span v-else class="truncate">{{ text ?? '-' }}</span>
              </template>
            </template>
          </template>
        </template>
      </Table>

      <!-- ==================== Card List ==================== -->
      <div
        v-else-if="isCardList"
        :style="{ gridTemplateColumns: `repeat(${cardColumns}, 1fr)` }"
        class="grid gap-4"
      >
        <Card
          v-for="row in pagedData"
          :key="row.id"
          :hoverable="true"
          size="small"
          class="cursor-pointer"
          @click="emit('edit', row)"
        >
          <template v-if="cardCoverField" #cover>
            <img
              :src="String(row[cardCoverField] || '')"
              alt=""
              class="h-32 w-full object-cover"
            />
          </template>
          <div class="space-y-1">
            <div
              v-for="field in cardFields"
              :key="field.name"
              class="flex items-center justify-between text-sm"
            >
              <span class="text-muted-foreground">{{ fieldLabel(field) }}</span>
              <span class="truncate max-w-[60%] text-right">
                <Tag v-if="field.type === 'enum'" :color="getEnumColor(field.name, row[field.name])" class="m-0">
                  {{ getEnumLabel(field.name, row[field.name]) }}
                </Tag>
                <span v-else>{{ row[field.name] ?? '-' }}</span>
              </span>
            </div>
          </div>
        </Card>
      </div>

      <!-- ==================== Kanban ==================== -->
      <div v-else-if="isKanban" class="flex gap-4 overflow-x-auto pb-2">
        <div
          v-for="group in kanbanGroups"
          :key="group.value"
          class="bg-accent/30 min-w-[260px] flex-shrink-0 rounded-lg p-3"
        >
          <div class="mb-3 flex items-center gap-2">
            <Tag :color="group.color" class="m-0">{{ group.label }}</Tag>
            <span class="text-muted-foreground text-xs">{{ group.items.length }}</span>
          </div>
          <div class="space-y-2">
            <Card
              v-for="row in group.items.slice(0, 5)"
              :key="row.id"
              size="small"
              class="cursor-pointer"
              @click="emit('edit', row)"
            >
              <div class="text-sm">
                <div v-for="field in cardFields.slice(0, 2)" :key="field.name" class="truncate">
                  {{ row[field.name] ?? '-' }}
                </div>
              </div>
            </Card>
            <div v-if="group.items.length > 5" class="text-muted-foreground text-center text-xs">
              +{{ group.items.length - 5 }}
            </div>
          </div>
        </div>
      </div>

      <!-- ==================== Timeline ==================== -->
      <div v-else-if="isTimeline" class="max-h-[500px] overflow-auto px-4">
        <Timeline>
          <Timeline.Item
            v-for="row in pagedData"
            :key="row.id"
          >
            <div class="cursor-pointer" @click="emit('edit', row)">
              <div class="text-muted-foreground mb-1 text-xs">
                {{ row[timelineDateField] ?? '-' }}
              </div>
              <div class="text-sm">
                <span v-for="(field, idx) in cardFields.slice(0, 3)" :key="field.name">
                  <span v-if="idx > 0" class="mx-1 text-muted-foreground">·</span>
                  {{ row[field.name] ?? '-' }}
                </span>
              </div>
            </div>
          </Timeline.Item>
        </Timeline>
      </div>

      <!-- Pagination -->
      <div v-if="config.list_config.pager" class="mt-3 flex items-center justify-end">
        <Pagination
          v-model:current="currentPage"
          v-model:page-size="pageSize"
          :page-size-options="['10', '20', '50']"
          :show-size-changer="true"
          :show-total="(total: number) => $t(`${T}.listPreview.total`, { total })"
          :total="data.length"
          size="small"
        />
      </div>
    </template>
  </div>
</template>
