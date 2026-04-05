<script setup lang="ts">
import type { MemberPanelMember } from '../types';

import type { IdentityDisplayModel } from '#/components/business/identity-display';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, Popconfirm, Tooltip } from 'ant-design-vue';

import { IdentityDisplay } from '#/components/business/identity-display';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import IdentityTrigger from '#/views/_shared/identity/IdentityTrigger.vue';
import type { IdentityDetailMeta } from '#/views/_shared/identity/identity-interactions';

const props = withDefaults(
  defineProps<{
    /** API prefix (admin or tenant) for permission check / API 前缀，用于权限校验 */
    apiPrefix?: 'admin' | 'tenant';
    /** Whether actions are disabled / 是否禁用操作 */
    disabled?: boolean;
    /** Whether this member is a leader / 是否为负责人 */
    isLeader?: boolean;
    /** Member info / 成员信息 */
    member: MemberPanelMember;
    /** Whether online (only effective when showOnlineStatus=true) / 是否在线 */
    online?: boolean;
    /** Whether to show action buttons / 是否显示操作按钮 */
    showActions?: boolean;
    /** Whether to show online status indicator / 是否显示在线状态指示器 */
    showOnlineStatus?: boolean;
  }>(),
  {
    apiPrefix: 'admin',
    isLeader: false,
    disabled: false,
    online: false,
    showActions: true,
    showOnlineStatus: false,
  },
);

const emit = defineEmits<{
  (e: 'cancelLeader', member: MemberPanelMember): void;
  (e: 'edit', member: MemberPanelMember): void;
  (e: 'forceLogout', member: MemberPanelMember): void;
  (e: 'remove', member: MemberPanelMember): void;
  (e: 'resetPassword', member: MemberPanelMember): void;
  (e: 'setLeader', member: MemberPanelMember): void;
}>();

const identityModel = computed<IdentityDisplayModel>(() => ({
  avatar: props.member.avatar ?? null,
  displayName: props.member.nickname || props.member.username,
  id: props.member.id,
  isActive: props.member.isActive,
  isLeader: props.isLeader,
  isOwner: false,
  nickname: props.member.nickname,
  orgNodeName: props.member.orgNodeName,
  roleName: props.member.roleName,
  userType: props.apiPrefix === 'admin' ? 'admin' : 'tenant_admin',
  username: props.member.username,
}));

const memberPrimaryMeta = computed(() => {
  return props.member.email || props.member.username || `#${props.member.id}`;
});

const identityMeta = computed<IdentityDetailMeta>(() => ({
  createdAt: props.member.createdAt,
  email: props.member.email,
  orgNodeName: props.member.orgNodeName,
  roleName: props.member.roleName,
  scope: props.apiPrefix,
  subjectType: identityModel.value.userType,
  userType: identityModel.value.userType,
  username: props.member.username,
}));

/** Handle remove member / 处理移除成员 */
function handleRemove() {
  emit('remove', props.member);
}

/** Handle set as leader / 处理设置为负责人 */
function handleSetLeader() {
  emit('setLeader', props.member);
}

/** Handle cancel leader / 处理取消负责人 */
function handleCancelLeader() {
  emit('cancelLeader', props.member);
}

/** Handle edit member / 处理编辑成员 */
function handleEdit() {
  emit('edit', props.member);
}

/** Handle reset password / 处理重置密码 */
function handleResetPassword() {
  emit('resetPassword', props.member);
}

/** Handle force logout / 处理强制下线 */
function handleForceLogout() {
  emit('forceLogout', props.member);
}
</script>

