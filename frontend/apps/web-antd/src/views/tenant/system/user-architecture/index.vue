<script lang="ts" setup>
import type { TenantUserRoleInfo } from '#/api/tenant/tenant-user-roles';
import type { TenantUserInfo } from '#/api/tenant/tenant-users';

import { computed, h, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';
import { registerPageOperations } from '#/components/business/ai-slide-panel/page-operation-registry';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Badge,
  Button,
  Card,
  Empty,
  Input,
  message,
  Modal,
  Popconfirm,
  Spin,
  Switch,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  deleteTenantUserRoleApi,
  getTenantUserRoleListApi,
  toggleTenantUserRoleStatusApi,
} from '#/api/tenant/tenant-user-roles';
import {
  getTenantUserListApi,
  resetTenantUserPasswordApi,
  toggleTenantUserStatusApi,
} from '#/api/tenant/tenant-users';
import { $t } from '#/locales';
import { usePresenceStore } from '#/store';
import { formatDate, formatRelativeTime } from '#/utils/common';

import { useMemberColumns, useMemberSearchSchema } from './data';
import PermissionDrawer from './modules/PermissionDrawer.vue';
import UserForm from './modules/UserForm.vue';
import UserRoleFormComponent from './modules/UserRoleForm.vue';

defineOptions({ name: 'TenantUserArchitecture' });

// ============================================================
// 左侧角色列表
// ============================================================

const roles = ref<TenantUserRoleInfo[]>([]);
const rolesLoading = ref(false);
const searchKeyword = ref('');
const selectedRole = ref<TenantUserRoleInfo | null>(null);
const panelCollapsed = ref(false);

const filteredRoles = computed(() => {
  if (!searchKeyword.value) return roles.value;
  const kw = searchKeyword.value.toLowerCase();
  return roles.value.filter(
    (r) =>
      r.name.toLowerCase().includes(kw) ||
      r.code.toLowerCase().includes(kw),
  );
});

async function loadRoles() {
  rolesLoading.value = true;
  try {
    const res = await getTenantUserRoleListApi({
      'page[size]': 100,
      sort: 'sort_order',
    });
    roles.value = res.items;
    // 如果之前选中的角色仍然存在，更新引用
    if (selectedRole.value) {
      const updated = roles.value.find((r) => r.id === selectedRole.value!.id);
      if (updated) {
        selectedRole.value = updated;
      } else {
        selectedRole.value = null;
      }
    }
  } catch {
    roles.value = [];
  } finally {
    rolesLoading.value = false;
  }
}

function handleSelectRole(role: TenantUserRoleInfo) {
  selectedRole.value = role;
}

// ============================================================
// 角色 CRUD 弹窗（使用 useVbenDrawer）
// ============================================================

const [RoleFormDrawer, roleFormApi] = useVbenDrawer({
  connectedComponent: UserRoleFormComponent,
  destroyOnClose: true,
});

function handleCreateRole() {
  roleFormApi
    .setData({
      mode: 'add' as const,
      _resource: '/tenant/user-roles',
      _defaults: { is_active: true, sort_order: 0 },
    })
    .open();
}

function handleEditRole(role: TenantUserRoleInfo) {
  roleFormApi
    .setData({
      ...role,
      mode: 'edit' as const,
      _resource: '/tenant/user-roles',
    })
    .open();
}

// ============================================================
// 角色删除
// ============================================================

const roleDeleting = ref(false);

async function handleDeleteRole(role: TenantUserRoleInfo) {
  if (role.isSystem) {
    message.warning($t('tenant.system.userRole.messages.systemRoleCannotDelete'));
    return;
  }
  roleDeleting.value = true;
  try {
    await deleteTenantUserRoleApi(role.id);
    message.success($t('tenant.system.userRole.messages.deleteSuccess'));
    if (selectedRole.value?.id === role.id) {
      selectedRole.value = null;
    }
    await loadRoles();
  } catch {
    message.error($t('shared.common.deleteFailed'));
  } finally {
    roleDeleting.value = false;
  }
}

