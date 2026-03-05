<script setup lang="ts">
import type { FormInstance, RadioChangeEvent } from 'ant-design-vue';

import type { OrgNodeFormData } from './types';

import type { OrgNodeType } from '#/api/admin/organization';
import type { PermissionNode } from '#/components/business/permission-selector';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Collapse,
  CollapsePanel,
  Form,
  FormItem,
  Input,
  InputNumber,
  Modal,
  Radio,
  RadioGroup,
  Spin,
  Switch,
  Textarea,
} from 'ant-design-vue';

// Admin API
import { getPermissionTreeApi as adminGetPermissionTreeApi } from '#/api/admin/permission';
import {
  createRoleApi as adminCreateRoleApi,
  getRoleDetailApi as adminGetRoleDetailApi,
  updateRoleApi as adminUpdateRoleApi,
} from '#/api/admin/role';
// Tenant API
import { getTenantPermissionTreeApi } from '#/api/tenant/permission';
import {
  createTenantRoleApi,
  getTenantRoleDetailApi,
  updateTenantRoleApi,
} from '#/api/tenant/role';
import { PermissionSelector } from '#/components/business/permission-selector';
import { $t } from '#/locales';

import {
  formRules,
  getAllowedChildTypes,
  getDefaultAllowMembers,
  getNodeTypeOptions,
} from './types';

const props = withDefaults(
  defineProps<{
    /** API 前缀 */
    apiPrefix?: 'admin' | 'tenant';
    /** 编辑时的初始数据 */
    initialData?: Partial<OrgNodeFormData>;
    /** 弹窗模式：创建/编辑 */
    mode?: 'create' | 'edit';
    /** 编辑的节点 ID */
    nodeId?: null | number;
    /** 是否显示弹窗 */
    open?: boolean;
    /** 父节点 ID（创建时使用） */
    parentId?: null | number;
    /** 父节点名称（显示用） */
    parentName?: string;
    /** 父节点类型（用于限制子节点类型） */
    parentType?: null | OrgNodeType;
  }>(),
  {
    open: false,
    mode: 'create',
    parentId: null,
    parentType: null,
    parentName: '',
    nodeId: null,
    initialData: undefined,
    apiPrefix: 'admin',
  },
);

const emit = defineEmits<{
  (e: 'cancel'): void;
  (e: 'success', node: { id: number; name: string; type: OrgNodeType }): void;
  (e: 'update:open', value: boolean): void;
}>();

// 表单引用
const formRef = ref<FormInstance>();

// 状态
const loading = ref(false);
const submitting = ref(false);
const permissionLoading = ref(false);
const permissionTree = ref<PermissionNode[]>([]);

// 表单数据
const formData = ref<OrgNodeFormData>({
  name: '',
  description: '',
  type: 'department',
  allowMembers: false,
  isActive: true,
  sortOrder: 0,
  permissionIds: [],
});

// 根据 apiPrefix 选择 API
const api = computed(() => {
  if (props.apiPrefix === 'tenant') {
    return {
      getPermissionTree: getTenantPermissionTreeApi,
      getRoleDetail: getTenantRoleDetailApi,
      createRole: createTenantRoleApi,
      updateRole: updateTenantRoleApi,
    };
  }
  return {
    getPermissionTree: adminGetPermissionTreeApi,
    getRoleDetail: adminGetRoleDetailApi,
    createRole: adminCreateRoleApi,
    updateRole: adminUpdateRoleApi,
  };
});

/** 弹窗标题 */
const dialogTitle = computed(() => {
  if (props.mode === 'edit') {
    return $t('shared.orgNode.editNode');
  }
  if (props.parentName) {
    return $t('shared.orgNode.createChildNode', { parent: props.parentName });
  }
  return $t('shared.orgNode.createRootNode');
});

/** 允许的子节点类型 */
const allowedTypes = computed(() => {
  return props.mode === 'edit'
    ? [formData.value.type] // 编辑模式不允许更改类型
    : getAllowedChildTypes(props.parentType);
});

