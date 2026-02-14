/**
 * Slot Persistence — SlotEditor 编辑结果持久化到 CrudConfig
 *
 * 职责:
 * 1. 将 SlotEditor 产出的 CustomSlotConfig 写入 CrudConfig.custom_slots
 * 2. 同步更新对应字段的 list_render / list_slot
 * 3. 验证 slot 代码基本合法性
 * 4. 在代码生成时，将 custom_slots 注入到目标 .vue 文件
 */

import type { CrudConfig, CustomSlotConfig, FieldConfig } from '../types';

import {
  collectPresetImports,
  getPresetDefinition,
  renderPresetTemplate,
} from './preset-registry';

// ============================================================
// Slot validation
// ============================================================

export interface SlotValidationResult {
  valid: boolean;
  errors: string[];
}

/**
 * 验证 slot 代码基本合法性
 * - 非空
 * - 不包含 <script> 标签 (安全)
 * - 基本的标签闭合检查
 */
export function validateSlotCode(code: string): SlotValidationResult {
  const errors: string[] = [];

  if (!code.trim()) {
    errors.push('slot.error.empty');
    return { valid: false, errors };
  }

  if (/<script/i.test(code)) {
    errors.push('slot.error.scriptForbidden');
    return { valid: false, errors };
  }

  const openTags = (code.match(/<[a-z][a-z0-9-]*(?:\s|>)/gi) || []).length;
  const closeTags = (code.match(/<\/[a-z][a-z0-9-]*>/gi) || []).length;
  const selfClosing = (code.match(/\/>/g) || []).length;

  if (openTags > closeTags + selfClosing + 2) {
    errors.push('slot.error.unclosedTags');
  }

  return { valid: errors.length === 0, errors };
}

// ============================================================
// Slot persistence (write to CrudConfig)
// ============================================================

/**
 * 将 SlotEditor 编辑结果写入 CrudConfig
 * - 更新或新增 custom_slots 条目
 * - 同步更新字段的 list_slot 标记
 */
export function applySlotToConfig(
  config: CrudConfig,
  slot: CustomSlotConfig,
): CrudConfig {
  const validation = validateSlotCode(slot.template);
  if (!validation.valid) {
    return config;
  }

  const existingIdx = config.custom_slots.findIndex(
    (s) => s.field === slot.field && s.slot_type === slot.slot_type,
  );

  let customSlots: CustomSlotConfig[];
  if (existingIdx >= 0) {
    customSlots = config.custom_slots.map((s, i) =>
      i === existingIdx ? slot : s,
    );
  } else {
    customSlots = [...config.custom_slots, slot];
  }

  const fields = config.fields.map((f) => {
    if (f.name === slot.field && slot.slot_type === 'list') {
      return { ...f, list_slot: `slot_${slot.field}` };
    }
    return f;
  });

  return { ...config, custom_slots: customSlots, fields };
}

/**
 * 移除某字段的 custom slot
 */
export function removeSlotFromConfig(
  config: CrudConfig,
  fieldName: string,
  slotType: string,
): CrudConfig {
  const customSlots = config.custom_slots.filter(
    (s) => !(s.field === fieldName && s.slot_type === slotType),
  );

  const fields = config.fields.map((f) => {
    if (f.name === fieldName && slotType === 'list') {
      return { ...f, list_slot: null };
    }
    return f;
  });

  return { ...config, custom_slots: customSlots, fields };
}

// ============================================================
// Code generation — slot injection
// ============================================================

/**
 * 生成列表页 bodyCell slot 代码
 * 根据字段的 list_render (preset) 或 custom_slots (自定义) 生成
 */
export function generateListSlotCode(config: CrudConfig): string {
  const lines: string[] = [];

  for (const field of config.fields.filter((f) => f.in_list)) {
    const customSlot = config.custom_slots.find(
      (s) => s.field === field.name && s.slot_type === 'list',
    );

    if (customSlot) {
      lines.push(`          <!-- ${field.name}: custom slot -->`);
      lines.push(`          <template v-if="column.dataIndex === '${field.name}'">`);
      lines.push(`            ${customSlot.template}`);
      lines.push(`          </template>`);
    } else if (field.list_render) {
      const preset = getPresetDefinition(field.list_render);
      if (preset) {
        const template = renderPresetTemplate(preset.codegenTemplate, field.name);
        lines.push(`          <!-- ${field.name}: ${preset.label} preset -->`);
        lines.push(`          <template v-if="column.dataIndex === '${field.name}'">`);
        lines.push(`            ${template}`);
        lines.push(`          </template>`);
      }
    }
  }

  return lines.join('\n');
}

/**
 * 收集列表页需要导入的组件
 */
export function collectListImports(config: CrudConfig): string[] {
  const presets = config.fields
    .filter((f: FieldConfig) => f.in_list && f.list_render)
    .map((f: FieldConfig) => f.list_render);

  const presetImports = collectPresetImports(presets);

  const hasCustomSlots = config.custom_slots.some((s) => s.slot_type === 'list');
  if (hasCustomSlots) {
    // Custom slots may need additional imports — user is responsible
  }

  return presetImports;
}

/**
 * 生成表单页 slot 代码 (form_item 级)
 */
export function generateFormSlotCode(config: CrudConfig): string {
  const lines: string[] = [];

  for (const slot of config.custom_slots.filter((s) => s.slot_type === 'form')) {
    lines.push(`        <!-- ${slot.field}: custom form slot -->`);
    lines.push(`        <template #${slot.field}="{ formModel }">`);
    lines.push(`          ${slot.template}`);
    lines.push(`        </template>`);
  }

  return lines.join('\n');
}
