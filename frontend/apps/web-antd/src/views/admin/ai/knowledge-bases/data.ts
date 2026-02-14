/**
 * 平台管理端知识库管理 - 表格列、搜索配置、表单 Schema
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { AdminKnowledgeBaseItem } from '#/api/admin/knowledge-bases';

import type { AIModelInfo } from '#/api/admin/ai';

import { inputField, numberField, searchInput, select, textareaField } from '#/adapter/form';
import { getAIModelListApi } from '#/api/admin/ai';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { $t } from '#/locales';

// ============ Scope 辅助 ============

export function getScopeOptions() {
  return [
    { label: $t('admin.knowledgeBase.scope.tenant'), value: 'tenant' },
    { label: $t('admin.knowledgeBase.scope.global'), value: 'global' },
    { label: $t('admin.knowledgeBase.scope.admin'), value: 'admin' },
  ];
}

export function getScopeColor(scope: string | undefined): string {
  switch (scope) {
    case 'global': return 'blue';
    case 'admin': return 'purple';
    case 'tenant': return 'green';
    default: return 'default';
  }
}

// ============ Embedding 模型下拉 ============

export async function getEmbeddingModelOptions() {
  try {
    const res = await getAIModelListApi({
      'page[size]': 100,
      'filter[type][eq]': 'embedding',
      'filter[is_active][eq]': true,
    });
    return (res.items || []).map((m: AIModelInfo) => ({
      label: `${m.name} (${m.provider_name || '-'})`,
      value: m.id,
    }));
  } catch {
    return [];
  }
}

// ============ 表单默认值 ============

export function getFormDefaults() {
  return {
    name: '',
    description: '',
    scope: 'global',
    tenant_id: null,
    embedding_model_id: undefined,
    chunk_size: 512,
    chunk_overlap: 50,
    chunk_strategy: 'recursive',
    search_mode: 'hybrid',
    top_k: 5,
    score_threshold: 0.5,
  };
}

// ============ 表格列 ============

export function useColumns<T = AdminKnowledgeBaseItem>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'scope',
      title: $t('admin.knowledgeBase.field.scope'),
      width: 110,
      align: 'center',
      slots: { default: 'scope_cell' },
    },
    {
      field: 'tenant_id',
      title: $t('admin.knowledgeBase.field.tenantName'),
      width: 100,
      align: 'center',
    },
    {
      field: 'name',
      title: $t('admin.knowledgeBase.field.name'),
      minWidth: 180,
    },
    {
      field: 'embedding_model_name',
      title: $t('admin.knowledgeBase.field.embeddingModel'),
      width: 180,
    },
    {
      field: 'document_count',
      title: $t('admin.knowledgeBase.field.documentCount'),
      width: 100,
      align: 'center',
    },
    {
      field: 'total_chunks',
      title: $t('admin.knowledgeBase.field.totalChunks'),
      width: 100,
      align: 'center',
    },
    {
      field: 'total_size_bytes',
      title: $t('admin.knowledgeBase.field.totalSizeBytes'),
      width: 120,
      align: 'center',
      slots: { default: 'size_cell' },
    },
    {
      field: 'status',
      title: $t('admin.knowledgeBase.field.status'),
      width: 100,
      align: 'center',
      slots: { default: 'status_cell' },
    },
    {
      field: 'created_at',
      title: $t('admin.knowledgeBase.field.createdAt'),
      width: 170,
      sortable: true,
      slots: { default: 'createdAt_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'ai_knowledge_base',
          nameField: 'name',
          nameTitle: $t('admin.knowledgeBase.field.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: ['edit', 'delete'],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('admin.common.operation'),
      width: 160,
    },
  ];
}

// ============ 搜索表单 ============

export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('name', $t('admin.knowledgeBase.field.name')),
    {
      ...select('filter[scope][eq]', $t('admin.knowledgeBase.field.scope'), {
        options: getScopeOptions(),
      }),
      fieldName: 'filter[scope][eq]',
    },
  ];
}

// ============ 编辑表单 ============

export function useFormSchema(isEdit = false): VbenFormSchema[] {
  const schemas: VbenFormSchema[] = [
    inputField('name', $t('admin.knowledgeBase.field.name'), {
      required: true,
    }),
    textareaField('description', $t('admin.knowledgeBase.field.description'), {
      rows: 3,
    }),
    {
      ...select('scope', $t('admin.knowledgeBase.field.scope'), {
        options: getScopeOptions(),
        required: true,
      }),
    },
    {
      ...select('tenant_id', $t('admin.knowledgeBase.field.tenantId'), {
        api: getTenantSelectApi,
        params: { is_active: 'true' },
        placeholder: $t('admin.knowledgeBase.field.tenantIdPlaceholder'),
      }),
      dependencies: {
        show(values: Record<string, unknown>) {
          return values.scope === 'tenant';
        },
        triggerFields: ['scope'],
      },
    },
    {
      ...select('embedding_model_id', $t('admin.knowledgeBase.field.embeddingModel'), {
        api: getEmbeddingModelOptions,
        required: !isEdit,
      }),
    },
  ];

  if (!isEdit) {
    schemas.push(
      numberField('chunk_size', $t('admin.knowledgeBase.field.chunkSize'), {
        min: 128,
        max: 4096,
      }),
      numberField('chunk_overlap', $t('admin.knowledgeBase.field.chunkOverlap'), {
        min: 0,
        max: 200,
      }),
      numberField('top_k', $t('admin.knowledgeBase.field.topK'), {
        min: 1,
        max: 20,
      }),
      numberField('score_threshold', $t('admin.knowledgeBase.field.scoreThreshold'), {
        min: 0,
        max: 1,
      }),
    );
  }

  return schemas;
}
