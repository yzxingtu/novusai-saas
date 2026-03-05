<script setup lang="ts">
import type { OrgMember } from '#/api/admin/organization';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Avatar, Button, Popconfirm, Tag, Tooltip } from 'ant-design-vue';

import { formatDate } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';

const props = withDefaults(
  defineProps<{
    /** 是否禁用操作 */
    disabled?: boolean;
    /** 是否为负责人 */
    isLeader?: boolean;
    /** 成员信息 */
    member: OrgMember;
    /** 是否在线（仅 showOnlineStatus=true 时有效） */
    online?: boolean;
    /** 是否显示操作按钮 */
    showActions?: boolean;
    /** 是否显示在线状态指示器 */
    showOnlineStatus?: boolean;
  }>(),
  {
    isLeader: false,
    disabled: false,
    online: false,
    showActions: true,
    showOnlineStatus: false,
  },
);

const emit = defineEmits<{
  (e: 'cancelLeader', member: OrgMember): void;
  (e: 'edit', member: OrgMember): void;
  (e: 'remove', member: OrgMember): void;
  (e: 'resetPassword', member: OrgMember): void;
  (e: 'setLeader', member: OrgMember): void;
}>();

/** 显示名称：优先显示 nickname，如果为空则回退到 username */
const displayName = computed(() => {
  return props.member.nickname || props.member.username;
});

/** 头像文字（取显示名称首字符） */
const avatarText = computed(() => {
  const name = displayName.value;
  return name.charAt(0).toUpperCase();
});

/** 处理移除成员 */
function handleRemove() {
  emit('remove', props.member);
}

/** 处理设置为负责人 */
function handleSetLeader() {
  emit('setLeader', props.member);
}

/** 处理取消负责人 */
function handleCancelLeader() {
  emit('cancelLeader', props.member);
}

/** 处理编辑成员 */
function handleEdit() {
  emit('edit', props.member);
}

/** 处理重置密码 */
function handleResetPassword() {
  emit('resetPassword', props.member);
}
</script>

<template>
  <div
    class="member-item flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800"
    :class="{ 'opacity-60': !member.isActive }"
  >
    <!-- 头像 + 在线指示器 -->
    <div class="relative flex-shrink-0">
      <Avatar
        v-if="member.avatar"
        :src="toAvatarDisplayUrl(member.avatar)"
        :size="40"
      />
      <Avatar v-else :size="40" class="bg-primary text-white">
        {{ avatarText }}
      </Avatar>
      <!-- 在线状态圆点（头像右下角） -->
      <span
        v-if="showOnlineStatus"
        class="absolute -bottom-0.5 -right-0.5 block size-3 rounded-full border-2 border-background"
        :class="online ? 'bg-green-500' : 'bg-muted-foreground/30'"
      ></span>
      <!-- 负责人皇冠图标 -->
      <div
        v-if="isLeader"
        class="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-warning shadow-sm"
      >
        <IconifyIcon icon="lucide:crown" class="h-3 w-3 text-white" />
      </div>
    </div>

    <!-- 成员信息 -->
    <div class="min-w-0 flex-1">
      <div class="flex items-center gap-2">
        <span class="truncate font-medium text-gray-900 dark:text-gray-100">
          {{ displayName }}
        </span>
        <Tag v-if="isLeader" color="warning" class="flex-shrink-0">
          <template #icon>
            <IconifyIcon icon="lucide:crown" class="mr-1" />
          </template>
          {{ $t('shared.memberPanel.leader') }}
        </Tag>
        <Tag v-if="!member.isActive" color="default" class="flex-shrink-0">
          {{ $t('shared.memberPanel.item.disabled') }}
        </Tag>
        <!-- 角色名称标签 -->
        <Tag
          v-if="member.roleName"
          class="flex-shrink-0 !border-primary/30 !bg-primary/10 !text-primary"
        >
          <template #icon>
            <IconifyIcon icon="lucide:shield" class="mr-1" />
          </template>
          {{ member.roleName }}
        </Tag>
      </div>
      <div
        class="flex items-center gap-2 truncate text-sm text-gray-500 dark:text-gray-400"
      >
        <span>{{ member.email || member.username }}</span>
        <!-- 创建时间 -->
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
    </div>

    <!-- 操作按钮 -->
    <div v-if="showActions && !disabled" class="flex flex-shrink-0 gap-1">
      <!-- 编辑成员 -->
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

      <!-- 重置密码 -->
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

      <!-- 设置/取消负责人 -->
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

      <!-- 移除成员 -->
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
