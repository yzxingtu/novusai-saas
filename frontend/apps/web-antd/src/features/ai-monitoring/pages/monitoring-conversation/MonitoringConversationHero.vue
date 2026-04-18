<script lang="ts" setup>
import type { MonitoringConversationDetail, MonitoringScope } from '../../api';

import type { IdentityDetailMeta } from '#/views/_shared/identity/identity-interactions';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Tag } from 'ant-design-vue';

import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';
import IdentityTrigger from '#/views/_shared/identity/IdentityTrigger.vue';

import {
  conversationStatusColor,
  formatCost,
  formatTokens,
  getInitialLetter,
  isIconAvatar,
} from './helpers';

defineOptions({ name: 'MonitoringConversationHero' });

const props = defineProps<{
  detail: MonitoringConversationDetail;
  i18nPrefix: string;
  scope: MonitoringScope;
}>();

const detailAgentName = computed(() => props.detail.agent_name || '-');

const heroStats = computed(() => [
  {
    icon: 'lucide:messages-square',
    key: 'messages',
    label: $t(`${props.i18nPrefix}.messageCount`),
    value: formatTokens(props.detail.message_count),
  },
  {
    icon: 'lucide:cpu',
    key: 'calls',
    label: $t(`${props.i18nPrefix}.totalCalls`),
    value: formatTokens(props.detail.call_count),
  },
  {
    icon: 'lucide:sigma',
    key: 'tokens',
    label: $t(`${props.i18nPrefix}.tokenCount`),
    value: formatTokens(props.detail.total_tokens),
  },
  {
    icon: 'lucide:badge-dollar-sign',
    key: 'cost',
    label: $t(`${props.i18nPrefix}.cost`),
    value: formatCost(props.detail.total_cost),
  },
]);

function getActorDisplayName(actor?: MonitoringConversationDetail['actor']) {
  if (!actor) {
    return '-';
  }
  return actor.display_name || actor.nickname || actor.username || '-';
}

function actorTypeLabel(type?: null | string) {
  if (!type) {
    return '';
  }
  const key = `${props.i18nPrefix}.actorType.${type}`;
  const translated = $t(key);
  return translated === key ? type : translated;
}

const actorIdentityModel = computed(() => {
  const actor = props.detail.actor;
  if (!actor) {
    return null;
  }

  return {
    avatar: actor.avatar,
    badges: actor.type
      ? [
          {
            color: 'blue',
            key: `actor-type-${actor.id ?? actor.username ?? 'unknown'}`,
            label: actorTypeLabel(actor.type),
          },
        ]
      : [],
    displayName: actor.display_name,
    id: actor.id ?? '-',
    isActive: actor.is_active,
    isLeader: actor.is_leader,
    isOwner: actor.is_owner,
    nickname: getActorDisplayName(actor),
    orgNodeName: actor.org_node_name,
    roleName: actor.role_name,
    username: actor.display_name || actor.nickname ? undefined : actor.username,
  };
});

const actorIdentityMeta = computed<IdentityDetailMeta>(() => ({
  orgNodeName: props.detail.actor?.org_node_name,
  roleName: props.detail.actor?.role_name,
  scope: props.scope,
  subjectType: props.detail.actor?.type,
  tenantId: props.detail.actor?.tenant_id ?? props.detail.tenant_id,
  tenantName: props.detail.actor?.tenant_name ?? props.detail.tenant_name,
  userType: props.detail.actor?.type,
  username:
    props.detail.actor?.username ||
    props.detail.actor?.display_name ||
    props.detail.actor?.nickname ||
    undefined,
}));
</script>

<template>
  <section class="monitoring-hero">
    <div class="monitoring-hero__topline">
      <div
        class="inline-flex items-center gap-2 rounded-full bg-sky-500/10 px-3 py-1"
      >
        <IconifyIcon
          class="size-3.5 text-sky-600"
          icon="lucide:activity-square"
        />
        <span class="text-xs font-medium text-sky-700">
          {{ $t(`${i18nPrefix}.conversationTitle`) }}
        </span>
      </div>
    </div>

    <div class="monitoring-hero__content">
      <div class="monitoring-hero__main">
        <div class="monitoring-hero__title">
          {{ detail.title || '-' }}
        </div>
        <div class="monitoring-hero__meta">
          <span class="monitoring-hero__meta-item">
            <span
              class="flex size-6 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-primary/10 text-primary"
            >
              <img
                v-if="detail.agent_avatar && !isIconAvatar(detail.agent_avatar)"
                :alt="detailAgentName"
                :src="toAvatarDisplayUrl(detail.agent_avatar)"
                class="size-full object-cover"
              />
              <IconifyIcon
                v-else-if="isIconAvatar(detail.agent_avatar)"
                :icon="String(detail.agent_avatar)"
                class="size-4"
              />
              <span v-else class="text-[11px] font-semibold">
                {{ getInitialLetter(detailAgentName) }}
              </span>
            </span>
            <span>{{ detailAgentName }}</span>
          </span>
          <span class="monitoring-hero__meta-item">
            <IconifyIcon class="size-3.5" icon="lucide:building-2" />
            <span>{{ detail.tenant_name || '-' }}</span>
          </span>
          <div
            v-if="actorIdentityModel"
            class="min-w-[180px] rounded-xl bg-background/75 px-2 py-2"
          >
            <IdentityTrigger
              :avatar-size="32"
              :model="actorIdentityModel"
              :meta="actorIdentityMeta"
            />
          </div>
        </div>
        <div class="mt-3 flex flex-wrap items-center gap-2">
          <Tag :color="conversationStatusColor(detail.status)">
            {{ detail.status }}
          </Tag>
          <Tag v-if="detail.last_call_at" color="cyan">
            {{ formatDate(detail.last_call_at) }}
          </Tag>
        </div>
      </div>

      <div class="monitoring-hero__stats">
        <div
          v-for="stat in heroStats"
          :key="stat.key"
          class="monitoring-hero__stat"
        >
          <div class="monitoring-hero__stat-label">
            <IconifyIcon :icon="stat.icon" class="size-3.5" />
            <span>{{ stat.label }}</span>
          </div>
          <div class="monitoring-hero__stat-value">{{ stat.value }}</div>
        </div>
      </div>
    </div>
  </section>
</template>
