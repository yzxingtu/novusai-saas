/**
 * useProjectGraph — Project knowledge graph composable
 *
 * Fetches model metadata from GET /admin/dev/crud/project-graph
 * and caches within page lifecycle. Provides getModelOptions() for Select.
 */

import { ref } from 'vue';

import { requestClient } from '#/utils/request';

export interface GraphColumn {
  name: string;
  type: string;
  nullable: boolean;
  comment: string | null;
  foreign_key: string | null;
}

export interface GraphRelation {
  name: string;
  target: string;
  type: string;
}

export interface GraphModel {
  class_name: string;
  table_name: string;
  base_class: string;
  columns: GraphColumn[];
  relations: GraphRelation[];
  filterable: string[];
  sortable: string[];
}

interface ProjectGraphResponse {
  data: {
    models: Record<string, GraphModel>;
    total: number;
    summary: string;
  };
}

const cachedModels = ref<Record<string, GraphModel>>({});
const cachedSummary = ref('');
const loaded = ref(false);
const loading = ref(false);
const loadError = ref<string | null>(null);

export function useProjectGraph() {
  async function loadGraph(refresh = false) {
    if (loaded.value && !refresh) return;
    if (loading.value) return;

    loading.value = true;
    loadError.value = null;
    try {
      const res = await requestClient.get<ProjectGraphResponse['data']>(
        '/admin/dev/crud/project-graph',
        { params: refresh ? { refresh: true } : {} },
      );
      cachedModels.value = res.models;
      cachedSummary.value = res.summary;
      loaded.value = true;
    } catch (err) {
      loadError.value = String(err);
    } finally {
      loading.value = false;
    }
  }

  function getModelOptions(): Array<{ label: string; value: string }> {
    return Object.entries(cachedModels.value).map(([key, model]) => ({
      label: `${model.class_name} (${model.table_name})`,
      value: key,
    }));
  }

  function getTableNames(): string[] {
    return Object.values(cachedModels.value).map((m) => m.table_name);
  }

  function getModel(key: string): GraphModel | undefined {
    return cachedModels.value[key];
  }

  return {
    models: cachedModels,
    summary: cachedSummary,
    loading,
    loaded,
    loadError,
    loadGraph,
    getModelOptions,
    getTableNames,
    getModel,
  };
}
