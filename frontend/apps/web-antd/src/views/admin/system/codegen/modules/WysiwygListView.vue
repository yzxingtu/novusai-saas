<script lang="ts" setup>
/**
 * WYSIWYG 列表页预览 / WYSIWYG List View
 *
 * 使用真实 useVbenVxeGrid + CrudGrid 渲染，与生成后的 CRUD 页面效果一致
 */

import type { VbenFormSchema } from '#/adapter/form';

import { computed, nextTick, watch } from 'vue';
import { Empty, Tag, Tooltip } from 'ant-design-vue';
import { IconifyIcon } from '@vben/icons';
import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';
import { useGridSearchFormOptions, useVbenVxeGrid } from '#/adapter/vxe-table';
import CrudGrid from '#/core/adapter/vxe-table/components/crud-grid.vue';
import { searchDateRange, searchInput } from '#/adapter/form';

import { getComponent, getFieldLabel, shouldHideInList } from './field-utils';
import { buildGridColumns, buildMockRows } from './preview-builders';
import { useConfigFeatures } from './useConfigFeatures';
import type { FieldRecord } from './preview-builders';

defineOptions({ name: 'WysiwygListView' });

const store = useCodegenBuilderStore();
const features = useConfigFeatures(store);
const displayNameStr = computed(() => String(features.displayName.value ?? ''));

const dataFields = computed(() => {
  const arr = (store.configJson.fields as FieldRecord[]) || [];
  return arr.filter((f) => f.type !== '__divider__' && !f.divider);
});

const searchFields = computed(() =>
  dataFields.value.filter(
    (f) => f.name && (f as Record<string, unknown>).filterable === true,
  ),
);

const listVisibleFields = computed(() =>
  dataFields.value.filter(
    (f) => f.list_visible !== false && !shouldHideInList(f),
  ),
);

/** 有 comment 的可见列，用于表格列头 Tooltip slot */
const columnsWithComment = computed(() =>
  listVisibleFields.value.filter((f) => f.name && f.comment),
);

const columns = computed(() =>
  buildGridColumns(dataFields.value, {
    hasBatchDelete: features.hasBatchDelete.value,
    hasDragSort: features.hasDragSort.value,
    hasDetail: features.hasDetail.value,
    hasClone: features.hasClone.value,
  }),
);

const mockData = computed(() => buildMockRows(dataFields.value, 3));

const hasVisibleColumns = computed(() =>
  dataFields.value.some(
    (f) => f.list_visible !== false && !shouldHideInList(f),
  ),
);

const previewBadges = computed(() => [
  {
    key: 'mode',
    label: features.isCardMode?.value
      ? $t('admin.system.codegen.frontend.card')
      : $t('admin.system.codegen.frontend.table'),
  },
  {
    key: 'visible',
    label: $t('admin.system.codegen.builder.previewVisibleColumns', {
      count: listVisibleFields.value.length,
    }),
  },
  {
    key: 'search',
    label: $t('admin.system.codegen.builder.previewSearchFields', {
      count: searchFields.value.length,
    }),
  },
  {
    key: 'page',
    label: $t('admin.system.codegen.builder.previewPageSize', {
      count: features.pageSize.value,
    }),
  },
]);

/** 用于在搜索配置/列变化时强制 CrudGrid 重新挂载，避免 proxy 与 setState 循环 */
const gridRemountKey = computed(
  () =>
    `${searchFields.value.length}-${listVisibleFields.value.length}-${columns.value.length}`,
);

/** 根据 filterable 字段构建搜索表单 schema */
function buildSearchSchema(fields: FieldRecord[]): VbenFormSchema[] {
  const schema: VbenFormSchema[] = [];
  for (const f of fields) {
    const name = String(f.name || '').trim();
    const label = getFieldLabel(f) || name;
    const form = (f.form as Record<string, unknown>) || {};
    const queryType = String(
      form.queryType || f.query_type || 'ilike',
    ).toLowerCase();
    const t = String(f.type || '').toLowerCase();

    if (queryType === 'between' || t.includes('date') || t.includes('time')) {
      schema.push(
        searchDateRange({
          field: name,
          label,
          showTime: t.includes('datetime'),
        }),
      );
    } else if (Array.isArray(f.enum_values) && f.enum_values.length > 0) {
      const opts = (
        f.enum_values as Array<{ value: unknown; label_zh?: string }>
      ).map((e) => ({
        label: e.label_zh ?? String(e.value),
        value: e.value,
      }));
      schema.push({
        component: 'Select',
        componentProps: {
          allowClear: true,
          class: 'w-full',
          options: opts,
          placeholder: label,
        },
        fieldName: `filter[${name}]`,
        label,
      });
    } else {
      schema.push(
        searchInput(name, label, {
          op: queryType === 'eq' ? 'eq' : 'ilike',
        }),
      );
    }
  }
  return schema;
}

