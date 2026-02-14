<script lang="ts" setup>
defineOptions({ name: 'AdminKnowledgeBaseForm' });
/**
 * 管理端知识库新建/编辑表单抽屉
 */
import type { AdminKnowledgeBaseItem } from '#/api/admin/knowledge-bases';

import { computed } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { getAdminKnowledgeBaseDetailApi } from '#/api/admin/knowledge-bases';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { getFormDefaults, useFormSchema } from '../data';

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
      scope: values.scope,
    };
    if (values.scope === 'tenant') {
      result.tenant_id = values.tenant_id;
    } else {
      result.tenant_id = null;
    }
    if (!edit) {
      result.embedding_model_id = values.embedding_model_id;
    }
    result.chunk_size = values.chunk_size;
    result.chunk_overlap = values.chunk_overlap;
    result.top_k = values.top_k;
    result.score_threshold = values.score_threshold;
    return result;
  },
  toFormValues: (data) => {
    return {
      name: data.name,
      description: data.description,
      scope: data.scope,
      tenant_id: data.tenant_id,
      embedding_model_id: data.embedding_model_id,
      chunk_size: data.chunk_size,
      chunk_overlap: data.chunk_overlap,
      top_k: data.top_k,
      score_threshold: data.score_threshold,
    };
  },
  onSuccess: () => {
    emits('success');
  },
  detailApi: (id) => getAdminKnowledgeBaseDetailApi(id as number),
});

const title = computed(() =>
  isEdit.value
    ? $t('admin.common.edit')
    : $t('admin.knowledgeBase.create'),
);
</script>

<template>
  <Drawer :title="title" class="w-[600px]">
    <Form />
  </Drawer>
</template>
