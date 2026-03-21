<script lang="ts" setup>
import type { TenantUserRoleInfo } from '#/api/tenant/tenant-user-roles';
import type { TenantUserInfo } from '#/api/tenant/tenant-users';

import { computed, h, nextTick, onMounted, ref, watch } from 'vue';

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

import {
  clearSelection,
  getSelectedIds,
  useCrudPage,
} from '#/adapter/vxe-table';
import {
  deleteTenantUserRoleApi,
  getTenantUserRoleListApi,
  toggleTenantUserRoleStatusApi,
} from '#/api/tenant/tenant-user-roles';
import {
  approveTenantUserApi,
  batchApproveTenantUserApi,
  batchRejectTenantUserApi,
  forceLogoutTenantUserApi,
  getTenantUserListApi,
  rejectTenantUserApi,
  resetTenantUserPasswordApi,
  toggleTenantUserStatusApi,
} from '#/api/tenant/tenant-users';
import {
  buildPageAIFormExtraData,
  createKeywordSearchPageOperation,
  createPrefilledCreatePageOperation,
  createRefreshPageOperation,
} from '#/composables/use-page-ai-operation-helpers';
import {
  usePageAIContext,
  usePageAIOperations,
} from '#/composables/use-page-ai-registration';
import { $t } from '#/locales';
import { usePresenceStore } from '#/store';
import { formatDate, formatRelativeTime } from '#/utils/common';

import {
  getRoleFormDefaults,
  getUserFormDefaults,
  useMemberColumns,
  useMemberSearchSchema,
  useUserFormSchema,
} from './data';
import PermissionDrawer from './modules/PermissionDrawer.vue';
import UserForm from './modules/UserForm.vue';
import UserRoleFormComponent from './modules/UserRoleForm.vue';

defineOptions({ name: 'TenantUserArchitecture' });

const AI_PAGE_KEY = 'tenant.system.userArchitecture';

// ============================================================
// Left: Role list / 左侧角色列表
// ============================================================

const ALL_USERS_ID = -1;

const roles = ref<TenantUserRoleInfo[]>([]);
const rolesLoading = ref(false);
const searchKeyword = ref('');
const selectedRole = ref<null | TenantUserRoleInfo>(null);
const panelCollapsed = ref(false);
const isAllUsersSelected = computed(
  () => selectedRole.value?.id === ALL_USERS_ID,
);

