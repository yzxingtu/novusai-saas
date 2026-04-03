<script lang="ts" setup>
import type { OrganizationTreeSelectOption } from './data';

import type { TenantUserRoleInfo } from '#/api/tenant/tenant-user-roles';
import type { TenantUserInfo } from '#/api/tenant/tenant-users';

import { computed, h, nextTick, onMounted, ref, watch } from 'vue';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
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
import { getTenantOrganizationTreeApi } from '#/api/tenant/organization';
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
import { showRequestError } from '#/utils/error-helpers';

import {
  buildOrganizationOptionLabelMap,
  getRoleFormDefaults,
  getUserFormDefaults,
  toOrganizationTreeSelectOptions,
  useMemberColumns,
  useMemberSearchSchema,
  useUserFormSchema,
} from './data';
import PermissionDrawer from './modules/PermissionDrawer.vue';
import UserForm from './modules/UserForm.vue';
import UserRoleFormComponent from './modules/UserRoleForm.vue';

defineOptions({ name: 'TenantUserArchitecture' });

const AI_PAGE_KEY = 'tenant.system.userArchitecture';

const roles = ref<TenantUserRoleInfo[]>([]);
const rolesLoading = ref(false);
const roleSearchKeyword = ref('');
const selectedRole = ref<null | TenantUserRoleInfo>(null);
const organizationOptions = ref<OrganizationTreeSelectOption[]>([]);
const organizationLabelMap = ref<Map<number, string>>(new Map());
const currentOrgFilterId = ref<null | number>(null);
const currentOrgFilterName = ref<null | string>(null);
const sidebarCollapsed = ref(false);
const permissionDrawerVisible = ref(false);
const currentPermissionRole = ref<null | TenantUserRoleInfo>(null);
const roleDeleting = ref(false);
const newPasswordRef = ref('');
const confirmPasswordRef = ref('');
const presenceStore = usePresenceStore();

const filteredRoles = computed(() => {
  if (!roleSearchKeyword.value) return roles.value;
  const keyword = roleSearchKeyword.value.toLowerCase();
  return roles.value.filter(
    (role) =>
      role.name.toLowerCase().includes(keyword) ||
      role.code.toLowerCase().includes(keyword),
  );
});

const orgFilterLabel = computed(
  () =>
    currentOrgFilterName.value ||
    $t('tenant.system.userArchitecture.allOrganizations'),
);

const roleFilterLabel = computed(
  () =>
    selectedRole.value?.name ||
    $t('tenant.system.userArchitecture.allPermissionRoles'),
);

function normalizeNumericFilterValue(value: unknown): null | number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  return null;
}

function syncOrgFilterState(values: Record<string, unknown> = {}) {
  const nextOrgId = normalizeNumericFilterValue(
    values['filter[org_node_id][eq]'],
  );
  currentOrgFilterId.value = nextOrgId;
  currentOrgFilterName.value =
    nextOrgId === null
      ? null
      : (organizationLabelMap.value.get(nextOrgId) ?? null);
}

const [RoleFormDrawer, roleFormApi] = useVbenDrawer({
  connectedComponent: UserRoleFormComponent,
  destroyOnClose: true,
});

async function loadRoles() {
  rolesLoading.value = true;
  try {
    const response = await getTenantUserRoleListApi({
      'page[size]': 100,
      sort: 'sort_order',
    });
    roles.value = response.items;
    if (selectedRole.value) {
      selectedRole.value =
        roles.value.find((role) => role.id === selectedRole.value?.id) || null;
    }
  } catch {
    roles.value = [];
  } finally {
    rolesLoading.value = false;
  }
}

async function loadOrganizationOptions() {
  try {
    const orgTree = await getTenantOrganizationTreeApi();
    const options = toOrganizationTreeSelectOptions(orgTree);
    organizationOptions.value = options;
    organizationLabelMap.value = buildOrganizationOptionLabelMap(options);
  } catch {
    organizationOptions.value = [];
    organizationLabelMap.value = new Map();
  }

  await nextTick();
  if (memberGridApi.formApi) {
    memberGridApi.formApi.updateSchema([
      {
        componentProps: {
          treeData: organizationOptions.value,
        },
        fieldName: 'filter[org_node_id][eq]',
      },
    ]);
    syncOrgFilterState(
      ((await memberGridApi.formApi.getValues()) as Record<string, unknown>) ??
        {},
    );
  }
}

