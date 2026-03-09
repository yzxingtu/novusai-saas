/**
 * 平台管理端知识库管理 - 表格列、搜索配置、表单 Schema
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { AIModelInfo } from '#/api/admin/ai';
import type { AdminKnowledgeBaseItem } from '#/api/admin/knowledge-bases';

import {
  inputField,
  numberField,
  searchInput,
  select,
  switchField,
  textareaField,
} from '#/adapter/form';
import { getAIModelListApi } from '#/api/admin/ai';
import { useScopeFields } from '#/components/business/scope-select';
import { $t } from '#/locales';
import {
  getScopeOptions as _getScopeOptions,
  getScopeColor,
  getScopeText,
} from '#/utils/scope-helpers';

export { getScopeColor, getScopeText };

// ============ Scope 辅助 ============

export function getScopeOptions() {
  return _getScopeOptions();
}

export function getVisibilityOptions() {
  return [
    { label: $t('admin.knowledgeBase.visibility.private'), value: 'private' },
    {
      label: $t('admin.knowledgeBase.visibility.all_tenants'),
      value: 'all_tenants',
    },
    { label: $t('admin.knowledgeBase.visibility.assigned'), value: 'assigned' },
  ];
}

// ============ Embedding / Vision 模型下拉 ============

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

export async function getVisionModelOptions() {
  try {
    const res = await getAIModelListApi({
      'page[size]': 100,
      'filter[type][eq]': 'chat',
      'filter[is_active][eq]': true,
      'filter[supports_vision][eq]': true,
    });
    return [
      { label: $t('admin.knowledgeBase.field.visionModelAuto'), value: null },
      ...(res.items || []).map((m: AIModelInfo) => ({
        label: `${m.name} (${m.provider_name || '-'})`,
        value: m.id,
      })),
    ];
  } catch {
    return [
      { label: $t('admin.knowledgeBase.field.visionModelAuto'), value: null },
    ];
  }
}

// ============ 表单默认值 ============

export function getFormDefaults() {
  return {
    name: '',
    description: '',
    scope: 'admin_and_all',
    tenant_id: null,
    tenant_ids: [],
    embedding_model_id: undefined,
    vision_model_id: null,
    extract_images: false,
    chunk_size: 512,
    chunk_overlap: 50,
    chunk_strategy: 'recursive',
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
      slots: { default: 'name_cell' },
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
        options: [{ code: 'detail', accessCodes: [] }, 'edit', 'delete'],
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
    ...useScopeFields({
      scopeHelp: $t('admin.knowledgeBase.help.scope'),
    }),
    {
      ...select(
        'embedding_model_id',
        $t('admin.knowledgeBase.field.embeddingModel'),
        {
          api: getEmbeddingModelOptions,
          required: !isEdit,
        },
      ),
      help: $t('admin.knowledgeBase.help.embeddingModel'),
    },
    {
      ...select(
        'vision_model_id',
        $t('admin.knowledgeBase.field.visionModel'),
        {
          api: getVisionModelOptions,
          required: false,
        },
      ),
      help: $t('admin.knowledgeBase.help.visionModel'),
    },
    {
      ...switchField(
        'extract_images',
        $t('admin.knowledgeBase.field.extractImages'),
      ),
      help: $t('admin.knowledgeBase.help.extractImages'),
    },
  ];

  if (!isEdit) {
    schemas.push(
      {
        ...numberField(
          'chunk_size',
          $t('admin.knowledgeBase.field.chunkSize'),
          {
            min: 128,
            max: 4096,
          },
        ),
        help: $t('admin.knowledgeBase.help.chunkSize'),
      },
      {
        ...numberField(
          'chunk_overlap',
          $t('admin.knowledgeBase.field.chunkOverlap'),
          {
            min: 0,
            max: 200,
          },
        ),
        help: $t('admin.knowledgeBase.help.chunkOverlap'),
      },
    );
  }

  return schemas;
}
