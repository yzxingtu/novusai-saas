/**
 * CRUD Generator — Shared option constants
 *
 * Centralized option lists used across multiple components
 * (StepListConfig, StepFormConfig, FieldDetailDrawer, SlotEditor).
 */

import { $t } from '#/locales';

import type { FormComponent, ListRenderPreset } from './types';

const T = 'admin.dev.crudGenerator';

// ============================================================
// Render Presets
// ============================================================

export function getRenderPresetOptions(): { label: string; value: ListRenderPreset }[] {
  return [
    { label: $t(`${T}.renderPresets.tag`), value: 'tag' },
    { label: $t(`${T}.renderPresets.badge`), value: 'badge' },
    { label: $t(`${T}.renderPresets.switch`), value: 'switch' },
    { label: $t(`${T}.renderPresets.money`), value: 'money' },
    { label: $t(`${T}.renderPresets.percent`), value: 'percent' },
    { label: $t(`${T}.renderPresets.progress`), value: 'progress' },
    { label: $t(`${T}.renderPresets.relativeTime`), value: 'relative_time' },
    { label: $t(`${T}.renderPresets.datetime`), value: 'datetime' },
    { label: $t(`${T}.renderPresets.date`), value: 'date' },
    { label: $t(`${T}.renderPresets.avatar`), value: 'avatar' },
    { label: $t(`${T}.renderPresets.image`), value: 'image' },
    { label: $t(`${T}.renderPresets.link`), value: 'link' },
    { label: $t(`${T}.renderPresets.copy`), value: 'copy' },
    { label: $t(`${T}.renderPresets.icon`), value: 'icon' },
    { label: $t(`${T}.renderPresets.color`), value: 'color' },
    { label: $t(`${T}.renderPresets.ellipsis`), value: 'ellipsis' },
  ];
}

// ============================================================
// Form Components
// ============================================================

export const FORM_COMPONENT_OPTIONS: { label: string; value: FormComponent }[] = [
  { label: 'Input', value: 'Input' },
  { label: 'InputNumber', value: 'InputNumber' },
  { label: 'Textarea', value: 'Textarea' },
  { label: 'Select', value: 'Select' },
  { label: 'Switch', value: 'Switch' },
  { label: 'DatePicker', value: 'DatePicker' },
  { label: 'RangePicker', value: 'RangePicker' },
  { label: 'RadioGroup', value: 'RadioGroup' },
  { label: 'CheckboxGroup', value: 'CheckboxGroup' },
  { label: 'Upload', value: 'Upload' },
  { label: 'ApiSelect', value: 'ApiSelect' },
  { label: 'ApiTreeSelect', value: 'ApiTreeSelect' },
  { label: 'Cascader', value: 'Cascader' },
  { label: 'Rate', value: 'Rate' },
  { label: 'Slider', value: 'Slider' },
  { label: 'ColorPicker', value: 'ColorPicker' },
  { label: 'JsonEditor', value: 'JsonEditor' },
  { label: 'RichText', value: 'RichText' },
];

// ============================================================
// Align Options
// ============================================================

export function getAlignOptions() {
  return [
    { label: $t(`${T}.listConfig.alignLeft`), value: 'left' },
    { label: $t(`${T}.listConfig.alignCenter`), value: 'center' },
    { label: $t(`${T}.listConfig.alignRight`), value: 'right' },
  ];
}

// ============================================================
// Fixed Column Options
// ============================================================

export function getFixedOptions() {
  return [
    { label: $t(`${T}.listConfig.fixedNone`), value: '' },
    { label: $t(`${T}.listConfig.fixedLeft`), value: 'left' },
    { label: $t(`${T}.listConfig.fixedRight`), value: 'right' },
  ];
}

// ============================================================
// Search Operators
// ============================================================

export const SEARCH_OPERATOR_OPTIONS = [
  { label: 'ilike', value: 'ilike' },
  { label: 'eq', value: 'eq' },
  { label: 'in', value: 'in' },
  { label: 'gte', value: 'gte' },
  { label: 'lte', value: 'lte' },
  { label: 'between', value: 'between' },
];

// ============================================================
// Search Components
// ============================================================

export const SEARCH_COMPONENT_OPTIONS = [
  { label: 'Input', value: 'Input' },
  { label: 'Select', value: 'Select' },
  { label: 'DatePicker', value: 'DatePicker' },
  { label: 'RangePicker', value: 'RangePicker' },
  { label: 'InputNumber', value: 'InputNumber' },
  { label: 'ApiSelect', value: 'ApiSelect' },
  { label: 'TreeSelect', value: 'TreeSelect' },
];
