<script lang="ts" setup>
/**
 * 租户新建/编辑表单抽屉
 *
 * 使用 fields 简化字段映射，自动处理：
 * - 编辑模式：后端 camelCase -> 表单 snake_case
 * - 提交时：表单 snake_case -> API snake_case（空值转 null）
 */
import type { adminApi } from '#/api';

import { computed } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { getTenantDetailApi } from '#/api/admin/tenant';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { useFormSchema } from '../data';

type TenantInfo = adminApi.TenantInfo;

const emits = defineEmits<{ success: [] }>();

// 基础字段
const baseFields = [
  'name',
  'contact_name',
  'contact_phone',
  'contact_email',
  'plan_id',
  'expires_at',
  'remark',
  'code',
];

// 新建时额外的管理员字段
const adminFields = ['admin_username', 'admin_email', 'admin_password'];

// 所有字段
const allFields = [...baseFields, ...adminFields];

// 表单（套餐下拉由 ApiSelect 自动加载）
const [Form, formApi] = useVbenForm({
  schema: useFormSchema(false),
  showDefaultActions: false,
});

// CRUD 抽屉
const { Drawer, isEdit } = useCrudDrawer<TenantInfo>({
  formApi,
  schema: useFormSchema,
  // 使用所有字段（新建时 schema 会包含管理员字段，编辑时不包含）
  fields: allFields,
  // 自定义 transform：编辑时排除管理员字段
  transform: (values, editMode) => {
    const fieldsToUse = editMode ? baseFields : allFields;
    const result: Record<string, any> = {};
    for (const field of fieldsToUse) {
      const value = values[field];
      result[field] = value === '' || value === undefined ? null : value;
    }
    return result;
  },
  onSuccess: () => emits('success'),
  detailApi: (id) => getTenantDetailApi(id as number),
});

const title = computed(() =>
  isEdit.value ? $t('admin.tenant.edit') : $t('admin.tenant.create'),
);
</script>

<template>
  <Drawer :title="title">
    <Form />
  </Drawer>
</template>