async function refreshFilters() {
  await Promise.all([loadOrganizationOptions(), loadRoles()]);
  onMemberRefresh();
}

function handleSelectRole(role: TenantUserRoleInfo) {
  selectedRole.value = role;
}

function clearRoleFilter() {
  selectedRole.value = null;
}

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

async function handleToggleRoleStatus(role: TenantUserRoleInfo) {
  try {
    await toggleTenantUserRoleStatusApi(role.id, !role.isActive);
    message.success($t('ui.actionMessage.operationSuccess'));
    await loadRoles();
  } catch {
    // Error handled by request client / 错误由请求拦截器处理
  }
}

function handleAssignPermissions(role: TenantUserRoleInfo) {
  currentPermissionRole.value = role;
  permissionDrawerVisible.value = true;
}

function onPermissionSaved() {
  loadRoles();
}

async function toggleUserStatus(id: number, data: Record<string, boolean>) {
  return toggleTenantUserStatusApi(id, !!data.is_active);
}

function getUserListForFilters(params: Record<string, unknown>) {
  syncOrgFilterState(params);
  const nextParams: Record<string, unknown> = { ...params };
  if (selectedRole.value?.id) {
    nextParams['filter[role_id][eq]'] = selectedRole.value.id;
  }
  return getTenantUserListApi(nextParams);
}

async function onApproveUser(row: TenantUserInfo) {
  try {
    await approveTenantUserApi(row.id);
    message.success($t('tenant.system.user.messages.approveSuccess'));
    onMemberRefresh();
  } catch {
    // Error handled by request client / 错误由请求拦截器处理
  }
}

async function onRejectUser(row: TenantUserInfo) {
  try {
    await rejectTenantUserApi(row.id);
    message.success($t('tenant.system.user.messages.rejectSuccess'));
    onMemberRefresh();
  } catch {
    // Error handled by request client / 错误由请求拦截器处理
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
    // Error handled by request client / 错误由请求拦截器处理
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
    // Error handled by request client / 错误由请求拦截器处理
  }
}

