/**
 * ER Diagram — 实体关系图可视化
 *
 * 从 CrudConfig (单表) 或 BatchCrudProject (多表) 生成
 * 实体节点 + 关系连线的数据结构。
 * 可用于 Vue Flow 或其他图形库渲染。
 */

import type {
  BatchCrudProject,
  CrudConfig,
  EntityRelation,
  FieldConfig,
  RelationConfig,
} from '../types';

// ============================================================
// ER Node / Edge types
// ============================================================

export interface ERNode {
  id: string;
  label: string;
  fields: ERField[];
  x: number;
  y: number;
}

export interface ERField {
  name: string;
  type: string;
  isPrimary: boolean;
  isForeign: boolean;
  isRequired: boolean;
}

export interface EREdge {
  id: string;
  source: string;
  target: string;
  sourceField: string;
  targetField: string;
  relationType: string;
  label: string;
}

// ============================================================
// Single entity → ER node
// ============================================================

function configToERNode(config: CrudConfig, x: number, y: number): ERNode {
  const fields: ERField[] = [
    { name: 'id', type: 'integer', isPrimary: true, isForeign: false, isRequired: true },
  ];

  for (const field of config.fields) {
    fields.push({
      name: field.name,
      type: field.type,
      isPrimary: false,
      isForeign: isForeignKey(field),
      isRequired: field.required,
    });
  }

  return {
    id: config.module,
    label: config.display_name || config.module,
    fields,
    x,
    y,
  };
}

function isForeignKey(field: FieldConfig): boolean {
  return field.name.endsWith('_id') && field.type === 'integer';
}

// ============================================================
// Relations → ER edges
// ============================================================

function relationToEREdge(
  relation: RelationConfig,
  sourceModule: string,
): EREdge {
  const labelMap: Record<string, string> = {
    belongs_to: '1:N',
    has_many: '1:N',
    many_to_many: 'M:N',
    self_ref_tree: 'tree',
  };

  return {
    id: `${sourceModule}-${relation.name}`,
    source: sourceModule,
    target: relation.target_model || relation.name,
    sourceField: relation.foreign_key || `${relation.name}_id`,
    targetField: 'id',
    relationType: relation.type,
    label: labelMap[relation.type] || relation.type,
  };
}

function crossRelationToEREdge(relation: EntityRelation): EREdge {
  const labelMap: Record<string, string> = {
    belongs_to: '1:N',
    has_many: '1:N',
    many_to_many: 'M:N',
    self_ref_tree: 'tree',
  };

  return {
    id: `${relation.source_entity}-${relation.target_entity}`,
    source: relation.source_entity,
    target: relation.target_entity,
    sourceField: relation.foreign_key || `${relation.target_entity}_id`,
    targetField: 'id',
    relationType: relation.relation_type,
    label: labelMap[relation.relation_type] || relation.relation_type,
  };
}

// ============================================================
// Build ER diagram from CrudConfig
// ============================================================

/**
 * 从单个 CrudConfig 构建 ER 图数据
 */
export function buildSingleERDiagram(config: CrudConfig): {
  nodes: ERNode[];
  edges: EREdge[];
} {
  const nodes: ERNode[] = [configToERNode(config, 300, 200)];
  const edges: EREdge[] = [];

  for (const relation of config.relations) {
    edges.push(relationToEREdge(relation, config.module));

    // Create a stub node for the related entity
    const targetId = relation.target_model || relation.name;
    if (!nodes.some((n) => n.id === targetId)) {
      nodes.push({
        id: targetId,
        label: targetId,
        fields: [
          { name: 'id', type: 'integer', isPrimary: true, isForeign: false, isRequired: true },
          { name: 'name', type: 'string', isPrimary: false, isForeign: false, isRequired: true },
        ],
        x: 600,
        y: 100 + nodes.length * 200,
      });
    }
  }

  return { nodes, edges };
}

/**
 * 从 BatchCrudProject 构建多表 ER 图
 */
export function buildBatchERDiagram(project: BatchCrudProject): {
  nodes: ERNode[];
  edges: EREdge[];
} {
  const nodes: ERNode[] = [];
  const edges: EREdge[] = [];

  const cols = Math.ceil(Math.sqrt(project.entities.length));

  for (let i = 0; i < project.entities.length; i++) {
    const config = project.entities[i]!;
    const col = i % cols;
    const row = Math.floor(i / cols);
    nodes.push(configToERNode(config, 100 + col * 350, 100 + row * 300));

    for (const relation of config.relations) {
      edges.push(relationToEREdge(relation, config.module));
    }
  }

  for (const relation of project.cross_relations) {
    edges.push(crossRelationToEREdge(relation));
  }

  return { nodes, edges };
}
