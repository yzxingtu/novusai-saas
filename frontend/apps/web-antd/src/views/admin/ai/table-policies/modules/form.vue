<script lang="ts" setup>
/**
 * AI 表策略编辑表单抽屉
 * AI table policy edit form drawer
 *
 * 仅编辑模式（策略由系统自动创建），支持动态加载列选项 / Edit-only; dynamic column options.
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { AITablePolicyInfo } from '#/api/admin/ai';

import { computed, ref, watch } from 'vue';

import { Input } from 'ant-design-vue';
import { useVbenForm } from '#/adapter/form';
import { getAITablePolicyDetailApi, getAITablePolicyColumnsApi } from '#/api/admin/ai';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';
import { message } from 'ant-design-vue';

import { loadColumnOptions, useFormSchema } from '../data';

defineOptions({ name: 'AITablePolicyForm' });

const emits = defineEmits<{ success: [] }>();

const columnList = ref<Array<{ name: string; type: string; comment?: string }>>([]);
const columnDescs = ref<Record<string, string>>({});

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

const { Drawer, recordId } = useCrudDrawer<AITablePolicyInfo>({
  formApi,
  schema: (): VbenFormSchema[] => useFormSchema(),
  toFormValues: (data) => {
    columnDescs.value = { ...(data.column_descriptions || {}) };
    return {
      table_name: data.table_name,
      label: data.label,
      description: data.description,
      keywords: data.keywords || [],
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
      keywords: values.keywords || [],
      column_descriptions: columnDescs.value,
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

function updateColumnDesc(name: string, value: string) {
  columnDescs.value = {
    ...columnDescs.value,
    [name]: value,
  };
}

/**
 * 当记录 ID 变化时，加载列选项并更新 blocked_columns / readonly_columns / 列描述
 * On record ID change: load column options and update form schema options
 */
watch(recordId, async (newId) => {
  const id = newId != null ? Number(newId) : NaN;
  if (!Number.isFinite(id)) {
    columnList.value = [];
    columnDescs.value = {};
    return;
  }
  const requestId = id;
  try {
    const [options, cols] = await Promise.all([
      loadColumnOptions(requestId),
      getAITablePolicyColumnsApi(requestId),
    ]);
    if (Number(recordId.value) !== requestId) return;
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
    columnList.value = cols.map((c) => ({
      name: c.name,
      type: c.type || 'unknown',
      comment: c.comment,
    }));
    // columnDescs 由 toFormValues（detailApi 返回后）负责，无需重复请求 getAITablePolicyDetailApi
  } catch {
    if (Number(recordId.value) !== requestId) return;
    message.warning($t('admin.ai.tablePolicy.messages.columnLoadFailed'));
    columnList.value = [];
  }
});
</script>

<template>
  <Drawer :title="title" class="w-[600px]">
    <Form />
    <div
      v-if="recordId && columnList.length > 0"
      class="mt-4"
    >
      <div class="mb-2 text-sm font-medium">
        {{ $t('admin.ai.tablePolicy.columnDescriptions') }}
      </div>
      <div class="rounded border border-border">
        <div
          v-for="col in columnList"
          :key="col.name"
          class="flex items-center gap-2 border-b border-border/30 px-3 py-2 last:border-b-0"
        >
          <code class="w-36 shrink-0 text-xs">{{ col.name }}</code>
          <span class="w-20 shrink-0 text-xs text-muted-foreground">{{
            col.type
          }}</span>
          <Input
            :value="columnDescs[col.name]"
            size="small"
            :placeholder="
              col.comment || $t('admin.ai.tablePolicy.placeholder.inputColumnDesc')
            "
            class="flex-1"
            @update:value="(v: string) => updateColumnDesc(col.name, v)"
          />
        </div>
      </div>
    </div>
  </Drawer>
</template>
