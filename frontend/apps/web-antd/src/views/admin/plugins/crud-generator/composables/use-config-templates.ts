/**
 * Config Templates — CrudConfig 模板管理
 *
 * 保存/加载/删除配置模板到 localStorage。
 * 支持: 模板列表、导入导出 JSON、模板覆盖。
 */

import { computed, ref } from 'vue';

import type { CrudConfig } from '../types';

const STORAGE_KEY = 'crud-generator-templates';

export interface ConfigTemplate {
  id: string;
  name: string;
  description: string;
  config: CrudConfig;
  createdAt: string;
  updatedAt: string;
}

function generateId(): string {
  return `tpl_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function loadTemplates(): ConfigTemplate[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as ConfigTemplate[];
  } catch {
    return [];
  }
}

function saveTemplates(templates: ConfigTemplate[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(templates));
}

/**
 * useConfigTemplates — 配置模板管理 composable
 */
export function useConfigTemplates() {
  const templates = ref<ConfigTemplate[]>(loadTemplates());

  const templateOptions = computed(() =>
    templates.value.map((t) => ({
      label: t.name,
      value: t.id,
      description: t.description,
    })),
  );

  function save(name: string, description: string, config: CrudConfig): ConfigTemplate {
    const now = new Date().toISOString();
    const existing = templates.value.find((t) => t.name === name);

    if (existing) {
      existing.config = structuredClone(config);
      existing.description = description;
      existing.updatedAt = now;
      saveTemplates(templates.value);
      return existing;
    }

    const tpl: ConfigTemplate = {
      id: generateId(),
      name,
      description,
      config: structuredClone(config),
      createdAt: now,
      updatedAt: now,
    };
    templates.value.push(tpl);
    saveTemplates(templates.value);
    return tpl;
  }

  function load(id: string): CrudConfig | null {
    const tpl = templates.value.find((t) => t.id === id);
    if (!tpl) return null;
    return structuredClone(tpl.config);
  }

  function remove(id: string): boolean {
    const idx = templates.value.findIndex((t) => t.id === id);
    if (idx < 0) return false;
    templates.value.splice(idx, 1);
    saveTemplates(templates.value);
    return true;
  }

  function rename(id: string, name: string): boolean {
    const tpl = templates.value.find((t) => t.id === id);
    if (!tpl) return false;
    tpl.name = name;
    tpl.updatedAt = new Date().toISOString();
    saveTemplates(templates.value);
    return true;
  }

  function exportTemplate(id: string): string | null {
    const tpl = templates.value.find((t) => t.id === id);
    if (!tpl) return null;
    return JSON.stringify(tpl, null, 2);
  }

  function importTemplate(json: string): ConfigTemplate | null {
    try {
      const tpl = JSON.parse(json) as ConfigTemplate;
      if (!tpl.name || !tpl.config) return null;
      tpl.id = generateId();
      tpl.createdAt = new Date().toISOString();
      tpl.updatedAt = tpl.createdAt;
      templates.value.push(tpl);
      saveTemplates(templates.value);
      return tpl;
    } catch {
      return null;
    }
  }

  function exportAll(): string {
    return JSON.stringify(templates.value, null, 2);
  }

  function importAll(json: string): number {
    try {
      const imported = JSON.parse(json) as ConfigTemplate[];
      if (!Array.isArray(imported)) return 0;
      let count = 0;
      for (const tpl of imported) {
        if (tpl.name && tpl.config) {
          tpl.id = generateId();
          templates.value.push(tpl);
          count++;
        }
      }
      saveTemplates(templates.value);
      return count;
    } catch {
      return 0;
    }
  }

  return {
    templates,
    templateOptions,
    save,
    load,
    remove,
    rename,
    exportTemplate,
    importTemplate,
    exportAll,
    importAll,
  };
}