/** 节点类型选项 */
const typeOptions = computed(() => {
  return getNodeTypeOptions(allowedTypes.value);
});

/** 是否可以创建子节点 */
const canCreateChild = computed(() => {
  return allowedTypes.value.length > 0;
});

/** 加载权限树 */
async function loadPermissionTree() {
  permissionLoading.value = true;
  try {
    permissionTree.value = await api.value.getPermissionTree();
  } catch (error) {
    console.error('Failed to load permission tree:', error);
    permissionTree.value = [];
  } finally {
    permissionLoading.value = false;
  }
}

/** 加载节点详情（编辑模式） */
async function loadNodeDetail() {
  if (!props.nodeId) return;

  loading.value = true;
  try {
    const detail = await api.value.getRoleDetail(props.nodeId);
    formData.value = {
      name: detail.name,
      description: detail.description || '',
      type: detail.type || 'role',
      allowMembers: detail.allowMembers ?? true,
      isActive: detail.isActive,
      sortOrder: detail.sortOrder,
      permissionIds: detail.permissionIds || [],
    };
  } catch (error) {
    console.error('Failed to load node detail:', error);
  } finally {
    loading.value = false;
  }
}

/** 重置表单 */
function resetForm() {
  formData.value = {
    name: '',
    description: '',
    type: allowedTypes.value[0] || 'department',
    allowMembers: getDefaultAllowMembers(allowedTypes.value[0] || 'department'),
    isActive: true,
    sortOrder: 0,
    permissionIds: [],
  };
  formRef.value?.resetFields();
}

/** 处理类型变更 */
function handleTypeChange(type: OrgNodeType) {
  // 自动更新 allowMembers 默认值
  formData.value.allowMembers = getDefaultAllowMembers(type);
}

/** 关闭弹窗 */
function handleClose() {
  emit('update:open', false);
  emit('cancel');
}

/** 提交表单 */
async function handleSubmit() {
  try {
    await formRef.value?.validate();
  } catch {
    return;
  }

  submitting.value = true;
  try {
    const requestData = {
      name: formData.value.name,
      description: formData.value.description || undefined,
      type: formData.value.type,
      allow_members: formData.value.allowMembers,
      is_active: formData.value.isActive,
      sort_order: formData.value.sortOrder,
      permission_ids: formData.value.permissionIds,
      parent_id: props.mode === 'create' ? props.parentId : undefined,
    };

    const result = await (props.mode === 'edit' && props.nodeId
      ? api.value.updateRole(props.nodeId, requestData)
      : api.value.createRole(requestData));

    emit('success', {
      id: result.id,
      name: result.name,
      type: result.type || 'role',
    });
    emit('update:open', false);
  } catch (error) {
    console.error('Failed to save node:', error);
  } finally {
    submitting.value = false;
  }
}

// 监听弹窗打开
watch(
  () => props.open,
  (open) => {
    if (open) {
      // 加载权限树
      loadPermissionTree();

      if (props.mode === 'edit' && props.nodeId) {
        // 编辑模式加载详情
        loadNodeDetail();
      } else if (props.initialData) {
        // 使用初始数据
        formData.value = {
          name: props.initialData.name || '',
          description: props.initialData.description || '',
          type: props.initialData.type || allowedTypes.value[0] || 'department',
          allowMembers:
            props.initialData.allowMembers ??
            getDefaultAllowMembers(allowedTypes.value[0] || 'department'),
          isActive: props.initialData.isActive ?? true,
          sortOrder: props.initialData.sortOrder ?? 0,
          permissionIds: props.initialData.permissionIds || [],
        };
      } else {
        // 重置表单
        resetForm();
      }
    }
  },
);
</script>

