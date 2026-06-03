import { describe, expect, it } from 'vitest';

import { getFieldPropertyPanelSectionState } from '../field-property-panel-sections';

describe('getFieldPropertyPanelSectionState', () => {
  it('shows enum section only for enum fields', () => {
    const state = getFieldPropertyPanelSectionState({
      selectedFieldType: 'Enum',
      selectedFormComponent: 'select',
      showSelectRelationConfig: false,
      showTreeRelationConfig: false,
      showUserRelationConfig: false,
    });

    expect(state.showEnumSection).toBe(true);
    expect(state.showCascaderSection).toBe(false);
    expect(state.showUploadSection).toBe(false);
    expect(state.relationModes).toEqual([]);
  });

  it('preserves relation section ordering', () => {
    const state = getFieldPropertyPanelSectionState({
      selectedFieldType: 'ForeignKey',
      selectedFormComponent: 'ApiSelect',
      showSelectRelationConfig: true,
      showTreeRelationConfig: true,
      showUserRelationConfig: true,
    });

    expect(state.relationModes).toEqual(['tree', 'select', 'user']);
  });

  it('shows upload section for upload types and upload components', () => {
    const byType = getFieldPropertyPanelSectionState({
      selectedFieldType: 'FilePicker',
      selectedFormComponent: 'input',
      showSelectRelationConfig: false,
      showTreeRelationConfig: false,
      showUserRelationConfig: false,
    });
    const byComponent = getFieldPropertyPanelSectionState({
      selectedFieldType: 'String',
      selectedFormComponent: 'ImageUpload',
      showSelectRelationConfig: false,
      showTreeRelationConfig: false,
      showUserRelationConfig: false,
    });

    expect(byType.showUploadSection).toBe(true);
    expect(byComponent.showUploadSection).toBe(true);
  });

  it('shows cascader section only for cascader fields', () => {
    const state = getFieldPropertyPanelSectionState({
      selectedFieldType: 'Cascader',
      selectedFormComponent: 'input',
      showSelectRelationConfig: false,
      showTreeRelationConfig: false,
      showUserRelationConfig: false,
    });

    expect(state.showCascaderSection).toBe(true);
    expect(state.showEnumSection).toBe(false);
  });
});
