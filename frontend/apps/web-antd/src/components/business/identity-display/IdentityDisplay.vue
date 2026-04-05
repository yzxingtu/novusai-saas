<script setup lang="ts">
import type {
  IdentityDisplayBadge,
  IdentityDisplayModel,
  ResolvedIdentityDisplayModel,
} from './types';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Avatar, Tag } from 'ant-design-vue';

import { $t } from '#/locales';
import { toAvatarDisplayUrl } from '#/utils/image';

import {
  resolveIdentityAvatarText,
  resolveIdentityDisplayModel,
  resolveIdentityDisplayTitle,
  resolveIdentityOrgNodeLabel,
} from './types';

defineOptions({ name: 'IdentityDisplay' });

const props = withDefaults(
  defineProps<{
    avatarSize?: number;
    disabledLabel?: string;
    leaderLabel?: string;
    model: IdentityDisplayModel;
    online?: boolean;
    orgLabel?: string;
    ownerLabel?: string;
    showAvatar?: boolean;
    showOnlineStatus?: boolean;
    showOrgLine?: boolean;
    showRoleBadge?: boolean;
    showStatusBadge?: boolean;
    showUserTypeBadge?: boolean;
  }>(),
  {
    avatarSize: 40,
    disabledLabel: undefined,
    leaderLabel: undefined,
    online: false,
    orgLabel: undefined,
    ownerLabel: undefined,
    showAvatar: true,
    showOnlineStatus: false,
    showOrgLine: true,
    showRoleBadge: false,
    showStatusBadge: true,
    showUserTypeBadge: false,
  },
);

const resolvedModel = computed<ResolvedIdentityDisplayModel>(() =>
  resolveIdentityDisplayModel(props.model),
);

const resolvedTitle = computed(() =>
  resolveIdentityDisplayTitle(resolvedModel.value),
);

const resolvedAvatarText = computed(() =>
  resolveIdentityAvatarText(resolvedModel.value),
);

const avatarValue = computed(() => resolvedModel.value.avatar?.trim() || '');
const isIconAvatar = computed(() =>
  /^[a-z0-9-]+:[a-z0-9-]+$/i.test(avatarValue.value),
);

const avatarSrc = computed(() => {
  if (!avatarValue.value || isIconAvatar.value) {
    return '';
  }
  return toAvatarDisplayUrl(avatarValue.value);
});

const resolvedSecondaryText = computed(() => {
  return resolvedModel.value.secondaryText;
});

const leaderLabel = computed(
  () => props.leaderLabel || $t('shared.memberPanel.leader'),
);

const ownerLabel = computed(
  () => props.ownerLabel || $t('shared.identity.owner'),
);

const disabledLabel = computed(
  () => props.disabledLabel || $t('shared.memberPanel.item.disabled'),
);

const orgLineText = computed(
  () =>
    props.orgLabel ||
    resolveIdentityOrgNodeLabel(resolvedModel.value.orgNodeName),
);

const displayBadges = computed<IdentityDisplayBadge[]>(() => {
  const badges: IdentityDisplayBadge[] = [];
  const keys = new Set<string>();

  function pushBadge(badge: IdentityDisplayBadge) {
    if (!badge.label.trim() || keys.has(badge.key)) {
      return;
    }
    keys.add(badge.key);
    badges.push(badge);
  }

  if (resolvedModel.value.isLeader) {
    pushBadge({
      color: 'warning',
      icon: 'lucide:crown',
      key: 'leader',
      label: leaderLabel.value,
    });
  }

  if (resolvedModel.value.isOwner) {
    pushBadge({
      color: 'gold',
      icon: 'lucide:shield-check',
      key: 'owner',
      label: ownerLabel.value,
    });
  }

  if (props.showStatusBadge && !resolvedModel.value.isActive) {
    pushBadge({
      color: 'default',
      icon: 'lucide:ban',
      key: 'disabled',
      label: disabledLabel.value,
    });
  }

  resolvedModel.value.badges.forEach((badge) => pushBadge(badge));

  if (props.showRoleBadge && resolvedModel.value.roleName) {
    pushBadge({
      color: 'processing',
      icon: 'lucide:shield',
      key: 'role',
      label: resolvedModel.value.roleName,
    });
  }

  const userTypeLabel =
    resolvedModel.value.userTypeLabel || resolvedModel.value.userType;
  if (props.showUserTypeBadge && userTypeLabel) {
    pushBadge({
      color: 'blue',
      icon: 'lucide:users',
      key: 'user-type',
      label: userTypeLabel,
    });
  }

  return badges;
});
</script>

<template>
  <div v-bind="$attrs" class="identity-display flex min-w-0 items-center gap-3">
    <div v-if="showAvatar" class="relative shrink-0">
      <Avatar
        v-if="avatarSrc"
        :src="avatarSrc"
        :size="avatarSize"
        class="identity-display__avatar"
      />
      <Avatar
        v-else
        :size="avatarSize"
        class="identity-display__avatar bg-primary text-white"
      >
        <IconifyIcon v-if="isIconAvatar" :icon="avatarValue" class="size-4" />
        <template v-else>
          {{ resolvedAvatarText }}
        </template>
      </Avatar>
      <span
        v-if="showOnlineStatus"
        class="absolute -bottom-0.5 -right-0.5 block size-3 rounded-full border-2 border-background"
        :class="online ? 'bg-green-500' : 'bg-muted-foreground/30'"
      ></span>
    </div>

    <div class="min-w-0 flex-1">
      <div class="flex flex-wrap items-center gap-2">
        <span
          class="truncate text-sm font-medium text-gray-900 dark:text-gray-100"
        >
          {{ resolvedTitle }}
        </span>
        <Tag
          v-for="badge in displayBadges"
          :key="badge.key"
          :color="badge.color"
          class="!m-0 flex-shrink-0"
        >
          <template v-if="badge.icon" #icon>
            <IconifyIcon :icon="badge.icon" class="mr-1 size-3" />
          </template>
          {{ badge.label }}
        </Tag>
      </div>

      <div
        v-if="showOrgLine"
        class="mt-1 flex min-w-0 items-center gap-2 text-xs text-gray-500 dark:text-gray-400"
      >
        <Tag
          class="identity-display__org-tag !m-0 !inline-flex !items-center !gap-1 !rounded-full !border-sky-200 !bg-sky-50 !px-2 !py-0.5 !text-sky-700"
        >
          <template #icon>
            <IconifyIcon icon="lucide:building-2" class="size-3" />
          </template>
          {{ orgLineText }}
        </Tag>
      </div>

      <div v-if="resolvedSecondaryText || $slots.after" class="mt-1 min-w-0">
        <slot name="after" :model="resolvedModel">
          <div class="truncate text-xs text-gray-500 dark:text-gray-400">
            {{ resolvedSecondaryText }}
          </div>
        </slot>
      </div>
    </div>
  </div>
</template>

<style scoped>
.identity-display__avatar {
  flex-shrink: 0;
}
</style>
