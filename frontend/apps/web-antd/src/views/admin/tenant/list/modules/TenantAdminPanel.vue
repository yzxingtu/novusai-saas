<script lang="ts" setup>
/**
 * 企业管理员展开面板；展示管理员列表与在线状态，支持创建/禁用/启用。
 * Tenant admin expand panel; list admins and online status, create/disable/enable.
 */
import type { TenantAdminItem } from '#/api/admin/tenant';
import type { IdentityDisplayBadge } from '#/components/business/identity-display';
import type { IdentityDetailMeta } from '#/views/_shared/identity/identity-interactions';

import { onMounted, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Empty,
  message,
  Popconfirm,
  Spin,
  Switch,
  Tooltip,
} from 'ant-design-vue';

import {
  forceLogoutTenantAdminApi,
  getTenantAdminsApi,
  toggleTenantAdminStatusApi,
} from '#/api/admin/tenant';
import { IdentityDisplay } from '#/components/business/identity-display';
import { $t } from '#/locales';
import { usePresenceStore } from '#/store';
import { useAccess } from '#/utils';
import { formatRelativeTime } from '#/utils/common';
import { showRequestError } from '#/utils/error-helpers';
import IdentityTrigger from '#/views/_shared/identity/IdentityTrigger.vue';

import { createAdminIdentityModel } from '../../../_shared/identity';
import TenantAdminForm from './TenantAdminForm.vue';
import TenantAdminResetPwdModal from './TenantAdminResetPwdModal.vue';

defineOptions({ name: 'TenantAdminPanel' });

const props = defineProps<{
  /** 企业 ID / Tenant ID */
  tenantId: number;
  /** 企业名称 / Tenant name */
  tenantName: string;
}>();

const presenceStore = usePresenceStore();
const { hasAccessByCodes } = useAccess();
const canCreateTenantAdmin = hasAccessByCodes(['tenant_admin:create']);
const canListTenantAdmins = hasAccessByCodes(['tenant_admin:list']);
const canUpdateTenantAdmin = hasAccessByCodes(['tenant_admin:update']);

const admins = ref<TenantAdminItem[]>([]);
const loading = ref(false);
const formRef = ref<InstanceType<typeof TenantAdminForm>>();
const resetPwdRef = ref<InstanceType<typeof TenantAdminResetPwdModal>>();

/** 加载管理员列表 + 在线状态 / Load admin list and online status */
async function loadAdmins() {
  if (!canListTenantAdmins) {
    admins.value = [];
    loading.value = false;
    return;
  }
  loading.value = true;
  try {
    const [data] = await Promise.all([
      getTenantAdminsApi(props.tenantId),
      presenceStore.loadTenantPresence(props.tenantId),
    ]);
    admins.value = data || [];
  } catch {
    admins.value = [];
  } finally {
    loading.value = false;
  }
}

/** 切换管理员状态 / Toggle admin status */
async function handleToggleStatus(admin: TenantAdminItem) {
  try {
    await toggleTenantAdminStatusApi(
      props.tenantId,
      admin.id,
      !admin.is_active,
    );
    admin.is_active = !admin.is_active;
    message.success($t('common.saveSuccess'));
  } catch (error) {
    showRequestError(error, 'common.requestFailed');
  }
}

/** 打开创建表单 / Open create form */
function handleCreate() {
  formRef.value?.open(props.tenantId, props.tenantName);
}

/** 打开编辑表单 / Open edit form */
function handleEdit(admin: TenantAdminItem) {
  formRef.value?.open(props.tenantId, props.tenantName, admin);
}

/** 重置密码 / Reset password */
function handleResetPassword(admin: TenantAdminItem) {
  resetPwdRef.value?.open(admin.id, admin.nickname || admin.username);
}

/** 强制下线 / Force logout */
async function handleForceLogout(admin: TenantAdminItem) {
  try {
    await forceLogoutTenantAdminApi(props.tenantId, admin.id);
    message.success(
      $t('common.auth.forceLogoutSuccess', {
        name: admin.nickname || admin.username,
      }),
    );
    await loadAdmins();
  } catch (error) {
    showRequestError(error, 'common.requestFailed');
  }
}

/** 创建成功后刷新 / Refresh after create success */
function handleCreateSuccess() {
  loadAdmins();
}

/** 判断管理员是否在线 / Check if admin is online */
function isAdminOnline(adminId: number): boolean {
  const ids = presenceStore.tenantPresenceMap.get(props.tenantId);
  return ids ? ids.has(adminId) : false;
}

function getRoleBadges(
  roleName: null | string | undefined,
): IdentityDisplayBadge[] {
  if (!roleName?.trim()) {
    return [];
  }

  return [
    {
      color: 'blue',
      key: `role-${roleName}`,
      label: roleName,
    },
  ];
}

function getAdminIdentityModel(admin: TenantAdminItem) {
  return createAdminIdentityModel({
    avatar: admin.avatar,
    badges: getRoleBadges(admin.role_name),
    id: admin.id,
    isActive: admin.is_active,
    isOwner: admin.is_owner,
    nickname: admin.nickname,
    orgNodeName: admin.org_node_name,
    roleName: admin.role_name,
    username: admin.username,
  });
}

function buildAdminMeta(admin: TenantAdminItem): IdentityDetailMeta {
  return {
    email: admin.email,
    lastLoginAt: admin.last_login_at,
    orgNodeName: admin.org_node_name,
    roleName: admin.role_name,
    scope: 'admin',
    subjectType: 'tenant_admin',
    tenantId: props.tenantId,
    tenantName: props.tenantName,
    userType: 'tenant_admin',
    username: admin.username,
  };
}

const shown = ref(false);