<template>
  <Modal
    :open="open"
    :title="dialogTitle"
    :width="680"
    :confirm-loading="submitting"
    :mask-closable="false"
    :ok-text="$t('shared.orgNode.save')"
    :cancel-text="$t('shared.orgNode.cancel')"
    @cancel="handleClose"
    @ok="handleSubmit"
  >
    <!-- 不允许创建子节点提示 -->
    <Alert
      v-if="mode === 'create' && !canCreateChild"
      :message="$t('shared.orgNode.cannotCreateChild')"
      :description="$t('shared.orgNode.cannotCreateChildDesc')"
      type="warning"
      show-icon
      class="mb-4"
    />

    <Spin :spinning="loading">
      <Form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        layout="vertical"
        :disabled="mode === 'create' && !canCreateChild"
      >
        <!-- 节点类型选择 -->
        <FormItem :label="$t('shared.orgNode.nodeType')" name="type" required>
          <RadioGroup
            v-model:value="formData.type"
            :disabled="mode === 'edit'"
            @change="
              (e: RadioChangeEvent) =>
                handleTypeChange(e.target.value as OrgNodeType)
            "
          >
            <div class="grid grid-cols-3 gap-3">
              <div
                v-for="option in typeOptions"
                :key="option.value"
                class="relative"
              >
                <Radio
                  :value="option.value"
                  :disabled="option.disabled"
                  class="!absolute !opacity-0"
                />
                <div
                  class="cursor-pointer rounded-lg border-2 p-3 transition-all"
                  :class="[
                    formData.type === option.value
                      ? 'border-primary bg-primary/5'
                      : 'border-gray-200 hover:border-gray-300 dark:border-gray-700',
                    option.disabled ? 'cursor-not-allowed opacity-50' : '',
                  ]"
                  @click="
                    !option.disabled &&
                    mode !== 'edit' &&
                    ((formData.type = option.value),
                    handleTypeChange(option.value))
                  "
                >
                  <div class="flex items-center gap-2">
                    <IconifyIcon :icon="option.icon" class="h-5 w-5" />
                    <span class="font-medium">{{ option.label }}</span>
                  </div>
                  <div class="mt-1 text-xs text-gray-500">
                    {{ option.description }}
                  </div>
                </div>
              </div>
            </div>
          </RadioGroup>
        </FormItem>

        <!-- 名称 -->
        <FormItem :label="$t('shared.orgNode.name')" name="name" required>
          <Input
            v-model:value="formData.name"
            :placeholder="$t('shared.orgNode.namePlaceholder')"
            :maxlength="50"
            show-count
          />
        </FormItem>

        <!-- 描述 -->
        <FormItem :label="$t('shared.orgNode.description')" name="description">
          <Textarea
            v-model:value="formData.description"
            :placeholder="$t('shared.orgNode.descriptionPlaceholder')"
            :rows="3"
            :maxlength="200"
            show-count
          />
        </FormItem>

        <!-- 设置行 -->
        <div class="grid grid-cols-3 gap-4">
          <!-- 是否允许成员 -->
          <FormItem
            :label="$t('shared.orgNode.allowMembers')"
            name="allowMembers"
          >
            <Switch v-model:checked="formData.allowMembers" />
          </FormItem>

          <!-- 状态 -->
          <FormItem :label="$t('shared.orgNode.isActive')" name="isActive">
            <Switch v-model:checked="formData.isActive" />
          </FormItem>

          <!-- 排序 -->
          <FormItem :label="$t('shared.orgNode.sortOrder')" name="sortOrder">
            <InputNumber
              v-model:value="formData.sortOrder"
              :min="0"
              :max="9999"
              class="!w-full"
            />
          </FormItem>
        </div>

        <!-- 权限分配 -->
        <Collapse class="mt-4" :bordered="false">
          <CollapsePanel
            key="permissions"
            :header="$t('shared.orgNode.permissions')"
          >
            <template #extra>
              <span class="text-sm text-gray-500">
                {{
                  $t('shared.orgNode.selectedCount', {
                    count: formData.permissionIds.length,
                  })
                }}
              </span>
            </template>
            <Spin :spinning="permissionLoading">
              <PermissionSelector
                v-model="formData.permissionIds"
                :permissions="permissionTree"
                :loading="permissionLoading"
                :default-expanded-level="1"
              />
            </Spin>
          </CollapsePanel>
        </Collapse>
      </Form>
    </Spin>
  </Modal>
</template>
