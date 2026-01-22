/**
 * 系统配置模块 - 前端类型定义
 */

export type ConfigValueType =
  | 'boolean'
  | 'color'
  | 'image'
  | 'json'
  | 'multi_select'
  | 'number'
  | 'password'
  | 'select'
  | 'string'
  | 'text';

export interface ValidationRuleMeta {
  type: 'max_length' | 'max_value' | 'min_length' | 'min_value' | 'pattern';
  value: number | string;
  message_key: string;
}

export interface ConfigOptionMeta {
  value: string;
  /** 选项标签（直接文本） */
  label?: string;
  /** 选项标签（翻译 key） */
  label_key?: string;
}

export interface ConfigItemMeta {
  key: string;
  /** 配置项名称（直接文本） */
  name?: string;
  /** 配置项名称（翻译 key） */
  name_key?: string;
  /** 配置项描述（直接文本） */
  description?: string;
  /** 配置项描述（翻译 key） */
  description_key?: string;
  value_type: ConfigValueType;
  value?: any;
  default_value?: any;
  options?: ConfigOptionMeta[];
  validation_rules?: ValidationRuleMeta[];
  is_required?: boolean;
  is_encrypted?: boolean;
  sort_order?: number;
}

export interface ConfigGroupListItemMeta {
  code: string;
  /** 分组名称（直接文本或翻译 key） */
  name?: string;
  name_key?: string;
  /** 分组描述（直接文本或翻译 key） */
  description?: string;
  description_key?: string;
  icon?: string;
  sort_order: number;
  config_count: number;
}

export interface ConfigGroupMeta {
  code: string;
  name_key: string;
  description_key?: string;
  icon?: string;
  sort_order: number;
  configs: ConfigItemMeta[];
}

export type ConfigSubmitPayload = Record<string, any>;
