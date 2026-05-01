import type { JSONContent } from '@tiptap/core';
import type { Dayjs } from 'dayjs';

import type { CodegenDbTableRowItem } from '#/api/admin/codegen';

import { computed, reactive, ref, watch } from 'vue';

import dayjs from 'dayjs';

import { getCodegenDbTableRowsApi } from '#/api/admin/codegen';
import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';

import {
  getComponent,
  getFieldLabel,
  isDatetimeType,
  isMultiple,
} from './field-utils';
import { useConfigFeatures } from './useConfigFeatures';

type BuilderField = Record<string, unknown>;

interface FormItem extends BuilderField {
  _comp: string;
}

type SelectScalarValue = number | string;
type SelectValue = SelectScalarValue | SelectScalarValue[] | undefined;
type TreeValue = SelectScalarValue | SelectScalarValue[] | undefined;
type ApiSelectOptionSource = Record<string, unknown>;

interface ApiSelectResponse {
  items: ApiSelectOptionSource[];
  total: number;
  [key: string]: unknown;
}

function asBoolean(value: unknown): boolean {
  if (typeof value === 'boolean') {
    return value;
  }
  return Boolean(value);
}

function asNumberOrUndefined(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value)
    ? value
    : undefined;
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

/** RichTextEditor 默认空文档结构（稳定引用，避免每次渲染创建新对象）
 * 注意：ProseMirror 不允许空文本节点，故使用空 paragraph 而非 { type: 'text', text: '' }
 */
const richTextDefaultDoc = {
  type: 'doc' as const,
  content: [{ type: 'paragraph' as const }],
};

