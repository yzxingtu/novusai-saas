<script lang="ts" setup>
import type { MonitoringConversationDetail, MonitoringScope } from '../../api';

import type { IdentityDetailMeta } from '#/views/_shared/identity/identity-interactions';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Avatar, Card, Tag } from 'ant-design-vue';

import { IdentitySummaryCard } from '#/components/business/identity-display';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';
import IdentityTrigger from '#/views/_shared/identity/IdentityTrigger.vue';

import {
  conversationStatusColor,
  getInitialLetter,
  isIconAvatar,
} from './helpers';

defineOptions({ name: 'MonitoringConversationOverviewCard' });

const props = defineProps<{
  detail: MonitoringConversationDetail;
  i18nPrefix: string;
  scope: MonitoringScope;
}>();

const detailAgentName = computed(() => props.detail.agent_name || '-');

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
  <Card class="monitoring-card mt-4" :bordered="false">
    <template #title>
      <div class="monitoring-card__title">
        <IconifyIcon class="size-4" icon="lucide:scan-face" />
        <span>{{ $t('common.basicInfo') }}</span>
      </div>
    </template>

    <div class="monitoring-overview-grid">
      <div class="monitoring-overview-item">
        <div class="monitoring-overview-label">
          {{ $t(`${i18nPrefix}.agentName`) }}
        </div>
        <div class="monitoring-overview-value">
          <div class="flex items-center gap-2">
            <Avatar
              v-if="detail.agent_avatar && !isIconAvatar(detail.agent_avatar)"
              :size="24"
              :src="toAvatarDisplayUrl(detail.agent_avatar)"
            />
            <IconifyIcon
              v-else-if="isIconAvatar(detail.agent_avatar)"
              :icon="String(detail.agent_avatar)"
              class="size-4 text-primary"
            />
            <Avatar
              v-else
              :size="24"
              class="bg-primary/10 text-xs text-primary"
            >
              {{ getInitialLetter(detailAgentName) }}
            </Avatar>
            <span>{{ detailAgentName }}</span>
          </div>
        </div>
      </div>

      <div
        v-if="actorIdentityModel"
        class="monitoring-overview-item md:col-span-2"
      >
        <IdentityTrigger :model="actorIdentityModel" :meta="actorIdentityMeta">
          <template #default="{ detailRequest }">
            <IdentitySummaryCard
              :detail-request="detailRequest"
              :model="actorIdentityModel"
              mode="embedded"
            />
          </template>
        </IdentityTrigger>
      </div>

      <div class="monitoring-overview-item">
        <div class="monitoring-overview-label">
          {{ $t(`${i18nPrefix}.tenantName`) }}
        </div>
        <div class="monitoring-overview-value">
          {{ detail.tenant_name || '-' }}
        </div>
      </div>

      <div class="monitoring-overview-item">
        <div class="monitoring-overview-label">
          {{ $t(`${i18nPrefix}.status`) }}
        </div>
        <div class="monitoring-overview-value">
          <Tag :color="conversationStatusColor(detail.status)">
            {{ detail.status }}
          </Tag>
        </div>
      </div>

      <div class="monitoring-overview-item">
        <div class="monitoring-overview-label">
          {{ $t(`${i18nPrefix}.createdAt`) }}
        </div>
        <div class="monitoring-overview-value">
          {{ formatDate(detail.created_at) }}
        </div>
      </div>

      <div class="monitoring-overview-item">
        <div class="monitoring-overview-label">
          {{ $t(`${i18nPrefix}.lastCallAt`) }}
        </div>
        <div class="monitoring-overview-value">
          {{ detail.last_call_at ? formatDate(detail.last_call_at) : '-' }}
        </div>
      </div>
    </div>
  </Card>
</template>
