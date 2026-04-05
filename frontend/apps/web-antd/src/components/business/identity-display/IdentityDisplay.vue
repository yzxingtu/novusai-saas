<script setup lang="ts">
import type {
  IdentityDisplayBadge,
  IdentityDisplayModel,
  ResolvedIdentityDisplayModel,
} from './types';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Avatar, Tooltip } from 'ant-design-vue';

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

function resolveBadgeIcon(badge: IdentityDisplayBadge): string {
  if (badge.icon?.trim()) {
    return badge.icon.trim();
  }

  const normalizedKey = badge.key.toLowerCase();
  if (normalizedKey.includes('type') || normalizedKey.includes('user')) {
    return 'lucide:users';
  }
  if (normalizedKey.includes('role')) {
    return 'lucide:shield';
  }
  return 'lucide:badge-info';
}

function resolveBadgeToneClass(color?: string): string {
  switch ((color || '').toLowerCase()) {
    case 'blue':
    case 'cyan':
    case 'processing': {
      return 'identity-display__indicator--blue';
    }
    case 'gold':
    case 'warning':
    case 'orange': {
      return 'identity-display__indicator--gold';
    }
    case 'green':
    case 'success': {
      return 'identity-display__indicator--green';
    }
    case 'error':
    case 'red': {
      return 'identity-display__indicator--red';
    }
    case 'purple': {
      return 'identity-display__indicator--purple';
    }
    default: {
      return 'identity-display__indicator--default';
    }
  }
}
</script>

<template>
  <div
    v-bind="$attrs"
    class="identity-display flex min-w-0 items-start gap-2.5"
  >
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

    <div class="identity-display__content min-w-0 flex-1">
      <div class="identity-display__heading">
        <span class="identity-display__title text-sm font-medium">
          {{ resolvedTitle }}
        </span>
        <div
          v-if="displayBadges.length > 0"
          class="identity-display__badge-list"
        >
          <Tooltip
            v-for="badge in displayBadges"
            :key="badge.key"
            :title="badge.label"
            :trigger="['hover', 'focus', 'click']"
          >
            <button
              :aria-label="badge.label"
              class="identity-display__indicator"
              :class="resolveBadgeToneClass(badge.color)"
              type="button"
            >
              <IconifyIcon
                :icon="resolveBadgeIcon(badge)"
                class="size-3.5"
              />
            </button>
          </Tooltip>
        </div>
      </div>

      <div
        v-if="showOrgLine"
        class="identity-display__org-line flex min-w-0 items-center"
      >
        <span class="identity-display__org-chip">
          <IconifyIcon
            class="identity-display__org-icon size-3"
            icon="lucide:building-2"
          />
          <span class="identity-display__org-text">
            {{ orgLineText }}
          </span>
        </span>
      </div>

      <div v-if="resolvedSecondaryText || $slots.after" class="min-w-0">
        <slot name="after" :model="resolvedModel">
          <div class="identity-display__secondary truncate text-xs">
            {{ resolvedSecondaryText }}
          </div>
        </slot>
      </div>
    </div>
  </div>
</template>

<style scoped>
.identity-display__content {
  align-items: flex-start;
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  text-align: left;
}

.identity-display__heading {
  align-items: flex-start;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 6px;
  justify-content: flex-start;
  line-height: 1.15;
  max-width: 100%;
  min-width: 0;
  text-align: left;
  width: 100%;
}

.identity-display__title {
  color: rgb(17 24 39);
  flex: 0 1 auto;
  max-width: 100%;
  min-width: 0;
  overflow: hidden;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dark .identity-display__title {
  color: rgb(243 244 246);
}

.identity-display__avatar {
  flex-shrink: 0;
}

.identity-display__badge-list {
  align-items: flex-start;
  align-self: flex-start;
  display: flex;
  flex: 0 1 auto;
  flex-wrap: wrap;
  gap: 2px;
  justify-content: flex-start;
  max-width: 100%;
  min-width: 0;
}

.identity-display__indicator {
  align-items: center;
  appearance: none;
  background: transparent;
  border: none;
  border-radius: 9999px;
  cursor: pointer;
  display: inline-flex;
  height: 18px;
  justify-content: center;
  padding: 0;
  transition:
    color 0.15s ease,
    background-color 0.15s ease,
    transform 0.15s ease;
  width: 18px;
}

.identity-display__indicator:hover,
.identity-display__indicator:focus-visible {
  background: var(--identity-indicator-bg);
  outline: none;
  transform: translateY(-0.5px);
}

.identity-display__indicator--default {
  --identity-indicator-bg: rgb(243 244 246 / 0.92);
  color: rgb(107 114 128);
}

.identity-display__indicator--blue {
  --identity-indicator-bg: rgb(239 246 255 / 0.95);
  color: rgb(37 99 235);
}

.identity-display__indicator--gold {
  --identity-indicator-bg: rgb(255 247 237 / 0.95);
  color: rgb(217 119 6);
}

.identity-display__indicator--green {
  --identity-indicator-bg: rgb(236 253 245 / 0.95);
  color: rgb(5 150 105);
}

.identity-display__indicator--red {
  --identity-indicator-bg: rgb(254 242 242 / 0.95);
  color: rgb(220 38 38);
}

.identity-display__indicator--purple {
  --identity-indicator-bg: rgb(245 243 255 / 0.95);
  color: rgb(124 58 237);
}

.dark .identity-display__indicator--default {
  --identity-indicator-bg: rgb(31 41 55 / 0.95);
  color: rgb(209 213 219);
}

.dark .identity-display__indicator--blue {
  --identity-indicator-bg: rgb(30 41 59 / 0.95);
  color: rgb(147 197 253);
}

.dark .identity-display__indicator--gold {
  --identity-indicator-bg: rgb(120 53 15 / 0.2);
  color: rgb(252 211 77);
}

.dark .identity-display__indicator--green {
  --identity-indicator-bg: rgb(6 78 59 / 0.22);
  color: rgb(110 231 183);
}

.dark .identity-display__indicator--red {
  --identity-indicator-bg: rgb(69 10 10 / 0.22);
  color: rgb(252 165 165);
}

.dark .identity-display__indicator--purple {
  --identity-indicator-bg: rgb(59 7 100 / 0.2);
  color: rgb(196 181 253);
}

.identity-display__org-line {
  justify-content: flex-start;
  min-height: 20px;
  text-align: left;
}

.identity-display__org-chip {
  align-items: center;
  background: rgb(239 246 255 / 0.78);
  border: 1px solid rgb(191 219 254 / 0.9);
  border-radius: 9999px;
  color: rgb(3 105 161);
  display: inline-flex;
  gap: 4px;
  max-width: 100%;
  min-width: 0;
  padding: 1px 8px;
  text-align: left;
}

.identity-display__org-icon {
  flex-shrink: 0;
}

.identity-display__org-text {
  display: inline-block;
  font-size: 11px;
  font-weight: 500;
  line-height: 1.35;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.identity-display__secondary {
  color: rgb(107 114 128);
  line-height: 1.35;
  text-align: left;
}

.identity-display {
  align-items: flex-start;
  justify-content: flex-start;
  text-align: left;
  width: 100%;
}

.dark .identity-display__org-chip {
  background: rgb(8 47 73 / 0.32);
  border-color: rgb(14 116 144 / 0.38);
  color: rgb(125 211 252);
}

.dark .identity-display__secondary {
  color: rgb(156 163 175);
}
</style>
