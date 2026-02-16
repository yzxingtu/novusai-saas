/**
 * CRUD Generator — Shared option constants
 *
 * Centralized option lists used across multiple components
 * (StepListConfig, StepFormConfig, FieldDetailDrawer, SlotEditor).
 */

import { $t } from '#/locales';

import type { ListRenderPreset } from './types';

const T = 'admin.dev.crudGenerator';

// ============================================================
// Render Presets
// ============================================================

export interface IconOption {
  icon: string;
  label: string;
  value: string;
}

const RENDER_PRESET_ICONS: Record<string, string> = {
  tag: 'icon-[lucide--tag]',
  badge: 'icon-[lucide--circle-dot]',
  switch: 'icon-[lucide--toggle-left]',
  money: 'icon-[lucide--dollar-sign]',
  percent: 'icon-[lucide--percent]',
  progress: 'icon-[lucide--bar-chart-3]',
  relative_time: 'icon-[lucide--clock]',
  datetime: 'icon-[lucide--calendar-clock]',
  date: 'icon-[lucide--calendar]',
  avatar: 'icon-[lucide--user-circle]',
  image: 'icon-[lucide--image]',
  link: 'icon-[lucide--external-link]',
  copy: 'icon-[lucide--copy]',
  icon: 'icon-[lucide--smile]',
  color: 'icon-[lucide--palette]',
  ellipsis: 'icon-[lucide--more-horizontal]',
};

export function getRenderPresetOptions(): IconOption[] {
  const presets: ListRenderPreset[] = [
    'tag', 'badge', 'switch', 'money', 'percent', 'progress',
    'relative_time', 'datetime', 'date', 'avatar', 'image',
    'link', 'copy', 'icon', 'color', 'ellipsis',
  ];
  return presets.map((p) => ({
    label: $t(`${T}.renderPresets.${p}`),
    value: p,
    icon: RENDER_PRESET_ICONS[p] || 'icon-[lucide--minus]',
  }));
}

// ============================================================
// Form Components
// ============================================================

const FORM_COMPONENT_ICONS: Record<string, string> = {
  Input: 'icon-[lucide--text-cursor]',
  InputNumber: 'icon-[lucide--hash]',
  Textarea: 'icon-[lucide--text]',
  Select: 'icon-[lucide--chevrons-up-down]',
  Switch: 'icon-[lucide--toggle-left]',
  DatePicker: 'icon-[lucide--calendar]',
  RangePicker: 'icon-[lucide--calendar-range]',
  RadioGroup: 'icon-[lucide--circle-dot]',
  CheckboxGroup: 'icon-[lucide--check-square]',
  Upload: 'icon-[lucide--upload]',
  ApiSelect: 'icon-[lucide--database]',
  ApiTreeSelect: 'icon-[lucide--git-branch]',
  Cascader: 'icon-[lucide--layers]',
  Rate: 'icon-[lucide--star]',
  Slider: 'icon-[lucide--sliders-horizontal]',
  ColorPicker: 'icon-[lucide--palette]',
  JsonEditor: 'icon-[lucide--braces]',
  RichText: 'icon-[lucide--file-text]',
};

export const FORM_COMPONENT_OPTIONS: IconOption[] = [
  'Input', 'InputNumber', 'Textarea', 'Select', 'Switch',
  'DatePicker', 'RangePicker', 'RadioGroup', 'CheckboxGroup',
  'Upload', 'ApiSelect', 'ApiTreeSelect', 'Cascader',
  'Rate', 'Slider', 'ColorPicker', 'JsonEditor', 'RichText',
].map((c) => ({
  label: c,
  value: c,
  icon: FORM_COMPONENT_ICONS[c] || 'icon-[lucide--minus]',
}));

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

export function getSearchOperatorOptions() {
  return [
    { label: $t(`${T}.searchOp.ilike`), value: 'ilike' },
    { label: $t(`${T}.searchOp.eq`), value: 'eq' },
    { label: $t(`${T}.searchOp.in`), value: 'in' },
    { label: $t(`${T}.searchOp.gte`), value: 'gte' },
    { label: $t(`${T}.searchOp.lte`), value: 'lte' },
    { label: $t(`${T}.searchOp.between`), value: 'between' },
  ];
}

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
