<script lang="ts" setup>
/**
 * AI 表策略编辑表单抽屉
 * AI table policy edit form drawer
 *
 * 仅编辑模式（策略由系统自动创建），支持动态加载列选项 / Edit-only; dynamic column options.
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { AITablePolicyInfo } from '#/api/admin/ai';

import { computed, watch } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { getAITablePolicyDetailApi } from '#/api/admin/ai';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { loadColumnOptions, useFormSchema } from '../data';

defineOptions({ name: 'AITablePolicyForm' });

const emits = defineEmits<{ success: [] }>();

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

const { Drawer, recordId } = useCrudDrawer<AITablePolicyInfo>({
  formApi,
  schema: (): VbenFormSchema[] => useFormSchema(),
  toFormValues: (data) => {
    return {
      table_name: data.table_name,
      label: data.label,
      description: data.description,
      permission_code: data.permission_code,
      max_rows: data.max_rows,
      allow_read: data.allow_read,
      allow_create: data.allow_create,
      allow_update: data.allow_update,
      allow_delete: data.allow_delete,
      blocked_columns: data.blocked_columns || [],
      readonly_columns: data.readonly_columns || [],
      sort_order: data.sort_order,
      is_active: data.is_active,
    };
  },
  transform: (values) => {
    return {
      label: values.label,
      description: values.description || null,
      permission_code: values.permission_code,
      max_rows: values.max_rows,
      allow_read: values.allow_read ?? true,
      allow_create: values.allow_create ?? false,
      allow_update: values.allow_update ?? false,
      allow_delete: values.allow_delete ?? false,
      blocked_columns: values.blocked_columns || [],
      readonly_columns: values.readonly_columns || [],
      sort_order: values.sort_order ?? 0,
      is_active: values.is_active ?? true,
    };
  },
  onSuccess: () => {
    emits('success');
  },
  detailApi: (id) => getAITablePolicyDetailApi(id as number),
});

const title = computed(() => $t('admin.common.edit'));

/**
 * 当记录 ID 变化时，加载列选项并更新 blocked_columns / readonly_columns 的 options
 * On record ID change: load column options and update form schema options
 */
watch(recordId, async (newId) => {
  if (newId && typeof newId === 'number') {
    try {
      const options = await loadColumnOptions(newId);
      formApi.updateSchema([
        {
          fieldName: 'blocked_columns',
          componentProps: {
            mode: 'multiple',
            options,
            placeholder: $t(
              'admin.ai.tablePolicy.placeholder.selectBlockedColumns',
            ),
          },
        },
        {
          fieldName: 'readonly_columns',
          componentProps: {
            mode: 'multiple',
            options,
            placeholder: $t(
              'admin.ai.tablePolicy.placeholder.selectReadonlyColumns',
            ),
          },
        },
      ]);
    } catch {
      // column load failed silently / 列加载失败时静默处理
    }
  }
});
</script>

<template>
  <Drawer :title="title" class="w-[600px]">
    <Form />
  </Drawer>
</template>
