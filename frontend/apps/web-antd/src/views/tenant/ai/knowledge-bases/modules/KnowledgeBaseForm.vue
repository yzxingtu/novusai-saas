<script lang="ts" setup>
defineOptions({ name: 'TenantKnowledgeBaseForm' });
/**
 * 租户端知识库新建/编辑表单抽屉
 */
import type { KnowledgeBaseItem } from '#/api/tenant/knowledge-bases';

import { computed } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { useFormSchema } from '../data';

const emits = defineEmits<{ success: [] }>();

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

const { Drawer, isEdit, openNew, openEdit } = useCrudDrawer<KnowledgeBaseItem>({
  formApi,
  schema: useFormSchema,
  apiPath: '/tenant/ai/knowledge-bases',
  fields: [
    'name',
    'description',
    'embedding_model_id',
    'chunk_size',
    'chunk_overlap',
    'chunk_strategy',
    'search_mode',
    'top_k',
    'score_threshold',
  ],
  onSuccess: () => {
    emits('success');
  },
});

defineExpose({ openNew, openEdit });

const title = computed(() =>
  isEdit.value
    ? $t('tenant.knowledgeBase.edit')
    : $t('tenant.knowledgeBase.create'),
);
</script>

<template>
  <Drawer :title="title" class="w-[600px]">
    <Form />
  </Drawer>
</template>
