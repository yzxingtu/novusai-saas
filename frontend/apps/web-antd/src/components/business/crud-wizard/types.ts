/**
 * CRUD Wizard — Batch Entity List Panel Types
 *
 * TypeScript interfaces for BatchCrudProject entity management.
 * Mirrors backend app.codegen.schemas.BatchCrudProject structure.
 */

/** Field config (simplified for entity list display) */
export interface EntityFieldConfig {
  name: string;
  type: string;
  label_zh: string;
  label_en: string;
  required?: boolean;
}

/** Cross-entity relation */
export interface EntityRelation {
  source_entity: string;
  target_entity: string;
  relation_type: 'belongs_to' | 'has_many' | 'has_one' | 'many_to_many';
  foreign_key?: string;
  nullable?: boolean;
}

/** Single entity config (simplified for list panel) */
export interface EntityConfig {
  module: string;
  table_name: string;
  display_name: string;
  display_name_en: string;
  scope: 'admin' | 'both' | 'tenant';
  parent_menu: string;
  fields: EntityFieldConfig[];
  enums?: Array<Record<string, unknown>>;
  relations?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

/** Batch CRUD project */
export interface BatchCrudProject {
  project_name: string;
  description?: string;
  entities: EntityConfig[];
  cross_relations?: EntityRelation[];
  shared_enums?: Array<Record<string, unknown>>;
  generation_order?: string[];
}

/** Entity list item (for sidebar display) */
export interface EntityListItem {
  /** Index in entities array */
  index: number;
  module: string;
  display_name: string;
  display_name_en: string;
  field_count: number;
  scope: string;
  /** Whether this entity has validation errors */
  hasError?: boolean;
}

/** Batch preview entity group */
export interface BatchEntityPreview {
  entity_name: string;
  file_count: number;
  files: Array<{
    path: string;
    size: number;
    exists: boolean;
    operation: string;
  }>;
}

/** Batch preview output */
export interface BatchPreviewOutput {
  entities: BatchEntityPreview[];
  shared_files: Array<Record<string, unknown>>;
  total_files: number;
  total_new: number;
  total_conflict: number;
  ddl_preview?: string;
}
