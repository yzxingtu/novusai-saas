/**
 * CRUD Generator — TypeScript 类型定义
 *
 * 与后端 app/codegen/schemas.py 完全对应。
 * 前端使用 camelCase，通过 fields 映射转换为后端 snake_case。
 */

// ============================================================
// 基础枚举
// ============================================================

export type FieldType =
  | 'string'
  | 'text'
  | 'integer'
  | 'float'
  | 'decimal'
  | 'boolean'
  | 'datetime'
  | 'date'
  | 'json'
  | 'enum'
  | 'file';

export type RelationType =
  | 'belongs_to'
  | 'has_many'
  | 'many_to_many'
  | 'self_ref_tree';

export type LayoutVariant =
  | 'standard'
  | 'card_list'
  | 'master_detail'
  | 'tree_table'
  | 'kanban'
  | 'timeline';

export type ListRenderPreset =
  | 'tag'
  | 'switch'
  | 'money'
  | 'percent'
  | 'relative_time'
  | 'datetime'
  | 'date'
  | 'avatar'
  | 'image'
  | 'link'
  | 'copy'
  | 'progress'
  | 'ellipsis'
  | 'badge'
  | 'icon'
  | 'color';

export type ScopeType = 'admin' | 'tenant' | 'both';

export type FormType = 'drawer' | 'modal';

export type SearchOperator =
  | 'ilike'
  | 'eq'
  | 'in'
  | 'gte'
  | 'lte'
  | 'between';

export type SearchComponent =
  | 'Input'
  | 'Select'
  | 'DatePicker'
  | 'RangePicker'
  | 'InputNumber'
  | 'ApiSelect'
  | 'TreeSelect';

export type FormComponent =
  | 'Input'
  | 'InputNumber'
  | 'Textarea'
  | 'Select'
  | 'Switch'
  | 'DatePicker'
  | 'RangePicker'
  | 'RadioGroup'
  | 'CheckboxGroup'
  | 'Upload'
  | 'ApiSelect'
  | 'ApiTreeSelect'
  | 'Cascader'
  | 'Rate'
  | 'Slider'
  | 'ColorPicker'
  | 'JsonEditor'
  | 'RichText';

export type LogicNodeType =
  | 'validate'
  | 'transform'
  | 'compute'
  | 'condition'
  | 'query'
  | 'notify'
  | 'assign'
  | 'loop'
  | 'error'
  | 'exception'
  | 'log'
  | 'call_service';

// ============================================================
// 原子配置块
// ============================================================

export interface EnumOption {
  value: string;
  label_zh: string;
  label_en: string;
  color?: string | null;
  icon?: string | null;
}

export interface StateTransition {
  from_state: string;
  to_state: string;
  action: string;
  label_zh: string;
  label_en: string;
  confirm: boolean;
  permission?: string | null;
}

export interface EnumDefinition {
  name: string;
  description: string;
  values: EnumOption[];
  transitions?: StateTransition[] | null;
}

export interface ValidationRule {
  type: string;
  value?: unknown;
  message_zh?: string | null;
  message_en?: string | null;
}

export interface FormDependency {
  field: string;
  condition: string;
  value?: unknown;
  values?: unknown[] | null;
}

export interface UploadFieldConfig {
  upload_type: string;
  accept: string;
  max_size_mb: number;
  max_count: number;
  storage: string;
}

// ============================================================
// 字段配置
// ============================================================

export interface FieldConfig {
  // 基础
  name: string;
  type: FieldType;
  label_zh: string;
  label_en: string;

  // 数据库约束
  required: boolean;
  nullable: boolean;
  unique: boolean;
  max_length?: number | null;
  default?: unknown;
  index: boolean;

  // 枚举
  enum_ref?: string | null;
  enum_values?: EnumOption[] | null;

  // 关联
  relation_ref?: string | null;

  // JSON:API 查询
  filterable: boolean;
  sortable: boolean;

  // 搜索
  searchable: boolean;
  search_op: SearchOperator;

  // 列表
  in_list: boolean;
  list_width?: number | null;
  list_align: string;
  list_render?: ListRenderPreset | null;
  list_slot?: string | null;
  list_fixed?: string | null;
  list_sortable: boolean;