// ============================================================
// 角色状态切换
// ============================================================

async function handleToggleRoleStatus(role: TenantUserRoleInfo) {
  const newStatus = !role.isActive;
  try {
    await toggleTenantUserRoleStatusApi(role.id, newStatus);
    message.success($t('ui.actionMessage.operationSuccess'));
    await loadRoles();
  } catch {
    // error handled by request client
  }
}

// ============================================================
// 权限分配
// ============================================================

const permissionDrawerVisible = ref(false);
const currentPermissionRole = ref<TenantUserRoleInfo | null>(null);

function handleAssignPermissions(role: TenantUserRoleInfo) {
  currentPermissionRole.value = role;
  permissionDrawerVisible.value = true;
}

function onPermissionSaved() {
  loadRoles();
}

// ============================================================
// 右侧用户成员表格
// ============================================================

/** Wrapper to match ToggleStatusApi signature */
async function toggleUserStatus(
  id: number,
  data: Record<string, boolean>,
) {
  return toggleTenantUserStatusApi(id, !!data.is_active);
}

/** 带 role_id 过滤的用户列表 API */
function getUserListForRole(params: Record<string, unknown>) {
  if (!selectedRole.value) {
    return Promise.resolve({ items: [], total: 0, page: 1, page_size: 20 });
  }
  return getTenantUserListApi({
    ...params,
    'filter[role_id][eq]': selectedRole.value.id,
  });
}

const newPasswordRef = ref('');

async function onResetPassword(row: TenantUserInfo) {
  newPasswordRef.value = '';
  Modal.confirm({
    title: $t('tenant.system.user.resetPassword'),
    content: () =>
      h(Input.Password, {
        'placeholder': $t('tenant.system.user.newPassword'),
        'value': newPasswordRef.value,
        'onUpdate:value': (val: string) => {
          newPasswordRef.value = val;
        },
      }),
    onOk: async () => {
      if (!newPasswordRef.value || newPasswordRef.value.length < 6) {
        message.warning($t('tenant.system.user.placeholder.inputPassword'));
        throw new Error('validation');
      }
      await resetTenantUserPasswordApi(row.id, {
        new_password: newPasswordRef.value,
      });
      message.success($t('tenant.system.user.messages.resetPasswordSuccess'));
    },
  });
}

const {
  Grid: MemberGrid,
  FormDrawer: MemberFormDrawer,
  onRefresh: onMemberRefresh,
  handleToggleStatus: handleMemberToggleStatus,
} = useCrudPage<TenantUserInfo>({
  api: {
    list: getUserListForRole,
    resource: '/tenant/users',
    toggles: { is_active: toggleUserStatus },
  },
  columns: useMemberColumns,
  searchSchema: useMemberSearchSchema(),
  formComponent: UserForm,
  i18nPrefix: 'tenant.system.user',
  nameField: 'username',
  defaultSort: '-created_at',
  createPermission: 'tenant_user:create',
  customActions: {
    resetPassword: onResetPassword,
  },
});

/** 角色选择变化时重新加载成员表（nextTick 等待 Grid 挂载） */
watch(selectedRole, async () => {
  await nextTick();
  onMemberRefresh();
});

/** 成员表单提交成功后同时刷新角色列表（更新 memberCount） */
function onMemberFormSuccess() {
  onMemberRefresh();
  loadRoles();
}

// ============================================================
// 角色表单弹窗回调
// ============================================================

function onRoleFormSuccess() {
  loadRoles();
}

// ============================================================
// 生命周期
// ============================================================

const presenceStore = usePresenceStore();

onMounted(async () => {
  await loadRoles();
  // 自动选择第一个角色
  if (roles.value.length > 0) {
    selectedRole.value = roles.value[0]!;
  }
  // 加载业务用户在线状态
  presenceStore.loadTenantUserPresence();
});

