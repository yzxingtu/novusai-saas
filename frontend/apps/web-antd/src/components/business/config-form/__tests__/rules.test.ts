// Test type: behavioral
// Verifies: backend config validation metadata is converted into real AntD rules.
// Mock strategy: only the translation function is a deterministic formatter.

import type { ConfigItemMeta } from '#/types/config';

import { describe, expect, it } from 'vitest';

import { convertConfigRules, getValidationRuleNumber } from '../rules';

const translate = (
  key: string,
  params?: Record<string, number | string>,
): string => `${key}:${JSON.stringify(params ?? {})}`;

describe('config form rules', () => {
  it('supports backend min/max aliases and backend message text', () => {
    const cfg: ConfigItemMeta = {
      key: 'tenant_ai_max_capability_items_per_category',
      is_required: true,
      validation_rules: [
        {
          type: 'min',
          value: 1,
          message: '至少 {min} 项',
        },
        {
          type: 'max',
          value: 50,
          message_key: 'shared.config.validation.custom_max',
        },
      ],
      value_type: 'number',
    };

    const rules = convertConfigRules(cfg, {
      fieldName: '每类能力最大条目数',
      translate,
    });

    expect(rules).toMatchObject([
      {
        message:
          'shared.config.validation.required:{"field":"每类能力最大条目数"}',
        required: true,
      },
      {
        message: '至少 1 项',
        min: 1,
        type: 'number',
      },
      {
        max: 50,
        message: 'shared.config.validation.custom_max:{"max":50}',
        type: 'number',
      },
    ]);
    expect(getValidationRuleNumber(cfg, 'min_value')).toBe(1);
    expect(getValidationRuleNumber(cfg, 'max_value')).toBe(50);
  });

  it('keeps pattern and length rules user-visible without message_key', () => {
    const cfg: ConfigItemMeta = {
      key: 'tenant_storage_allowed_extensions',
      validation_rules: [
        {
          type: 'pattern',
          value: '^[a-z,]+$',
        },
        {
          type: 'max_length',
          value: 20,
        },
      ],
      value_type: 'tag',
    };

    const rules = convertConfigRules(cfg, {
      fieldName: '允许扩展名',
      translate,
    });

    expect(rules[0]).toMatchObject({
      message: 'shared.config.validation.pattern:{}',
      pattern: /^[a-z,]+$/,
    });
    expect(rules[1]).toMatchObject({
      max: 20,
      message: 'shared.config.validation.max_length:{"max":20}',
    });
  });
});
