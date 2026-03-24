<script setup lang="ts">
import type { FormInstance, RadioChangeEvent } from 'ant-design-vue';

import type { OrgNodeFormData } from './types';

import type { OrgNodeInfo, OrgNodeType } from '#/api/admin/organization';
import type { PermissionNode } from '#/api/admin/permission';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Form,
  FormItem,
  Input,
  InputNumber,
  Modal,
  Radio,
  RadioGroup,
  Select,
  SelectOption,
  Spin,
  Switch,
  Textarea,
  TreeSelect,
} from 'ant-design-vue';

import {
  createOrganizationNodeApi,
  getOrganizationNodeDetailApi,
  getOrganizationTreeApi,
  updateOrganizationNodeApi,
} from '#/api/admin/organization';
import { getPermissionTreeApi } from '#/api/admin/permission';
import {
  createTenantOrganizationNodeApi,
  getTenantOrganizationNodeDetailApi,
  getTenantOrganizationTreeApi,
  updateTenantOrganizationNodeApi,
} from '#/api/tenant/organization';
import { PermissionSelector } from '#/components/business/permission-selector';
import { $t } from '#/locales';

import {
  formRules,
  getAllowedChildTypes,
  getDefaultAllowMembers,
  getLeaderScopeOptions,
  getNodeTypeOptions,
} from './types';

type DeptTreeOption = {
  children?: DeptTreeOption[];
  title: string;
  value: number;
};