// ============================================================
// AI Page Context
// ============================================================

const cleanupPageContext = registerPageContext(
  'tenant/system/user-architecture',
  () => ({
    page_key: 'tenant.system.userArchitecture',
    page_title: $t('tenant.system.userArchitecture.title'),
    page_data: {
      resource: '/tenant/user-roles',
    },
  }),
);

const cleanupPageOps = registerPageOperations(
  'tenant.system.userArchitecture',
  [
    {
      name: 'refresh_roles',
      label: $t('shared.pageOperation.refreshList'),
      description: 'Refresh the role list',
      readonly: true,
      handler: async () => {
        await loadRoles();
        return { success: true, message: 'Role list refreshed' };
      },
    },
    {
      name: 'create_role',
      label: $t('shared.pageOperation.createRecord'),
      description: 'Open the create role form',
      readonly: false,
      handler: async () => {
        handleCreateRole();
        return { success: true, message: 'Create role form opened' };
      },
    },
    {
      name: 'search_roles',
      label: $t('shared.pageOperation.searchByKeyword'),
      description: 'Search roles by name keyword',
      readonly: true,
      params: {
        keyword: { type: 'string', description: 'Role name keyword' },
      },
      handler: async (params) => {
        const keyword = ((params?.keyword as string) || '').toLowerCase();
        searchKeyword.value = keyword;
        return { success: true, message: `Searched roles for: ${keyword}` };
      },
    },
    {
      name: 'add_member',
      label: $t('tenant.system.userArchitecture.addMember'),
      description: 'Open the add member form for the selected role',
      readonly: false,
      handler: async () => {
        if (!selectedRole.value) {
          return { success: false, message: 'No role selected' };
        }
        handleCreateRole();
        return { success: true, message: 'Add member form opened' };
      },
    },
  ],
);

onUnmounted(() => {
  cleanupPageContext();
  cleanupPageOps();
});
</script>

