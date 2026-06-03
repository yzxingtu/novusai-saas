export type FieldPropertyRelationSectionMode = 'select' | 'tree' | 'user';

export interface FieldPropertyPanelSectionInput {
  selectedFieldType: string;
  selectedFormComponent: string;
  showSelectRelationConfig: boolean;
  showTreeRelationConfig: boolean;
  showUserRelationConfig: boolean;
}

export interface FieldPropertyPanelSectionState {
  relationModes: FieldPropertyRelationSectionMode[];
  showCascaderSection: boolean;
  showEnumSection: boolean;
  showUploadSection: boolean;
}

const UPLOAD_FIELD_TYPES = new Set([
  'File',
  'FilePicker',
  'Files',
  'Image',
  'Images',
  'ImageUpload',
]);

export function getFieldPropertyPanelSectionState(
  input: FieldPropertyPanelSectionInput,
): FieldPropertyPanelSectionState {
  const relationModes: FieldPropertyRelationSectionMode[] = [];

  if (input.showTreeRelationConfig) {
    relationModes.push('tree');
  }
  if (input.showSelectRelationConfig) {
    relationModes.push('select');
  }
  if (input.showUserRelationConfig) {
    relationModes.push('user');
  }

  return {
    relationModes,
    showCascaderSection: input.selectedFieldType === 'Cascader',
    showEnumSection: input.selectedFieldType === 'Enum',
    showUploadSection:
      UPLOAD_FIELD_TYPES.has(input.selectedFieldType) ||
      input.selectedFormComponent === 'FilePicker' ||
      input.selectedFormComponent === 'ImageUpload',
  };
}