onMounted(() => {
  loadAdmins();
  requestAnimationFrame(() => {
    shown.value = true;
  });
});
</script>

<template>
  <Transition name="panel-expand">
    <div v-show="shown" class="min-h-[120px] px-4 py-3">
      <!-- 标题栏 -->
      <div class="mb-3 flex items-center justify-between">
        <span class="text-sm font-medium text-foreground">
          {{ $t('admin.tenant.adminPanel.title') }}
        </span>
        <Button
          v-if="canCreateTenantAdmin"
          type="primary"
          size="small"
          @click="handleCreate"
        >
          <template #icon>
            <IconifyIcon icon="lucide:user-plus" />
          </template>
          {{ $t('admin.tenant.adminPanel.createAdmin') }}
        </Button>
      </div>

      <!-- 加载中 -->
      <Spin :spinning="loading">
        <!-- 空状态 -->
        <Empty
          v-if="!loading && admins.length === 0"
          :description="$t('admin.tenant.adminPanel.empty')"
          class="py-4"
        />

        <!-- 管理员列表 -->
        <div v-else class="space-y-2">
          <div
            v-for="admin in admins"
            :key="admin.id"
            class="flex items-center gap-3 rounded-lg border border-border/50 px-3 py-2 transition-colors hover:bg-accent/30"
            :class="{ 'opacity-50': !admin.is_active }"
          >
            <IdentityTrigger
              :meta="buildAdminMeta(admin)"
              :model="getAdminIdentityModel(admin)"
              class="min-w-0 flex-1"
            >
              <IdentityDisplay
                :avatar-size="36"
                :model="getAdminIdentityModel(admin)"
                :online="isAdminOnline(admin.id)"
                :show-online-status="true"
                class="min-w-0 flex-1"
              >
                <template #after>
                  <div
                    class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground"
                  >
                    <span v-if="admin.email" class="truncate">
                      {{ admin.email }}
                    </span>
                    <span v-if="admin.last_login_at">
                      · {{ $t('admin.tenant.adminPanel.lastLogin') }}
                      {{ formatRelativeTime(admin.last_login_at) }}
                    </span>
                  </div>
                </template>
              </IdentityDisplay>
            </IdentityTrigger>

            <!-- 操作 -->
            <div class="flex flex-shrink-0 items-center gap-2">
              <!-- 编辑按钮 -->
              <Tooltip
                v-if="canUpdateTenantAdmin"
                :title="$t('shared.common.edit')"
              >
                <Button
                  type="text"
                  size="small"
                  class="hover:!text-primary"
                  @click="handleEdit(admin)"
                >
                  <template #icon>
                    <IconifyIcon icon="lucide:pencil" class="size-3.5" />
                  </template>
                </Button>
              </Tooltip>
              <!-- 重置密码按钮 -->
              <Tooltip
                v-if="canUpdateTenantAdmin"
                :title="$t('admin.tenant.resetPassword')"
              >
                <Button
                  type="text"
                  size="small"
                  class="hover:!text-warning"
                  @click="handleResetPassword(admin)"
                >
                  <template #icon>
                    <IconifyIcon icon="lucide:key-round" class="size-3.5" />
                  </template>
                </Button>
              </Tooltip>
              <!-- 强制下线按钮（仅在线时显示） -->
              <span
                v-if="isAdminOnline(admin.id)"
                v-access:code="['tenant_admin:force_logout']"
              >
                <Tooltip :title="$t('common.auth.forceLogout')">
                  <Popconfirm
                    :title="$t('common.auth.forceLogoutConfirm')"
                    :ok-text="$t('common.confirm')"
                    :cancel-text="$t('common.cancel')"
                    @confirm="handleForceLogout(admin)"
                  >
                    <Button
                      type="text"
                      size="small"
                      class="hover:!bg-destructive/10 hover:!text-destructive"
                    >
                      <template #icon>
                        <IconifyIcon icon="lucide:log-out" class="size-3.5" />
                      </template>
                    </Button>
                  </Popconfirm>
                </Tooltip>
              </span>
              <!-- 启用/禁用开关 -->
              <Tooltip
                v-if="admin.is_owner && canUpdateTenantAdmin"
                :title="$t('admin.tenant.adminPanel.ownerCannotDisable')"
              >
                <Switch :checked="true" size="small" disabled />
              </Tooltip>
              <Tooltip
                v-else-if="canUpdateTenantAdmin"
                :title="
                  admin.is_active
                    ? $t('admin.common.disable')
                    : $t('admin.common.enable')
                "
              >
                <Popconfirm
                  :title="
                    admin.is_active
                      ? $t('admin.tenant.adminPanel.confirmDisable')
                      : $t('admin.tenant.adminPanel.confirmEnable')
                  "
                  :ok-text="$t('shared.common.confirm')"
                  :cancel-text="$t('shared.common.cancel')"
                  @confirm="handleToggleStatus(admin)"
                >
                  <Switch :checked="admin.is_active" size="small" />
                </Popconfirm>
              </Tooltip>
            </div>
          </div>
        </div>
      </Spin>

      <!-- 创建管理员表单 -->
      <TenantAdminForm ref="formRef" @success="handleCreateSuccess" />
      <TenantAdminResetPwdModal ref="resetPwdRef" :tenant-id="tenantId" />
    </div>
  </Transition>
</template>

<style scoped>
.panel-expand-enter-active {
  animation: panel-slide-in 0.3s ease-out;
}

.panel-expand-leave-active {
  animation: panel-slide-in 0.2s ease-in reverse;
}

@keyframes panel-slide-in {
  from {
    max-height: 0;
    opacity: 0;
    transform: translateY(-8px);
  }

  to {
    max-height: 500px;
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
