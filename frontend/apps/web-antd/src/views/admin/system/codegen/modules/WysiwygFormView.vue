<script lang="ts" setup>
/**
 * WYSIWYG 新建表单预览 / WYSIWYG Form View
 *
 * 使用直接 Ant Design 组件渲染，支持密码掩码、字段点击选中、多列布局。
 * 表单可编辑、可提交，提交后弹窗显示 JSON。
 */

import type { Recordable } from '@vben/types';

import dayjs from 'dayjs';
import { computed, reactive, ref, watch } from 'vue';
import {
  Button,
  Cascader,
  DatePicker,
  Divider,
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
const displayNameStr = computed(
  () => String(features.displayName.value ?? ''),
);

const formTitle = computed(
  () => $t('admin.system.codegen.wysiwyg.formTitle', { name: displayNameStr.value }),
);

const formItemsWithDividers = computed(() => {
  const fields = (store.configJson.fields as Recordable[]) || [];
  return fields
    .filter(
      (f) =>
        f.divider ||
        f.type === '__divider__' ||
        (f.insertable !== false && (f.name || f.display_name) && !!String(f.name || '').trim()),
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
function resolveDefaultValue(f: Recordable, comp: string): unknown {
  const def = f.default;
  const hasDefault = def !== undefined && def !== null && def !== '';
  if (!hasDefault) return undefined;
  const isRichText = comp === 'RichText' || String(f.type || '').trim() === 'RichText';
  if (isRichText && typeof def === 'string') {
    return {
      type: 'doc',
      content: [{ type: 'paragraph', content: [{ type: 'text', text: def }] }],
    };
  }
  return def;
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
      const fn = String(f.name || '').trim();
      if (!fn) continue;
      const comp = getComponent(f);
      const resolvedDefault = resolveDefaultValue(f, comp);

      if (!(fn in formValues)) {
        if (resolvedDefault !== undefined) {
          formValues[fn] = resolvedDefault;
        } else if (comp === 'switch') formValues[fn] = false;
        else if (comp === 'checkbox') formValues[fn] = [];
        else if (comp === 'Rate') formValues[fn] = 0;
        else if (comp === 'Slider') formValues[fn] = 0;
        else if (comp === 'ColorPicker') formValues[fn] = '#6366f1';
        else if (comp === 'CronPicker') formValues[fn] = '';
        else if ((comp === 'ApiSelect' || comp === 'UserSelect') && isMultiple(f))
          formValues[fn] = [];
        else if (comp === 'ImageUpload' && isMultiple(f)) formValues[fn] = [];
        else if (comp === 'FilePicker' && isMultiple(f)) formValues[fn] = [];
        else if (comp === 'CodeEditor' || String(f.type || '').trim() === 'JSON')
          formValues[fn] = '{}';
        else formValues[fn] = undefined;
      } else if (resolvedDefault !== undefined) {
        formValues[fn] = resolvedDefault;
      }
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
      const t = String((f as Recordable).relation_table || '').trim();
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

function onCloseFormPreview() {
  store.wysiwygViewMode = 'list';
}

function getRichTextAi(f: Recordable): boolean {
  const form = (f.form as Record<string, unknown>) || {};
  if (form.ai === false) return false;
  return true;
}

function onFieldClick(f: Record<string, unknown>) {
  store.selectedFieldKey = (f.__key as string) || (f.name as string);
}

function isFieldSelected(f: Record<string, unknown>): boolean {
  const key = (f.__key as string) || (f.name as string);
  return store.selectedFieldKey === key;
}

/** 从 enum_values 构造 Select options */
function getEnumOptions(f: Recordable): Array<{ label: string; value: string; disabled?: boolean }> {
  const ev = (f.enum_values as Array<{ value: string; label_zh?: string; label_en?: string }>) || [];
  if (ev.length === 0) {
    return [{ label: $t('admin.system.codegen.preview.noEnumHint'), value: '', disabled: true }];
  }
  return ev.map((e) => ({
    label: (e.label_zh || e.label_en || e.value) as string,
    value: String(e.value ?? ''),
  }));
}

/** DictSelect mock options（基于 dict_code） */
function getDictMockOptions(f: Recordable): Array<{ label: string; value: string }> {
  const code = String(f.dict_code || 'dict').replace(/_/g, ' ');
  return [
    { label: `${code} 选项 A`, value: 'a' },
    { label: `${code} 选项 B`, value: 'b' },
    { label: `${code} 选项 C`, value: 'c' },
  ];
}

/** 关联字段 mock options（ForeignKey/ApiSelect/UserSelect/DeptSelect） */
function getMockRelationOptions(f: Recordable): Array<{ label: string; value: number }> {
  const table = String(f.relation_table || '关联').replace(/_/g, ' ');
  const cached = relationColumnsCache.value[String(f.relation_table || '')];
  const display = String(
    f.relation_display || f.relation_display_field || cached?.displayField || 'name',
  );
  return [
    { label: `${table} A (${display})`, value: 1 },
    { label: `${table} B (${display})`, value: 2 },
    { label: `${table} C (${display})`, value: 3 },
  ];
}

/** 关联表真实数据 API（供 ApiSelect 使用） */
function getRelationApi(f: Recordable) {
  const table = String(f.relation_table || '');
  const valueField = String(f.relation_value_field || f.relation_value || 'id');
  const displayField = String(
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
function getRelationPlaceholder(f: Recordable): string {
  const table = String(f.relation_table || '').replace(/_/g, ' ');
  return table ? $t('admin.system.codegen.preview.selectRelation') + ` (${table})` : $t('admin.system.codegen.preview.selectRelation');
}

/** 字段占位符：优先用户配置，否则 fallback */
function getFieldPlaceholder(f: Recordable, fallbackKey: string): string {
  const p = f.placeholder;
  if (p != null && String(p).trim() !== '') return String(p).trim();
  return $t(fallbackKey);
}

/** 树形选择 mock 树数据（TreeSelect treeData 格式：label, value, children） */
function getMockTreeOptions(f: Recordable): Array<{ label: string; value: number; children?: Array<{ label: string; value: number }> }> {
  const table = String(f.relation_table || '树').replace(/_/g, ' ');
  return [
    { label: `${table} 父级 A`, value: 1, children: [{ label: `${table} 子 A1`, value: 11 }, { label: `${table} 子 A2`, value: 12 }] },
    { label: `${table} 父级 B`, value: 2, children: [{ label: `${table} 子 B1`, value: 21 }] },
  ];
}

/** 级联 mock 数据 */
function getMockCascaderOptions(f: Recordable): Array<{ label: string; value: string; children?: Array<{ label: string; value: string }> }> {
  return [
    { label: '省 A', value: 'a', children: [{ label: '市 A1', value: 'a1' }, { label: '市 A2', value: 'a2' }] },
    { label: '省 B', value: 'b', children: [{ label: '市 B1', value: 'b1' }] },
  ];
}

/** 将表单值转为可序列化的 JSON（处理 dayjs、富文本、RangePicker 等） */
function toSerializableValues(): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(formValues)) {
    if (dayjs.isDayjs(v)) {
      out[k] = v.format('YYYY-MM-DD HH:mm:ss');
    } else if (Array.isArray(v) && v.length === 2 && dayjs.isDayjs(v[0]) && dayjs.isDayjs(v[1])) {
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
    formValues[k] = undefined;
  });
}
</script>

<template>
  <div class="overflow-hidden rounded-xl border border-border/40 bg-card">
    <div class="flex items-center justify-between border-b border-border/30 px-5 py-3 text-base font-medium">
      <span>{{ formTitle }}</span>
      <Button type="text" size="small" @click="onCloseFormPreview">
        <IconifyIcon icon="lucide:x" />
      </Button>
    </div>

    <div
      v-if="hasFormFields"
      class="p-4"
      :class="
        features.formColumns.value === 2
          ? 'grid grid-cols-2 gap-3'
          : 'flex flex-col gap-3'
      "
    >
      <template
        v-for="(f, i) in formItemsWithDividers"
        :key="(f.__key as string) || f.name || `d-${i}`"
      >
        <template v-if="f.divider || f.type === '__divider__'">
          <Divider
            :class="[
              '!my-2',
              features.formColumns.value === 2 && 'col-span-2',
            ]"
            orientation="left"
          >
            <span class="text-xs">{{ f.divider_title || f.title || '' }}</span>
          </Divider>
        </template>
        <div
          v-else
          :class="[
            'flex flex-col gap-1 cursor-pointer rounded p-1 -m-1 transition-colors',
            isFieldSelected(f) && 'ring-2 ring-primary',
          ]"
          @mousedown="onFieldClick(f)"
        >
          <label class="text-xs text-muted-foreground">
            <span v-if="f.required" class="text-destructive mr-0.5">*</span>
            <Tooltip v-if="f.comment" :title="f.comment">
              <span>{{ getFieldLabel(f) || $t('admin.system.codegen.property.unnamed') }}</span>
            </Tooltip>
            <span v-else>{{ getFieldLabel(f) || $t('admin.system.codegen.property.unnamed') }}</span>
          </label>
          <Input
            v-if="(f._comp as string) === 'input'"
            v-model:value="formValues[f.name as string]"
            :maxlength="(f.max_length as number) ?? undefined"
            :placeholder="getFieldPlaceholder(f, 'admin.system.codegen.preview.pleaseInput')"
          />
          <Input
            v-else-if="(f._comp as string) === 'password'"
            v-model:value="formValues[f.name as string]"
            type="password"
            :placeholder="getFieldPlaceholder(f, 'admin.system.codegen.preview.pleaseInput')"
          />
          <Input.TextArea
            v-else-if="(f._comp as string) === 'textarea'"
            v-model:value="formValues[f.name as string]"
            :maxlength="(f.max_length as number) ?? undefined"
            :rows="2"
            :placeholder="getFieldPlaceholder(f, 'admin.system.codegen.preview.pleaseInput')"
          />
          <InputNumber
            v-else-if="(f._comp as string) === 'number'"
            v-model:value="formValues[f.name as string]"
            :min="(f.min_value as number) ?? undefined"
            :max="(f.max_value as number) ?? undefined"
            class="w-full"
          />
          <Select
            v-else-if="['select', 'radio', 'checkbox'].includes((f._comp as string) || '')"
            v-model:value="formValues[f.name as string]"
            :options="getEnumOptions(f)"
            :mode="(f._comp as string) === 'checkbox' ? 'multiple' : undefined"
            :placeholder="getFieldPlaceholder(f, 'admin.system.codegen.preview.pleaseSelect')"
            class="w-full"
          />
          <div
            v-else-if="(f._comp as string) === 'switch'"
            class="flex w-fit items-center"
          >
            <Switch
              v-model:checked="formValues[f.name as string]"
            />
          </div>
          <DatePicker
            v-else-if="(f._comp as string) === 'date' && isDatetimeType(f)"
            v-model:value="formValues[f.name as string]"
            show-time
            :placeholder="getFieldPlaceholder(f, 'admin.system.codegen.preview.datePlaceholder')"
            class="w-full"
          />
          <DatePicker
            v-else-if="(f._comp as string) === 'date'"
            v-model:value="formValues[f.name as string]"
            :placeholder="getFieldPlaceholder(f, 'admin.system.codegen.preview.datePlaceholder')"
            class="w-full"
          />
          <div
            v-else-if="(f._comp as string) === 'ImageUpload'"
            class="flex w-full flex-col gap-1.5"
          >
            <div
              class="flex min-h-[80px] items-center justify-center gap-2 rounded border border-dashed border-border bg-muted/30"
              :class="isMultiple(f) ? 'flex-row flex-wrap' : ''"
            >
              <div class="flex flex-col items-center justify-center gap-1 py-4">
                <IconifyIcon icon="lucide:image-plus" class="size-8 text-muted-foreground" />
                <span class="text-muted-foreground text-xs">
                  {{
                    isMultiple(f)
                      ? $t('admin.system.codegen.preview.uploadImageMulti')
                      : $t('admin.system.codegen.preview.uploadImage')
                  }}
                </span>
                <span v-if="f.max_count" class="text-muted-foreground text-xs">
                  {{ $t('admin.system.codegen.preview.maxCountHint', { count: f.max_count }) }}
                </span>
              </div>
              <div
                v-if="isMultiple(f)"
                class="flex size-16 shrink-0 items-center justify-center rounded border border-dashed border-border bg-muted/20"
              >
                <IconifyIcon icon="lucide:image-plus" class="size-5 text-muted-foreground" />
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
              <div class="flex flex-col items-center justify-center gap-1 py-3">
                <IconifyIcon icon="lucide:file-plus" class="size-6 text-muted-foreground" />
                <span class="text-muted-foreground text-xs">
                  {{
                    isMultiple(f)
                      ? $t('admin.system.codegen.preview.uploadFileMulti')
                      : $t('admin.system.codegen.preview.uploadFile')
                  }}
                </span>
                <span v-if="f.max_count" class="text-muted-foreground text-xs">
                  {{ $t('admin.system.codegen.preview.maxCountHint', { count: f.max_count }) }}
                </span>
              </div>
              <div
                v-if="isMultiple(f)"
                class="flex size-12 shrink-0 items-center justify-center rounded border border-dashed border-border bg-muted/20"
              >
                <IconifyIcon icon="lucide:file" class="size-4 text-muted-foreground" />
              </div>
            </div>
          </div>
          <div
            v-else-if="
              (f._comp as string) === 'RichText' || String(f.type || '').trim() === 'RichText'
            "
            class="w-full"
          >
            <RichTextEditor
              v-model="formValues[f.name as string]"
              :default-value="RICH_TEXT_DEFAULT_DOC"
              :placeholder="getFieldPlaceholder(f, 'common.editorPlaceholder')"
              mode="compact"
              :toolbar="true"
              :ai="getRichTextAi(f)"
              :upload="false"
              :editable="true"
              :min-height="120"
              class="rounded border border-border"
            />
          </div>
          <ApiSelect
            v-else-if="(f._comp as string) === 'ApiSelect' && f.relation_table"
            :key="`rel-${f.relation_table}-${f.relation_display || f.relation_display_field || 'name'}`"
            v-model:value="formValues[f.name as string]"
            :api="getRelationApi(f)"
            :placeholder="(f.placeholder && String(f.placeholder).trim()) ? String(f.placeholder).trim() : getRelationPlaceholder(f)"
            :mode="isMultiple(f) ? 'multiple' : undefined"
            result-field="items"
            label-field="label"
            value-field="value"
            search-param-name="search"
            :page-size="200"
            class="w-full"
          />
          <Select
            v-else-if="(f._comp as string) === 'ApiSelect'"
            v-model:value="formValues[f.name as string]"
            :options="getMockRelationOptions(f)"
            :placeholder="(f.placeholder && String(f.placeholder).trim()) ? String(f.placeholder).trim() : getRelationPlaceholder(f)"
            :mode="isMultiple(f) ? 'multiple' : undefined"
            class="w-full"
          />
          <TreeSelect
            v-else-if="['ApiTreeSelect', 'TreeSelect'].includes((f._comp as string) || '')"
            v-model:value="formValues[f.name as string]"
            :tree-data="getMockTreeOptions(f)"
            :placeholder="(f.placeholder && String(f.placeholder).trim()) ? String(f.placeholder).trim() : getRelationPlaceholder(f)"
            class="w-full"
          />
          <Cascader
            v-else-if="(f._comp as string) === 'Cascader'"
            v-model:value="formValues[f.name as string]"
            :options="getMockCascaderOptions(f)"
            :placeholder="getFieldPlaceholder(f, 'admin.system.codegen.preview.pleaseSelect')"
            class="w-full"
          />
          <TimePicker
            v-else-if="(f._comp as string) === 'TimePicker'"
            v-model:value="formValues[f.name as string]"
            :placeholder="getFieldPlaceholder(f, 'admin.system.codegen.preview.timePlaceholder')"
            class="w-full"
          />
          <div
            v-else-if="(f._comp as string) === 'ColorPicker'"
            class="flex items-center gap-2"
          >
            <div class="relative size-8 shrink-0 cursor-pointer overflow-hidden rounded border border-border">
              <input
                v-model="formValues[f.name as string]"
                type="color"
                class="absolute inset-0 size-full cursor-pointer opacity-0"
              >
              <div
                class="absolute inset-0"
                :style="{ backgroundColor: (formValues[f.name as string] as string) || '#6366f1' }"
              />
            </div>
            <Input
              v-model:value="formValues[f.name as string]"
              class="flex-1 font-mono text-xs"
              :placeholder="(f.placeholder && String(f.placeholder).trim()) ? String(f.placeholder).trim() : '#6366f1'"
            />
          </div>
          <div
            v-else-if="(f._comp as string) === 'IconPicker'"
            class="flex-1 min-w-0"
          >
            <IconPicker
              :value="(formValues[f.name as string] as string) || ''"
              :placeholder="(f.placeholder && String(f.placeholder).trim()) ? String(f.placeholder).trim() : 'lucide:sparkles'"
              @update:value="(v: string) => (formValues[f.name as string] = v)"
            />
          </div>
          <Rate
            v-else-if="(f._comp as string) === 'Rate'"
            v-model:value="formValues[f.name as string]"
          />
          <Slider
            v-else-if="(f._comp as string) === 'Slider'"
            v-model:value="formValues[f.name as string]"
          />
          <Select
            v-else-if="(f._comp as string) === 'DictSelect'"
            v-model:value="formValues[f.name as string]"
            :options="getDictMockOptions(f)"
            :placeholder="getFieldPlaceholder(f, 'admin.system.codegen.preview.dictSelectPlaceholder')"
            class="w-full"
          />
          <div
            v-else-if="(f._comp as string) === 'CodeEditor'"
            class="h-20 w-full rounded border border-border bg-muted/20 font-mono text-xs"
          />
          <CronPicker
            v-else-if="(f._comp as string) === 'CronPicker'"
            v-model:value="formValues[f.name as string]"
            :placeholder="getFieldPlaceholder(f, 'admin.system.codegen.preview.cronPlaceholder')"
          />
          <DatePicker.RangePicker
            v-else-if="(f._comp as string) === 'RangePicker'"
            v-model:value="formValues[f.name as string]"
            :placeholder="[getFieldPlaceholder(f, 'admin.system.codegen.preview.rangePlaceholder'), getFieldPlaceholder(f, 'admin.system.codegen.preview.rangePlaceholder')]"
            class="w-full"
          />
          <div
            v-else-if="(f._comp as string) === 'Upload'"
            class="flex h-16 w-full items-center justify-center gap-2 rounded border border-dashed border-border bg-muted/30"
          >
            <IconifyIcon icon="lucide:upload" class="size-6 text-muted-foreground" />
            <span class="text-muted-foreground text-xs">
              {{ $t('admin.system.codegen.preview.uploadFile') }}
            </span>
          </div>
          <Input
            v-else
            v-model:value="formValues[f.name as string]"
            :maxlength="(f.max_length as number) ?? undefined"
            :placeholder="getFieldPlaceholder(f, 'admin.system.codegen.preview.pleaseInput')"
          />
          <span v-if="f.help_text" class="text-muted-foreground mt-0.5 text-xs">{{ f.help_text }}</span>
        </div>
      </template>
    </div>

    <div
      v-if="hasFormFields"
      class="flex justify-end gap-2 border-t border-border/30 px-3 py-2"
    >
      <Button size="small" @click="handleCancel">{{ $t('common.cancel') }}</Button>
      <Button size="small" type="primary" @click="handleSubmit">{{ $t('common.confirm') }}</Button>
    </div>

    <div v-else class="py-12">
      <Empty :image="Empty.PRESENTED_IMAGE_SIMPLE">
        <template #description>
          <p class="mb-1">{{ $t('admin.system.codegen.wysiwyg.emptyHint') }}</p>
          <p class="text-muted-foreground text-xs">
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
      <pre class="max-h-[400px] overflow-auto rounded bg-muted/30 p-3 text-xs">{{ submitResultJson }}</pre>
    </Modal>
  </div>
</template>