export function useWysiwygFormPreview() {
  const store = useCodegenBuilderStore();
  const features = useConfigFeatures(store);
  const displayNameStr = computed(() =>
    String(features.displayName.value ?? ''),
  );

  const formTitle = computed(() =>
    $t('admin.system.codegen.wysiwyg.formTitle', {
      name: displayNameStr.value,
    }),
  );

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

  const requiredCount = computed(
    () =>
      formItemsWithDividers.value.filter(
        (item) =>
          !item.divider &&
          item.type !== '__divider__' &&
          Boolean(item.required),
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
        content: [
          { type: 'paragraph', content: [{ type: 'text', text: def }] },
        ],
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
    return Array.isArray(value)
      ? value.filter((item): item is SelectScalarValue =>
          isSelectScalarValue(item),
        )
      : [];
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
    return Array.isArray(value)
      ? value.filter((item): item is SelectScalarValue =>
          isSelectScalarValue(item),
        )
      : undefined;
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
        if (!currentNames.has(key)) {
          formValues[key] = undefined;
        }
      }
      for (const f of items) {
        if (f.divider || f.type === '__divider__') continue;
        const fn = getFieldName(f);
        if (!fn) continue;
        const comp = f._comp || getComponent(f);
        const resolvedDefault = resolveDefaultValue(f, comp);

        if (!(fn in formValues)) {
          // 仅对新增字段初始化默认值，已存在字段保留用户输入 / Only init default for new fields, preserve user input for existing
          if (resolvedDefault === undefined) {
            switch (comp) {
              case 'checkbox': {
                formValues[fn] = [];
                break;
              }
              case 'ColorPicker': {
                formValues[fn] = '#6366f1';
                break;
              }
              case 'CronPicker': {
                formValues[fn] = '';
                break;
              }
              case 'Rate': {
                formValues[fn] = 0;
                break;
              }
              case 'Slider': {
                formValues[fn] = 0;
                break;
              }
              case 'switch': {
                formValues[fn] = false;
                break;
              }
              default: {
                if (
                  (comp === 'ApiSelect' || comp === 'UserSelect') &&
                  isMultiple(f)
                )
                  formValues[fn] = [];
                else if (comp === 'ImageUpload' && isMultiple(f))
                  formValues[fn] = [];
                else if (comp === 'FilePicker' && isMultiple(f))
                  formValues[fn] = [];
                else if (
                  comp === 'CodeEditor' ||
                  String(f.type || '').trim() === 'JSON'
                )
                  formValues[fn] = '{}';
                else formValues[fn] = undefined;
              }
            }
          } else {
            formValues[fn] = resolvedDefault;
          }
        }
        // 不覆盖已存在字段：字段配置变更时保留用户输入 / Do not overwrite existing: preserve user input when field config changes
      }
    },
    { immediate: true },
  );

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
  ): Array<{ disabled?: boolean; label: string; value: string }> {
    const ev =
      (f.enum_values as Array<{
        label_en?: string;
        label_zh?: string;
        value: string;
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

  /** 关联字段 mock options（ForeignKey/ApiSelect/UserSelect/DeptSelect） */
  function getMockRelationOptions(
    f: BuilderField,
  ): Array<{ label: string; value: number }> {
    const table = asString(
      f.relation_table || $t('admin.system.codegen.preview.mockRelation'),
    ).replaceAll('_', ' ');
    const display = String(
      f.relation_display || f.relation_display_field || 'name',
    );
    return [
      { label: `${table} A (${display})`, value: 1 },
      { label: `${table} B (${display})`, value: 2 },
      { label: `${table} C (${display})`, value: 3 },
    ];
  }

  /** 关联表真实数据 API（供 ApiSelect 使用） */
  function toApiSelectOptionSource(
    item: CodegenDbTableRowItem,
  ): ApiSelectOptionSource {
    return {
      label: item.label,
      value: item.value,
    };
  }

  function getRelationApi(
    f: BuilderField,
  ): (params: Record<string, unknown>) => Promise<ApiSelectResponse> {
    const table = asString(f.relation_table);
    const valueField = asString(
      f.relation_value_field || f.relation_value || 'id',
    );
    const displayField = asString(
      f.relation_display || f.relation_display_field || 'name',
    );
    return async (params: Record<string, unknown>) => {
      const response = await getCodegenDbTableRowsApi(table, {
        value_field: valueField,
        display_field: displayField,
        limit: 200,
        search: (params?.search as string) || undefined,
      });
      return {
        ...response,
        items: response.items.map((item) => toApiSelectOptionSource(item)),
      };
    };
  }

  /** 关联字段 placeholder */
  function getRelationPlaceholder(f: BuilderField): string {
    const table = asString(f.relation_table).replaceAll('_', ' ');
    return table
      ? `${$t('admin.system.codegen.preview.selectRelation')} (${table})`
      : $t('admin.system.codegen.preview.selectRelation');
  }

  /** 字段占位符：优先用户配置，否则 fallback */
  function getFieldPlaceholder(f: BuilderField, fallbackKey: string): string {
    const p = f.placeholder;
    if (p !== null && p !== undefined && String(p).trim() !== '') {
      return String(p).trim();
    }
    return $t(fallbackKey);
  }

  /** 树形选择 mock 树数据（TreeSelect treeData 格式：label, value, children） */
  function getMockTreeOptions(f: BuilderField): Array<{
    children?: Array<{ label: string; value: number }>;
    label: string;
    value: number;
  }> {
    const table = asString(
      f.relation_table || $t('admin.system.codegen.preview.mockTree'),
    ).replaceAll('_', ' ');
    const pre = 'admin.system.codegen.preview';
    return [
      {
        label: `${table} ${$t(`${pre}.mockParentA`)}`,
        value: 1,
        children: [
          { label: `${table} ${$t(`${pre}.mockChildA1`)}`, value: 11 },
          { label: `${table} ${$t(`${pre}.mockChildA2`)}`, value: 12 },
        ],
      },
      {
        label: `${table} ${$t(`${pre}.mockParentB`)}`,
        value: 2,
        children: [
          { label: `${table} ${$t(`${pre}.mockChildB1`)}`, value: 21 },
        ],
      },
    ];
  }

  /** 级联 mock 数据 */
  function getMockCascaderOptions(_f: BuilderField): Array<{
    children?: Array<{ label: string; value: string }>;
    label: string;
    value: string;
  }> {
    const pre = 'admin.system.codegen.preview';
    return [
      {
        label: $t(`${pre}.mockProvinceA`),
        value: 'a',
        children: [
          { label: $t(`${pre}.mockCityA1`), value: 'a1' },
          { label: $t(`${pre}.mockCityA2`), value: 'a2' },
        ],
      },
      {
        label: $t(`${pre}.mockProvinceB`),
        value: 'b',
        children: [{ label: $t(`${pre}.mockCityB1`), value: 'b1' }],
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
      formValues[k] = undefined;
    });
  }

  return {
    features,
    displayNameStr,
    formTitle,
    previewBadges,
    formItemsWithDividers,
    hasFormFields,
    formValues,
    submitResultVisible,
    submitResultJson,
    richTextDefaultDoc,
    asBoolean,
    asNumberOrUndefined,
    getFieldLabel,
    getFieldPlaceholder,
    getStringValue,
    getNumberValue,
    getSelectValue,
    getBooleanValue,
    getDateValue,
    getDateRangeValue,
    getRichTextValue,
    getScalarSelectValue,
    getMultipleAwareSelectValue,
    getTreeValue,
    getCascaderValue,
    getEnumOptions,
    getMockRelationOptions,
    getRelationApi,
    getRelationPlaceholder,
    getMockTreeOptions,
    getMockCascaderOptions,
    onNativeColorInput,
    setFormValue,
    isFieldSelected,
    onFieldClick,
    handleSubmit,
    handleCancel,
    isDatetimeType,
    isMultiple,
  };
}

export type WysiwygFormPreviewState = ReturnType<typeof useWysiwygFormPreview>;
