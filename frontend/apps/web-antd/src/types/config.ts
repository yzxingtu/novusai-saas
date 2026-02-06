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

/**
 * 显示规则操作符类型
 */
export type DisplayRuleOperator = 'equals' | 'in';

/**
 * 显示规则定义
 * 用于控制配置项的条件显示/隐藏
 */
export interface DisplayRuleMeta {
  /** 依赖字段的 key */
  field: string;
  /** 规则类型 */
  operator: DisplayRuleOperator;
  /** 目标值（equals 时为单值，in 时为数组） */
  value: any;
  /** 动作（目前固定为 show） */
  action?: 'show';
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
  /** 所属分组代码 */
  group_code?: string;
  /**
   * 显示规则数组
   * 多个规则之间为 AND 关系，全部满足才显示
   */
  display_rules?: DisplayRuleMeta[];
  /**
   * JSON 子字段映射路径
   * 用于将子字段值映射到父字段 JSON 内部路径（`.` 分隔）
   */
  value_path?: string;
  /**
   * 子字段数组
   * 用于 JSON 类型字段的结构化表单渲染
   */
  children?: ConfigItemMeta[];
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
