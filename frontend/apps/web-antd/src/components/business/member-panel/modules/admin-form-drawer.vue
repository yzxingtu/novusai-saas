<script lang="ts" setup>
import type { RoleTreeApi } from '../data';

/**
 * 管理员新建/编辑表单抽屉
 * 使用 useCrudDrawer 实现声明式 CRUD，自动处理 create/update 请求
 */
import type { adminApi } from '#/api';

import { computed } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { getAdminFormDefaults, useAdminFormSchema } from '../data';

type AdminInfo = adminApi.AdminInfo;

const props = withDefaults(
  defineProps<{
    /** API 前缀 */
    apiPrefix?: 'admin' | 'tenant';
    /** 当前节点 ID（作为角色 ID，新建时使用） */
    nodeId?: null | number;
    /** 节点名称（用于显示） */
    nodeName?: string;
    /** 角色树 API（编辑模式下可选择角色） */
    roleTreeApi?: RoleTreeApi;
  }>(),
  {
    nodeId: null,
    nodeName: '',
    apiPrefix: 'admin',
    roleTreeApi: undefined,
  },
);

const emits = defineEmits<{ success: [] }>();

// 资源路径（响应式）
const resourcePath = computed(() =>
  props.apiPrefix === 'tenant' ? '/tenant/admins' : '/admin/admins',
);

// 表单（schema 由 useCrudDrawer 动态管理）
const [Form, formApi] = useVbenForm({
  showDefaultActions: false,
});

// CRUD 抽屉
const {
  Drawer,
  isEdit,
  openNew: openCreate,
  openEdit,
} = useCrudDrawer<AdminInfo>({
  formApi,
  apiPath: resourcePath,
  schema: (edit) =>
    useAdminFormSchema({
      isEdit: edit,
      nodeName: props.nodeName,
      roleTreeApi: props.roleTreeApi,
    }),
  // 新建模式默认值（声明式配置）
  defaults: () => getAdminFormDefaults(props.nodeName),
  // 表单值 -> API 请求体
  transform: (values, edit) => ({
    ...(edit ? {} : { username: values.username, password: values.password }),
    email: values.email,
    phone: values.phone || null,
    nickname: values.nickname || null,
    is_active: values.is_active ?? true,
    // 新建时使用 nodeId，编辑时可修改角色
    ...(edit
      ? (props.roleTreeApi
        ? { role_id: values.role_id }
        : {})
      : { role_id: props.nodeId }),
  }),
  // 编辑模式：后端数据 -> 表单值
  toFormValues: (data) => ({
    username: data.username,
    email: data.email,
    phone: data.phone,
    nickname: data.nickname,
    is_active: data.isActive,
    // 如果有 roleTreeApi，使用 role_id；否则使用 role_display
    ...(props.roleTreeApi
      ? { role_id: data.roleId }
      : {
          role_display:
            data.roleName || props.nodeName || $t('admin.common.unassigned'),
        }),
  }),
  onSuccess: () => emits('success'),
});

// 标题
const title = computed(() =>
  isEdit.value
    ? $t('admin.system.admin.edit')
    : $t('admin.system.admin.create'),
);

defineExpose({ openCreate, openEdit });
</script>

<template>
  <Drawer :title="title" class="w-[400px]">
    <Form />
  </Drawer>
</template>
