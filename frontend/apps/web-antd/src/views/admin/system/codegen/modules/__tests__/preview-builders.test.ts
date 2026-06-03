import { describe, expect, it, vi } from 'vitest';

import { getComponent } from '../field-utils';
import { buildGridColumns, getMockCellValue } from '../preview-builders';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/preferences', () => ({
  preferences: {
    app: {
      locale: 'zh-CN',
    },
  },
}));

vi.mock('#/adapter/vxe-table', () => ({
  checkboxColumn: { field: '__checkbox__' },
  dragColumn: { field: '__drag__' },
  seqColumn: { field: '__seq__' },
}));

describe('preview builders', () => {
  it('falls back to non-list-visible fields when all are hidden', () => {
    const columns = buildGridColumns(
      [
        {
          name: 'title',
          list_visible: false,
          type: 'String',
          display_name: 'Title',
        },
        {
          name: 'status',
          list_visible: false,
          type: 'Enum',
          enum_values: [{ label_zh: '启用', value: 1 }],
        },
      ],
      { hasBatchDelete: true, hasDragSort: true },
    );

    expect(columns[0]?.field).toBe('__checkbox__');
    expect(columns[1]?.field).toBe('__drag__');
    expect(columns[2]?.field).toBe('__seq__');

    const fieldNames = columns.map((col) => col.field);
    expect(fieldNames).toContain('title');
    expect(fieldNames).toContain('status');

    const operation = columns[columns.length - 1];
    if (!operation) {
      throw new Error('operation column missing');
    }
    expect(operation.field).toBe('operation');
    expect(operation.cellRender?.attrs?.nameField).toBe('title');

    const statusColumn = columns.find((col) => col.field === 'status');
    expect(statusColumn?.cellRender?.name).toBe('CellTag');
    expect(statusColumn?.cellRender?.options?.[0]).toMatchObject({
      label: '启用',
      value: 1,
    });
  });

  it('honors defaults for mock values on the first row', () => {
    const booleanField = {
      name: 'enabled',
      type: 'Boolean',
      default: 'true',
    };
    const numberField = {
      name: 'count',
      type: 'Integer',
      default: '12',
    };

    expect(getMockCellValue(booleanField, 0)).toBe(true);
    expect(getMockCellValue(booleanField, 1)).toBe(false);

    expect(getMockCellValue(numberField, 0)).toBe(12);
    expect(getMockCellValue(numberField, 1)).toBe(101);
  });

  it('does not fabricate dict-backed preview behavior from dict_code metadata', () => {
    const dictMetadataField = {
      name: 'type',
      type: 'String',
      dict_code: 'sys_status',
      display_name: 'Type',
    };

    expect(getMockCellValue(dictMetadataField, 0)).toBe(
      'admin.system.codegen.preview.sampleA',
    );

    const columns = buildGridColumns([dictMetadataField]);
    const typeColumn = columns.find((col) => col.field === 'type');

    expect(typeColumn?.cellRender?.name).toBeUndefined();
  });

  it('does not normalize retired DictSelect fields into live select behavior', () => {
    const legacyTypeField = {
      name: 'legacy_type',
      type: 'DictSelect',
    };
    const legacyComponentField = {
      name: 'legacy_component',
      form: { component: 'DictSelect' },
      type: 'String',
    };

    expect(getComponent(legacyTypeField)).toBe('input');
    expect(getComponent(legacyComponentField)).toBe('DictSelect');
    expect(getMockCellValue(legacyTypeField, 0)).toBe(
      'admin.system.codegen.preview.sampleA',
    );

    const columns = buildGridColumns([legacyTypeField]);
    const legacyColumn = columns.find((col) => col.field === 'legacy_type');

    expect(legacyColumn?.cellRender?.name).toBeUndefined();
  });
});