<template>
  <Page auto-content-height>
    <div class="flex h-full gap-2 overflow-hidden lg:gap-4">
      <!-- ==================== 左侧：角色列表 ==================== -->
      <div
        class="flex flex-shrink-0 flex-col overflow-hidden rounded-xl bg-card shadow-sm transition-all duration-300"
        :class="[
          panelCollapsed ? 'w-12' : 'w-[280px] lg:w-[320px] xl:w-[360px]',
        ]"
      >
        <!-- 工具栏 -->
        <div
          class="flex items-center justify-between border-b border-border/50 px-2 py-2 lg:px-4 lg:py-3"
        >
          <div v-show="!panelCollapsed" class="flex min-w-0 items-center gap-2">
            <IconifyIcon
              icon="lucide:network"
              class="h-4 w-4 flex-shrink-0 text-primary lg:h-5 lg:w-5"
            />
            <span class="truncate text-sm font-medium lg:text-base">
              {{ $t('tenant.system.userArchitecture.roleList') }}
            </span>
          </div>
          <div class="flex items-center gap-0.5 lg:gap-1">
            <template v-if="!panelCollapsed">
              <Tooltip :title="$t('tenant.system.userArchitecture.refresh')">
                <Button
                  type="text"
                  size="small"
                  :loading="rolesLoading"
                  @click="loadRoles"
                >
                  <template #icon>
                    <IconifyIcon
                      icon="lucide:refresh-cw"
                      class="!text-xs lg:!text-sm"
                    />
                  </template>
                </Button>
              </Tooltip>
              <Button
                v-access:code="['tenant_user_role:create']"
                type="primary"
                size="small"
                class="!px-2 lg:!px-3"
                @click="handleCreateRole"
              >
                <template #icon>
                  <IconifyIcon icon="lucide:plus" />
                </template>
                <span class="hidden sm:inline">
                  {{ $t('tenant.system.userArchitecture.createRole') }}
                </span>
              </Button>
            </template>
            <!-- 折叠/展开按钮 -->
            <Tooltip
              :title="
                panelCollapsed
                  ? $t('tenant.system.userArchitecture.expandSidebar')
                  : $t('tenant.system.userArchitecture.collapseSidebar')
              "
            >
              <Button
                type="text"
                size="small"
                @click="panelCollapsed = !panelCollapsed"
              >
                <template #icon>
                  <IconifyIcon
                    :icon="
                      panelCollapsed
                        ? 'lucide:panel-left-open'
                        : 'lucide:panel-left-close'
                    "
                  />
                </template>
              </Button>
            </Tooltip>
          </div>
        </div>

        <!-- 搜索框 -->
        <div v-show="!panelCollapsed" class="border-b border-border/30 px-2 py-2 lg:px-3">
          <Input
            v-model:value="searchKeyword"
            :placeholder="$t('tenant.system.userArchitecture.searchRole')"
            allow-clear
            size="small"
          >
            <template #prefix>
              <IconifyIcon icon="lucide:search" class="text-muted-foreground" />
            </template>
          </Input>
        </div>

        <!-- 角色列表 -->
        <div v-show="!panelCollapsed" class="flex-1 overflow-y-auto p-2 lg:p-3">
          <Spin :spinning="rolesLoading">
            <div v-if="filteredRoles.length > 0" class="space-y-1">
              <div
                v-for="role in filteredRoles"
                :key="role.id"
                class="group cursor-pointer rounded-lg border border-transparent px-3 py-2.5 transition-all duration-150 hover:bg-accent/50"
                :class="[
                  selectedRole?.id === role.id
                    ? 'border-primary/30 bg-primary/5 shadow-sm'
                    : '',
                ]"
                @click="handleSelectRole(role)"
              >
                <div class="flex items-center gap-2.5">
                  <div
                    class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg"
                    :class="role.isActive ? 'bg-primary/10' : 'bg-muted'"
                  >
                    <IconifyIcon
                      icon="lucide:shield"
                      class="h-4 w-4"
                      :class="
                        role.isActive
                          ? 'text-primary'
                          : 'text-muted-foreground'
                      "
                    />
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-1.5">
                      <span class="truncate text-sm font-medium text-foreground">
                        {{ role.name }}
                      </span>
                      <Tag v-if="role.isSystem" color="orange" class="!text-[10px] !leading-tight !px-1">
                        {{ $t('tenant.system.userRole.isSystem') }}
                      </Tag>
                    </div>
                    <div class="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                      <code class="rounded bg-muted/70 px-1 text-[10px]">{{ role.code }}</code>
                      <span>{{ role.memberCount }}{{ $t('tenant.system.userArchitecture.memberUnit') }}</span>
                    </div>
                  </div>
                  <div class="flex-shrink-0">
                    <span
                      class="inline-block h-2 w-2 rounded-full"
                      :class="role.isActive ? 'bg-success' : 'bg-muted-foreground/30'"
                    />
                  </div>
                </div>
              </div>
            </div>
            <Empty
              v-else
              :description="$t('tenant.system.userArchitecture.noRoles')"
              class="py-8"
            />
          </Spin>
        </div>

        <!-- 折叠时显示图标 -->
        <div
          v-show="panelCollapsed"
          class="flex flex-1 flex-col items-center gap-2 py-4"
        >
          <Tooltip
            :title="$t('tenant.system.userArchitecture.roleList')"
            placement="right"
          >
            <IconifyIcon icon="lucide:network" class="h-5 w-5 text-primary" />
          </Tooltip>
        </div>
      </div>

      <!-- ==================== 右侧：角色详情 + 用户成员 ==================== -->
      <div
        class="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl bg-card shadow-sm"
      >
        <!-- 未选中角色时的提示 -->
        <div
          v-if="!selectedRole"
          class="flex flex-1 items-center justify-center text-muted-foreground"
        >
          <div class="px-4 text-center">
            <IconifyIcon
              icon="lucide:mouse-pointer-click"
              class="mx-auto mb-3 h-12 w-12 opacity-30 lg:h-16 lg:w-16"
            />
            <p class="text-base lg:text-lg">
              {{ $t('tenant.system.userArchitecture.selectRoleHint') }}
            </p>
            <p class="mt-1 text-xs lg:text-sm">
              {{ $t('tenant.system.userArchitecture.selectRoleSubHint') }}
            </p>
          </div>
        </div>

        <!-- 选中角色时显示详情 + 成员表格 -->
        <template v-else>
          <!-- 角色头部信息 -->
          <div class="border-b border-border/50 px-3 py-3 lg:px-6 lg:py-4">
            <!-- 第一行：标题和操作按钮 -->
            <div class="flex items-start justify-between gap-3">
              <div class="flex min-w-0 items-center gap-2 lg:gap-3">
                <div
                  class="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-primary/10 lg:h-12 lg:w-12"
                >
                  <IconifyIcon
                    icon="lucide:shield"
                    class="h-5 w-5 text-primary lg:h-6 lg:w-6"
                  />
                </div>
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-2">
                    <h2 class="truncate text-base font-semibold lg:text-xl">
                      {{ selectedRole.name }}
                    </h2>
                    <Tag
                      :class="
                        selectedRole.isActive
                          ? 'border-success/30 bg-success/10 text-success'
                          : ''
                      "
                      class="flex-shrink-0"
                    >
                      {{
                        selectedRole.isActive
                          ? $t('tenant.system.userArchitecture.enabled')
                          : $t('tenant.system.userArchitecture.disabled')
                      }}
                    </Tag>
                    <Tag v-if="selectedRole.isSystem" color="orange">
                      {{ $t('tenant.system.userRole.isSystem') }}
                    </Tag>
                  </div>
                  <div
                    class="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground lg:mt-1 lg:gap-x-3 lg:text-sm"
                  >
                    <code class="rounded bg-muted px-1.5 py-0.5 text-xs">{{
                      selectedRole.code
                    }}</code>
                    <span>·</span>
                    <span>
                      {{ selectedRole.memberCount }}{{ $t('tenant.system.userArchitecture.memberUnit') }}
                    </span>
                    <span>·</span>
                    <Badge
                      v-if="selectedRole.permissionsCount > 0"
                      :count="selectedRole.permissionsCount"
                      :number-style="{ backgroundColor: 'var(--primary)' }"
                    />
                    <span v-else class="text-muted-foreground">
                      {{ $t('tenant.system.userRole.noPermissions') }}
                    </span>
                  </div>
                </div>
              </div>
              <div class="flex flex-shrink-0 gap-2">
                <Tooltip :title="$t('tenant.system.userRole.assignPermissions')">
                  <Button
                    v-access:code="['tenant_user_role:assign_permissions']"
                    size="small"
                    @click="handleAssignPermissions(selectedRole)"
                  >
                    <template #icon>
                      <IconifyIcon icon="lucide:shield-check" />
                    </template>
                  </Button>
                </Tooltip>
                <Switch
                  v-access:code="['tenant_user_role:toggle']"
                  :checked="selectedRole.isActive"
                  size="small"
                  @change="handleToggleRoleStatus(selectedRole)"
                />
                <Button
                  v-access:code="['tenant_user_role:update']"
                  size="small"
                  @click="handleEditRole(selectedRole)"
                >
                  <template #icon>
                    <IconifyIcon icon="lucide:pencil" />
                  </template>
                  <span class="hidden sm:inline">{{
                    $t('shared.common.edit')
                  }}</span>
                </Button>
                <Popconfirm
                  :title="
                    $t('tenant.system.userRole.messages.deleteConfirm', {
                      name: selectedRole.name,
                    })
                  "
                  :ok-text="$t('shared.common.confirm')"
                  :cancel-text="$t('shared.common.cancel')"
                  :ok-button-props="{ danger: true }"
                  @confirm="handleDeleteRole(selectedRole)"
                >
                  <Button
                    v-access:code="['tenant_user_role:delete']"
                    danger
                    size="small"
                    :loading="roleDeleting"
                    :disabled="selectedRole.isSystem"
                  >
                    <template #icon>
                      <IconifyIcon icon="lucide:trash-2" />
                    </template>
                    <span class="hidden sm:inline">{{
                      $t('shared.common.delete')
                    }}</span>
                  </Button>
                </Popconfirm>
              </div>
            </div>

            <!-- 第二行：描述 -->
            <div
              v-if="selectedRole.description"
              class="mt-2 rounded bg-muted/50 px-2 py-1.5 text-xs text-muted-foreground"
            >
              {{ selectedRole.description }}
            </div>
          </div>

          <!-- 成员管理面板 -->
          <div class="flex-1 overflow-hidden p-2 lg:p-4">
            <Card class="h-full overflow-hidden" size="small">
              <template #title>
                <span class="text-sm lg:text-base">
                  {{ $t('tenant.system.userArchitecture.memberTitle') }}
                </span>
              </template>
              <MemberFormDrawer @success="onMemberFormSuccess" />
              <MemberGrid>
                <template #username_cell="{ row }">
                  <div class="flex items-center gap-2">
                    <div class="relative flex-shrink-0">
                      <div
                        class="flex size-8 items-center justify-center rounded-lg"
                        :class="row.isActive ? 'bg-primary/10' : 'bg-muted'"
                      >
                        <IconifyIcon
                          icon="lucide:user"
                          class="size-4"
                          :class="
                            row.isActive
                              ? 'text-primary'
                              : 'text-muted-foreground'
                          "
                        />
                      </div>
                      <Tooltip
                        :title="
                          presenceStore.isOnline('tenant_user', row.id)
                            ? $t('tenant.system.userArchitecture.online')
                            : $t('tenant.system.userArchitecture.offline')
                        "
                      >
                        <span
                          class="absolute -bottom-0.5 -right-0.5 block size-2.5 rounded-full border-2 border-background"
                          :class="
                            presenceStore.isOnline('tenant_user', row.id)
                              ? 'bg-green-500'
                              : 'bg-muted-foreground/30'
                          "
                        />
                      </Tooltip>
                    </div>
                    <div class="flex flex-col">
                      <span class="font-medium text-foreground">
                        {{ row.username }}
                      </span>
                      <span
                        v-if="row.nickname"
                        class="text-xs text-muted-foreground"
                      >
                        {{ row.nickname }}
                      </span>
                    </div>
                  </div>
                </template>

                <template #status_cell="{ row }">
                  <Switch
                    v-access:code="['tenant_user:toggle']"
                    :checked="row.isActive"
                    size="small"
                    @change="
                      (checked: boolean | string | number) =>
                        handleMemberToggleStatus(!!checked, row)
                    "
                  />
                </template>

                <template #lastLoginAt_cell="{ row }">
                  <Tooltip
                    v-if="row.lastLoginAt"
                    :title="formatDate(row.lastLoginAt)"
                  >
                    <span class="text-muted-foreground">
                      {{ formatRelativeTime(row.lastLoginAt) }}
                    </span>
                  </Tooltip>
                  <span v-else class="text-muted-foreground">-</span>
                </template>

                <template #createdAt_cell="{ row }">
                  <Tooltip :title="formatDate(row.createdAt)">
                    <span class="text-muted-foreground">
                      {{ formatRelativeTime(row.createdAt) }}
                    </span>
                  </Tooltip>
                </template>
              </MemberGrid>
            </Card>
          </div>
        </template>
      </div>
    </div>

    <!-- 角色表单弹窗 -->
    <RoleFormDrawer @success="onRoleFormSuccess" />

    <!-- 权限分配抽屉 -->
    <PermissionDrawer
      v-model:open="permissionDrawerVisible"
      :role="currentPermissionRole"
      @saved="onPermissionSaved"
    />
  </Page>
</template>