const props = withDefaults(
  defineProps<{
    apiPrefix?: 'admin' | 'tenant';
    initialData?: Partial<OrgNodeFormData>;
    mode?: 'create' | 'edit';
    nodeId?: null | number;
    open?: boolean;
    parentId?: null | number;
    parentName?: string;
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

const formRef = ref<FormInstance>();
const loading = ref(false);
const submitting = ref(false);
const deptTreeLoading = ref(false);
const deptTreeData = ref<DeptTreeOption[]>([]);
const permissionTreeLoading = ref(false);
const permissionTree = ref<PermissionNode[]>([]);

const formData = ref<OrgNodeFormData>({
  name: '',
  description: '',
  type: 'department',
  allowMembers: false,
  isActive: true,
  sortOrder: 0,
  permissionIds: [],
  dataScope: 'self',
  customDeptIds: [],
});

const leaderScopeOptions = computed(() => getLeaderScopeOptions());
const showCustomDeptSelector = computed(
  () => formData.value.dataScope === 'custom',
);

const formRulesWithScope = computed(() => ({
  ...formRules,
  customDeptIds: [
    {
      validator: (_rule: unknown, value: number[]) => {
        if (formData.value.dataScope === 'custom' && (!value || value.length === 0)) {
          return Promise.reject($t('shared.orgNode.validation.customScopeRequired'));
        }
        return Promise.resolve();
      },
      trigger: 'change' as const,
    },
  ],
}));

const api = computed(() => {
  if (props.apiPrefix === 'tenant') {
    return {
      createNode: createTenantOrganizationNodeApi,
      getNodeDetail: getTenantOrganizationNodeDetailApi,
      getTree: getTenantOrganizationTreeApi,
      updateNode: updateTenantOrganizationNodeApi,
    };
  }

  return {
    createNode: createOrganizationNodeApi,
    getNodeDetail: getOrganizationNodeDetailApi,
    getTree: getOrganizationTreeApi,
    updateNode: updateOrganizationNodeApi,
  };
});

const dialogTitle = computed(() => {
  if (props.mode === 'edit') {
    return $t('shared.orgNode.editNode');
  }
  if (props.parentName) {
    return $t('shared.orgNode.createChildNode', { parent: props.parentName });
  }
  return $t('shared.orgNode.createRootNode');
});

const allowedTypes = computed(() => {
  return props.mode === 'edit'
    ? [formData.value.type]
    : getAllowedChildTypes(props.parentType);
});

const typeOptions = computed(() => getNodeTypeOptions(allowedTypes.value));
const canCreateChild = computed(() => allowedTypes.value.length > 0);

async function loadDeptTree() {
  deptTreeLoading.value = true;
  try {
    const nodes = await api.value.getTree();
    const buildTree = (
      items: Array<{
        children?: unknown[];
        id: number;
        name: string;
        type?: string;
      }>,
    ): DeptTreeOption[] => {
      return items
        .filter((item) => item.type === 'department')
        .map((item) => ({
          title: item.name,
          value: item.id,
          children: item.children
            ? buildTree(
                item.children as Array<{
                  children?: unknown[];
                  id: number;
                  name: string;
                  type?: string;
                }>,
              )
            : undefined,
        }));
    };

    deptTreeData.value = buildTree(nodes as never);
  } catch {
    deptTreeData.value = [];
  } finally {
    deptTreeLoading.value = false;
  }
}

async function loadPermissionTree() {
  if (props.apiPrefix !== 'admin') {
    permissionTree.value = [];
    return;
  }

  permissionTreeLoading.value = true;
  try {
    permissionTree.value = await getPermissionTreeApi();
  } catch {
    permissionTree.value = [];
  } finally {
    permissionTreeLoading.value = false;
  }
}

async function loadNodeDetail() {
  if (!props.nodeId) return;

  loading.value = true;
  try {
    const detail = await api.value.getNodeDetail(props.nodeId);
    const permissionIds: number[] =
      props.apiPrefix === 'admin'
        ? (((detail as OrgNodeInfo).permissionIds ?? []) as number[])
        : [];
    formData.value = {
      name: detail.name,
      description: detail.description || '',
      type: detail.type || 'department',
      allowMembers: detail.allowMembers ?? true,
      isActive: detail.isActive,
      sortOrder: detail.sortOrder,
      permissionIds,
      dataScope: detail.dataScope || 'self',
      customDeptIds: detail.customDeptIds || [],
    };
  } finally {
    loading.value = false;
  }
}

function resetForm() {
  const initialType = allowedTypes.value[0] || 'department';
  formData.value = {
    name: '',
    description: '',
    type: initialType,
    allowMembers: getDefaultAllowMembers(initialType),
    isActive: true,
    sortOrder: 0,
    permissionIds: [],
    dataScope: 'self',
    customDeptIds: [],
  };
  formRef.value?.resetFields();
}

function handleTypeChange(type: OrgNodeType) {
  formData.value.allowMembers = getDefaultAllowMembers(type);
}

function handleClose() {
  emit('update:open', false);
  emit('cancel');
}

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
      parent_id: props.mode === 'create' ? props.parentId : undefined,
      permission_ids:
        props.apiPrefix === 'admin' ? formData.value.permissionIds : undefined,
      data_scope: formData.value.dataScope,
      custom_dept_ids:
        formData.value.dataScope === 'custom' ? formData.value.customDeptIds : undefined,
    };

    const result = await (props.mode === 'edit' && props.nodeId
      ? api.value.updateNode(props.nodeId, requestData)
      : api.value.createNode(requestData));

    emit('success', {
      id: result.id,
      name: result.name,
      type: result.type || 'department',
    });
    emit('update:open', false);
  } finally {
    submitting.value = false;
  }
}

