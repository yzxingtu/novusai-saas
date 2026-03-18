/**
 * 中间预览板块 — 构建器函数
 * WYSIWYG preview builders: build Grid columns, mock rows
 *
 * 将 configJson.fields 转为 VxeGrid columns，供 WysiwygListView 使用。
 * 表单预览改用直接 Ant Design 组件渲染，不再需要 buildFormSchema。
 */
import type { VxeTableGridOptions } from '#/adapter/vxe-table';

/** VxeGrid 单列配置类型 */
type VxeColumn = NonNullable<VxeTableGridOptions['columns']>[number];
import {
  checkboxColumn,
  dragColumn as vxeDragColumn,
  seqColumn,
} from '#/adapter/vxe-table';
import { $t } from '#/locales';

import {
  getComponent,
  getColumnAlign,
  getFieldLabel,
  getTableCellRenderType,
  shouldHideInList,
} from './field-utils';

export type FieldRecord = Record<string, unknown>;

/** 根据字段类型生成单元格 mock 值（用于表格预览） */
function getMockCellValue(f: FieldRecord, rowIdx: number): unknown {
  const name = String(f.name || '').toLowerCase();
  const t = String(f.type || '').toLowerCase();
  const comp = getComponent(f);
  if (name === 'id') return rowIdx + 1;
  if (t.includes('boolean')) return rowIdx === 0;
  if (t.includes('int') || t.includes('float') || t.includes('decimal')) return 100 + rowIdx;
  if (t.includes('date') || t.includes('datetime'))
    return `2024-01-${String(rowIdx + 1).padStart(2, '0')}`;
  if (t.includes('image')) return `https://example.com/img_${rowIdx}.jpg`;
  if (t.includes('file')) return `file_${rowIdx}.pdf`;
  if (t.includes('richtext')) return '...';
  if (comp === 'ColorPicker') return '#6366f1';
  if (comp === 'IconPicker') return 'lucide:star';
  if (comp === 'Rate') return 3 + rowIdx;
  if (comp === 'Slider') return 50 + rowIdx * 10;
  const ev = (f.enum_values as Array<{ value: unknown }>) || [];
  if (ev.length > 0) {
    const picked = ev[rowIdx % ev.length];
    return (
      picked?.value ??
      (rowIdx === 0 ? $t('admin.system.codegen.preview.sampleA') : rowIdx === 1 ? $t('admin.system.codegen.preview.sampleB') : $t('admin.system.codegen.preview.sampleC'))
    );
  }
  if (f.dict_code) return rowIdx === 0 ? 'a' : rowIdx === 1 ? 'b' : 'c';
  return rowIdx === 0 ? $t('admin.system.codegen.preview.sampleA') : rowIdx === 1 ? $t('admin.system.codegen.preview.sampleB') : $t('admin.system.codegen.preview.sampleC');
}

/** 生成 mock 行数据 */
export function buildMockRows(
  fields: FieldRecord[],
  count = 3,
): Record<string, unknown>[] {
  const dataFields = fields.filter(
    (f) => f.type !== '__divider__' && !f.divider,
  );
  const rows: Record<string, unknown>[] = [];
  for (let i = 0; i < count; i++) {
    const row: Record<string, unknown> = { id: i + 1 };
    for (const f of dataFields) {
      const fn = String(f.name || '').trim();
      if (fn) row[fn] = getMockCellValue(f, i);
    }
    rows.push(row);
  }
  return rows;
}

/** 将 align class 转为 vxe align */
function toVxeAlign(alignClass: string): 'left' | 'center' | 'right' {
  if (alignClass.includes('center')) return 'center';
  if (alignClass.includes('right')) return 'right';
  return 'left';
}

/** fields -> VxeGrid columns */
export function buildGridColumns(
  fields: FieldRecord[],
  opts: {
    hasBatchDelete?: boolean;
    hasDragSort?: boolean;
    hasDetail?: boolean;
    hasClone?: boolean;
    nameField?: string;
    onFieldClick?: (f: FieldRecord) => void;
  } = {},
): NonNullable<VxeTableGridOptions['columns']> {
  const {
    hasBatchDelete = false,
    hasDragSort = false,
    hasDetail = false,
    hasClone = false,
    nameField: nameFieldOpt,
  } = opts;

  let listFields = fields.filter(
    (f) =>
      f.list_visible !== false &&
      f.type !== '__divider__' &&
      !f.divider &&
      !shouldHideInList(f),
  );
  if (listFields.length === 0) {
    listFields = fields.filter(
      (f) => f.type !== '__divider__' && !f.divider && !shouldHideInList(f),
    );
  }

  const nameField =
    nameFieldOpt ||
    (listFields[0] ? String(listFields[0].name || 'name') : 'name');

  const cols: NonNullable<VxeTableGridOptions['columns']> = [];

  if (hasBatchDelete) cols.push(checkboxColumn as VxeColumn);
  if (hasDragSort) cols.push(vxeDragColumn as VxeColumn);
  cols.push(seqColumn as VxeColumn);

  for (const f of listFields) {
    const fieldName = String(f.name || '').trim();
    if (!fieldName) continue;
    const title = getFieldLabel(f) || fieldName;
    const renderType = getTableCellRenderType(f);
    const alignClass = getColumnAlign(f);
    const align = toVxeAlign(alignClass);

    const col: VxeColumn = {
      field: fieldName,
      title,
      minWidth: 100,
      align,
      sortable: f.sortable !== false,
      ...(f.comment
        ? { slots: { header: `header_comment_${fieldName}` as string } }
        : {}),
    };

    if (renderType === 'Switch') {
      col.cellRender = {
        name: 'CellSwitch',
        attrs: { beforeChange: () => Promise.resolve() },
        options: [
          { color: 'success', label: $t('common.enabled'), value: true },
          { color: 'error', label: $t('common.disabled'), value: false },
        ],
      };
    } else if (renderType === 'Image') {
      col.cellRender = { name: 'CellImage' };
    } else if (renderType === 'Tag' || (f.dict_code || String(f.type || '').toLowerCase() === 'enum')) {
      const ev = (f.enum_values as Array<{ label?: string; label_zh?: string; label_en?: string; value: unknown }>) || [];
      const options = ev.length
        ? ev.map((e) => ({ color: 'default', label: (e.label_zh || e.label_en || e.label || e.value) as string, value: e.value }))
        : [
            { color: 'success', label: $t('common.enabled'), value: 1 },
            { color: 'error', label: $t('common.disabled'), value: 0 },
          ];
      col.cellRender = { name: 'CellTag', options };
    }
    cols.push(col);
  }

  cols.push({
    field: 'operation',
    title: $t('admin.common.operation'),
    width: 180,
    fixed: 'right',
    align: 'center',
    cellRender: {
      name: 'CellOperation',
      attrs: {
        nameField,
        nameTitle: $t('common.name'),
        onClick: () => {},
      },
      options: [
        ...(hasDetail ? [{ code: 'detail', text: $t('common.detail'), icon: 'lucide:eye' }] : []),
        { code: 'edit', text: $t('common.edit'), icon: 'lucide:pencil' },
        ...(hasClone ? [{ code: 'clone', text: $t('common.duplicate'), icon: 'lucide:copy' }] : []),
        { code: 'delete', text: $t('common.delete'), icon: 'lucide:trash-2' },
      ],
    },
  });

  return cols;
}
