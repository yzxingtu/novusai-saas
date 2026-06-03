<script lang="ts" setup>
/**
 * Plan permissions settings modal
 * 套餐权限设置弹窗
 * Reuses PermissionSelector component
 * 复用 PermissionSelector 组件
 */
import type { adminApi } from '#/api';
import type { PermissionNode } from '#/components/business/permission-selector';

import { computed, ref } from 'vue';

import { useVbenModal } from '@vben/common-ui';

import { Spin } from 'ant-design-vue';

import { adminApi as admin } from '#/api';
import { PermissionSelector } from '#/components/business/permission-selector';
import { $t } from '#/locales';

type TenantPlanInfo = adminApi.TenantPlanInfo;

// Emits / 组件事件
const emits = defineEmits<{
  success: [];
}>();

// State / 状态
const permissionTree = ref<PermissionNode[]>([]);
const selectedPermissionIds = ref<number[]>([]);
const loading = ref(false);
const currentPlan = ref<null | TenantPlanInfo>(null);

// Computed title / 计算标题
const title = computed(() =>
  currentPlan.value
    ? $t('admin.tenant.plan.permissionsTitle', { name: currentPlan.value.name })
    : $t('admin.tenant.plan.setPermissions'),
);

// Modal - use onConfirm callback to handle save / 使用 onConfirm 回调处理保存
const [Modal, modalApi] = useVbenModal({
  async onConfirm() {
    if (!currentPlan.value?.id) return;

    modalApi.lock();
    try {
      await admin.setTenantPlanPermissionsApi(currentPlan.value.id, {
        permission_ids: selectedPermissionIds.value,
      });
      emits('success');
      modalApi.close();
    } catch {
      modalApi.unlock();
    }
  },

  async onOpenChange(isOpen) {
    if (isOpen) {
      // Get data passed via modalApi / 从 modalApi 获取传入的数据
      const data = modalApi.getData<TenantPlanInfo>();
      if (data?.id) {
        currentPlan.value = data;
        await loadData();
      }
    } else {
      // Clear data on close / 关闭时清空数据
      currentPlan.value = null;
      permissionTree.value = [];
      selectedPermissionIds.value = [];
    }
  },
});

/**
 * 加载权限数据
 */
async function loadData() {
  if (!currentPlan.value?.id) return;

  loading.value = true;
  try {
    // Load available & assigned permissions in parallel / 并行加载可分配权限和已分配权限
    const [availablePermissions, assignedPermissions] = await Promise.all([
      admin.getAvailablePermissionsApi(),
      admin.getTenantPlanPermissionsApi(currentPlan.value.id),
    ]);

    // Convert to PermissionNode format / 转换为 PermissionNode 格式
    permissionTree.value = transformPermissions(availablePermissions);

    // Extract assigned permission IDs / 提取已分配权限的 ID
    selectedPermissionIds.value = assignedPermissions.map((p) => p.id);
  } catch {
  } finally {
    loading.value = false;
  }
}

/**
 * 转换权限数据格式
 */
function transformPermissions(
  items: adminApi.PermissionInfo[],
): PermissionNode[] {
  return items.map((item) => ({
    id: item.id,
    code: item.code,
    name: item.name,
    type: 'menu' as const,
    parentId: item.parentId ?? null,
    sortOrder: 0,
    children: item.children ? transformPermissions(item.children) : undefined,
  }));
}

/**
 * 打开弹窗
 */
function open(plan: TenantPlanInfo) {
  modalApi.setData(plan).open();
}

defineExpose({ open });
</script>

<template>
  <Modal :title="title" :loading="loading" class="w-[700px]">
    <div class="min-h-[300px]">
      <Spin :spinning="loading">
        <p class="mb-4 text-sm text-muted-foreground">
          {{ $t('admin.tenant.plan.permissionsHint') }}
        </p>

        <PermissionSelector
          v-if="permissionTree.length > 0"
          v-model="selectedPermissionIds"
          :permissions="permissionTree"
          :loading="loading"
          :default-expanded-level="0"
          :show-inherited-badge="false"
        />

        <div
          v-else-if="!loading"
          class="flex items-center justify-center py-10 text-muted-foreground"
        >
          {{ $t('admin.tenant.plan.noPermissions') }}
        </div>
      </Spin>
    </div>
  </Modal>
</template>