async function onForceLogout(row: TenantUserInfo) {
  try {
    await forceLogoutTenantUserApi(row.id);
    message.success(
      $t('common.auth.forceLogoutSuccess', { name: row.username }),
    );
    onMemberRefresh();
  } catch (error) {
    showRequestError(error, 'common.requestFailed');
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
          'onUpdate:value': (value: string) => {
            newPasswordRef.value = value;
          },
        }),
        h(Input.Password, {
          placeholder: $t(
            'tenant.system.user.placeholder.inputNewPasswordConfirm',
          ),
          value: confirmPasswordRef.value,
          'onUpdate:value': (value: string) => {
            confirmPasswordRef.value = value;
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
    list: getUserListForFilters,
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

function onMemberFormSuccess() {
  onMemberRefresh();
  loadRoles();
  loadOrganizationOptions();
}

function onRoleFormSuccess() {
  loadRoles();
}

watch(
  () => selectedRole.value?.id,
  async () => {
    await nextTick();
    onMemberRefresh();
  },
);

onMounted(async () => {
  await Promise.all([loadRoles(), loadOrganizationOptions()]);
  presenceStore.loadTenantUserPresence();
});

usePageAIContext({
  pageKey: AI_PAGE_KEY,
  contextStrategy: 'extras',
  data: () => ({
    org_filter_id: currentOrgFilterId.value,
    org_filter_name: currentOrgFilterName.value,
    permission_role_filter_id: selectedRole.value?.id ?? null,
    permission_role_filter_name: selectedRole.value?.name ?? null,
    permission_roles_total: roles.value.length,
  }),
});

usePageAIOperations({
  pageKey: AI_PAGE_KEY,
  operationStrategy: 'append',
  operations: [
    createRefreshPageOperation({
      name: 'refresh_filters',
      action: async () => {
        await refreshFilters();
      },
      description: $t(
        'tenant.system.userArchitecture.aiOperations.refreshFiltersDesc',
      ),
    }),
    createKeywordSearchPageOperation({
      label: $t('shared.pageOperation.searchByKeyword'),
      description: $t(
        'tenant.system.userArchitecture.aiOperations.searchRoleDesc',
      ),
      keywordDescription: $t(
        'tenant.system.userArchitecture.aiOperations.searchRoleKeyword',
      ),
      normalize: (keyword) => keyword.toLowerCase(),
      setKeyword: (keyword) => {
        roleSearchKeyword.value = keyword;
      },
    }),
    createPrefilledCreatePageOperation({
      name: 'create_permission_role',
      label: $t('tenant.system.userArchitecture.createRole'),
      description: $t(
        'tenant.system.userArchitecture.aiOperations.createRoleDesc',
      ),
      params: {
        description: {
          type: 'string',
          description: $t(
            'tenant.system.userArchitecture.aiOperations.createRoleParams.description',
          ),
        },
        is_active: {
          type: 'boolean',
          description: $t(
            'tenant.system.userArchitecture.aiOperations.createRoleParams.isActive',
          ),
        },
        name: {
          type: 'string',
          description: $t(
            'tenant.system.userArchitecture.aiOperations.createRoleParams.name',
          ),
        },
        sort_order: {
          type: 'number',
          description: $t(
            'tenant.system.userArchitecture.aiOperations.createRoleParams.sortOrder',
          ),
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
    createPrefilledCreatePageOperation({
      name: 'create_user',
      label: $t('tenant.system.user.create'),
      description: $t(
        'tenant.system.userArchitecture.aiOperations.createUserDesc',
      ),
      params: {
        email: {
          type: 'string',
          description: $t(
            'tenant.system.userArchitecture.aiOperations.createUserParams.email',
          ),
        },
        is_active: {
          type: 'boolean',
          description: $t(
            'tenant.system.userArchitecture.aiOperations.createUserParams.isActive',
          ),
        },
        nickname: {
          type: 'string',
          description: $t(
            'tenant.system.userArchitecture.aiOperations.createUserParams.nickname',
          ),
        },
        org_node_id: {
          type: 'number',
          description: $t(
            'tenant.system.userArchitecture.aiOperations.createUserParams.orgNodeId',
          ),
        },
        phone: {
          type: 'string',
          description: $t(
            'tenant.system.userArchitecture.aiOperations.createUserParams.phone',
          ),
        },
        role_id: {
          type: 'number',
          description: $t(
            'tenant.system.userArchitecture.aiOperations.createUserParams.roleId',
          ),
        },
        username: {
          type: 'string',
          description: $t(
            'tenant.system.userArchitecture.aiOperations.createUserParams.username',
          ),
        },
      },
      normalizeParams: (params) => {
        const fallbackOrgNodeId = currentOrgFilterId.value
          ? { org_node_id: currentOrgFilterId.value }
          : {};
        const fallbackRoleId = selectedRole.value?.id
          ? { role_id: selectedRole.value.id }
          : {};
        return {
          ...(params?.email ? { email: params.email } : {}),
          ...(typeof params?.is_active === 'boolean'
            ? { is_active: params.is_active }
            : {}),
          ...(params?.nickname ? { nickname: params.nickname } : {}),
          ...(typeof params?.org_node_id === 'number'
            ? { org_node_id: params.org_node_id }
            : fallbackOrgNodeId),
          ...(params?.phone ? { phone: params.phone } : {}),
          ...(typeof params?.role_id === 'number'
            ? { role_id: params.role_id }
            : fallbackRoleId),
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
      <div
        class="flex flex-shrink-0 flex-col overflow-hidden rounded-xl bg-card shadow-sm transition-all duration-300"
        :class="[
          sidebarCollapsed ? 'w-12' : 'w-[320px] lg:w-[360px] xl:w-[400px]',
        ]"
      >
        <div
          class="flex items-center justify-between border-b border-border/50 px-2 py-2 lg:px-4 lg:py-3"
        >
          <div
            v-show="!sidebarCollapsed"
            class="flex min-w-0 items-center gap-2"
          >
            <IconifyIcon
              icon="lucide:shield"
              class="h-4 w-4 flex-shrink-0 text-primary lg:h-5 lg:w-5"
            />
            <span class="truncate text-sm font-medium lg:text-base">
              {{ $t('tenant.system.userArchitecture.roleSidebarTitle') }}
            </span>
          </div>
          <div class="flex items-center gap-1">
            <template v-if="!sidebarCollapsed">
              <Tooltip :title="$t('tenant.system.userArchitecture.refresh')">
                <Button
                  type="text"
                  size="small"
                  :loading="rolesLoading"
                  @click="refreshFilters"
                >
                  <template #icon>
                    <IconifyIcon icon="lucide:refresh-cw" />
                  </template>
                </Button>
              </Tooltip>
            </template>
            <Tooltip
              :title="
                sidebarCollapsed
                  ? $t('tenant.system.userArchitecture.expandSidebar')
                  : $t('tenant.system.userArchitecture.collapseSidebar')
              "
            >
              <Button
                type="text"
                size="small"
                @click="sidebarCollapsed = !sidebarCollapsed"
              >
                <template #icon>
                  <IconifyIcon
                    :icon="
                      sidebarCollapsed
                        ? 'lucide:panel-left-open'
                        : 'lucide:panel-left-close'
                    "
                  />
                </template>
              </Button>
            </Tooltip>
          </div>
        </div>

        <div v-show="!sidebarCollapsed" class="flex-1 overflow-y-auto p-3">
          <Card size="small">
            <template #extra>
              <Button
                v-access:code="['tenant_user_role:create']"
                type="primary"
                size="small"
                @click="handleCreateRole"
              >
                <template #icon>
                  <IconifyIcon icon="lucide:plus" />
                </template>
                {{ $t('tenant.system.userArchitecture.createRole') }}
              </Button>
            </template>
            <Input
              v-model:value="roleSearchKeyword"
              :placeholder="$t('tenant.system.userArchitecture.searchRole')"
              allow-clear
              class="mb-3"
            >
              <template #prefix>
                <IconifyIcon
                  icon="lucide:search"
                  class="text-muted-foreground"
                />
              </template>
            </Input>
            <div
              class="mb-2 cursor-pointer rounded-lg border px-3 py-2 transition"
              :class="
                !selectedRole
                  ? 'border-primary bg-primary/5'
                  : 'border-border/60 hover:border-primary/20'
              "
              @click="clearRoleFilter"
            >
              <div class="flex items-center gap-2">
                <IconifyIcon icon="lucide:shield" class="size-4 text-primary" />
                <span class="font-medium">
                  {{ $t('tenant.system.userArchitecture.allPermissionRoles') }}
                </span>
              </div>
              <div class="mt-1 text-xs text-muted-foreground">
                {{
                  $t('tenant.system.userArchitecture.allPermissionRolesDesc')
                }}
              </div>
            </div>
            <Spin :spinning="rolesLoading">
              <div v-if="filteredRoles.length > 0" class="space-y-2">
                <div
                  v-for="role in filteredRoles"
                  :key="role.id"
                  class="cursor-pointer rounded-lg border px-3 py-2 transition"
                  :class="
                    selectedRole?.id === role.id
                      ? 'border-primary bg-primary/5'
                      : 'border-border/60 hover:border-primary/20'
                  "
                  @click="handleSelectRole(role)"
                >
                  <div class="flex items-center justify-between gap-3">
                    <div class="min-w-0">
                      <div class="truncate font-medium">{{ role.name }}</div>
                      <div
                        class="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground"
                      >
                        <code class="rounded bg-muted px-1.5 py-0.5">{{
                          role.code
                        }}</code>
                        <span>
                          {{ role.memberCount }}
                          {{ $t('tenant.system.userArchitecture.memberUnit') }}
                        </span>
                      </div>
                    </div>
                    <Tag :color="role.isActive ? 'success' : 'default'">
                      {{
                        role.isActive
                          ? $t('tenant.system.userArchitecture.enabled')
                          : $t('tenant.system.userArchitecture.disabled')
                      }}
                    </Tag>
                  </div>
                </div>
              </div>
              <Empty
                v-else
                :description="$t('tenant.system.userArchitecture.noRoles')"
                class="py-6"
              />
            </Spin>
          </Card>
        </div>

        <div
          v-show="sidebarCollapsed"
          class="flex flex-1 flex-col items-center gap-2 py-4"
        >
          <Tooltip
            :title="$t('tenant.system.userArchitecture.roleSidebarTitle')"
            placement="right"
          >
            <IconifyIcon icon="lucide:shield" class="h-5 w-5 text-primary" />
          </Tooltip>
        </div>
      </div>

      <div
        class="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl bg-card shadow-sm"
      >
        <div class="border-b border-border/50 px-3 py-3 lg:px-6 lg:py-4">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="flex min-w-0 flex-1 flex-wrap gap-3">
              <Card class="min-w-[220px] flex-1" size="small">
                <div class="flex items-start gap-3">
                  <div
                    class="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary"
                  >
                    <IconifyIcon icon="lucide:building-2" class="h-5 w-5" />
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="text-xs text-muted-foreground">
                      {{ $t('tenant.system.userArchitecture.orgFilterTitle') }}
                    </div>
                    <div class="truncate text-base font-semibold">
                      {{ orgFilterLabel }}
                    </div>
                    <div class="mt-1 text-xs text-muted-foreground">
                      {{ $t('tenant.system.userArchitecture.orgFilterHint') }}
                    </div>
                  </div>
                </div>
              </Card>

              <Card class="min-w-[220px] flex-1" size="small">
                <div class="flex items-start gap-3">
                  <div
                    class="flex h-10 w-10 items-center justify-center rounded-xl bg-warning/10 text-warning"
                  >
                    <IconifyIcon icon="lucide:shield" class="h-5 w-5" />
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="text-xs text-muted-foreground">
                      {{
                        $t(
                          'tenant.system.userArchitecture.permissionRoleListTitle',
                        )
                      }}
                    </div>
                    <div class="truncate text-base font-semibold">
                      {{ roleFilterLabel }}
                    </div>
                    <div class="mt-1 text-xs text-muted-foreground">
                      {{
                        selectedRole?.description ||
                        $t('tenant.system.userArchitecture.permissionRoleHint')
                      }}
                    </div>
                  </div>
                </div>
              </Card>
            </div>

            <div
              v-if="selectedRole"
              class="flex flex-shrink-0 flex-wrap items-center gap-2"
            >
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
                {{ $t('shared.common.edit') }}
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
                  {{ $t('shared.common.delete') }}
                </Button>
              </Popconfirm>
            </div>
          </div>
        </div>

        <div class="flex-1 overflow-hidden p-2 lg:p-4">
          <Card class="h-full overflow-hidden" size="small">
            <template #title>
              <span class="text-sm lg:text-base">
                {{ $t('tenant.system.userArchitecture.userListTitle') }}
              </span>
            </template>
            <template #extra>
              <div class="flex items-center gap-2">
                <Tag color="blue">{{ orgFilterLabel }}</Tag>
                <Tag color="gold">{{ roleFilterLabel }}</Tag>
                <Popconfirm
                  :title="$t('tenant.system.user.messages.batchApproveConfirm')"
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
                  :title="$t('tenant.system.user.messages.batchRejectConfirm')"
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
            <MemberGrid :checkbox-config="{ trigger: 'cell', highlight: true }">
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
                  <div class="flex min-w-0 flex-col">
                    <span class="truncate font-medium text-foreground">
                      {{ row.username }}
                    </span>
                    <span
                      v-if="row.nickname"
                      class="truncate text-xs text-muted-foreground"
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
      </div>
    </div>

    <RoleFormDrawer @success="onRoleFormSuccess" />

    <PermissionDrawer
      v-model:open="permissionDrawerVisible"
      :role="currentPermissionRole"
      @saved="onPermissionSaved"
    />
  </Page>
</template>
