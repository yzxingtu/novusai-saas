<script lang="ts" setup>
/**
 * 管理端知识库新建/编辑表单抽屉
 */
import type { AdminKnowledgeBaseItem } from '#/api/admin/knowledge-bases';

import { computed } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { getAdminKnowledgeBaseDetailApi } from '#/api/admin/knowledge-bases';
import { extractScopePayload } from '#/components/business/scope-select';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { getFormDefaults, useFormSchema } from '../data';

defineOptions({ name: 'AdminKnowledgeBaseForm' });

const emits = defineEmits<{ success: [] }>();

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

const { Drawer, isEdit } = useCrudDrawer<AdminKnowledgeBaseItem>({
  formApi,
  schema: (edit) => useFormSchema(edit),
  defaults: getFormDefaults,
  transform: (values, edit) => {
    const result: Record<string, unknown> = {
      name: values.name,
      description: values.description || null,
      ...extractScopePayload(values),
      vision_model_id: values.vision_model_id ?? null,
      audio_model_id: values.audio_model_id ?? null,
      video_model_id: values.video_model_id ?? null,
      extract_images: values.extract_images ?? false,
    };
    if (!edit) {
      result.embedding_model_id = values.embedding_model_id;
      result.chunk_size = values.chunk_size;
      result.chunk_overlap = values.chunk_overlap;
    }
    return result;
  },
  toFormValues: (data) => ({
    name: data.name,
    description: data.description,
    scope: data.scope,
    tenant_id: data.tenant_id ?? null,
    tenant_ids: data.assigned_tenant_ids ?? [],
    embedding_model_id: data.embedding_model_id,
    vision_model_id: (data as unknown as Record<string, unknown>).vision_model_id ?? null,
    audio_model_id: (data as unknown as Record<string, unknown>).audio_model_id ?? null,
    video_model_id: (data as unknown as Record<string, unknown>).video_model_id ?? null,
    extract_images: (data as unknown as Record<string, unknown>).extract_images ?? false,
    chunk_size: data.chunk_size,
    chunk_overlap: data.chunk_overlap,
  }),
  onSuccess: () => {
    emits('success');
  },
  detailApi: (id) => getAdminKnowledgeBaseDetailApi(id as number),
});

const title = computed(() =>
  isEdit.value ? $t('admin.common.edit') : $t('admin.knowledgeBase.create'),
);
</script>

<template>
  <Drawer :title="title" class="w-[680px]">
    <Form />
  </Drawer>
</template>
