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
  resolveIdentityContextIcon,
  resolveIdentityContextLabel,
  resolveIdentityDisplayModel,
  resolveIdentityDisplayTitle,
} from './types';

defineOptions({ name: 'IdentityDisplay' });

const props = withDefaults(
  defineProps<{
    avatarSize?: number;
    badgeWrap?: 'nowrap' | 'wrap';
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
    showSecondaryText?: boolean;
    showStatusBadge?: boolean;
    showUserTypeBadge?: boolean;
    verticalAlign?: 'center' | 'start';
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
    badgeWrap: 'wrap',
    showSecondaryText: true,
    showStatusBadge: true,
    showUserTypeBadge: false,
    verticalAlign: 'start',
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

const contextLineText = computed(
  () => props.orgLabel || resolveIdentityContextLabel(resolvedModel.value),
);

const contextLineIcon = computed(() =>
  resolveIdentityContextIcon(resolvedModel.value),
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
    case 'error':
    case 'red': {
      return 'identity-display__indicator--red';
    }
    case 'gold':
    case 'orange':
    case 'warning': {
      return 'identity-display__indicator--gold';
    }
    case 'green':
    case 'success': {
      return 'identity-display__indicator--green';
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
    class="identity-display flex min-w-0 gap-2.5"
    :class="props.verticalAlign === 'center' ? 'items-center' : 'items-start'"
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
      <div
        class="identity-display__heading"
        :class="
          props.badgeWrap === 'nowrap'
            ? 'identity-display__heading--nowrap'
            : 'identity-display__heading--wrap'
        "
      >
        <span
          class="identity-display__title text-sm font-medium"
          :class="
            props.badgeWrap === 'nowrap'
              ? 'identity-display__title--nowrap'
              : 'identity-display__title--wrap'
          "
        >
          {{ resolvedTitle }}
        </span>
        <div
          v-if="displayBadges.length > 0"
          class="identity-display__badge-list"
          :class="
            props.badgeWrap === 'nowrap'
              ? 'identity-display__badge-list--nowrap'
              : 'identity-display__badge-list--wrap'
          "
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
              <IconifyIcon :icon="resolveBadgeIcon(badge)" class="size-3.5" />
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
            :icon="contextLineIcon"
          />
          <span class="identity-display__org-text">
            {{ contextLineText }}
          </span>
        </span>
      </div>

      <div
        v-if="
          (props.showSecondaryText && resolvedSecondaryText) || $slots.after
        "
        class="min-w-0"
      >
        <slot name="after" :model="resolvedModel">
          <div
            v-if="props.showSecondaryText && resolvedSecondaryText"
            class="identity-display__secondary truncate text-xs"
          >
            {{ resolvedSecondaryText }}
          </div>
        </slot>
      </div>
    </div>
  </div>
</template>

<style scoped>
.identity-display__content {
  display: flex;
  flex-direction: column;
  gap: 3px;
  align-items: flex-start;
  min-width: 0;
  text-align: left;
}

.identity-display__heading {
  display: flex;
  gap: 4px 6px;
  align-items: flex-start;
  justify-content: flex-start;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  line-height: 1.15;
  text-align: left;
}

.identity-display__heading--wrap {
  flex-wrap: wrap;
}

.identity-display__heading--nowrap {
  flex-wrap: nowrap;
  gap: 4px;
  align-items: center;
}

.identity-display__title {
  flex: 0 1 auto;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  color: rgb(17 24 39);
  text-align: left;
  white-space: nowrap;
}

.identity-display__title--nowrap {
  flex: 1 1 auto;
}

.dark .identity-display__title {
  color: rgb(243 244 246);
}

.identity-display__avatar {
  flex-shrink: 0;
}

.identity-display__badge-list {
  display: flex;
  gap: 2px;
  align-items: flex-start;
  align-self: flex-start;
  justify-content: flex-start;
  min-width: 0;
  max-width: 100%;
}

.identity-display__badge-list--wrap {
  flex: 0 1 auto;
  flex-wrap: wrap;
}

.identity-display__badge-list--nowrap {
  flex: 0 0 auto;
  flex-wrap: nowrap;
  gap: 1px;
  align-items: center;
  align-self: center;
  max-width: none;
}

.identity-display__indicator {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  padding: 0;
  appearance: none;
  cursor: pointer;
  background: transparent;
  border: none;
  border-radius: 9999px;
  transition:
    color 0.15s ease,
    background-color 0.15s ease,
    transform 0.15s ease;
}

.identity-display__indicator:hover,
.identity-display__indicator:focus-visible {
  outline: none;
  background: var(--identity-indicator-bg);
  transform: translateY(-0.5px);
}

.identity-display__indicator--default {
  --identity-indicator-bg: rgb(243 244 246 / 92%);

  color: rgb(107 114 128);
}

.identity-display__indicator--blue {
  --identity-indicator-bg: rgb(239 246 255 / 95%);

  color: rgb(37 99 235);
}

.identity-display__indicator--gold {
  --identity-indicator-bg: rgb(255 247 237 / 95%);

  color: rgb(217 119 6);
}

.identity-display__indicator--green {
  --identity-indicator-bg: rgb(236 253 245 / 95%);

  color: rgb(5 150 105);
}

.identity-display__indicator--red {
  --identity-indicator-bg: rgb(254 242 242 / 95%);

  color: rgb(220 38 38);
}

.identity-display__indicator--purple {
  --identity-indicator-bg: rgb(245 243 255 / 95%);

  color: rgb(124 58 237);
}

.dark .identity-display__indicator--default {
  --identity-indicator-bg: rgb(31 41 55 / 95%);

  color: rgb(209 213 219);
}

.dark .identity-display__indicator--blue {
  --identity-indicator-bg: rgb(30 41 59 / 95%);

  color: rgb(147 197 253);
}

.dark .identity-display__indicator--gold {
  --identity-indicator-bg: rgb(120 53 15 / 20%);

  color: rgb(252 211 77);
}

.dark .identity-display__indicator--green {
  --identity-indicator-bg: rgb(6 78 59 / 22%);

  color: rgb(110 231 183);
}

.dark .identity-display__indicator--red {
  --identity-indicator-bg: rgb(69 10 10 / 22%);

  color: rgb(252 165 165);
}

.dark .identity-display__indicator--purple {
  --identity-indicator-bg: rgb(59 7 100 / 20%);

  color: rgb(196 181 253);
}

.identity-display__org-line {
  justify-content: flex-start;
  min-height: 20px;
  text-align: left;
}

.identity-display__org-chip {
  display: inline-flex;
  gap: 4px;
  align-items: center;
  min-width: 0;
  max-width: 100%;
  padding: 1px 8px;
  color: hsl(var(--primary));
  text-align: left;
  background: hsl(var(--primary) / 10%);
  border: 1px solid hsl(var(--primary) / 22%);
  border-radius: 9999px;
}

.identity-display__org-icon {
  flex-shrink: 0;
}

.identity-display__org-text {
  display: inline-block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 11px;
  font-weight: 500;
  line-height: 1.35;
  white-space: nowrap;
}

.identity-display__secondary {
  line-height: 1.35;
  color: rgb(107 114 128);
  text-align: left;
}

.identity-display {
  justify-content: flex-start;
  width: 100%;
  text-align: left;
}

.dark .identity-display__secondary {
  color: rgb(156 163 175);
}
</style>
