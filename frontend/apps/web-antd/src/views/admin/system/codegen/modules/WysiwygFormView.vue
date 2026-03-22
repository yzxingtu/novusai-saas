<script lang="ts" setup>
/**
 * WYSIWYG 新建表单预览 / WYSIWYG Form View
 *
 * 使用直接 Ant Design 组件渲染，支持密码掩码、字段点击选中、多列布局。
 * 表单可编辑、可提交，提交后弹窗显示 JSON。
 */
import type { JSONContent } from '@tiptap/core';
import type { Dayjs } from 'dayjs';

import dayjs from 'dayjs';
import { computed, reactive, ref, watch } from 'vue';
import {
  Button,
  Cascader,
  DatePicker,
  Empty,
  Input,
  InputNumber,
  Modal,
  Rate,
  Select,
  Slider,
  Switch,
  TimePicker,
  Tooltip,
  TreeSelect,
} from 'ant-design-vue';
import { IconifyIcon } from '@vben/icons';
import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';

import { ApiSelect } from '#/components/business/api-select';
import CronPicker from '#/components/business/cron-picker/CronPicker.vue';
import { IconPicker } from '#/components/business/icon-picker';
import RichTextEditor from '#/components/business/rich-text-editor/RichTextEditor.vue';

import {
  getCodegenDbColumnsApi,
  getCodegenDbTableRowsApi,
} from '#/api/admin/codegen';

import {
  getComponent,
  getFieldLabel,
  isDatetimeType,
  isMultiple,
} from './field-utils';
import { useConfigFeatures } from './useConfigFeatures';

defineOptions({ name: 'WysiwygFormView' });

type BuilderField = Record<string, unknown>;

interface FormItem extends BuilderField {
  _comp: string;
}

type SelectScalarValue = number | string;
type SelectValue = SelectScalarValue | SelectScalarValue[] | undefined;
type TreeValue = SelectScalarValue | SelectScalarValue[] | undefined;

function asBoolean(value: unknown): boolean {
  return Boolean(value);
}

function asNumberOrUndefined(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value)
    ? value
    : undefined;
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null
    ? (value as Record<string, unknown>)
    : {};
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function isJsonContent(value: unknown): value is JSONContent {
  return typeof value === 'object' && value !== null;
}

function isSelectScalarValue(value: unknown): value is SelectScalarValue {
  return typeof value === 'number' || typeof value === 'string';
}

/** 缓存关联表的列信息，用于预览时显示真实列名 */
const relationColumnsCache = ref<Record<string, { displayField: string }>>({});

/** RichTextEditor 默认空文档结构（稳定引用，避免每次渲染创建新对象）
 * 注意：ProseMirror 不允许空文本节点，故使用空 paragraph 而非 { type: 'text', text: '' }
 */
const RICH_TEXT_DEFAULT_DOC = {
  type: 'doc' as const,
  content: [{ type: 'paragraph' as const }],
};

const store = useCodegenBuilderStore();
const features = useConfigFeatures(store);
const displayNameStr = computed(() => String(features.displayName.value ?? ''));

const formTitle = computed(() =>
  $t('admin.system.codegen.wysiwyg.formTitle', { name: displayNameStr.value }),
);
const requiredCount = computed(
  () =>
    formItemsWithDividers.value.filter(
      (item) =>
        !item.divider && item.type !== '__divider__' && Boolean(item.required),
    ).length,
);
const previewBadges = computed(() => [
  {
    key: 'fields',
    label: $t('admin.system.codegen.builder.previewFormFields', {
      count: formItemsWithDividers.value.filter(
        (item) => !item.divider && item.type !== '__divider__',
      ).length,
    }),
  },
  {
    key: 'required',
    label: $t('admin.system.codegen.builder.previewRequiredFields', {
      count: requiredCount.value,
    }),
  },
  {
    key: 'columns',
    label: $t('admin.system.codegen.builder.previewFormColumns', {
      count: features.formColumns.value,
    }),
  },
]);

const formItemsWithDividers = computed<FormItem[]>(() => {
  const fields = (store.configJson.fields as BuilderField[]) || [];
  return fields
    .filter(
      (f) =>
        f.divider ||
        f.type === '__divider__' ||
        (f.insertable !== false &&
          (f.name || f.display_name) &&
          !!asString(f.name).trim()),
    )
    .map((f) => ({ ...f, _comp: getComponent(f) }));
});

