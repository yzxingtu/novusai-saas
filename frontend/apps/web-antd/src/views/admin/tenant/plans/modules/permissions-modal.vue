<script lang="ts" setup>
/**
 * 套餐权限设置弹窗
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

// Emits
const emits = defineEmits<{
  success: [];
}>();

// 状态
const permissionTree = ref<PermissionNode[]>([]);
const selectedPermissionIds = ref<number[]>([]);
const loading = ref(false);
const currentPlan = ref<null | TenantPlanInfo>(null);

// 计算标题
const title = computed(() =>
  currentPlan.value
    ? $t('admin.tenant.plan.permissionsTitle', { name: currentPlan.value.name })
    : $t('admin.tenant.plan.setPermissions'),
);

// Modal - 使用 onConfirm 回调处理保存
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
    } catch (error) {
      console.error('Failed to save permissions:', error);
      modalApi.unlock();
    }
  },

  async onOpenChange(isOpen) {
    if (isOpen) {
      // 从 modalApi 获取传入的数据
      const data = modalApi.getData<TenantPlanInfo>();
      if (data?.id) {
        currentPlan.value = data;
        await loadData();
      }
    } else {
      // 关闭时清空数据
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
    // 并行加载可分配权限和已分配权限
    const [availablePermissions, assignedResult] = await Promise.all([
      admin.getAvailablePermissionsApi(),
      admin.getTenantPlanPermissionsApi(currentPlan.value.id),
    ]);

    // 转换为 PermissionNode 格式
    permissionTree.value = transformPermissions(availablePermissions);

    // 确保 assignedIds 是数字数组（防御性处理）
    const assignedIds = Array.isArray(assignedResult)
      ? assignedResult.map((item) =>
          typeof item === 'object' && item !== null ? (item as any).id : item,
        )
      : [];
    selectedPermissionIds.value = assignedIds.filter(
      (id): id is number => typeof id === 'number',
    );
  } catch (error) {
    console.error('Failed to load permissions:', error);
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
          :default-expanded-level="1"
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