const showSearchForm = computed(() => searchFields.value.length > 0);
const searchFormOptions = computed(() =>
  searchFields.value.length > 0
    ? useGridSearchFormOptions(buildSearchSchema(searchFields.value))
    : undefined,
);

const [Grid, gridApi] = useVbenVxeGrid({
  showSearchForm: showSearchForm.value,
  formOptions: searchFormOptions.value,
  gridOptions: {
    columns: columns.value,
    data: mockData.value,
    pagerConfig: { enabled: false },
    minHeight: 320,
    stripe: true,
    rowConfig: { keyField: 'id' },
    cellConfig: { height: 56 },
  },
});

watch(
  [showSearchForm, searchFormOptions],
  ([showSearch, options]) => {
    gridApi.setState({
      formOptions: options,
      showSearchForm: showSearch,
    });
  },
  { deep: true, immediate: true },
);

watch(
  [columns, mockData],
  () => {
    nextTick(() => {
      gridApi.setGridOptions({
        columns: columns.value,
        data: mockData.value,
      });
    });
  },
  { deep: true, flush: 'post' },
);

/** 获取 enum 项的 label */
function getEnumLabel(f: FieldRecord, value: unknown): string {
  const ev =
    (f.enum_values as Array<{
      value: unknown;
      label_zh?: string;
      label_en?: string;
    }>) || [];
  const item = ev.find((e) => String(e.value) === String(value));
  return (item?.label_zh || item?.label_en || String(value ?? '—')) as string;
}

/** 从文件路径提取文件名 */
function getFileName(val: unknown): string {
  if (val == null || val === '') return '—';
  const s = String(val);
  const idx = s.lastIndexOf('/');
  return idx >= 0 ? s.slice(idx + 1) : s;
}
</script>

