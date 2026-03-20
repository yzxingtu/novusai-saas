/**
 * Knowledge base management — search config, form schema
 * 平台管理端知识库管理 — 搜索配置、表单 Schema
 */
import type { VbenFormSchema } from '#/adapter/form';

import {
  inputField,
  numberField,
  searchInput,
  select,
  switchField,
  textareaField,
} from '#/adapter/form';
import { getAIModelSelectApi } from '#/api/admin/ai';
import { useScopeFields } from '#/components/business/scope-select';
import { $t } from '#/locales';
import {
  getScopeOptions as _getScopeOptions,
  getScopeColor,
  getScopeText,
} from '#/utils/scope-helpers';

export { getScopeColor, getScopeText };

// ============ Scope helpers / Scope 辅助 ============

export function getScopeOptions() {
  return _getScopeOptions();
}

// ============ Embedding / Vision 模型下拉 ============

export function getEmbeddingModelSelectApi(params?: Record<string, unknown>) {
  return getAIModelSelectApi({ ...params, type: 'embedding' });
}

export async function getVisionModelSelectApi(
  params?: Record<string, unknown>,
) {
  const res = await getAIModelSelectApi({
    ...params,
    type: 'chat',
    supports_vision: 'true',
  });
  if (res?.items && (!params?.page || Number(params.page) <= 1)) {
    res.items.unshift({
      label: $t('admin.knowledgeBase.field.visionModelAuto'),
      value: null,
    });
    if (res.total !== undefined) res.total += 1;
  }
  return res;
}

export async function getAudioModelSelectApi(
  params?: Record<string, unknown>,
) {
  const res = await getAIModelSelectApi({
    ...params,
    type: 'chat',
    supports_audio: 'true',
  });
  if (res?.items && (!params?.page || Number(params.page) <= 1)) {
    res.items.unshift({
      label: $t('admin.knowledgeBase.field.audioModelAuto'),
      value: null,
    });
    if (res.total !== undefined) res.total += 1;
  }
  return res;
}

export async function getVideoModelSelectApi(
  params?: Record<string, unknown>,
) {
  const res = await getAIModelSelectApi({
    ...params,
    type: 'chat',
    supports_video: 'true',
  });
  if (res?.items && (!params?.page || Number(params.page) <= 1)) {
    res.items.unshift({
      label: $t('admin.knowledgeBase.field.videoModelAuto'),
      value: null,
    });
    if (res.total !== undefined) res.total += 1;
  }
  return res;
}

// ============ 表单默认值 ============

export function getFormDefaults() {
  return {
    name: '',
    description: '',
    scope: 'global_shared',
    tenant_id: null,
    tenant_ids: [],
    embedding_model_id: undefined,
    vision_model_id: null,
    audio_model_id: null,
    video_model_id: null,
    extract_images: false,
    chunk_size: 512,
    chunk_overlap: 50,
  };
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
          api: getEmbeddingModelSelectApi,
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
          api: getVisionModelSelectApi,
          required: false,
        },
      ),
      help: $t('admin.knowledgeBase.help.visionModel'),
    },
    {
      ...select(
        'audio_model_id',
        $t('admin.knowledgeBase.field.audioModel'),
        {
          api: getAudioModelSelectApi,
          required: false,
        },
      ),
      help: $t('admin.knowledgeBase.help.audioModel'),
    },
    {
      ...select(
        'video_model_id',
        $t('admin.knowledgeBase.field.videoModel'),
        {
          api: getVideoModelSelectApi,
          required: false,
        },
      ),
      help: $t('admin.knowledgeBase.help.videoModel'),
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
