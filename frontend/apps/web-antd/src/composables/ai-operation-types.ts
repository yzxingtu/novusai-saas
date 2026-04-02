/**
 * AI operation shared field descriptor types
 * AI 操作共享字段描述类型
 */

/** Option item for select/checkbox/radio fields / 选择器可选项 */
export interface AiFieldOption {
  label: string;
  value: unknown;
}

/** Component type enum for AI field descriptors / AI 字段描述的组件类型枚举 */
export type AiFieldComponent =
  | 'custom'
  | 'date'
  | 'icon'
  | 'input'
  | 'number'
  | 'remote_select'
  | 'select'
  | 'switch'
  | 'textarea'
  | 'tree_select';

/**
 * Enhanced form field descriptor — provides complete metadata for AI
 * 增强的表单字段描述 — 为 AI 提供完整元数据
 */
export interface EnhancedFormFieldDescriptor {
  type: 'array' | 'boolean' | 'number' | 'string';
  description: string;
  required?: boolean;
  /** UI component kind / UI 组件种类 */
  component: AiFieldComponent;
  /** Field constraints / 字段约束 */
  constraints?: {
    max?: number;
    maxLength?: number;
    min?: number;
    precision?: number;
  };
  /** Static options (for select/checkbox/radio) / 静态可选项 */
  options?: AiFieldOption[];
  /** Options source type / 选项来源 */
  optionsSource?: 'remote' | 'static';
  /** Default value / 默认值 */
  defaultValue?: unknown;
  /** Placeholder hint / 占位提示 */
  placeholder?: string;
}
