/**
 * System configuration module - frontend type definitions
 * 系统配置模块 - 前端类型定义
 */

export type ConfigValueType =
  | 'boolean'
  | 'color'
  | 'file'
  | 'html'
  | 'image'
  | 'json'
  | 'multi_select'
  | 'number'
  | 'password'
  | 'select'
  | 'string'
  | 'tag'
  | 'text';

export type ConfigScalar = boolean | null | number | string;

export interface ConfigObject {
  [key: string]: ConfigValue | undefined;
}

export type ConfigValue = ConfigObject | ConfigScalar | ConfigValue[];

export interface ValidationRuleMeta {
  type:
    | 'max'
    | 'max_length'
    | 'max_value'
    | 'min'
    | 'min_length'
    | 'min_value'
    | 'pattern';
  value: number | string;
  message?: string;
  message_key?: string;
}

export interface ConfigOptionMeta {
  value: string;
  /** Option label (direct text) / 选项标签（直接文本） */
  label?: string;
  /** Option label (translation key) / 选项标签（翻译 key） */
  label_key?: string;
}

/**
 * Display rule operator type
 * 显示规则操作符类型
 */
export type DisplayRuleOperator = 'equals' | 'in';

/**
 * Display rule definition
 * Controls conditional display/hide of config items
 * 显示规则定义
 * 用于控制配置项的条件显示/隐藏
 */
export interface DisplayRuleMeta {
  /** Dependent field key / 依赖字段的 key */
  field: string;
  /** Rule type / 规则类型 */
  operator: DisplayRuleOperator;
  /** Target value (single value for equals, array for in) / 目标值（equals 时为单值，in 时为数组） */
  value: ConfigScalar | ConfigScalar[];
  /** Action (currently fixed to show) / 动作（目前固定为 show） */
  action?: 'show';
}

export interface ConfigItemMeta {
  key: string;
  /** Config item name (direct text) / 配置项名称（直接文本） */
  name?: string;
  /** Config item name (translation key) / 配置项名称（翻译 key） */
  name_key?: string;
  /** Config item description (direct text) / 配置项描述（直接文本） */
  description?: string;
  /** Config item description (translation key) / 配置项描述（翻译 key） */
  description_key?: string;
  value_type: ConfigValueType;
  value?: ConfigValue;
  default_value?: ConfigValue;
  options?: ConfigOptionMeta[];
  validation_rules?: ValidationRuleMeta[];
  is_required?: boolean;
  is_encrypted?: boolean;
  sort_order?: number;
  /** Group code / 所属分组代码 */
  group_code?: string;
  /**
   * Display rules array
   * Multiple rules use AND logic; all must be satisfied to show
   * 显示规则数组
   * 多个规则之间为 AND 关系，全部满足才显示
   */
  display_rules?: DisplayRuleMeta[];
  /**
   * JSON sub-field mapping path
   * Maps sub-field values to parent field's JSON internal path (`.` separated)
   * JSON 子字段映射路径
   * 用于将子字段值映射到父字段 JSON 内部路径（`.` 分隔）
   */
  value_path?: string;
  /**
   * Child fields array
   * Used for structured form rendering of JSON type fields
   * 子字段数组
   * 用于 JSON 类型字段的结构化表单渲染
   */
  children?: ConfigItemMeta[];
  /** Tag separator for tag fields / 标签字段分隔符 */
  tag_separator?: string;
  /** File accept pattern for file fields / 文件字段接受类型 */
  file_accept?: string;
}

export interface ConfigGroupListItemMeta {
  code: string;
  /** Group name (direct text or translation key) / 分组名称（直接文本或翻译 key） */
  name?: string;
  name_key?: string;
  /** Group description (direct text or translation key) / 分组描述（直接文本或翻译 key） */
  description?: string;
  description_key?: string;
  icon?: string;
  sort_order: number;
  config_count: number;
}

export interface ConfigGroupMeta {
  code: string;
  /** Group name (direct text) / 分组名称（直接文本） */
  name?: string;
  /** Group name (translation key) / 分组名称（翻译 key） */
  name_key?: string;
  /** Group description (direct text) / 分组描述（直接文本） */
  description?: string;
  description_key?: string;
  icon?: string;
  sort_order: number;
  configs: ConfigItemMeta[];
}

export type ConfigSubmitPayload = Record<string, unknown>;