watch(
  () => props.open,
  async (open) => {
    if (!open) return;

    await Promise.all([loadDeptTree(), loadPermissionTree()]);

    if (props.mode === 'edit' && props.nodeId) {
      await loadNodeDetail();
      return;
    }

    if (props.initialData) {
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
        dataScope: props.initialData.dataScope || 'self',
        customDeptIds: props.initialData.customDeptIds || [],
      };
      return;
    }

    resetForm();
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
    <Alert
      v-if="mode === 'create' && !canCreateChild"
      :message="$t('shared.orgNode.cannotCreateChild')"
      :description="$t('shared.orgNode.cannotCreateChildDesc')"
      type="warning"
      show-icon
      class="mb-4"
    />

    <Alert
      :message="$t('shared.orgNode.scopeHintTitle')"
      :description="$t('shared.orgNode.scopeHintDescription')"
      type="info"
      show-icon
      class="mb-4"
    />

    <Spin :spinning="loading">
      <Form
        ref="formRef"
        :model="formData"
        :rules="formRulesWithScope"
        layout="vertical"
        :disabled="mode === 'create' && !canCreateChild"
      >
        <FormItem :label="$t('shared.orgNode.nodeType')" name="type" required>
          <RadioGroup
            v-model:value="formData.type"
            :disabled="mode === 'edit'"
            @change="
              (event: RadioChangeEvent) =>
                handleTypeChange(event.target.value as OrgNodeType)
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

        <FormItem :label="$t('shared.orgNode.name')" name="name" required>
          <Input
            v-model:value="formData.name"
            :placeholder="$t('shared.orgNode.namePlaceholder')"
            :maxlength="50"
            show-count
          />
        </FormItem>

        <FormItem :label="$t('shared.orgNode.description')" name="description">
          <Textarea
            v-model:value="formData.description"
            :placeholder="$t('shared.orgNode.descriptionPlaceholder')"
            :rows="3"
            :maxlength="200"
            show-count
          />
        </FormItem>

        <div class="grid grid-cols-3 gap-4">
          <FormItem
            :label="$t('shared.orgNode.allowMembers')"
            name="allowMembers"
          >
            <Switch v-model:checked="formData.allowMembers" />
          </FormItem>
          <FormItem :label="$t('shared.orgNode.isActive')" name="isActive">
            <Switch v-model:checked="formData.isActive" />
          </FormItem>
          <FormItem :label="$t('shared.orgNode.sortOrder')" name="sortOrder">
            <InputNumber
              v-model:value="formData.sortOrder"
              :min="0"
              :max="9999"
              class="!w-full"
            />
          </FormItem>
        </div>

        <div
          v-if="props.apiPrefix === 'admin'"
          class="rounded-lg border border-border/60 p-4"
        >
          <div class="mb-3">
            <div class="text-sm font-medium text-foreground">
              {{ $t('shared.orgNode.permissions') }}
            </div>
            <div class="mt-1 text-xs text-muted-foreground">
              {{
                $t('shared.orgNode.selectedCount', {
                  count: formData.permissionIds.length,
                })
              }}
            </div>
          </div>
          <PermissionSelector
            v-model="formData.permissionIds"
            :permissions="permissionTree"
            :loading="permissionTreeLoading"
            :show-inherited-badge="false"
          />
        </div>

        <div class="rounded-lg border border-border/60 p-4">
          <div class="mb-3">
            <div class="text-sm font-medium text-foreground">
              {{ $t('shared.orgNode.leaderScope') }}
            </div>
            <div class="mt-1 text-xs text-muted-foreground">
              {{ $t('shared.orgNode.leaderScopeDescription') }}
            </div>
          </div>

          <FormItem :label="$t('shared.orgNode.leaderScope')" name="dataScope">
            <Select
              v-model:value="formData.dataScope"
              :placeholder="$t('shared.orgNode.selectLeaderScope')"
              class="!w-full"
            >
              <SelectOption
                v-for="option in leaderScopeOptions"
                :key="option.value"
                :value="option.value"
              >
                <div>
                  <span>{{ option.label }}</span>
                  <span class="ml-2 text-xs text-muted-foreground">
                    {{ option.description }}
                  </span>
                </div>
              </SelectOption>
            </Select>
          </FormItem>

          <FormItem
            v-if="showCustomDeptSelector"
            :label="$t('shared.orgNode.customScopeNodes')"
            name="customDeptIds"
          >
            <TreeSelect
              v-model:value="formData.customDeptIds"
              :tree-data="deptTreeData"
              :loading="deptTreeLoading"
              tree-checkable
              multiple
              allow-clear
              show-checked-strategy="SHOW_CHILD"
              :placeholder="$t('shared.orgNode.selectCustomScopeNodes')"
              class="!w-full"
            />
          </FormItem>
        </div>
      </Form>
    </Spin>
  </Modal>
</template>
