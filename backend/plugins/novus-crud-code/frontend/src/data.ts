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