const hasFormFields = computed(() => formItemsWithDividers.value.length > 0);

/** 表单值（按字段名） */
const formValues = reactive<Record<string, unknown>>({});

/** 提交结果弹窗 */
const submitResultVisible = ref(false);
const submitResultJson = ref('');

/** 将 default 转为 formValues 可用的值（含 RichText doc 转换） */
function resolveDefaultValue(f: BuilderField, comp: string): unknown {
  const def = f.default;
  const hasDefault = def !== undefined && def !== null && def !== '';
  if (!hasDefault) return undefined;
  const isRichText =
    comp === 'RichText' || String(f.type || '').trim() === 'RichText';
  if (isRichText && typeof def === 'string') {
    return {
      type: 'doc',
      content: [{ type: 'paragraph', content: [{ type: 'text', text: def }] }],
    };
  }
  return def;
}

function getFieldName(field: BuilderField): string {
  return asString(field.name).trim();
}

function getFormValue(field: BuilderField): unknown {
  const name = getFieldName(field);
  return name ? formValues[name] : undefined;
}

function setFormValue(field: BuilderField, value: unknown): void {
  const name = getFieldName(field);
  if (!name) return;
  formValues[name] = value;
}

function getArraySelectValue(field: BuilderField): SelectScalarValue[] {
  const value = getFormValue(field);
  return Array.isArray(value) ? value.filter(isSelectScalarValue) : [];
}

function getBooleanValue(field: BuilderField): boolean {
  return asBoolean(getFormValue(field));
}

function getCascaderValue(field: BuilderField): string[] {
  const value = getFormValue(field);
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : [];
}

function getDateRangeValue(field: BuilderField): [Dayjs, Dayjs] | undefined {
  const value = getFormValue(field);
  return Array.isArray(value) &&
    value.length === 2 &&
    dayjs.isDayjs(value[0]) &&
    dayjs.isDayjs(value[1])
    ? [value[0], value[1]]
    : undefined;
}

function getDateValue(field: BuilderField): Dayjs | undefined {
  const value = getFormValue(field);
  return dayjs.isDayjs(value) ? value : undefined;
}

function getNumberValue(field: BuilderField): number | undefined {
  return asNumberOrUndefined(getFormValue(field));
}

function getRichTextValue(field: BuilderField): JSONContent | null {
  const value = getFormValue(field);
  return isJsonContent(value) ? value : null;
}

function getScalarSelectValue(
  field: BuilderField,
): number | string | undefined {
  const value = getFormValue(field);
  return isSelectScalarValue(value) ? value : undefined;
}

function getMultipleAwareSelectValue(field: BuilderField): SelectValue {
  return isMultiple(field)
    ? getArraySelectValue(field)
    : getScalarSelectValue(field);
}

function getSelectValue(field: FormItem): SelectValue {
  return field._comp === 'checkbox'
    ? getArraySelectValue(field)
    : getScalarSelectValue(field);
}

function getStringValue(field: BuilderField): string {
  return asString(getFormValue(field));
}

function getTreeValue(field: BuilderField): TreeValue {
  const value = getFormValue(field);
  if (isSelectScalarValue(value)) return value;
  return Array.isArray(value) ? value.filter(isSelectScalarValue) : undefined;
}

function onNativeColorInput(field: BuilderField, event: Event) {
  const target = event.target;
  if (!(target instanceof HTMLInputElement)) return;
  setFormValue(field, target.value);
}

