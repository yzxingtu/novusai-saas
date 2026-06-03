/**
 * 企业端知识库管理 - 表格列、搜索配置、表单 Schema、辅助函数
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { KnowledgeBaseItem } from '#/api/tenant/knowledge-bases';

import {
  inputField,
  numberField,
  searchInput,
  select,
  switchField,
  textareaField,
} from '#/adapter/form';
import { getTenantAIModelsApi } from '#/api/tenant/ai';
import { $t } from '#/locales';

// ============ 状态辅助 / status helpers ============

export function getStatusOptions() {
  return [
    { label: $t('tenant.knowledgeBase.status.active'), value: 'active' },
    { label: $t('tenant.knowledgeBase.status.disabled'), value: 'disabled' },
  ];
}

export function getKBStatusText(status: string | undefined): string {
  if (!status) return '-';
  switch (status) {
    case 'active': {
      return $t('tenant.knowledgeBase.status.active');
    }
    case 'disabled': {
      return $t('tenant.knowledgeBase.status.disabled');
    }
    default: {
      return status;
    }
  }
}

export function getKBStatusColor(status: string | undefined): string {
  switch (status) {
    case 'active': {
      return 'success';
    }
    case 'disabled': {
      return 'error';
    }
    default: {
      return 'default';
    }
  }
}

export function getDocStatusText(status: string | undefined): string {
  if (!status) return '-';
  const key = `tenant.knowledgeBase.document.status.${status}`;
  return $t(key);
}

export function getDocStatusColor(status: string | undefined): string {
  switch (status) {
    case 'chunking':
    case 'embedding':
    case 'parsing': {
      return 'processing';
    }
    case 'completed': {
      return 'success';
    }
    case 'error': {
      return 'error';
    }
    case 'pending': {
      return 'default';
    }
    default: {
      return 'default';
    }
  }
}

// ============ Embedding / Vision 模型下拉 / embedding & vision model select ============

async function getEmbeddingModelOptions() {
  try {
    const models = await getTenantAIModelsApi();
    return models
      .filter((m) => m.type === 'embedding')
      .map((m) => ({
        label: `${m.name} (${m.provider_name || '-'})`,
        value: m.id,
      }));
  } catch {
    return [];
  }
}

async function getTenantVisionModelOptions() {
  try {
    const models = await getTenantAIModelsApi();
    const visionModels = models
      .filter((m) => m.type === 'chat' && m.supports_vision)
      .map((m) => ({
        label: `${m.name} (${m.provider_name || '-'})`,
        value: m.id,
      }));
    return [
      { label: $t('tenant.knowledgeBase.field.visionModelAuto'), value: null },
      ...visionModels,
    ];
  } catch {
    return [
      { label: $t('tenant.knowledgeBase.field.visionModelAuto'), value: null },
    ];
  }
}

// ============ 分块策略 / Chunking & retrieval mode ============

function getChunkStrategyOptions() {
  return [
    {
      label: $t('tenant.knowledgeBase.field.chunkStrategyRecursive'),
      value: 'recursive',
    },
    {
      label: $t('tenant.knowledgeBase.field.chunkStrategySentence'),
      value: 'sentence',
    },
    {
      label: $t('tenant.knowledgeBase.field.chunkStrategySemantic'),
      value: 'semantic',
    },
    {
      label: $t('tenant.knowledgeBase.field.chunkStrategyParagraph'),
      value: 'paragraph',
    },
  ];
}

export function getSearchModeOptions() {
  return [
    {
      label: $t('tenant.knowledgeBase.field.searchModeHybrid'),
      value: 'hybrid',
    },
    {
      label: $t('tenant.knowledgeBase.field.searchModeVector'),
      value: 'vector',
    },
    {
      label: $t('tenant.knowledgeBase.field.searchModeKeyword'),
      value: 'keyword',
    },
  ];
}

export function isTenantOwnedKnowledgeBase(tenantId: null | number): boolean {
  return tenantId !== null;
}

// ============ 表格列 / table columns ============

export function useColumns<T = KnowledgeBaseItem>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'name',
      title: $t('tenant.knowledgeBase.field.name'),
      minWidth: 180,
      slots: { default: 'name_cell' },
    },
    {
      field: 'status',
      title: $t('tenant.knowledgeBase.field.status'),
      width: 100,
      align: 'center',
      slots: { default: 'status_cell' },
    },
    {
      field: 'embedding_model_name',
      title: $t('tenant.knowledgeBase.field.embeddingModel'),
      width: 200,
      slots: { default: 'model_cell' },
    },
    {
      field: 'document_count',
      title: $t('tenant.knowledgeBase.field.documentCount'),
      width: 100,
      align: 'center',
    },
    {
      field: 'total_chunks',
      title: $t('tenant.knowledgeBase.field.totalChunks'),
      width: 100,
      align: 'center',
    },
    {
      field: 'total_size_bytes',
      title: $t('tenant.knowledgeBase.field.totalSizeBytes'),
      width: 120,
      align: 'center',
      slots: { default: 'size_cell' },
    },
    {
      field: 'description',
      title: $t('tenant.knowledgeBase.field.description'),
      minWidth: 180,
      slots: { default: 'desc_cell' },
    },
    {
      field: 'created_at',
      title: $t('tenant.common.createdAt'),
      width: 170,
      sortable: true,
      slots: { default: 'createdAt_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'knowledge_base',
          nameField: 'name',
          nameTitle: $t('tenant.knowledgeBase.field.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'detail',
            text: $t('tenant.knowledgeBase.detail'),
            icon: 'lucide:eye',
            accessCodes: ['knowledge_base:detail'],
          },
          {
            code: 'edit',
            show: (row: KnowledgeBaseItem) =>
              isTenantOwnedKnowledgeBase(row.tenant_id),
          },
          {
            code: 'delete',
            show: (row: KnowledgeBaseItem) =>
              isTenantOwnedKnowledgeBase(row.tenant_id),
          },
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('tenant.common.operation'),
      width: 220,
    },
  ];
}

// ============ 搜索表单 / search form ============

export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('name', $t('tenant.knowledgeBase.field.name'), {
      placeholder: $t('tenant.knowledgeBase.search'),
    }),
  ];
}

// ============ 编辑表单 / edit form ============

export function useFormSchema(): VbenFormSchema[] {
  return [
    inputField('name', $t('tenant.knowledgeBase.field.name'), {
      required: true,
    }),
    textareaField('description', $t('tenant.knowledgeBase.field.description'), {
      rows: 3,
    }),
    {
      ...select(
        'embedding_model_id',
        $t('tenant.knowledgeBase.field.embeddingModel'),
        {
          api: getEmbeddingModelOptions,
          required: true,
        },
      ),
      help: $t('tenant.knowledgeBase.help.embeddingModel'),
    },
    {
      ...select(
        'vision_model_id',
        $t('tenant.knowledgeBase.field.visionModel'),
        {
          api: getTenantVisionModelOptions,
          required: false,
        },
      ),
      help: $t('tenant.knowledgeBase.help.visionModel'),
    },
    {
      ...switchField(
        'extract_images',
        $t('tenant.knowledgeBase.field.extractImages'),
      ),
      help: $t('tenant.knowledgeBase.help.extractImages'),
    },
    {
      ...numberField('chunk_size', $t('tenant.knowledgeBase.field.chunkSize'), {
        min: 128,
        max: 4096,
        defaultValue: 512,
      }),
      help: $t('tenant.knowledgeBase.help.chunkSize'),
    },
    {
      ...numberField(
        'chunk_overlap',
        $t('tenant.knowledgeBase.field.chunkOverlap'),
        {
          min: 0,
          max: 200,
          defaultValue: 50,
        },
      ),
      help: $t('tenant.knowledgeBase.help.chunkOverlap'),
    },
    {
      ...select(
        'chunk_strategy',
        $t('tenant.knowledgeBase.field.chunkStrategy'),
        {
          options: getChunkStrategyOptions(),
        },
      ),
      defaultValue: 'recursive',
      help: $t('tenant.knowledgeBase.help.chunkStrategy'),
    },
  ];
}
