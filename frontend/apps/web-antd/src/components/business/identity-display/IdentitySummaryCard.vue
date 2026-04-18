<script setup lang="ts">
import type { IdentitySummaryMode } from './detail-presentation';
import type { IdentityDetail, IdentityDetailRequest } from './identity-detail';
import type { IdentityDisplayModel } from './types';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Avatar, Tag } from 'ant-design-vue';

import { usePresenceStore } from '#/store';
import { toAvatarDisplayUrl } from '#/utils/image';

import {
  buildIdentityAuxiliaryItems,
  buildIdentityStatusChips,
  buildIdentitySummaryRows,
  resolveIdentityPrimaryContextLabel,
  resolveIdentityPrimaryContextValue,
} from './detail-presentation';
import {
  createIdentityDetailPreview,
  mergeIdentityDetailFallbacks,
  normalizeIdentitySubjectType,
} from './identity-detail';
import {
  resolveIdentityAvatarText,
  resolveIdentityContextIcon,
  resolveIdentityDisplayTitle,
} from './types';

interface IdentityPresenceTarget {
  scope: 'admin' | 'tenant';
  tenantId?: number;
  userId: number;
  userType: 'admin' | 'tenant_admin' | 'tenant_user';
}

defineOptions({ name: 'IdentitySummaryCard' });

const props = withDefaults(
  defineProps<{
    detailRequest?: IdentityDetailRequest | null;
    mode?: Extract<IdentitySummaryMode, 'embedded' | 'quick'>;
    model: IdentityDetail | IdentityDisplayModel;
    showOnlineStatus?: boolean;
    showRows?: boolean;
  }>(),
  {
    detailRequest: null,
    mode: 'embedded',
    showOnlineStatus: false,
    showRows: true,
  },
);

function toFiniteNumber(value: unknown): null | number {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function resolvePresenceTarget(
  detail: IdentityDetail,
  detailRequest?: IdentityDetailRequest | null,
): IdentityPresenceTarget | null {
  const scope = detailRequest?.scope;
  const userId = toFiniteNumber(detail.id);
  if (!scope || userId === null) {
    return null;
  }

  const tenantId = toFiniteNumber(detail.tenantId ?? detailRequest?.tenantId);
  const subjectType = normalizeIdentitySubjectType(
    detailRequest?.subjectType ?? detail.userType,
  );

  if (scope === 'admin') {
    if (subjectType === 'admin') {
      return {
        scope,
        userId,
        userType: 'admin',
      };
    }
    if (subjectType === 'tenant_user' && tenantId !== null) {
      return {
        scope,
        tenantId,
        userId,
        userType: 'tenant_user',
      };
    }
    if (subjectType === 'tenant_admin' && tenantId !== null) {
      return {
        scope,
        tenantId,
        userId,
        userType: 'tenant_admin',
      };
    }
    return null;
  }

  if (subjectType === 'tenant_admin') {
    return {
      scope,
      userId,
      userType: 'tenant_admin',
    };
  }
  if (subjectType === 'tenant_user') {
    return {
      scope,
      userId,
      userType: 'tenant_user',
    };
  }
  return null;
}

const presenceStore = usePresenceStore();

const previewDetail = computed<IdentityDetail>(() =>
  createIdentityDetailPreview({
    ...props.detailRequest,
    fallback: mergeIdentityDetailFallbacks(
      props.detailRequest?.fallback,
      props.model,
    ),
    id: props.model.id,
  }),
);

const resolvedTitle = computed(() =>
  resolveIdentityDisplayTitle(previewDetail.value),
);

const avatarValue = computed(() => previewDetail.value.avatar?.trim() || '');
const avatarText = computed(() =>
  resolveIdentityAvatarText(previewDetail.value),
);
const isIconAvatar = computed(() =>
  /^[a-z0-9-]+:[a-z0-9-]+$/i.test(avatarValue.value),
);
const avatarSrc = computed(() => {
  if (!avatarValue.value || isIconAvatar.value) {
    return '';
  }
  return toAvatarDisplayUrl(avatarValue.value);
});

const statusChips = computed(() =>
  buildIdentityStatusChips(previewDetail.value),
);
const summaryRows = computed(() =>
  props.showRows
    ? buildIdentitySummaryRows(previewDetail.value, props.mode)
    : [],
);
const auxiliaryItems = computed(() =>
  buildIdentityAuxiliaryItems(previewDetail.value),
);
const primaryContextLabel = computed(() =>
  resolveIdentityPrimaryContextLabel(previewDetail.value),
);
const primaryContextValue = computed(() =>
  resolveIdentityPrimaryContextValue(previewDetail.value),
);
const primaryContextIcon = computed(() =>
  resolveIdentityContextIcon(previewDetail.value),
);

const presenceTarget = computed(() =>
  resolvePresenceTarget(previewDetail.value, props.detailRequest),
);

const presenceResolved = ref(false);
let latestPresenceRequestId = 0;

watch(
  [() => props.showOnlineStatus, presenceTarget],
  async ([showOnlineStatus, target]) => {
    const requestId = ++latestPresenceRequestId;
    presenceResolved.value = false;

    if (!showOnlineStatus || !target) {
      return;
    }

    const loaded = await presenceStore.ensurePresenceLoaded(
      target.userType,
      target.scope,
      target.tenantId,
    );
    if (requestId !== latestPresenceRequestId) {
      return;
    }
    presenceResolved.value = loaded;
  },
  {
    immediate: true,
  },
);

const showPresenceIndicator = computed(
  () =>
    props.showOnlineStatus && presenceResolved.value && !!presenceTarget.value,
);

const presenceOnline = computed(() => {
  const target = presenceTarget.value;
  if (!target || !presenceResolved.value) {
    return false;
  }
  return presenceStore.isOnline(
    target.userType,
    target.userId,
    target.tenantId,
  );
});
</script>

<template>
  <div
    class="identity-summary-card"
    :class="`identity-summary-card--${mode}`"
    :data-mode="mode"
  >
    <div class="identity-summary-card__header">
      <div class="identity-summary-card__avatar-wrap">
        <Avatar
          v-if="avatarSrc"
          :size="48"
          :src="avatarSrc"
          class="identity-summary-card__avatar"
        />
        <Avatar
          v-else
          :size="48"
          class="identity-summary-card__avatar identity-summary-card__avatar--fallback"
        >
          <IconifyIcon
            v-if="isIconAvatar"
            :icon="avatarValue"
            class="size-4.5"
          />
          <template v-else>
            {{ avatarText }}
          </template>
        </Avatar>
        <span
          v-if="showPresenceIndicator"
          data-testid="presence-indicator"
          class="absolute -bottom-0.5 -right-0.5 block size-3 rounded-full border-2 border-background"
          :class="presenceOnline ? 'bg-green-500' : 'bg-muted-foreground/30'"
        ></span>
      </div>

      <div class="identity-summary-card__main">
        <div class="identity-summary-card__title-row">
          <div class="identity-summary-card__title">
            {{ resolvedTitle }}
          </div>

          <div
            v-if="statusChips.length > 0"
            class="identity-summary-card__chip-list"
          >
            <Tag
              v-for="chip in statusChips"
              :key="chip.key"
              :color="chip.color"
              class="identity-summary-card__chip"
            >
              {{ chip.label }}
            </Tag>
          </div>
        </div>

        <div class="identity-summary-card__context-row">
          <span class="identity-summary-card__context-chip">
            <IconifyIcon
              :icon="primaryContextIcon"
              class="identity-summary-card__context-icon"
            />
            <span class="identity-summary-card__context-label">
              {{ primaryContextLabel }}
            </span>
            <span class="identity-summary-card__context-value">
              {{ primaryContextValue }}
            </span>
          </span>
        </div>

        <div
          v-if="auxiliaryItems.length > 0"
          class="identity-summary-card__auxiliary"
        >
          <span
            v-for="item in auxiliaryItems"
            :key="item"
            class="identity-summary-card__auxiliary-item"
          >
            {{ item }}
          </span>
        </div>
      </div>
    </div>

    <dl v-if="summaryRows.length > 0" class="identity-summary-card__meta-list">
      <div
        v-for="item in summaryRows"
        :key="item.key"
        class="identity-summary-card__meta-row"
      >
        <dt class="identity-summary-card__meta-label">
          {{ item.label }}
        </dt>
        <dd class="identity-summary-card__meta-value">
          {{ item.value }}
        </dd>
      </div>
    </dl>
  </div>
</template>

<style scoped>
.identity-summary-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  width: 100%;
  text-align: left;
}