<template>
  <div
    class="overflow-hidden rounded-[24px] border border-border/70 bg-card shadow-sm"
  >
    <div class="border-b border-border/50 px-5 py-4">
      <div class="flex flex-col gap-3">
        <div
          class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between"
        >
          <div class="min-w-0">
            <div
              class="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground"
            >
              {{ $t('admin.system.codegen.wysiwyg.listView') }}
            </div>
            <div class="mt-2 text-lg font-semibold text-foreground">
              {{
                $t('admin.system.codegen.wysiwyg.listTitle', {
                  name:
                    displayNameStr ||
                    $t('admin.system.codegen.wysiwyg.sampleData'),
                })
              }}
            </div>
            <div class="mt-1 text-sm leading-6 text-muted-foreground">
              {{ $t('admin.system.codegen.builder.previewListDesc') }}
            </div>
          </div>

          <div class="flex flex-wrap gap-2">
            <span
              v-for="item in previewBadges"
              :key="item.key"
              class="rounded-full border border-border/70 bg-muted/15 px-3 py-1 text-xs text-muted-foreground"
            >
              {{ item.label }}
            </span>
          </div>
        </div>

        <div class="flex flex-wrap gap-2">
          <span
            v-for="field in searchFields.slice(0, 6)"
            :key="String(field.__key || field.name || '')"
            class="bg-primary/8 rounded-full px-2.5 py-1 text-xs text-primary"
          >
            {{ getFieldLabel(field) }}
          </span>
          <span
            v-if="searchFields.length === 0"
            class="rounded-full border border-dashed border-border/80 px-2.5 py-1 text-xs text-muted-foreground"
          >
            {{ $t('admin.system.codegen.builder.previewNoSearchFields') }}
          </span>
        </div>
      </div>
    </div>

    <div
      v-if="features.isCardMode?.value && hasVisibleColumns"
      class="grid grid-cols-1 gap-3 bg-muted/10 p-5 sm:grid-cols-2 lg:grid-cols-3"
    >
      <div
        v-for="row in mockData"
        :key="String(row.id ?? '')"
        class="flex flex-col gap-3 rounded-[20px] border border-border/70 bg-background p-4 shadow-sm transition-shadow hover:shadow-md"
      >
        <div
          class="flex items-center justify-between gap-2 border-b border-border/50 pb-3"
        >
          <div class="text-sm font-medium text-foreground">#{{ row.id }}</div>
          <span
            class="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground"
          >
            {{ $t('admin.system.codegen.wysiwyg.sampleData') }}
          </span>
        </div>

        <div class="space-y-2 text-sm">
          <template
            v-for="f in listVisibleFields"
            :key="(f.__key as string) || (f.name as string) || ''"
          >
            <div v-if="f.name" class="flex justify-between gap-2">
              <Tooltip v-if="f.comment" :title="f.comment">
                <span class="shrink-0 text-muted-foreground">{{
                  getFieldLabel(f)
                }}</span>
              </Tooltip>
              <span v-else class="shrink-0 text-muted-foreground">{{
                getFieldLabel(f)
              }}</span>
              <span class="truncate text-right">
                <template
                  v-if="
                    getComponent(f) === 'switch' ||
                    String(f.type || '')
                      .toLowerCase()
                      .includes('boolean')
                  "
                >
                  <Tag :color="row[f.name as string] ? 'success' : 'default'">
                    {{
                      row[f.name as string]
                        ? $t('common.yes')
                        : $t('common.no')
                    }}
                  </Tag>
                </template>
                <template
                  v-else-if="
                    (Array.isArray(f.enum_values) &&
                      f.enum_values.length > 0) ||
                    f.dict_code
                  "
                >
                  <Tag color="processing">
                    {{ getEnumLabel(f, row[f.name as string]) }}
                  </Tag>
                </template>
                <template
                  v-else-if="
                    String(f.type || '')
                      .toLowerCase()
                      .includes('image')
                  "
                >
                  <div
                    class="inline-flex size-10 items-center justify-center overflow-hidden rounded border border-border/40 bg-muted/20"
                  >
                    <IconifyIcon
                      icon="lucide:image"
                      class="size-5 text-muted-foreground"
                    />
                  </div>
                </template>
                <template
                  v-else-if="
                    String(f.type || '')
                      .toLowerCase()
                      .includes('file')
                  "
                >
                  <span class="inline-flex items-center gap-1 text-xs">
                    <IconifyIcon icon="lucide:file" class="size-3.5" />
                    {{ getFileName(row[f.name as string]) }}
                  </span>
                </template>
                <template v-else>
                  {{ row[f.name as string] ?? '—' }}
                </template>
              </span>
            </div>
          </template>
        </div>
        <div
          class="mt-auto flex justify-end gap-1 border-t border-border/40 pt-3"
        >
          <Tooltip
            v-if="features.hasDetail?.value"
            :title="$t('admin.system.codegen.wysiwyg.cardPreviewOnly')"
          >
            <span
              role="link"
              tabindex="0"
              class="cursor-default text-xs text-primary opacity-75"
              >{{ $t('common.detail') }}</span
            >
          </Tooltip>
          <Tooltip :title="$t('admin.system.codegen.wysiwyg.cardPreviewOnly')">
            <span
              role="link"
              tabindex="0"
              class="cursor-default text-xs text-primary opacity-75"
              >{{ $t('common.edit') }}</span
            >
          </Tooltip>
          <Tooltip :title="$t('admin.system.codegen.wysiwyg.cardPreviewOnly')">
            <span
              role="link"
              tabindex="0"
              class="cursor-default text-xs text-destructive opacity-75"
              >{{ $t('common.delete') }}</span
            >
          </Tooltip>
        </div>
      </div>
    </div>

    <div v-else-if="hasVisibleColumns" class="bg-muted/10 p-5">
      <div
        class="overflow-hidden rounded-[20px] border border-border/70 bg-background"
      >
        <CrudGrid
          :key="gridRemountKey"
          :grid="Grid"
          :create-label="$t('admin.system.codegen.wysiwyg.toolbar.create')"
          :show-export="features.hasExport.value"
          :show-recycle-bin="features.hasRecycleBin.value"
          :recycle-bin-count="3"
          :on-create="() => {}"
        >
          <template
            v-for="f in columnsWithComment"
            :key="'header-' + String(f.name)"
            #[`header_comment_${f.name}`]
          >
            <Tooltip :title="f.comment">
              <span>{{ getFieldLabel(f) }}</span>
            </Tooltip>
          </template>
        </CrudGrid>
      </div>
    </div>

    <div v-else-if="dataFields.length > 0" class="bg-muted/10 py-12">
      <Empty
        :image="Empty.PRESENTED_IMAGE_SIMPLE"
        :description="$t('admin.system.codegen.wysiwyg.noVisibleColumns')"
      />
    </div>

    <div v-else class="bg-muted/10 py-12">
      <Empty :image="Empty.PRESENTED_IMAGE_SIMPLE">
        <template #description>
          <p class="mb-1">{{ $t('admin.system.codegen.wysiwyg.emptyHint') }}</p>
          <p class="text-xs text-muted-foreground">
            {{ $t('admin.system.codegen.wysiwyg.dragHint') }}
          </p>
        </template>
      </Empty>
    </div>
  </div>
</template>
