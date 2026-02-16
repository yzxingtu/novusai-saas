/**
 * Quick Start Presets — Built-in CrudConfig templates
 *
 * Each preset provides a complete CrudConfig with sensible defaults
 * for common CRUD patterns.
 */

import type { CrudConfig } from '../types';

import { createDefaultConfig } from './use-crud-config';
import { createDefaultField } from './field-inference';

export interface QuickStartPreset {
  key: string;
  icon: string;
  fields: Array<{ name: string }>;
  patchConfig?: Partial<CrudConfig>;
}

function field(name: string): ReturnType<typeof createDefaultField> {
  return createDefaultField(name);
}

/**
 * 6 built-in presets
 */
export const QUICK_START_PRESETS: QuickStartPreset[] = [
  {
    key: 'standard',
    icon: 'icon-[lucide--table]',
    fields: [
      { name: 'name' },
      { name: 'description' },
      { name: 'status' },
      { name: 'sort_order' },
      { name: 'remark' },
    ],
    patchConfig: {
      soft_delete: true,
      has_status_toggle: true,
    },
  },
  {
    key: 'tree',
    icon: 'icon-[lucide--git-branch]',
    fields: [
      { name: 'name' },
      { name: 'description' },
      { name: 'sort_order' },
    ],
    patchConfig: {
      layout: {
        variant: 'tree_table',
        card_fields: null,
        card_cover_field: null,
        card_columns: 3,
        detail_position: 'right',
        detail_width: '40%',
        kanban_group_field: null,
        timeline_date_field: null,
      },
      relations: [
        {
          name: 'parent',
          type: 'belongs_to',
          target_model: '',
          target_table: '',
          foreign_key: 'parent_id',
          label_field: 'name',
          cascade_delete: false,
          nullable: true,
          comment_zh: '',
          comment_en: '',
        },
      ],
    },
  },
  {
    key: 'content',
    icon: 'icon-[lucide--file-text]',
    fields: [
      { name: 'title' },
      { name: 'content' },
      { name: 'cover' },
      { name: 'status' },
      { name: 'published_at' },
    ],
    patchConfig: {
      soft_delete: true,
    },
  },
  {
    key: 'order',
    icon: 'icon-[lucide--shopping-cart]',
    fields: [
      { name: 'title' },
      { name: 'amount' },
      { name: 'status' },
      { name: 'remark' },
    ],
    patchConfig: {
      has_status_toggle: true,
      enums: [
        {
          name: 'OrderStatus',
          description: '',
          values: [
            { value: 'pending', label_zh: '\u5f85\u5904\u7406', label_en: 'Pending', color: 'orange' },
            { value: 'processing', label_zh: '\u5904\u7406\u4e2d', label_en: 'Processing', color: 'blue' },
            { value: 'completed', label_zh: '\u5df2\u5b8c\u6210', label_en: 'Completed', color: 'green' },
            { value: 'cancelled', label_zh: '\u5df2\u53d6\u6d88', label_en: 'Cancelled', color: 'red' },
          ],
          transitions: [
            { from_state: 'pending', to_state: 'processing', action: 'process', label_zh: '', label_en: '', confirm: false },
            { from_state: 'processing', to_state: 'completed', action: 'complete', label_zh: '', label_en: '', confirm: false },
            { from_state: 'pending', to_state: 'cancelled', action: 'cancel', label_zh: '', label_en: '', confirm: true },
          ],
        },
      ],
    },
  },
  {
    key: 'config',
    icon: 'icon-[lucide--settings]',
    fields: [
      { name: 'name' },
      { name: 'description' },
      { name: 'sort_order' },
    ],
    patchConfig: {
      drag_sort: true,
      has_status_toggle: false,
      soft_delete: false,
    },
  },
  {
    key: 'log',
    icon: 'icon-[lucide--scroll-text]',
    fields: [
      { name: 'title' },
      { name: 'type' },
      { name: 'content' },
    ],
    patchConfig: {
      soft_delete: false,
      has_status_toggle: false,
      recyclable: false,
      operations: [],
    },
  },
];

/**
 * Build a full CrudConfig from a preset
 */
export function buildConfigFromPreset(preset: QuickStartPreset): CrudConfig {
  const base = createDefaultConfig();
  const fields = preset.fields.map((f) => field(f.name));

  return {
    ...base,
    fields,
    ...preset.patchConfig,
  } as CrudConfig;
}