watch(
  formItemsWithDividers,
  (items) => {
    const currentNames = new Set(
      items
        .filter((f) => !f.divider && f.type !== '__divider__')
        .map((f) => String(f.name || '').trim())
        .filter(Boolean),
    );
    for (const key of Object.keys(formValues)) {
      if (!currentNames.has(key)) delete formValues[key];
    }
    for (const f of items) {
      if (f.divider || f.type === '__divider__') continue;
      const fn = getFieldName(f);
      if (!fn) continue;
      const comp = getComponent(f);
      const resolvedDefault = resolveDefaultValue(f, comp);

      if (!(fn in formValues)) {
        // 仅对新增字段初始化默认值，已存在字段保留用户输入 / Only init default for new fields, preserve user input for existing
        if (resolvedDefault !== undefined) {
          formValues[fn] = resolvedDefault;
        } else if (comp === 'switch') formValues[fn] = false;
        else if (comp === 'checkbox') formValues[fn] = [];
        else if (comp === 'Rate') formValues[fn] = 0;
        else if (comp === 'Slider') formValues[fn] = 0;
        else if (comp === 'ColorPicker') formValues[fn] = '#6366f1';
        else if (comp === 'CronPicker') formValues[fn] = '';
        else if (
          (comp === 'ApiSelect' || comp === 'UserSelect') &&
          isMultiple(f)
        )
          formValues[fn] = [];
        else if (comp === 'ImageUpload' && isMultiple(f)) formValues[fn] = [];
        else if (comp === 'FilePicker' && isMultiple(f)) formValues[fn] = [];
        else if (
          comp === 'CodeEditor' ||
          String(f.type || '').trim() === 'JSON'
        )
          formValues[fn] = '{}';
        else formValues[fn] = undefined;
      }
      // 不覆盖已存在字段：字段配置变更时保留用户输入 / Do not overwrite existing: preserve user input when field config changes
    }
  },
  { immediate: true },
);

/** 预加载关联表列信息（用于改善 mock 显示的列名） */
watch(
  () => formItemsWithDividers.value,
  (items) => {
    const tables = new Set<string>();
    for (const f of items) {
      const t = asString(f.relation_table).trim();
      if (t && !tables.has(t)) tables.add(t);
    }
    for (const table of tables) {
      if (relationColumnsCache.value[table]) continue;
      getCodegenDbColumnsApi(table)
        .then((cols) => {
          const displayCol = cols.find((c) => c.name !== 'id');
          if (displayCol) {
            relationColumnsCache.value = {
              ...relationColumnsCache.value,
              [table]: { displayField: displayCol.name },
            };
          }
        })
        .catch(() => {});
    }
  },
  { immediate: true },
);

function getRichTextAi(f: BuilderField): boolean {
  const form = asRecord(f.form);
  if (form.ai === false) return false;
  return true;
}

function onFieldClick(f: BuilderField) {
  store.selectedFieldKey = asString(f.__key) || asString(f.name);
}

function isFieldSelected(f: BuilderField): boolean {
  const key = asString(f.__key) || asString(f.name);
  return store.selectedFieldKey === key;
}

/** 从 enum_values 构造 Select options */
function getEnumOptions(
  f: BuilderField,
): Array<{ label: string; value: string; disabled?: boolean }> {
  const ev =
    (f.enum_values as Array<{
      value: string;
      label_zh?: string;
      label_en?: string;
    }>) || [];
  if (ev.length === 0) {
    return [
      {
        label: $t('admin.system.codegen.preview.noEnumHint'),
        value: '',
        disabled: true,
      },
    ];
  }
  return ev.map((e) => ({
    label: (e.label_zh || e.label_en || e.value) as string,
    value: String(e.value ?? ''),
  }));
}

/** DictSelect mock options（基于 dict_code） */
function getDictMockOptions(
  f: BuilderField,
): Array<{ label: string; value: string }> {
  const code = asString(f.dict_code || 'dict').replace(/_/g, ' ');
  return [
    {
      label: `${code} ${$t('admin.system.codegen.preview.mockOptionA')}`,
      value: 'a',
    },
    {
      label: `${code} ${$t('admin.system.codegen.preview.mockOptionB')}`,
      value: 'b',
    },
    {
      label: `${code} ${$t('admin.system.codegen.preview.mockOptionC')}`,
      value: 'c',
    },
  ];
}

/** 关联字段 mock options（ForeignKey/ApiSelect/UserSelect/DeptSelect） */
function getMockRelationOptions(
  f: BuilderField,
): Array<{ label: string; value: number }> {
  const table = asString(
    f.relation_table || $t('admin.system.codegen.preview.mockRelation'),
  ).replace(/_/g, ' ');
  const cached = relationColumnsCache.value[asString(f.relation_table)];
  const display = String(
    f.relation_display ||
      f.relation_display_field ||
      cached?.displayField ||
      'name',
  );
  return [
    { label: `${table} A (${display})`, value: 1 },
    { label: `${table} B (${display})`, value: 2 },
    { label: `${table} C (${display})`, value: 3 },
  ];
}