  // 表单
  in_form: boolean;
  form_component: FormComponent;
  form_group?: string | null;
  form_placeholder?: string | null;
  form_rules?: ValidationRule[] | null;
  form_depends_on?: FormDependency | null;
  form_col_span?: number | null;
  form_help?: string | null;

  // 文件上传
  upload?: UploadFieldConfig | null;
}

// ============================================================
// 关联关系
// ============================================================

export interface RelationConfig {
  name: string;
  type: RelationType;
  target_model: string;
  target_table: string;
  foreign_key?: string | null;
  pivot_table?: string | null;
  cascade_delete: boolean;
  label_field: string;
  nullable: boolean;
  comment_zh: string;
  comment_en: string;
}

// ============================================================
// 搜索配置
// ============================================================

export interface SearchFieldConfig {
  field: string;
  operator: SearchOperator;
  component: SearchComponent;
  placeholder_zh?: string | null;
  placeholder_en?: string | null;
  api?: string | null;
  options_enum?: string | null;
  default_value?: unknown;
  col_span: number;
}

export interface SearchConfig {
  fields: SearchFieldConfig[];
  collapsed: boolean;
  max_visible: number;
}

// ============================================================
// 列表 & 表单配置
// ============================================================

export interface ListConfig {
  show_checkbox: boolean;
  show_index: boolean;
  default_sort: string;
  row_height: number;
  stripe: boolean;
  pager: boolean;
  toolbar_export: boolean;
  toolbar_search: boolean;
}

export interface FormGroup {
  title_zh: string;
  title_en: string;
  fields: string[];
  collapsible: boolean;
  default_collapsed: boolean;
}

export interface FormConfig {
  drawer_width: string;
  form_type: FormType;
  groups?: FormGroup[] | null;
  columns: number;
  label_width: number;
}

// ============================================================
// 下拉选项
// ============================================================

export interface TreeSelectConfig {
  parent_field: string;
  children_field: string;
  order_by: string;
}

export interface SelectableConfig {
  label_field: string;
  value_field: string;
  search_fields: string[];
  extra_fields: string[];
  tree?: TreeSelectConfig | null;
}

// ============================================================
// 复合索引 & 权限 & 导入导出
// ============================================================

export interface IndexConfig {
  name?: string | null;
  fields: string[];
  unique: boolean;
}

export interface PermissionAction {
  code: string;
  label_zh: string;
  label_en: string;
}

export interface PermissionConfig {
  resource_code?: string | null;
  actions: string[];
  extra_actions?: PermissionAction[] | null;
  menu_icon: string;
  menu_sort_order: number;
}

export interface BatchAction {
  code: string;
  label_zh: string;
  label_en: string;
  icon?: string | null;
  confirm: boolean;
  permission?: string | null;
}

export interface ImportExportConfig {
  enable_export: boolean;
  enable_import: boolean;
  export_fields?: string[] | null;
  import_fields?: string[] | null;
  import_template: boolean;
  batch_delete: boolean;
  batch_status: boolean;
  batch_custom?: BatchAction[] | null;
}

// ============================================================
// 自定义 Slot & 布局 & 样式 & 动画
// ============================================================

export interface CustomSlotConfig {
  field: string;
  slot_type: string;
  template: string;
  description: string;
  ai_generated: boolean;
}

export interface LayoutConfig {
  variant: LayoutVariant;
  card_fields?: string[] | null;
  card_cover_field?: string | null;
  card_columns: number;
  detail_position: string;
  detail_width: string;
  kanban_group_field?: string | null;
  timeline_date_field?: string | null;
}

export interface StyleConfig {
  primary_color?: string | null;
  compact: boolean;
  bordered: boolean;
  rounded: boolean;
  header_sticky: boolean;
  custom_css?: string | null;
}

export interface AnimationConfig {
  row_enter: boolean;
  drawer_transition: boolean;
  status_transition: boolean;
  skeleton_loading: boolean;
}

// ============================================================
// Git & 审计 & 测试 & 行内编辑 & 可观测性
// ============================================================

export interface GitConfig {
  auto_branch: boolean;
  auto_commit: boolean;
  commit_message_template: string;
}

