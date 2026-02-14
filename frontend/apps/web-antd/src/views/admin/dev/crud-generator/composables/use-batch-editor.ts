/**
 * 多实体批量编辑器 — 状态管理 composable
 *
 * 管理 BatchCrudProject 的实体列表、跨表关联、touchedPaths、校验。
 */

import { computed, ref, watch } from 'vue';

import type {
  BatchCrudProject,
  BatchEditorTab,
  CrudConfig,
  EntityRelation,
  EnumDefinition,
  TouchedPathsMap,
  ValidationIssue,
} from '../types';

import { createDefaultConfig } from './use-crud-config';

// ============================================================
// 默认实体工厂 (reuses createDefaultConfig)
// ============================================================

function createDefaultEntity(module: string, displayName: string): CrudConfig {
  return {
    ...createDefaultConfig(),
    module,
    table_name: `${module.replace(/-/g, '_')}s`,
    display_name: displayName,
    display_name_en: module
      .split('-')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' '),
  };
}

// ============================================================
// Composable
// ============================================================

export function useBatchEditor() {
  // ---- 核心状态 ----
  const projectName = ref('');
  const projectDescription = ref('');
  const entities = ref<CrudConfig[]>([]);
  const crossRelations = ref<EntityRelation[]>([]);
  const sharedEnums = ref<EnumDefinition[]>([]);
  const generationOrder = ref<string[]>([]);

  // ---- 编辑器 UI 状态 ----
  const selectedModule = ref<string>('');
  const activeTab = ref<BatchEditorTab>('basic');
  const searchQuery = ref('');
  const isDirty = ref(false);

  // ---- touchedPaths ----
  const touchedPaths = ref<TouchedPathsMap>({});

  // ---- 校验 ----
  const validationIssues = ref<ValidationIssue[]>([]);

  // ---- 计算属性 ----
  const entityModules = computed(() => entities.value.map((e) => e.module));

  const filteredEntities = computed(() => {
    const q = searchQuery.value.toLowerCase().trim();
    if (!q) return entities.value;
    return entities.value.filter(
      (e) =>
        e.module.toLowerCase().includes(q) ||
        e.display_name.toLowerCase().includes(q),
    );
  });

  const selectedEntity = computed(() =>
    entities.value.find((e) => e.module === selectedModule.value),
  );

  const entityErrorCounts = computed(() => {
    const counts: Record<string, number> = {};
    for (const issue of validationIssues.value) {
      if (issue.severity === 'error') {
        counts[issue.entityModule] = (counts[issue.entityModule] || 0) + 1;
      }
    }
    return counts;
  });

  // ---- 实体操作 ----
  function addEntity(module: string, displayName: string) {
    if (entityModules.value.includes(module)) return;
    entities.value.push(createDefaultEntity(module, displayName));
    generationOrder.value.push(module);
    selectedModule.value = module;
    isDirty.value = true;
  }

  function removeEntity(module: string) {
    entities.value = entities.value.filter((e) => e.module !== module);
    crossRelations.value = crossRelations.value.filter(
      (r) => r.source_entity !== module && r.target_entity !== module,
    );
    generationOrder.value = generationOrder.value.filter((m) => m !== module);
    delete touchedPaths.value[module];

    if (selectedModule.value === module) {
      selectedModule.value = entities.value[0]?.module ?? '';
    }
    isDirty.value = true;
  }

  function selectEntity(module: string) {
    selectedModule.value = module;
  }

  // ---- touchedPaths 操作 ----
  function markTouched(entityModule: string, path: string) {
    if (!touchedPaths.value[entityModule]) {
      touchedPaths.value[entityModule] = new Set();
    }
    touchedPaths.value[entityModule].add(path);
  }

  function unlockPath(entityModule: string, path: string) {
    touchedPaths.value[entityModule]?.delete(path);
  }

  function unlockAllPaths(entityModule: string) {
    delete touchedPaths.value[entityModule];
  }

  function getLockedPaths(entityModule: string): string[] {
    return [...(touchedPaths.value[entityModule] ?? [])];
  }

  // ---- 克隆实体 ----
  interface CloneOptions {
    sourceModule: string;
    newModule: string;
    newTableName: string;
    newDisplayName: string;
    newDisplayNameEn: string;
    includeRelations: boolean;
    includeEnums: boolean;
    includeCrossRelations: boolean;
  }

  function cloneEntity(options: CloneOptions): { success: boolean; error?: string } {
    // Validate unique module
    if (entities.value.some((e) => e.module === options.newModule)) {
      return { success: false, error: 'module_exists' };
    }
    if (entities.value.some((e) => e.table_name === options.newTableName)) {
      return { success: false, error: 'table_exists' };
    }

    const source = entities.value.find((e) => e.module === options.sourceModule);
    if (!source) {
      return { success: false, error: 'source_not_found' };
    }

    // Deep clone fields
    const clonedFields = JSON.parse(JSON.stringify(source.fields)) as typeof source.fields;

    // Optionally clone relations
    const clonedRelations = options.includeRelations
      ? (JSON.parse(JSON.stringify(source.relations)) as typeof source.relations)
      : [];

    // Optionally clone enums
    const clonedEnums = options.includeEnums
      ? (JSON.parse(JSON.stringify(source.enums)) as typeof source.enums)
      : [];

    // Clone indexes
    const clonedIndexes = JSON.parse(JSON.stringify(source.indexes)) as typeof source.indexes;

    const newEntity: CrudConfig = {
      ...JSON.parse(JSON.stringify(source)) as CrudConfig,
      module: options.newModule,
      table_name: options.newTableName,
      display_name: options.newDisplayName,
      display_name_en: options.newDisplayNameEn,
      fields: clonedFields,
      relations: clonedRelations,
      enums: clonedEnums,
      indexes: clonedIndexes,
    };

    entities.value.push(newEntity);
    generationOrder.value.push(options.newModule);

    // Optionally clone cross-relations (with source rebind)
    if (options.includeCrossRelations) {
      const sourceCrossRels = crossRelations.value.filter(
        (r) => r.source_entity === options.sourceModule || r.target_entity === options.sourceModule,
      );
      for (const rel of sourceCrossRels) {
        const clonedRel: EntityRelation = {
          ...rel,
          source_entity: rel.source_entity === options.sourceModule ? options.newModule : rel.source_entity,
          target_entity: rel.target_entity === options.sourceModule ? options.newModule : rel.target_entity,
        };
        crossRelations.value.push(clonedRel);
      }
    }

    // Select the new entity
    selectedModule.value = options.newModule;
    isDirty.value = true;

    return { success: true };
  }

  // ---- 跨表关联 ----
  function addCrossRelation(relation: EntityRelation) {
    crossRelations.value.push(relation);
    isDirty.value = true;
  }

  function removeCrossRelation(index: number) {
    crossRelations.value.splice(index, 1);
    isDirty.value = true;
  }

  // ---- 生成顺序 ----
  function moveEntityOrder(from: number, to: number) {
    const removed = generationOrder.value.splice(from, 1);
    if (removed.length > 0) {
      generationOrder.value.splice(to, 0, removed[0] as string);
      isDirty.value = true;
    }
  }

  // ---- 项目导入/导出 ----
  function loadProject(project: BatchCrudProject) {
    projectName.value = project.project_name;
    projectDescription.value = project.description;
    entities.value = [...project.entities];
    crossRelations.value = [...project.cross_relations];
    sharedEnums.value = [...project.shared_enums];
    generationOrder.value = [...project.generation_order];

    const first = entities.value[0];
    if (first) {
      selectedModule.value = first.module;
    }

    touchedPaths.value = {};
    validationIssues.value = [];
    isDirty.value = false;
  }

  function exportProject(): BatchCrudProject {
    return {
      project_name: projectName.value,
      description: projectDescription.value,
      entities: entities.value,
      cross_relations: crossRelations.value,
      shared_enums: sharedEnums.value,
      generation_order: generationOrder.value,
    };
  }

  // ---- 自动 touchedPaths 记录 ----
  watch(
    entities,
    () => {
      isDirty.value = true;
    },
    { deep: true },
  );

  return {
    // 状态
    projectName,
    projectDescription,
    entities,
    crossRelations,
    sharedEnums,
    generationOrder,

    // UI 状态
    selectedModule,
    activeTab,
    searchQuery,
    isDirty,

    // 计算属性
    entityModules,
    filteredEntities,
    selectedEntity,
    entityErrorCounts,

    // 实体操作
    addEntity,
    removeEntity,
    selectEntity,
    cloneEntity,

    // touchedPaths
    touchedPaths,
    markTouched,
    unlockPath,
    unlockAllPaths,
    getLockedPaths,

    // 跨表关联
    addCrossRelation,
    removeCrossRelation,

    // 生成顺序
    moveEntityOrder,

    // 校验
    validationIssues,

    // 项目级
    loadProject,
    exportProject,
  };
}

export type UseBatchEditorReturn = ReturnType<typeof useBatchEditor>;