/** 关联表真实数据 API（供 ApiSelect 使用） */
function getRelationApi(f: BuilderField) {
  const table = asString(f.relation_table);
  const valueField = asString(
    f.relation_value_field || f.relation_value || 'id',
  );
  const displayField = asString(
    f.relation_display || f.relation_display_field || 'name',
  );
  return (params: Record<string, unknown>) =>
    getCodegenDbTableRowsApi(table, {
      value_field: valueField,
      display_field: displayField,
      limit: 200,
      search: (params?.search as string) || undefined,
    });
}

/** 关联字段 placeholder */
function getRelationPlaceholder(f: BuilderField): string {
  const table = asString(f.relation_table).replace(/_/g, ' ');
  return table
    ? $t('admin.system.codegen.preview.selectRelation') + ` (${table})`
    : $t('admin.system.codegen.preview.selectRelation');
}

/** 字段占位符：优先用户配置，否则 fallback */
function getFieldPlaceholder(f: BuilderField, fallbackKey: string): string {
  const p = f.placeholder;
  if (p != null && String(p).trim() !== '') return String(p).trim();
  return $t(fallbackKey);
}

/** 树形选择 mock 树数据（TreeSelect treeData 格式：label, value, children） */
function getMockTreeOptions(
  f: BuilderField,
): Array<{
  label: string;
  value: number;
  children?: Array<{ label: string; value: number }>;
}> {
  const table = asString(
    f.relation_table || $t('admin.system.codegen.preview.mockTree'),
  ).replace(/_/g, ' ');
  const pre = 'admin.system.codegen.preview';
  return [
    {
      label: `${table} ${$t(pre + '.mockParentA')}`,
      value: 1,
      children: [
        { label: `${table} ${$t(pre + '.mockChildA1')}`, value: 11 },
        { label: `${table} ${$t(pre + '.mockChildA2')}`, value: 12 },
      ],
    },
    {
      label: `${table} ${$t(pre + '.mockParentB')}`,
      value: 2,
      children: [{ label: `${table} ${$t(pre + '.mockChildB1')}`, value: 21 }],
    },
  ];
}

/** 级联 mock 数据 */
function getMockCascaderOptions(
  _f: BuilderField,
): Array<{
  label: string;
  value: string;
  children?: Array<{ label: string; value: string }>;
}> {
  const pre = 'admin.system.codegen.preview';
  return [
    {
      label: $t(pre + '.mockProvinceA'),
      value: 'a',
      children: [
        { label: $t(pre + '.mockCityA1'), value: 'a1' },
        { label: $t(pre + '.mockCityA2'), value: 'a2' },
      ],
    },
    {
      label: $t(pre + '.mockProvinceB'),
      value: 'b',
      children: [{ label: $t(pre + '.mockCityB1'), value: 'b1' }],
    },
  ];
}

/** 将表单值转为可序列化的 JSON（处理 dayjs、富文本、RangePicker 等） */
function toSerializableValues(): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(formValues)) {
    if (dayjs.isDayjs(v)) {
      out[k] = v.format('YYYY-MM-DD HH:mm:ss');
    } else if (
      Array.isArray(v) &&
      v.length === 2 &&
      dayjs.isDayjs(v[0]) &&
      dayjs.isDayjs(v[1])
    ) {
      out[k] = [v[0].format('YYYY-MM-DD'), v[1].format('YYYY-MM-DD')];
    } else {
      out[k] = v;
    }
  }
  return out;
}

function handleSubmit() {
  const data = toSerializableValues();
  submitResultJson.value = JSON.stringify(data, null, 2);
  submitResultVisible.value = true;
}

function handleCancel() {
  Object.keys(formValues).forEach((k) => {
    delete formValues[k];
  });
}
</script>