export interface AuditConfig {
  enable: boolean;
  log_fields?: string[] | null;
  sensitive_fields: string[];
}

export interface TestScaffoldConfig {
  generate_unit_tests: boolean;
  generate_api_tests: boolean;
  test_data_count: number;
  custom_fixtures: string[];
}

export interface InlineEditConfig {
  enable: boolean;
  editable_fields: string[];
  save_mode: string;
  debounce_ms: number;
}

export interface ObservabilityConfig {
  enable_metrics: boolean;
  enable_tracing: boolean;
  slow_query_threshold_ms: number;
  custom_tags: Record<string, string>;
}

export interface NLQueryConfig {
  enable: boolean;
  query_fields: string[];
  example_queries_zh: string[];
  example_queries_en: string[];
}

// ============================================================
// 逻辑编排
// ============================================================

export interface LogicNode {
  id: string;
  type: LogicNodeType;
  label: string;
  config: Record<string, unknown>;
  next_nodes: string[];
  condition_branches?: Record<string, string> | null;
}

export interface LogicFlow {
  hook: string;
  nodes: LogicNode[];
  entry_node_id?: string | null;
  description: string;
}

// ============================================================
// 顶层配置: CrudConfig
// ============================================================

export interface CrudConfig {
  // Step 1: 基本信息
  module: string;
  table_name: string;
  display_name: string;
  display_name_en: string;
  scope: ScopeType;
  parent_menu: string;
  description: string;

  // 选项
  soft_delete: boolean;
  drag_sort: boolean;
  has_status_toggle: boolean;
  recyclable: boolean;

  // Step 2: 字段
  fields: FieldConfig[];

  // 关联
  relations: RelationConfig[];

  // 搜索
  search_config?: SearchConfig | null;

  // 枚举
  enums: EnumDefinition[];

  // Step 3: 列表
  list_config: ListConfig;

  // Step 4: 表单
  form_config: FormConfig;

  // 操作列
  operations: string[];

  // 下拉选项
  selectable?: SelectableConfig | null;

  // 复合索引
  indexes: IndexConfig[];

  // 导入导出
  import_export?: ImportExportConfig | null;

  // 权限
  permissions?: PermissionConfig | null;

  // Hooks
  hooks: string[];

  // 自定义 Slot
  custom_slots: CustomSlotConfig[];

  // 布局
  layout: LayoutConfig;

  // 样式
  style: StyleConfig;

  // 动画
  animation: AnimationConfig;

  // Git
  git: GitConfig;

  // 审计
  audit: AuditConfig;

  // 测试
  test: TestScaffoldConfig;

  // 行内编辑
  inline_edit: InlineEditConfig;

  // 可观测性
  observability: ObservabilityConfig;

  // 自然语言查询
  nl_query: NLQueryConfig;

  // 逻辑编排
  logic_flows: LogicFlow[];
}

// ============================================================
// Wizard 状态
// ============================================================

export type WizardStep = 0 | 1 | 2 | 3 | 4;

export interface StepWarning {
  step: WizardStep;
  field?: string;
  message: string;
  severity: 'error' | 'info' | 'warning';
}

export interface WizardState {
  currentStep: WizardStep;
  config: CrudConfig;
  isDirty: boolean;
  isGenerating: boolean;
}

// ============================================================
// 模板系统
// ============================================================

export type TemplateModule =
  | 'fields'
  | 'enums'
  | 'relations'
  | 'indexes'
  | 'list'
  | 'form'
  | 'search'
  | 'slots';

export interface EntityTemplatePayload {
  fields?: FieldConfig[];
  enums?: EnumDefinition[];
  relations?: RelationConfig[];
  indexes?: IndexConfig[];
  list_config?: ListConfig;
  form_groups?: FormGroup[];
  search_fields?: SearchFieldConfig[];
  custom_slots?: CustomSlotConfig[];
}

export interface CrudTemplate {
  id: string;
  name: string;
  description: string;
  version: string;
  payload: EntityTemplatePayload;
  created_at: string;
  updated_at: string;
}

export interface TemplateApplyChange {
  module: TemplateModule;
  action: 'add' | 'replace' | 'skip';
  itemCount: number;
  lockedCount: number;
}
