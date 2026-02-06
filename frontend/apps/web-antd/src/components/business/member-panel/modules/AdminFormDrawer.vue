<script lang="ts" setup>
import type { RoleTreeApi } from '../data';

/**
 * 管理员新建/编辑表单抽屉
 * 使用自定义提交逻辑处理成员 CRUD（需要 roleId 参数）
 */
import type { adminApi, tenantApi } from '#/api';

import { computed, ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';

import { useVbenForm } from '#/adapter/form';
import { adminApi as admin, tenantApi as tenant } from '#/api';
import { $t } from '#/locales';

import { getAdminFormDefaults, useAdminFormSchema } from '../data';

type OrgMember = adminApi.OrgMember | tenantApi.TenantOrgMember;

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

const isEdit = ref(false);
const recordId = ref<number>();

// 表单
const [Form, formApi] = useVbenForm({
  showDefaultActions: false,
});

// 抽屉
const [Drawer, drawerApi] = useVbenDrawer({
  async onConfirm() {
    const { valid } = await formApi.validate();
    if (!valid) return;

    const values = await formApi.getValues();

    // 构造请求体
    const baseData = {
      email: values.email,
      phone: values.phone || null,
      nickname: values.nickname || null,
      is_active: values.is_active ?? true,
    };

    // 目标角色ID：优先取表单选择的 role_id，其次回退到当前节点 id
    const targetRoleId = (values as any).role_id ?? props.nodeId!;

    drawerApi.lock();
    try {
      if (isEdit.value && recordId.value) {
        // 更新成员（支持调整角色组）
        const data = {
          ...baseData,
          // 若用户修改了角色，传递 role_id 参数让后端处理角色切换
          role_id: (values as any).role_id ?? null,
        };
        await (props.apiPrefix === 'tenant'
          ? tenant.updateTenantMemberApi(
              props.nodeId!,
              recordId.value,
              data as tenantApi.TenantUpdateMemberRequest,
              {
                showSuccessMessage: true,
                successMessage: $t('ui.actionMessage.updateSuccess'),
              },
            )
          : admin.updateMemberApi(
              props.nodeId!,
              recordId.value,
              data as adminApi.UpdateMemberRequest,
              {
                showSuccessMessage: true,
                successMessage: $t('ui.actionMessage.updateSuccess'),
              },
            ));
      } else {
        // 创建成员
        const data = {
          ...baseData,
          username: values.username,
          password: values.password,
        };
        await (props.apiPrefix === 'tenant'
          ? tenant.createTenantMemberApi(
              targetRoleId,
              data as tenantApi.TenantCreateMemberRequest,
              {
                showSuccessMessage: true,
                successMessage: $t('ui.actionMessage.createSuccess'),
              },
            )
          : admin.createMemberApi(
              targetRoleId,
              data as adminApi.CreateMemberRequest,
              {
                showSuccessMessage: true,
                successMessage: $t('ui.actionMessage.createSuccess'),
              },
            ));
      }
      emits('success');
      drawerApi.close();
    } catch {
      drawerApi.unlock();
    }
  },

  async onOpenChange(isOpen) {
    if (!isOpen) return;

    const data = drawerApi.getData() as
      | (OrgMember & { mode?: string })
      | undefined;
    isEdit.value = data?.mode === 'edit';
    recordId.value = data?.id;

    await formApi.resetForm();

    // 更新 schema
    formApi.setState({
      schema: useAdminFormSchema({
        isEdit: isEdit.value,
        nodeName: props.nodeName,
        nodeId: props.nodeId,
        roleTreeApi: props.roleTreeApi,
      }),
    });

    // 填充表单数据
    if (isEdit.value && data) {
      formApi.setValues({
        username: data.username,
        email: data.email,
        nickname: data.nickname,
        is_active: data.isActive,
        // 若表单存在 role_id 字段，则设置为数据中的角色ID，否则回退到展示字段
        role_id: (data as any).roleId ?? props.nodeId,
        role_display:
          data.roleName || props.nodeName || $t('admin.common.unassigned'),
      });
    } else {
      // 新建模式默认值（默认选中当前节点作为角色，可下拉更改）
      formApi.setValues(getAdminFormDefaults(props.nodeName, props.nodeId));
    }
  },
});

// 标题
const title = computed(() =>
  isEdit.value
    ? $t('admin.system.admin.edit')
    : $t('admin.system.admin.create'),
);

// 打开创建表单
function openCreate() {
  drawerApi.setData({ mode: 'add' }).open();
}

// 打开编辑表单
function openEdit(record: OrgMember) {
  drawerApi.setData({ ...record, mode: 'edit' }).open();
}

defineExpose({ openCreate, openEdit });
</script>

<template>
  <Drawer :title="title" class="w-[400px]">
    <Form />
  </Drawer>
</template>