<template>
  <div
    class="overflow-hidden rounded-[24px] border border-border/70 bg-card shadow-sm"
  >
    <div class="border-b border-border/50 px-5 py-4">
      <div
        class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between"
      >
        <div class="min-w-0">
          <div
            class="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground"
          >
            {{ $t('admin.system.codegen.wysiwyg.formView') }}
          </div>
          <div class="mt-2 text-lg font-semibold text-foreground">
            {{ formTitle }}
          </div>
          <div class="mt-1 text-sm leading-6 text-muted-foreground">
            {{ $t('admin.system.codegen.builder.previewFormDesc') }}
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
    </div>

    <div v-if="hasFormFields" class="bg-muted/10 p-5">
      <div
        class="mx-auto max-w-5xl overflow-hidden rounded-[24px] border border-border/70 bg-background shadow-sm"
      >
        <div class="border-b border-border/50 px-5 py-4">
          <div
            class="flex flex-wrap items-center gap-2 text-xs text-muted-foreground"
          >
            <IconifyIcon icon="lucide:mouse-pointer" class="size-4" />
            <span>{{
              $t('admin.system.codegen.builder.previewFieldHint')
            }}</span>
          </div>
        </div>

        <div
          class="p-5"
          :class="
            features.formColumns.value === 2
              ? 'grid grid-cols-1 gap-4 xl:grid-cols-2'
              : 'flex flex-col gap-4'
          "
        >
          <template
            v-for="(f, i) in formItemsWithDividers"
            :key="(f.__key as string) || f.name || `d-${i}`"
          >
            <template v-if="f.divider || f.type === '__divider__'">
              <div
                :class="[
                  'rounded-2xl border border-dashed border-border/70 bg-muted/15 px-4 py-3',
                  features.formColumns.value === 2 && 'xl:col-span-2',
                ]"
              >
                <div
                  class="text-[11px] uppercase tracking-[0.16em] text-muted-foreground"
                >
                  {{ $t('admin.system.codegen.palette.divider') }}
                </div>
                <div class="mt-1 text-sm font-medium text-foreground">
                  {{ f.divider_title || f.title || '' }}
                </div>
              </div>
            </template>
            <div
              v-else
              :class="[
                'flex flex-col gap-2 rounded-[20px] border border-border/70 bg-background px-4 py-4 transition-colors',
                isFieldSelected(f) && 'border-primary ring-2 ring-primary/15',
              ]"
              @mousedown="onFieldClick(f)"
            >
              <label class="text-xs text-muted-foreground">
                <span v-if="f.required" class="mr-0.5 text-destructive">*</span>
                <Tooltip v-if="f.comment" :title="f.comment">
                  <span>{{
                    getFieldLabel(f) ||
                    $t('admin.system.codegen.property.unnamed')
                  }}</span>
                </Tooltip>
                <span v-else>{{
                  getFieldLabel(f) ||
                  $t('admin.system.codegen.property.unnamed')
                }}</span>
              </label>
              <Input
                v-if="(f._comp as string) === 'input'"
                :value="getStringValue(f)"
                :maxlength="(f.max_length as number) ?? undefined"
                :placeholder="
                  getFieldPlaceholder(
                    f,
                    'admin.system.codegen.preview.pleaseInput',
                  )
                "
                @update:value="(value) => setFormValue(f, value)"
              />
              <Input
                v-else-if="(f._comp as string) === 'password'"
                :value="getStringValue(f)"
                type="password"
                :placeholder="
                  getFieldPlaceholder(
                    f,
                    'admin.system.codegen.preview.pleaseInput',
                  )
                "
                @update:value="(value) => setFormValue(f, value)"
              />
              <Input.TextArea
                v-else-if="(f._comp as string) === 'textarea'"
                :value="getStringValue(f)"
                :maxlength="(f.max_length as number) ?? undefined"
                :rows="2"
                :placeholder="
                  getFieldPlaceholder(
                    f,
                    'admin.system.codegen.preview.pleaseInput',
                  )
                "
                @update:value="(value) => setFormValue(f, value)"
              />
              <InputNumber
                v-else-if="(f._comp as string) === 'number'"
                :value="getNumberValue(f)"
                :min="(f.min_value as number) ?? undefined"
                :max="(f.max_value as number) ?? undefined"
                class="w-full"
                @update:value="
                  (value) => setFormValue(f, asNumberOrUndefined(value))
                "
              />
              <Select
                v-else-if="
                  ['select', 'radio', 'checkbox'].includes(
                    (f._comp as string) || '',
                  )
                "
                :value="getSelectValue(f)"
                :options="getEnumOptions(f)"
                :mode="
                  (f._comp as string) === 'checkbox' ? 'multiple' : undefined
                "
                :placeholder="
                  getFieldPlaceholder(
                    f,
                    'admin.system.codegen.preview.pleaseSelect',
                  )
                "
                class="w-full"
                @update:value="(value) => setFormValue(f, value)"
              />
              <div
                v-else-if="(f._comp as string) === 'switch'"
                class="flex w-fit items-center"
              >
                <Switch
                  :checked="getBooleanValue(f)"
                  @update:checked="(value) => setFormValue(f, asBoolean(value))"
                />
              </div>
              <DatePicker
                v-else-if="(f._comp as string) === 'date' && isDatetimeType(f)"
                :value="getDateValue(f)"
                show-time
                :placeholder="
                  getFieldPlaceholder(
                    f,
                    'admin.system.codegen.preview.datePlaceholder',
                  )
                "
                class="w-full"
                @update:value="(value) => setFormValue(f, value)"
              />
              <DatePicker
                v-else-if="(f._comp as string) === 'date'"
                :value="getDateValue(f)"
                :placeholder="
                  getFieldPlaceholder(
                    f,
                    'admin.system.codegen.preview.datePlaceholder',
                  )
                "
                class="w-full"
                @update:value="(value) => setFormValue(f, value)"
              />
              <div
                v-else-if="(f._comp as string) === 'ImageUpload'"
                class="flex w-full flex-col gap-1.5"
              >
                <div
                  class="flex min-h-[80px] items-center justify-center gap-2 rounded border border-dashed border-border bg-muted/30"
                  :class="isMultiple(f) ? 'flex-row flex-wrap' : ''"
                >
                  <div
                    class="flex flex-col items-center justify-center gap-1 py-4"
                  >
                    <IconifyIcon
                      icon="lucide:image-plus"
                      class="size-8 text-muted-foreground"
                    />
                    <span class="text-xs text-muted-foreground">
                      {{
                        isMultiple(f)
                          ? $t('admin.system.codegen.preview.uploadImageMulti')
                          : $t('admin.system.codegen.preview.uploadImage')
                      }}
                    </span>
                    <span
                      v-if="f.max_count"
                      class="text-xs text-muted-foreground"
                    >
                      {{
                        $t('admin.system.codegen.preview.maxCountHint', {
                          count: f.max_count,
                        })
                      }}
                    </span>
                  </div>
                  <div
                    v-if="isMultiple(f)"
                    class="flex size-16 shrink-0 items-center justify-center rounded border border-dashed border-border bg-muted/20"
                  >
                    <IconifyIcon
                      icon="lucide:image-plus"
                      class="size-5 text-muted-foreground"
                    />
                  </div>
                </div>
              </div>
              <div
                v-else-if="(f._comp as string) === 'FilePicker'"
                class="flex w-full flex-col gap-1.5"
              >
                <div
                  class="flex min-h-[64px] items-center justify-center gap-2 rounded border border-dashed border-border bg-muted/30"
                  :class="isMultiple(f) ? 'flex-row flex-wrap' : ''"
                >
                  <div
                    class="flex flex-col items-center justify-center gap-1 py-3"
                  >
                    <IconifyIcon
                      icon="lucide:file-plus"
                      class="size-6 text-muted-foreground"
                    />
                    <span class="text-xs text-muted-foreground">
                      {{
                        isMultiple(f)
                          ? $t('admin.system.codegen.preview.uploadFileMulti')
                          : $t('admin.system.codegen.preview.uploadFile')
                      }}
                    </span>
                    <span
                      v-if="f.max_count"
                      class="text-xs text-muted-foreground"
                    >
                      {{
                        $t('admin.system.codegen.preview.maxCountHint', {
                          count: f.max_count,
                        })
                      }}
                    </span>
                  </div>
                  <div
                    v-if="isMultiple(f)"
                    class="flex size-12 shrink-0 items-center justify-center rounded border border-dashed border-border bg-muted/20"
                  >
                    <IconifyIcon
                      icon="lucide:file"
                      class="size-4 text-muted-foreground"
                    />
                  </div>
                </div>
              </div>
              <div
                v-else-if="
                  (f._comp as string) === 'RichText' ||
                  String(f.type || '').trim() === 'RichText'
                "
                class="w-full"
              >
                <RichTextEditor
                  :model-value="getRichTextValue(f)"
                  :default-value="RICH_TEXT_DEFAULT_DOC"
                  :placeholder="
                    getFieldPlaceholder(f, 'common.editorPlaceholder')
                  "
                  mode="compact"
                  :toolbar="true"
                  :ai="getRichTextAi(f)"
                  :upload="false"
                  :editable="true"
                  :min-height="120"
                  class="rounded border border-border"
                  @update:model-value="(value) => setFormValue(f, value)"
                />
              </div>
              <ApiSelect
                v-else-if="
                  (f._comp as string) === 'ApiSelect' &&
                  f.relation_table &&
                  !isMultiple(f)
                "
                :key="`rel-${f.relation_table}-${f.relation_display || f.relation_display_field || 'name'}`"
                :value="getScalarSelectValue(f)"
                :api="getRelationApi(f)"
                :placeholder="
                  f.placeholder && String(f.placeholder).trim()
                    ? String(f.placeholder).trim()
                    : getRelationPlaceholder(f)
                "
                result-field="items"
                label-field="label"
                value-field="value"
                search-param-name="search"
                :page-size="200"
                class="w-full"
                @update:value="(value) => setFormValue(f, value)"
              />
              <Select
                v-else-if="(f._comp as string) === 'ApiSelect'"
                :value="getMultipleAwareSelectValue(f)"
                :options="getMockRelationOptions(f)"
                :placeholder="
                  f.placeholder && String(f.placeholder).trim()
                    ? String(f.placeholder).trim()
                    : getRelationPlaceholder(f)
                "
                :mode="isMultiple(f) ? 'multiple' : undefined"
                class="w-full"
                @update:value="(value) => setFormValue(f, value)"
              />
              <TreeSelect
                v-else-if="
                  ['ApiTreeSelect', 'TreeSelect'].includes(
                    (f._comp as string) || '',
                  )
                "
                :value="getTreeValue(f)"
                :tree-data="getMockTreeOptions(f)"
                :placeholder="
                  f.placeholder && String(f.placeholder).trim()
                    ? String(f.placeholder).trim()
                    : getRelationPlaceholder(f)
                "
                class="w-full"
                @update:value="(value) => setFormValue(f, value)"
              />
              <Cascader
                v-else-if="(f._comp as string) === 'Cascader'"
                :value="getCascaderValue(f)"
                :options="getMockCascaderOptions(f)"
                :placeholder="
                  getFieldPlaceholder(
                    f,
                    'admin.system.codegen.preview.pleaseSelect',
                  )
                "
                class="w-full"
                @update:value="(value) => setFormValue(f, value)"
              />
              <TimePicker
                v-else-if="(f._comp as string) === 'TimePicker'"
                :value="getDateValue(f)"
                :placeholder="
                  getFieldPlaceholder(
                    f,
                    'admin.system.codegen.preview.timePlaceholder',
                  )
                "
                class="w-full"
                @update:value="(value) => setFormValue(f, value)"
              />
              <div
                v-else-if="(f._comp as string) === 'ColorPicker'"
                class="flex items-center gap-2"
              >
                <div
                  class="relative size-8 shrink-0 cursor-pointer overflow-hidden rounded border border-border"
                >
                  <input
                    :value="getStringValue(f)"
                    type="color"
                    class="absolute inset-0 size-full cursor-pointer opacity-0"
                    @input="(event) => onNativeColorInput(f, event)"
                  />
                  <div
                    class="absolute inset-0"
                    :style="{ backgroundColor: getStringValue(f) || '#6366f1' }"
                  />
                </div>
                <Input
                  :value="getStringValue(f)"
                  class="flex-1 font-mono text-xs"
                  :placeholder="
                    f.placeholder && String(f.placeholder).trim()
                      ? String(f.placeholder).trim()
                      : '#6366f1'
                  "
                  @update:value="(value) => setFormValue(f, value)"
                />
              </div>
              <div
                v-else-if="(f._comp as string) === 'IconPicker'"
                class="min-w-0 flex-1"
              >
                <IconPicker
                  :value="getStringValue(f)"
                  :placeholder="
                    f.placeholder && String(f.placeholder).trim()
                      ? String(f.placeholder).trim()
                      : 'lucide:sparkles'
                  "
                  @update:value="(value) => setFormValue(f, value)"
                />
              </div>
              <Rate
                v-else-if="(f._comp as string) === 'Rate'"
                :value="getNumberValue(f)"
                @update:value="
                  (value) => setFormValue(f, asNumberOrUndefined(value))
                "
              />
              <Slider
                v-else-if="(f._comp as string) === 'Slider'"
                :value="getNumberValue(f)"
                @update:value="
                  (value) => setFormValue(f, asNumberOrUndefined(value))
                "
              />
              <Select
                v-else-if="(f._comp as string) === 'DictSelect'"
                :value="getScalarSelectValue(f)"
                :options="getDictMockOptions(f)"
                :placeholder="
                  getFieldPlaceholder(
                    f,
                    'admin.system.codegen.preview.dictSelectPlaceholder',
                  )
                "
                class="w-full"
                @update:value="(value) => setFormValue(f, value)"
              />
              <div
                v-else-if="(f._comp as string) === 'CodeEditor'"
                class="h-20 w-full rounded border border-border bg-muted/20 font-mono text-xs"
              />
              <CronPicker
                v-else-if="(f._comp as string) === 'CronPicker'"
                :value="getStringValue(f)"
                :placeholder="
                  getFieldPlaceholder(
                    f,
                    'admin.system.codegen.preview.cronPlaceholder',
                  )
                "
                @update:value="(value) => setFormValue(f, value)"
              />
              <DatePicker.RangePicker
                v-else-if="(f._comp as string) === 'RangePicker'"
                :value="getDateRangeValue(f)"
                :placeholder="[
                  getFieldPlaceholder(
                    f,
                    'admin.system.codegen.preview.rangePlaceholder',
                  ),
                  getFieldPlaceholder(
                    f,
                    'admin.system.codegen.preview.rangePlaceholder',
                  ),
                ]"
                class="w-full"
                @update:value="(value) => setFormValue(f, value)"
              />
              <div
                v-else-if="(f._comp as string) === 'Upload'"
                class="flex h-16 w-full items-center justify-center gap-2 rounded border border-dashed border-border bg-muted/30"
              >
                <IconifyIcon
                  icon="lucide:upload"
                  class="size-6 text-muted-foreground"
                />
                <span class="text-xs text-muted-foreground">
                  {{ $t('admin.system.codegen.preview.uploadFile') }}
                </span>
              </div>
              <Input
                v-else
                :value="getStringValue(f)"
                :maxlength="(f.max_length as number) ?? undefined"
                :placeholder="
                  getFieldPlaceholder(
                    f,
                    'admin.system.codegen.preview.pleaseInput',
                  )
                "
                @update:value="(value) => setFormValue(f, value)"
              />
              <span
                v-if="f.help_text"
                class="mt-0.5 text-xs text-muted-foreground"
                >{{ f.help_text }}</span
              >
            </div>
          </template>
        </div>

        <div
          class="flex justify-end gap-2 border-t border-border/50 bg-muted/10 px-5 py-4"
        >
          <Button size="small" @click="handleCancel">{{
            $t('common.cancel')
          }}</Button>
          <Button size="small" type="primary" @click="handleSubmit">{{
            $t('common.confirm')
          }}</Button>
        </div>
      </div>
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

    <Modal
      v-model:open="submitResultVisible"
      :title="$t('admin.system.codegen.preview.submitData')"
      :footer="null"
      width="560"
    >
      <pre
        class="max-h-[400px] overflow-auto rounded bg-muted/30 p-3 text-xs"
        >{{ submitResultJson }}</pre
      >
    </Modal>
  </div>
</template>