const filteredRoles = computed(() => {
  if (!searchKeyword.value) return roles.value;
  const kw = searchKeyword.value.toLowerCase();
  return roles.value.filter(
    (r) =>
      r.name.toLowerCase().includes(kw) || r.code.toLowerCase().includes(kw),
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
    // If previously selected role still exists, update reference / 如果之前选中的角色仍然存在，更新引用
    if (selectedRole.value) {
      const updated = roles.value.find((r) => r.id === selectedRole.value!.id);
      selectedRole.value = updated || null;
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
// Role CRUD drawer (useVbenDrawer) / 角色 CRUD 弹窗
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
      ...buildPageAIFormExtraData({
        pageKey: AI_PAGE_KEY,
        defaults: getRoleFormDefaults(),
      }),
    })
    .open();
}

function handleEditRole(role: TenantUserRoleInfo) {
  roleFormApi
    .setData({
      ...role,
      mode: 'edit' as const,
      _resource: '/tenant/user-roles',
      ...buildPageAIFormExtraData({ pageKey: AI_PAGE_KEY }),
    })
    .open();
}

// ============================================================
// Role deletion / 角色删除
// ============================================================

const roleDeleting = ref(false);

async function handleDeleteRole(role: TenantUserRoleInfo) {
  if (role.isSystem) {
    message.warning(
      $t('tenant.system.userRole.messages.systemRoleCannotDelete'),
    );
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
// Role status toggle / 角色状态切换
// ============================================================

async function handleToggleRoleStatus(role: TenantUserRoleInfo) {
  const newStatus = !role.isActive;
  try {
    await toggleTenantUserRoleStatusApi(role.id, newStatus);
    message.success($t('ui.actionMessage.operationSuccess'));
    await loadRoles();
  } catch {
    // error handled by request client / 错误由请求拦截器处理
  }
}

// ============================================================
// Permission assignment / 权限分配
// ============================================================

const permissionDrawerVisible = ref(false);
const currentPermissionRole = ref<null | TenantUserRoleInfo>(null);

function handleAssignPermissions(role: TenantUserRoleInfo) {
  currentPermissionRole.value = role;
  permissionDrawerVisible.value = true;
}

function onPermissionSaved() {
  loadRoles();
}

// ============================================================
// Right: User member table / 右侧用户成员表格
// ============================================================

/** Wrapper to match ToggleStatusApi signature / 包装以匹配 ToggleStatusApi 签名 */
async function toggleUserStatus(id: number, data: Record<string, boolean>) {
  return toggleTenantUserStatusApi(id, !!data.is_active);
}

/** User list API with role_id filter (no filter for "all users") / 带 role_id 过滤的用户列表 API */
function getUserListForRole(params: Record<string, unknown>) {
  if (!selectedRole.value) {
    return Promise.resolve({ items: [], total: 0, page: 1, page_size: 20 });
  }
  if (isAllUsersSelected.value) {
    return getTenantUserListApi(params);
  }
  return getTenantUserListApi({
    ...params,
    'filter[role_id][eq]': selectedRole.value.id,
  });
}

// ============================================================
// User approval operations / 用户审批操作
// ============================================================

async function onApproveUser(row: TenantUserInfo) {
  try {
    await approveTenantUserApi(row.id);
    message.success($t('tenant.system.user.messages.approveSuccess'));
    onMemberRefresh();
  } catch {
    // error handled by request client / 错误由请求拦截器处理
  }
}

async function onRejectUser(row: TenantUserInfo) {
  try {
    await rejectTenantUserApi(row.id);
    message.success($t('tenant.system.user.messages.rejectSuccess'));
    onMemberRefresh();
  } catch {
    // error handled by request client / 错误由请求拦截器处理
  }
}

async function handleBatchApprove() {
  const ids = getSelectedIds<TenantUserInfo>(memberGridApi?.grid);
  if (ids.length === 0) {
    message.warning($t('tenant.system.user.messages.selectUsersFirst'));
    return;
  }
  try {
    await batchApproveTenantUserApi(ids as number[]);
    message.success($t('tenant.system.user.messages.batchApproveSuccess'));
    clearSelection(memberGridApi?.grid);
    onMemberRefresh();
  } catch {
    // error handled by request client / 错误由请求拦截器处理
  }
}

async function handleBatchReject() {
  const ids = getSelectedIds<TenantUserInfo>(memberGridApi?.grid);
  if (ids.length === 0) {
    message.warning($t('tenant.system.user.messages.selectUsersFirst'));
    return;
  }
  try {
    await batchRejectTenantUserApi(ids as number[]);
    message.success($t('tenant.system.user.messages.batchRejectSuccess'));
    clearSelection(memberGridApi?.grid);
    onMemberRefresh();
  } catch {
    // error handled by request client / 错误由请求拦截器处理
  }
}

const newPasswordRef = ref('');
const confirmPasswordRef = ref('');

async function onForceLogout(row: TenantUserInfo) {
  try {
    await forceLogoutTenantUserApi(row.id);
    message.success(
      $t('common.auth.forceLogoutSuccess', { name: row.username }),
    );
    onMemberRefresh();
  } catch {
    message.error($t('common.requestFailed'));
  }
}

async function onResetPassword(row: TenantUserInfo) {
  newPasswordRef.value = '';
  confirmPasswordRef.value = '';
  Modal.confirm({
    title: $t('tenant.system.user.resetPassword'),
    content: () =>
      h('div', { class: 'flex flex-col gap-3' }, [
        h(Input.Password, {
          placeholder: $t('tenant.system.user.newPassword'),
          value: newPasswordRef.value,
          'onUpdate:value': (val: string) => {
            newPasswordRef.value = val;
          },
        }),
        h(Input.Password, {
          placeholder: $t(
            'tenant.system.user.placeholder.inputNewPasswordConfirm',
          ),
          value: confirmPasswordRef.value,
          'onUpdate:value': (val: string) => {
            confirmPasswordRef.value = val;
          },
        }),
      ]),
    onOk: async () => {
      if (!newPasswordRef.value || newPasswordRef.value.length < 6) {
        message.warning($t('tenant.system.user.placeholder.inputPassword'));
        throw new Error('validation');
      }
      if (newPasswordRef.value !== confirmPasswordRef.value) {
        message.warning(
          $t('tenant.system.user.messages.resetPasswordMismatch'),
        );
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
  gridApi: memberGridApi,
  FormDrawer: MemberFormDrawer,
  formApi: memberFormApi,
  onRefresh: onMemberRefresh,
  handleToggleStatus: handleMemberToggleStatus,
  aiPageKey: memberAiPageKey,
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
    forceLogout: onForceLogout,
    resetPassword: onResetPassword,
  },
  ai: {
    pageKey: AI_PAGE_KEY,
    formSchema: (isEdit?: boolean) => useUserFormSchema(Boolean(isEdit)),
  },
});

/** Reload member table on role selection change (nextTick waits for Grid mount) / 角色选择变化时重新加载成员表 */
watch(selectedRole, async () => {
  await nextTick();
  onMemberRefresh();
});

/** After member form success, also refresh role list (update memberCount) / 成员表单成功后刷新角色列表 */
function onMemberFormSuccess() {
  onMemberRefresh();
  loadRoles();
}

// ============================================================
// Role form drawer callback / 角色表单弹窗回调
// ============================================================

function onRoleFormSuccess() {
  loadRoles();
}

// ============================================================
// Lifecycle / 生命周期
// ============================================================

const presenceStore = usePresenceStore();

onMounted(async () => {
  await loadRoles();
  // Select "All Users" by default / 默认选择"全部用户"
  selectedRole.value = {
    id: ALL_USERS_ID,
    name: $t('tenant.system.userArchitecture.allUsers'),
    code: 'all_users',
    memberCount: 0,
    isActive: true,
    isSystem: false,
    permissionsCount: 0,
  } as TenantUserRoleInfo;
  // Load business user online status / 加载业务用户在线状态
  presenceStore.loadTenantUserPresence();
});

// ============================================================
// AI Page Context
// ============================================================

usePageAIContext({
  pageKey: AI_PAGE_KEY,
  contextStrategy: 'extras',
  data: () => ({
    role_search_keyword: searchKeyword.value || null,
    roles_total: roles.value.length,
    selected_role_id: selectedRole.value?.id ?? null,
    selected_role_name: selectedRole.value?.name ?? null,
  }),
});

usePageAIOperations({
  pageKey: AI_PAGE_KEY,
  operationStrategy: 'append',
  operations: [
    createRefreshPageOperation({
      name: 'refresh_roles',
      action: loadRoles,
      description: 'Refresh the role list',
    }),
    createPrefilledCreatePageOperation({
      name: 'create_record',
      description:
        'Open the create role form and optionally pre-fill role fields',
      params: {
        description: {
          type: 'string',
          description: 'Role description',
        },
        is_active: {
          type: 'boolean',
          description: 'Whether the role should be active',
        },
        name: {
          type: 'string',
          description: 'Role name',
        },
        sort_order: {
          type: 'number',
          description: 'Role sort order',
        },
      },
      normalizeParams: (params) => {
        const defaults: Record<string, unknown> = {};
        if (params?.name) defaults.name = params.name;
        if (params?.description) defaults.description = params.description;
        if (typeof params?.sort_order === 'number') {
          defaults.sort_order = params.sort_order;
        }
        if (typeof params?.is_active === 'boolean') {
          defaults.is_active = params.is_active;
        }
        return defaults;
      },
      openCreate: async (defaults) => {
        roleFormApi
          .setData({
            mode: 'add' as const,
            _resource: '/tenant/user-roles',
            ...buildPageAIFormExtraData({
              pageKey: AI_PAGE_KEY,
              baseDefaults: getRoleFormDefaults(),
              defaults,
            }),
          })
          .open();
      },
    }),
    createKeywordSearchPageOperation({
      label: $t('shared.pageOperation.searchByKeyword'),
      description: 'Search roles by name keyword',
      keywordDescription: 'Role name keyword',
      normalize: (keyword) => keyword.toLowerCase(),
      setKeyword: (keyword) => {
        searchKeyword.value = keyword;
      },
    }),
    createPrefilledCreatePageOperation({
      name: 'add_member',
      label: $t('tenant.system.userArchitecture.addMember'),
      description:
        'Open the add member form and optionally pre-fill member fields',
      params: {
        email: {
          type: 'string',
          description: 'Member email',
        },
        is_active: {
          type: 'boolean',
          description: 'Whether the member should be active',
        },
        nickname: {
          type: 'string',
          description: 'Member nickname',
        },
        phone: {
          type: 'string',
          description: 'Member phone number',
        },
        role_id: {
          type: 'number',
          description: 'Target role ID',
        },
        username: {
          type: 'string',
          description: 'Member username',
        },
      },
      normalizeParams: (params) => {
        const selectedRoleId =
          selectedRole.value && !isAllUsersSelected.value
            ? selectedRole.value.id
            : undefined;
        return {
          ...(params?.email ? { email: params.email } : {}),
          ...(typeof params?.is_active === 'boolean'
            ? { is_active: params.is_active }
            : {}),
          ...(params?.nickname ? { nickname: params.nickname } : {}),
          ...(params?.phone ? { phone: params.phone } : {}),
          ...(typeof params?.role_id === 'number'
            ? { role_id: params.role_id }
            : selectedRoleId
              ? { role_id: selectedRoleId }
              : {}),
          ...(params?.username ? { username: params.username } : {}),
        };
      },
      openCreate: async (defaults) => {
        const formApi = memberFormApi;
        if (!formApi) return;
        formApi
          .setData({
            mode: 'add',
            _resource: '/tenant/users',
            ...buildPageAIFormExtraData({
              pageKey: memberAiPageKey ?? AI_PAGE_KEY,
              baseDefaults: getUserFormDefaults(),
              defaults,
            }),
          })
          .open();
      },
    }),
  ],
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
        <div
          v-show="!panelCollapsed"
          class="border-b border-border/30 px-2 py-2 lg:px-3"
        >
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
            <div class="space-y-1">
              <!-- 全部用户（虚拟选项） -->
              <div
                class="group cursor-pointer rounded-lg border border-transparent px-3 py-2.5 transition-all duration-150 hover:bg-accent/50"
                :class="[
                  isAllUsersSelected
                    ? 'border-primary/30 bg-primary/5 shadow-sm'
                    : '',
                ]"
                @click="
                  selectedRole = {
                    id: ALL_USERS_ID,
                    name: $t('tenant.system.userArchitecture.allUsers'),
                    code: 'all_users',
                    memberCount: 0,
                    isActive: true,
                    isSystem: false,
                    permissionsCount: 0,
                  } as TenantUserRoleInfo
                "
              >
                <div class="flex items-center gap-2.5">
                  <div
                    class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-accent"
                  >
                    <IconifyIcon
                      icon="lucide:users"
                      class="h-4 w-4 text-foreground"
                    />
                  </div>
                  <div class="min-w-0 flex-1">
                    <span class="truncate text-sm font-medium text-foreground">
                      {{ $t('tenant.system.userArchitecture.allUsers') }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- 角色分隔线 -->
              <div
                v-if="filteredRoles.length > 0"
                class="my-1 border-t border-border/30"
              ></div>

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
                        role.isActive ? 'text-primary' : 'text-muted-foreground'
                      "
                    />
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-1.5">
                      <span
                        class="truncate text-sm font-medium text-foreground"
                      >
                        {{ role.name }}
                      </span>
                      <Tag
                        v-if="role.isSystem"
                        color="orange"
                        class="!px-1 !text-[10px] !leading-tight"
                      >
                        {{ $t('tenant.system.userRole.isSystem') }}
                      </Tag>
                    </div>
                    <div
                      class="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground"
                    >
                      <code class="rounded bg-muted/70 px-1 text-[10px]">{{
                        role.code
                      }}</code>
                      <span
                        >{{ role.memberCount
                        }}{{
                          $t('tenant.system.userArchitecture.memberUnit')
                        }}</span
                      >
                    </div>
                  </div>
                  <div class="flex-shrink-0">
                    <span
                      class="inline-block h-2 w-2 rounded-full"
                      :class="
                        role.isActive ? 'bg-success' : 'bg-muted-foreground/30'
                      "
                    ></span>
                  </div>
                </div>
              </div>
            </div>
            <Empty
              v-if="filteredRoles.length === 0 && searchKeyword"
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
          <!-- 全部用户头部 -->
          <div
            v-if="isAllUsersSelected"
            class="border-b border-border/50 px-3 py-3 lg:px-6 lg:py-4"
          >
            <div class="flex min-w-0 items-center gap-2 lg:gap-3">
              <div
                class="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-accent lg:h-12 lg:w-12"
              >
                <IconifyIcon
                  icon="lucide:users"
                  class="h-5 w-5 text-foreground lg:h-6 lg:w-6"
                />
              </div>
              <div class="min-w-0 flex-1">
                <h2 class="truncate text-base font-semibold lg:text-xl">
                  {{ $t('tenant.system.userArchitecture.allUsers') }}
                </h2>
                <p class="mt-0.5 text-xs text-muted-foreground lg:text-sm">
                  {{ $t('tenant.system.userArchitecture.allUsersDesc') }}
                </p>
              </div>
            </div>
          </div>

          <!-- 角色头部信息 -->
          <div
            v-else
            class="border-b border-border/50 px-3 py-3 lg:px-6 lg:py-4"
          >
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
                      {{ selectedRole.memberCount
                      }}{{ $t('tenant.system.userArchitecture.memberUnit') }}
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
                <Tooltip
                  :title="$t('tenant.system.userRole.assignPermissions')"
                >
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

            <!-- 第二行：描述（内置角色用 i18n，与库中语言无关） -->
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
                  {{
                    isAllUsersSelected
                      ? $t('tenant.system.userArchitecture.allUsersListTitle')
                      : $t('tenant.system.userArchitecture.memberTitle')
                  }}
                </span>
              </template>
              <template #extra>
                <div class="flex items-center gap-2">
                  <Popconfirm
                    :title="
                      $t('tenant.system.user.messages.batchApproveConfirm')
                    "
                    :ok-text="$t('shared.common.confirm')"
                    :cancel-text="$t('shared.common.cancel')"
                    @confirm="handleBatchApprove"
                  >
                    <Button
                      v-access:code="['tenant_user:approve']"
                      size="small"
                      type="primary"
                      class="!border-success !bg-success hover:!bg-success/80"
                    >
                      <template #icon>
                        <IconifyIcon icon="lucide:check-circle" />
                      </template>
                      {{ $t('tenant.system.user.batchApprove') }}
                    </Button>
                  </Popconfirm>
                  <Popconfirm
                    :title="
                      $t('tenant.system.user.messages.batchRejectConfirm')
                    "
                    :ok-text="$t('shared.common.confirm')"
                    :cancel-text="$t('shared.common.cancel')"
                    :ok-button-props="{ danger: true }"
                    @confirm="handleBatchReject"
                  >
                    <Button
                      v-access:code="['tenant_user:reject']"
                      size="small"
                      danger
                    >
                      <template #icon>
                        <IconifyIcon icon="lucide:x-circle" />
                      </template>
                      {{ $t('tenant.system.user.batchReject') }}
                    </Button>
                  </Popconfirm>
                </div>
              </template>
              <MemberFormDrawer @success="onMemberFormSuccess" />
              <MemberGrid
                :checkbox-config="{ trigger: 'cell', highlight: true }"
              >
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
                        ></span>
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

                <template #approval_cell="{ row }">
                  <div class="flex items-center gap-1">
                    <Tag
                      v-if="row.approvalStatus === 'approved'"
                      color="success"
                      class="!m-0"
                    >
                      {{ $t('tenant.system.user.approvalStatus.approved') }}
                    </Tag>
                    <Tag
                      v-else-if="row.approvalStatus === 'rejected'"
                      color="error"
                      class="!m-0"
                    >
                      {{ $t('tenant.system.user.approvalStatus.rejected') }}
                    </Tag>
                    <template v-else-if="row.approvalStatus === 'pending'">
                      <Tag color="warning" class="!m-0">
                        {{ $t('tenant.system.user.approvalStatus.pending') }}
                      </Tag>
                      <Tooltip :title="$t('tenant.system.user.approve')">
                        <Button
                          v-access:code="['tenant_user:approve']"
                          type="link"
                          size="small"
                          class="!p-0 !text-success"
                          @click="onApproveUser(row)"
                        >
                          <template #icon>
                            <IconifyIcon icon="lucide:check" class="!text-xs" />
                          </template>
                        </Button>
                      </Tooltip>
                      <Tooltip :title="$t('tenant.system.user.reject')">
                        <Button
                          v-access:code="['tenant_user:reject']"
                          type="link"
                          size="small"
                          class="!p-0"
                          danger
                          @click="onRejectUser(row)"
                        >
                          <template #icon>
                            <IconifyIcon icon="lucide:x" class="!text-xs" />
                          </template>
                        </Button>
                      </Tooltip>
                    </template>
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