<template>
  <div
    class="member-item flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800"
    :class="{ 'opacity-60': !member.isActive }"
  >
    <IdentityTrigger :meta="identityMeta" :model="identityModel" class="flex-1">
      <IdentityDisplay
        :model="identityModel"
        :avatar-size="40"
        :online="online"
        :show-online-status="showOnlineStatus"
        class="flex-1"
      >
        <template #after>
          <div
            class="flex items-center gap-2 truncate text-xs text-gray-500 dark:text-gray-400"
          >
            <span class="truncate">{{ memberPrimaryMeta }}</span>
            <Tooltip
              v-if="member.createdAt"
              :title="
                $t('shared.memberPanel.item.createdAt', {
                  date: formatDate(member.createdAt),
                })
              "
            >
              <span class="flex items-center gap-0.5 text-xs text-gray-400">
                <IconifyIcon icon="lucide:calendar" class="h-3 w-3" />
                {{ formatDate(member.createdAt, 'YYYY-MM-DD') }}
              </span>
            </Tooltip>
          </div>
        </template>
      </IdentityDisplay>
    </IdentityTrigger>

    <!-- Action buttons / 操作按钮 -->
    <div v-if="showActions && !disabled" class="flex flex-shrink-0 gap-1">
      <!-- Edit member / 编辑成员 -->
      <Tooltip :title="$t('shared.memberPanel.item.edit')">
        <Button
          type="text"
          size="small"
          class="hover:!text-primary"
          @click="handleEdit"
        >
          <template #icon>
            <IconifyIcon icon="lucide:pencil" />
          </template>
        </Button>
      </Tooltip>

      <!-- Reset password / 重置密码 -->
      <Tooltip :title="$t('shared.memberPanel.item.resetPassword')">
        <Button
          type="text"
          size="small"
          class="hover:!text-primary"
          @click="handleResetPassword"
        >
          <template #icon>
            <IconifyIcon icon="lucide:key-round" />
          </template>
        </Button>
      </Tooltip>

      <!-- Force logout / 强制下线（仅在线时显示，需权限） -->
      <span
        v-if="showOnlineStatus && online"
        v-access:code="[
          apiPrefix === 'admin'
            ? 'admin_user:force_logout'
            : 'tenant_admin:force_logout',
        ]"
      >
        <Tooltip :title="$t('common.auth.forceLogout')">
          <Popconfirm
            :title="$t('common.auth.forceLogoutConfirm')"
            :ok-text="$t('common.confirm')"
            :cancel-text="$t('common.cancel')"
            @confirm="handleForceLogout"
          >
            <Button
              type="text"
              size="small"
              class="hover:!bg-destructive/10 hover:!text-destructive"
            >
              <template #icon>
                <IconifyIcon icon="lucide:log-out" />
              </template>
            </Button>
          </Popconfirm>
        </Tooltip>
      </span>

      <!-- Set/cancel leader / 设置/取消负责人 -->
      <Tooltip
        v-if="isLeader"
        :title="$t('shared.memberPanel.item.cancelLeader')"
      >
        <Popconfirm
          :title="$t('shared.memberPanel.item.cancelLeaderConfirm')"
          :ok-text="$t('shared.common.confirm')"
          :cancel-text="$t('shared.common.cancel')"
          @confirm="handleCancelLeader"
        >
          <Button
            type="text"
            size="small"
            class="!text-warning hover:!bg-warning/10"
          >
            <template #icon>
              <IconifyIcon icon="lucide:user-round-minus" />
            </template>
          </Button>
        </Popconfirm>
      </Tooltip>
      <Tooltip v-else :title="$t('shared.memberPanel.item.setAsLeader')">
        <Button
          type="text"
          size="small"
          class="hover:!bg-warning/10 hover:!text-warning"
          @click="handleSetLeader"
        >
          <template #icon>
            <IconifyIcon icon="lucide:crown" />
          </template>
        </Button>
      </Tooltip>

      <!-- Remove member / 移除成员 -->
      <Tooltip :title="$t('shared.memberPanel.item.removeMember')">
        <Popconfirm
          :title="$t('shared.memberPanel.item.removeConfirm')"
          :ok-text="$t('shared.common.confirm')"
          :cancel-text="$t('shared.common.cancel')"
          :ok-button-props="{ danger: true }"
          @confirm="handleRemove"
        >
          <Button type="text" size="small" danger>
            <template #icon>
              <IconifyIcon icon="lucide:user-minus" />
            </template>
          </Button>
        </Popconfirm>
      </Tooltip>
    </div>
  </div>
</template>

<style scoped>
.member-item {
  border: 1px solid transparent;
}

.member-item:hover {
  border-color: var(--ant-color-border);
}
</style>