.identity-summary-card--embedded {
  padding: 14px;
  background: linear-gradient(
    135deg,
    hsl(var(--background)) 0%,
    hsl(var(--accent) / 30%) 100%
  );
  border: 1px solid hsl(var(--border) / 70%);
  border-radius: 18px;
  box-shadow: 0 10px 24px -20px rgb(15 23 42 / 35%);
}

.identity-summary-card--quick {
  min-width: 300px;
}

.identity-summary-card__header {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.identity-summary-card__avatar-wrap {
  position: relative;
  flex: 0 0 auto;
}

.identity-summary-card__avatar {
  border: 1px solid hsl(var(--border) / 65%);
}

.identity-summary-card__avatar--fallback {
  color: hsl(var(--primary));
  background: hsl(var(--primary) / 12%);
}

.identity-summary-card__main {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.identity-summary-card__title-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  justify-content: space-between;
  min-width: 0;
}

.identity-summary-card__title {
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.4;
  color: hsl(var(--foreground));
  white-space: nowrap;
}

.identity-summary-card__chip-list {
  display: flex;
  flex: 0 0 auto;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}

.identity-summary-card__chip {
  margin-inline-end: 0;
}

.identity-summary-card__context-row {
  display: flex;
  align-items: center;
}

.identity-summary-card__context-chip {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  max-width: 100%;
  padding: 3px 10px;
  color: hsl(var(--primary));
  background: hsl(var(--primary) / 9%);
  border: 1px solid hsl(var(--primary) / 18%);
  border-radius: 9999px;
}

.identity-summary-card__context-icon {
  flex: 0 0 auto;
  font-size: 12px;
}

.identity-summary-card__context-label,
.identity-summary-card__context-value {
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 11px;
  line-height: 1.4;
  white-space: nowrap;
}

.identity-summary-card__context-label {
  opacity: 0.8;
}

.identity-summary-card__context-value {
  font-weight: 600;
}

.identity-summary-card__auxiliary {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  min-width: 0;
  font-size: 12px;
  line-height: 1.45;
  color: hsl(var(--muted-foreground));
}

.identity-summary-card__auxiliary-item {
  position: relative;
}

.identity-summary-card__auxiliary-item:not(:last-child)::after {
  margin-left: 10px;
  content: '·';
  opacity: 0.6;
}

.identity-summary-card__meta-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
}

.identity-summary-card__meta-row {
  display: grid;
  grid-template-columns: minmax(88px, 112px) minmax(0, 1fr);
  gap: 10px;
  align-items: flex-start;
}

.identity-summary-card__meta-label {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  color: hsl(var(--muted-foreground));
}

.identity-summary-card__meta-value {
  margin: 0;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.5;
  color: hsl(var(--foreground));
  overflow-wrap: anywhere;
}
</style>
