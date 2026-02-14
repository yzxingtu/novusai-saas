/**
 * 模板管理 composable
 *
 * 管理实体/项目模板的 CRUD、套用逻辑、变更预览。
 * 当前版本使用 localStorage 存储（dev-only），后续可对接 Templates API。
 */

import { computed, ref } from 'vue';

import type {
  CrudConfig,
  CrudTemplate,
  EntityTemplatePayload,
  ProjectTemplatePayload,
  TemplateApplyChange,
  TemplateModule,
  TemplateScope,
} from '../types';

const STORAGE_KEY = 'novusai_crud_templates';

function loadFromStorage(): CrudTemplate[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as CrudTemplate[];
  } catch {
    return [];
  }
}

function saveToStorage(templates: CrudTemplate[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(templates));
}

export function useTemplates() {
  const templates = ref<CrudTemplate[]>(loadFromStorage());
  const searchQuery = ref('');

  // ---- Filtered list ----
  const filteredTemplates = computed(() => {
    if (!searchQuery.value) return templates.value;
    const q = searchQuery.value.toLowerCase();
    return templates.value.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        t.description.toLowerCase().includes(q),
    );
  });

  const entityTemplates = computed(() =>
    filteredTemplates.value.filter((t) => t.scope === 'entity'),
  );

  const projectTemplates = computed(() =>
    filteredTemplates.value.filter((t) => t.scope === 'project'),
  );

  // ---- CRUD ----
  function saveTemplate(
    name: string,
    description: string,
    version: string,
    scope: TemplateScope,
    payload: EntityTemplatePayload | ProjectTemplatePayload,
  ): CrudTemplate {
    const now = new Date().toISOString();
    const template: CrudTemplate = {
      id: `tpl_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      name,
      description,
      scope,
      version,
      payload,
      created_at: now,
      updated_at: now,
    };
    templates.value.push(template);
    saveToStorage(templates.value);
    return template;
  }

  function deleteTemplate(id: string) {
    const idx = templates.value.findIndex((t) => t.id === id);
    if (idx >= 0) {
      templates.value.splice(idx, 1);
      saveToStorage(templates.value);
    }
  }

  // ---- Save current entity as template ----
  function saveEntityAsTemplate(
    entity: CrudConfig,
    name: string,
    description: string,
    version: string,
  ): CrudTemplate {
    const payload: EntityTemplatePayload = {
      fields: JSON.parse(JSON.stringify(entity.fields)) as EntityTemplatePayload['fields'],
      enums: JSON.parse(JSON.stringify(entity.enums)) as EntityTemplatePayload['enums'],
      relations: JSON.parse(JSON.stringify(entity.relations)) as EntityTemplatePayload['relations'],
      indexes: JSON.parse(JSON.stringify(entity.indexes)) as EntityTemplatePayload['indexes'],
      list_config: JSON.parse(JSON.stringify(entity.list_config)) as EntityTemplatePayload['list_config'],
      form_groups: entity.form_config?.groups
        ? (JSON.parse(JSON.stringify(entity.form_config.groups)) as EntityTemplatePayload['form_groups'])
        : undefined,
      search_fields: JSON.parse(JSON.stringify(entity.search_config?.fields ?? [])) as EntityTemplatePayload['search_fields'],
      custom_slots: JSON.parse(JSON.stringify(entity.custom_slots)) as EntityTemplatePayload['custom_slots'],
    };
    return saveTemplate(name, description, version, 'entity', payload);
  }

  // ---- Compute apply changes ----
  function computeApplyChanges(
    template: CrudTemplate,
    entity: CrudConfig,
    selectedModules: TemplateModule[],
    lockedPaths: string[],
  ): TemplateApplyChange[] {
    if (template.scope !== 'entity') return [];
    const payload = template.payload as EntityTemplatePayload;
    const changes: TemplateApplyChange[] = [];

    const moduleMap: Record<string, { key: keyof EntityTemplatePayload; entityKey: string }> = {
      fields: { key: 'fields', entityKey: 'fields' },
      enums: { key: 'enums', entityKey: 'enums' },
      relations: { key: 'relations', entityKey: 'relations' },
      indexes: { key: 'indexes', entityKey: 'indexes' },
      list: { key: 'list_config', entityKey: 'list' },
      form: { key: 'form_groups', entityKey: 'form.groups' },
      search: { key: 'search_fields', entityKey: 'search.fields' },
      slots: { key: 'custom_slots', entityKey: 'custom_slots' },
    };

    for (const mod of selectedModules) {
      const mapping = moduleMap[mod];
      if (!mapping) continue;

      const templateData = payload[mapping.key];
      if (!templateData) continue;

      const itemCount = Array.isArray(templateData) ? templateData.length : 1;
      const lockedCount = lockedPaths.filter((p) => p.startsWith(mod)).length;
      const existingData = (entity as unknown as Record<string, unknown>)[mapping.entityKey.split('.')[0] as string];
      const hasExisting = Array.isArray(existingData)
        ? existingData.length > 0
        : !!existingData;

      changes.push({
        module: mod,
        action: lockedCount > 0 ? 'skip' : hasExisting ? 'replace' : 'add',
        itemCount,
        lockedCount,
      });
    }

    return changes;
  }

  // ---- Apply entity template ----
  function applyEntityTemplate(
    template: CrudTemplate,
    entity: CrudConfig,
    selectedModules: TemplateModule[],
    forceUnlock: boolean,
    lockedPaths: string[],
  ): { applied: TemplateModule[]; skipped: TemplateModule[] } {
    if (template.scope !== 'entity') {
      return { applied: [], skipped: [] };
    }

    const payload = template.payload as EntityTemplatePayload;
    const applied: TemplateModule[] = [];
    const skipped: TemplateModule[] = [];

    for (const mod of selectedModules) {
      const isLocked = !forceUnlock && lockedPaths.some((p) => p.startsWith(mod));
      if (isLocked) {
        skipped.push(mod);
        continue;
      }

      switch (mod) {
        case 'fields': {
          if (payload.fields) {
            entity.fields = JSON.parse(JSON.stringify(payload.fields)) as typeof entity.fields;
            applied.push(mod);
          }
          break;
        }
        case 'enums': {
          if (payload.enums) {
            entity.enums = JSON.parse(JSON.stringify(payload.enums)) as typeof entity.enums;
            applied.push(mod);
          }
          break;
        }
        case 'relations': {
          if (payload.relations) {
            entity.relations = JSON.parse(JSON.stringify(payload.relations)) as typeof entity.relations;
            applied.push(mod);
          }
          break;
        }
        case 'indexes': {
          if (payload.indexes) {
            entity.indexes = JSON.parse(JSON.stringify(payload.indexes)) as typeof entity.indexes;
            applied.push(mod);
          }
          break;
        }
        case 'list': {
          if (payload.list_config) {
            entity.list_config = JSON.parse(JSON.stringify(payload.list_config)) as typeof entity.list_config;
            applied.push(mod);
          }
          break;
        }
        case 'form': {
          if (payload.form_groups && entity.form_config) {
            entity.form_config.groups = JSON.parse(JSON.stringify(payload.form_groups)) as typeof entity.form_config.groups;
            applied.push(mod);
          }
          break;
        }
        case 'search': {
          if (payload.search_fields && entity.search_config) {
            entity.search_config.fields = JSON.parse(JSON.stringify(payload.search_fields)) as typeof entity.search_config.fields;
            applied.push(mod);
          }
          break;
        }
        case 'slots': {
          if (payload.custom_slots) {
            entity.custom_slots = JSON.parse(JSON.stringify(payload.custom_slots)) as typeof entity.custom_slots;
            applied.push(mod);
          }
          break;
        }
      }
    }

    return { applied, skipped };
  }

  return {
    templates,
    searchQuery,
    filteredTemplates,
    entityTemplates,
    projectTemplates,
    saveTemplate,
    deleteTemplate,
    saveEntityAsTemplate,
    computeApplyChanges,
    applyEntityTemplate,
  };
}

export type UseTemplatesReturn = ReturnType<typeof useTemplates>;
