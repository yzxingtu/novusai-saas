<script lang="ts" setup>
/**
 * 租户管理员展开面板
 *
 * 显示在租户列表的展开行中，展示该租户的管理员列表及在线状态。
 * 支持创建子管理员、禁用/启用操作。
 */
import type { TenantAdminItem } from '#/api/admin/tenant';

import { onMounted, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Avatar,
  Button,
  Empty,
  message,
  Popconfirm,
  Spin,
  Switch,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import {
  getTenantAdminsApi,
  toggleTenantAdminStatusApi,
} from '#/api/admin/tenant';
import { $t } from '#/locales';
import { usePresenceStore } from '#/store';
import { formatRelativeTime } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';

import TenantAdminForm from './TenantAdminForm.vue';
import TenantAdminResetPwdModal from './TenantAdminResetPwdModal.vue';

defineOptions({ name: 'TenantAdminPanel' });

const props = defineProps<{
  /** 租户 ID */
  tenantId: number;
  /** 租户名称 */
  tenantName: string;
}>();

const presenceStore = usePresenceStore();

const admins = ref<TenantAdminItem[]>([]);
const loading = ref(false);
const formRef = ref<InstanceType<typeof TenantAdminForm>>();
const resetPwdRef = ref<InstanceType<typeof TenantAdminResetPwdModal>>();

/** 加载管理员列表 + 在线状态 */
async function loadAdmins() {
  loading.value = true;
  try {
    const [data] = await Promise.all([
      getTenantAdminsApi(props.tenantId),
      presenceStore.loadTenantPresence(props.tenantId),
    ]);
    admins.value = data || [];
  } catch {
    console.error('[TenantAdminPanel] Failed to load admins');
  } finally {
    loading.value = false;
  }
}

/** 切换管理员状态 */
async function handleToggleStatus(admin: TenantAdminItem) {
  try {
    await toggleTenantAdminStatusApi(
      props.tenantId,
      admin.id,
      !admin.is_active,
    );
    admin.is_active = !admin.is_active;
    message.success($t('common.saveSuccess'));
  } catch {
    message.error($t('common.requestFailed'));
  }
}

/** 打开创建表单 */
function handleCreate() {
  formRef.value?.open(props.tenantId, props.tenantName);
}

/** 打开编辑表单 */
function handleEdit(admin: TenantAdminItem) {
  formRef.value?.open(props.tenantId, props.tenantName, admin);
}

/** 重置密码 */
function handleResetPassword(admin: TenantAdminItem) {
  resetPwdRef.value?.open(admin.id, admin.nickname || admin.username);
}

/** 创建成功后刷新 */
function handleCreateSuccess() {
  loadAdmins();
}

/** 判断管理员是否在线 */
function isAdminOnline(adminId: number): boolean {
  const ids = presenceStore.tenantPresenceMap.get(props.tenantId);
  return ids ? ids.has(adminId) : false;
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
        <Button type="primary" size="small" @click="handleCreate">
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
            <!-- 头像 + 在线指示器 -->
            <div class="relative flex-shrink-0">
              <Avatar
                v-if="admin.avatar"
                :src="toAvatarDisplayUrl(admin.avatar)"
                :size="32"
              />
              <Avatar v-else :size="32" class="bg-primary text-xs text-white">
                {{ (admin.nickname || admin.username).charAt(0).toUpperCase() }}
              </Avatar>
              <!-- 在线状态圆点（头像右下角） -->
              <span
                class="absolute -bottom-0.5 -right-0.5 block size-2.5 rounded-full border-2 border-background"
                :class="
                  isAdminOnline(admin.id)
                    ? 'bg-green-500'
                    : 'bg-muted-foreground/30'
                "
              ></span>
            </div>

            <!-- 信息 -->
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-1.5">
                <span class="truncate text-sm font-medium text-foreground">
                  {{ admin.nickname || admin.username }}
                </span>
                <Tag
                  v-if="admin.is_owner"
                  color="warning"
                  class="!m-0 !text-[10px]"
                >
                  {{ $t('admin.tenant.adminPanel.owner') }}
                </Tag>
                <Tag
                  v-if="admin.role_name"
                  class="!m-0 !border-primary/30 !bg-primary/10 !text-[10px] !text-primary"
                >
                  {{ admin.role_name }}
                </Tag>
                <Tag
                  v-if="!admin.is_active"
                  color="default"
                  class="!m-0 !text-[10px]"
                >
                  {{ $t('admin.common.disabled') }}
                </Tag>
              </div>
              <div
                class="flex items-center gap-2 text-xs text-muted-foreground"
              >
                <span>{{ admin.email }}</span>
                <span v-if="admin.last_login_at">
                  · {{ $t('admin.tenant.adminPanel.lastLogin') }}
                  {{ formatRelativeTime(admin.last_login_at) }}
                </span>
              </div>
            </div>

            <!-- 操作 -->
            <div class="flex flex-shrink-0 items-center gap-2">
              <!-- 编辑按钮 -->
              <Tooltip :title="$t('shared.common.edit')">
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
              <Tooltip :title="$t('admin.tenant.resetPassword')">
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
              <!-- 启用/禁用开关 -->
              <Tooltip
                v-if="admin.is_owner"
                :title="$t('admin.tenant.adminPanel.ownerCannotDisable')"
              >
                <Switch :checked="true" size="small" disabled />
              </Tooltip>
              <Tooltip
                v-else
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
