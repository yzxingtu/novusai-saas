/**
 * DataForge Studio Plugin - Helper functions and constants
 */
import { $t } from '@novus/plugin-shared';

/** Localized translation helper with plugin prefix */
export function t(key: string): string {
  return $t(`plugin.novus-crud-code.${key}`);
}

/** Default project color presets */
export const COLOR_PRESETS = [
  '#6366f1', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444',
] as const;

/** Lucide icon name for each field type */
export const FIELD_TYPE_ICONS: Record<string, string> = {
  string: 'lucide:type',
  integer: 'lucide:hash',
  boolean: 'lucide:toggle-left',
  datetime: 'lucide:calendar',
  text: 'lucide:file-text',
  json: 'lucide:braces',
};

/** Lucide icon for each widget type */
export const WIDGET_ICONS: Record<string, string> = {
  input: 'lucide:type',
  password: 'lucide:lock',
  email: 'lucide:mail',
  url: 'lucide:link',
  number: 'lucide:hash',
  slider: 'lucide:sliders-horizontal',
  rate: 'lucide:star',
  select: 'lucide:chevrons-up-down',
  radio: 'lucide:circle-dot',
  'checkbox-group': 'lucide:check-square',
  switch: 'lucide:toggle-left',
  checkbox: 'lucide:square-check',
  date: 'lucide:calendar',
  datetime: 'lucide:calendar-clock',
  time: 'lucide:clock',
  textarea: 'lucide:file-text',
  upload: 'lucide:upload',
  'json-editor': 'lucide:braces',
  divider: 'lucide:minus',
};

/** Maps widget type → underlying schema data type */
export const WIDGET_DATA_TYPE: Record<string, string> = {
  input: 'string',
  password: 'string',
  email: 'string',
  url: 'string',
  number: 'integer',
  slider: 'integer',
  rate: 'integer',
  select: 'string',
  radio: 'string',
  'checkbox-group': 'json',
  switch: 'boolean',
  checkbox: 'boolean',
  date: 'datetime',
  datetime: 'datetime',
  time: 'string',
  textarea: 'text',
  upload: 'json',
  'json-editor': 'json',
  divider: 'string',
};

/** Badge color class for each widget */
export const WIDGET_COLORS: Record<string, string> = {
  input: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  password: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  email: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  url: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  number: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  slider: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  rate: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  select: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400',
  radio: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400',
  'checkbox-group': 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400',
  switch: 'bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-400',
  checkbox: 'bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-400',
  date: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  datetime: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  time: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  textarea: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
  upload: 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400',
  'json-editor': 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400',
  divider: 'bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400',
};

/** Palette categories for FormBuilder */
export interface PaletteItem { widget: string; labelKey: string }
export interface PaletteCategory { labelKey: string; icon: string; items: PaletteItem[] }

export const PALETTE_CATEGORIES: PaletteCategory[] = [
  {
    labelKey: 'formBuilder.cat.basic',
    icon: 'lucide:type',
    items: [
      { widget: 'input', labelKey: 'widget.input' },
      { widget: 'textarea', labelKey: 'widget.textarea' },
      { widget: 'number', labelKey: 'widget.number' },
      { widget: 'password', labelKey: 'widget.password' },
      { widget: 'email', labelKey: 'widget.email' },
      { widget: 'url', labelKey: 'widget.url' },
    ],
  },
  {
    labelKey: 'formBuilder.cat.selection',
    icon: 'lucide:list',
    items: [
      { widget: 'select', labelKey: 'widget.select' },
      { widget: 'radio', labelKey: 'widget.radio' },
      { widget: 'checkbox-group', labelKey: 'widget.checkboxGroup' },
      { widget: 'switch', labelKey: 'widget.switch' },
      { widget: 'checkbox', labelKey: 'widget.checkbox' },
    ],
  },
  {
    labelKey: 'formBuilder.cat.datetime',
    icon: 'lucide:calendar',
    items: [
      { widget: 'date', labelKey: 'widget.date' },
      { widget: 'datetime', labelKey: 'widget.datetime' },
      { widget: 'time', labelKey: 'widget.time' },
    ],
  },
  {
    labelKey: 'formBuilder.cat.advanced',
    icon: 'lucide:sparkles',
    items: [
      { widget: 'slider', labelKey: 'widget.slider' },
      { widget: 'rate', labelKey: 'widget.rate' },
      { widget: 'upload', labelKey: 'widget.upload' },
      { widget: 'json-editor', labelKey: 'widget.jsonEditor' },
    ],
  },
  {
    labelKey: 'formBuilder.cat.layout',
    icon: 'lucide:layout',
    items: [
      { widget: 'divider', labelKey: 'widget.divider' },
    ],
  },
];

/** Badge color class for each field type (dark mode compatible) */
export const FIELD_TYPE_COLORS: Record<string, string> = {
  string: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  integer: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  boolean: 'bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-400',
  datetime: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  text: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
  json: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400',
};

/** Format ISO date string to localized date */
export function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString();
  } catch {
    return dateStr;
  }
}
