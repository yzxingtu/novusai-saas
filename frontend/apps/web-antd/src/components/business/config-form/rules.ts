import type { Rule } from 'ant-design-vue/es/form';

import type { ConfigItemMeta, ValidationRuleMeta } from '#/types/config';

type TranslateFn = (
  key: string,
  params?: Record<string, number | string>,
) => string;

type NormalizedRuleType =
  | 'max_length'
  | 'max_value'
  | 'min_length'
  | 'min_value'
  | 'pattern';

const RULE_TYPE_ALIASES: Record<string, NormalizedRuleType> = {
  max: 'max_value',
  max_length: 'max_length',
  max_value: 'max_value',
  min: 'min_value',
  min_length: 'min_length',
  min_value: 'min_value',
  pattern: 'pattern',
};

function normalizeRuleType(type: string): NormalizedRuleType | undefined {
  return RULE_TYPE_ALIASES[type];
}

function formatTemplate(
  template: string,
  params: Record<string, number | string>,
): string {
  return template.replaceAll(/\{(\w+)\}/g, (_, key: string) =>
    String(params[key] ?? ''),
  );
}

function getRuleMessage(
  rule: ValidationRuleMeta,
  fallbackKey: string,
  params: Record<string, number | string>,
  translate: TranslateFn,
): string {
  if (rule.message) {
    return formatTemplate(rule.message, params);
  }
  if (rule.message_key) {
    return translate(rule.message_key, params);
  }
  return translate(fallbackKey, params);
}

export function convertConfigRules(
  cfg: ConfigItemMeta,
  options: {
    fieldName: string;
    translate: TranslateFn;
  },
): Rule[] {
  const rules: Rule[] = [];
  const { fieldName, translate } = options;
  if (cfg.is_required) {
    rules.push({
      required: true,
      message: translate('shared.config.validation.required', {
        field: fieldName,
      }),
    });
  }

  (cfg.validation_rules || []).forEach((rule) => {
    const ruleType = normalizeRuleType(rule.type);
    switch (ruleType) {
      case 'max_length': {
        rules.push({
          max: Number(rule.value),
          message: getRuleMessage(
            rule,
            'shared.config.validation.max_length',
            { max: rule.value },
            translate,
          ),
        });
        break;
      }
      case 'max_value': {
        rules.push({
          type: 'number',
          max: Number(rule.value),
          message: getRuleMessage(
            rule,
            'shared.config.validation.max_value',
            { max: rule.value },
            translate,
          ),
        });
        break;
      }
      case 'min_length': {
        rules.push({
          min: Number(rule.value),
          message: getRuleMessage(
            rule,
            'shared.config.validation.min_length',
            { min: rule.value },
            translate,
          ),
        });
        break;
      }
      case 'min_value': {
        rules.push({
          type: 'number',
          min: Number(rule.value),
          message: getRuleMessage(
            rule,
            'shared.config.validation.min_value',
            { min: rule.value },
            translate,
          ),
        });
        break;
      }
      case 'pattern': {
        rules.push({
          pattern: new RegExp(String(rule.value)),
          message: getRuleMessage(
            rule,
            'shared.config.validation.pattern',
            {},
            translate,
          ),
        });
        break;
      }
    }
  });
  return rules;
}

export function getValidationRuleNumber(
  cfg: ConfigItemMeta,
  type: 'max_value' | 'min_value',
): number | undefined {
  const aliases =
    type === 'min_value' ? new Set(['min', type]) : new Set(['max', type]);
  const rule = (cfg.validation_rules || []).find((item) =>
    aliases.has(item.type),
  );
  return rule ? Number(rule.value) : undefined;
}
