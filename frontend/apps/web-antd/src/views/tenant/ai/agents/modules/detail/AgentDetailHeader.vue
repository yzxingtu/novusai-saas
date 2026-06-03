<script lang="ts" setup>
import type { AgentInfo } from '#/api/tenant/agents';

import { computed, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, message, Spin, Tag, Upload } from 'ant-design-vue';

import { smartUploadFile } from '#/api/tenant/attachment';
import { $t } from '#/locales';
import { showRequestError } from '#/utils/error-helpers';
import { toAvatarDisplayUrl } from '#/utils/image';
import {
  getScopeColor,
  getScopeIcon,
  getScopeText,
} from '#/utils/scope-helpers';

import {
  getExecutionModeText,
  getStatusColor,
  getStatusText,
} from '../../data';

const props = defineProps<{
  agent: AgentInfo;
  isRoutingEnabled: boolean;
  isTenantOwned: boolean;
  onBack: () => void;
  onJumpToRoutingTab: () => void;
  onOpenAccessConfig: () => void;
  onOpenVersionHistory: () => void;
  onSaveFields: (fields: Record<string, unknown>) => Promise<void>;
}>();

const avatarUploading = ref(false);

const avatarDisplayUrl = computed(() => {
  const val = props.agent.avatar;
  return val ? toAvatarDisplayUrl(val) : '';
});

const avatarInitial = computed(() =>
  (props.agent.name || '?').charAt(0).toUpperCase(),
);

function getExecutionModeIcon(mode: string): string {
  switch (mode) {
    case 'api': {
      return 'lucide:code';
    }
    case 'batch': {
      return 'lucide:layers';
    }
    case 'conversation': {
      return 'lucide:message-circle';
    }
    case 'task': {
      return 'lucide:list-checks';
    }
    default: {
      return 'lucide:bot';
    }
  }
}

function beforeAvatarUpload(file: File) {
  const isImage = file.type.startsWith('image/');
  if (!isImage) {
    message.error($t('tenant.profile.messages.avatarTypeError'));
    return false;
  }
  const isLt2M = file.size / 1024 / 1024 < 2;
  if (!isLt2M) {
    message.error($t('tenant.profile.messages.avatarSizeError'));
    return false;
  }
  void handleAvatarUpload(file);
  return false;
}

async function handleAvatarUpload(file: File) {
  avatarUploading.value = true;
  try {
    const result = await smartUploadFile({
      file,
      visibility: 'public',
      business_type: 'avatar',
    });
    const attachmentId = String(result.attachment?.id || '');
    if (!attachmentId) throw new Error('Upload failed');
    await props.onSaveFields({ avatar: attachmentId });
  } catch (error) {
    showRequestError(error, 'shared.common.uploadFailed');
  } finally {
    avatarUploading.value = false;
  }
}

async function removeAvatar() {
  avatarUploading.value = true;
  try {
    await props.onSaveFields({ avatar: null });
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
  } finally {
    avatarUploading.value = false;
  }
}
</script>

<template>
  <div class="relative overflow-hidden rounded-xl border bg-card shadow-sm">
    <div
      class="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-transparent"
    ></div>
    <div class="relative p-6">
      <div class="mb-5 flex items-center justify-between">
        <button
          class="flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          @click="onBack"
        >
          <IconifyIcon icon="lucide:chevron-left" class="size-4" />
          {{ $t('common.back') }}
        </button>
        <div class="flex items-center gap-2">
          <Tag v-if="agent.published_version" color="blue" class="!mr-0">
            v{{ agent.published_version }}
          </Tag>
          <Tag :color="getStatusColor(agent.status)" class="!mr-0">
            {{ getStatusText(agent.status) }}
          </Tag>
          <Button size="small" @click="onOpenVersionHistory">
            <IconifyIcon icon="lucide:history" class="mr-1 size-3.5" />
            {{ $t('tenant.ai.agent.versionHistory') }}
          </Button>
          <Button size="small" @click="onOpenAccessConfig">
            <IconifyIcon icon="lucide:shield" class="mr-1 size-3.5" />
            {{ $t('tenant.ai.agent.accessConfig') }}
          </Button>
        </div>
      </div>

      <div class="flex items-start gap-5">
        <div class="group relative shrink-0">
          <Upload
            v-if="isTenantOwned"
            :show-upload-list="false"
            :before-upload="beforeAvatarUpload"
            :aria-label="$t('tenant.ai.agent.detail.uploadAvatar')"
            accept="image/*"
          >
            <div
              class="relative flex size-16 cursor-pointer items-center justify-center overflow-hidden rounded-2xl text-2xl font-bold shadow-sm ring-2 ring-offset-2 ring-offset-card"
              :class="
                agent.is_system
                  ? 'bg-amber-500/15 text-amber-600 ring-amber-400/30 dark:text-amber-400'
                  : 'bg-primary/10 text-primary ring-primary/20'
              "
              :aria-label="$t('tenant.ai.agent.detail.uploadAvatar')"
              :title="$t('tenant.ai.agent.detail.uploadAvatar')"
            >
              <img
                v-if="avatarDisplayUrl"
                :src="avatarDisplayUrl"
                :alt="agent.name"
                class="size-full object-cover"
              />
              <span v-else>{{ avatarInitial }}</span>
              <div
                class="absolute inset-0 flex items-center justify-center rounded-2xl bg-black/40 opacity-0 transition-all group-hover:opacity-100"
              >
                <Spin v-if="avatarUploading" size="small" />
                <IconifyIcon
                  v-else
                  icon="lucide:camera"
                  class="size-5 text-white"
                />
              </div>
            </div>
          </Upload>
          <div
            v-else
            class="flex size-16 items-center justify-center overflow-hidden rounded-2xl text-2xl font-bold shadow-sm ring-2 ring-offset-2 ring-offset-card"
            :class="
              agent.is_system
                ? 'bg-amber-500/15 text-amber-600 ring-amber-400/30 dark:text-amber-400'
                : 'bg-primary/10 text-primary ring-primary/20'
            "
          >
            <img
              v-if="avatarDisplayUrl"
              :src="avatarDisplayUrl"
              :alt="agent.name"
              class="size-full object-cover"
            />
            <span v-else>{{ avatarInitial }}</span>
          </div>
          <button
            v-if="isTenantOwned && avatarDisplayUrl && !avatarUploading"
            class="absolute -right-1 -top-1 flex size-5 items-center justify-center rounded-full bg-destructive text-white opacity-0 shadow-sm transition-opacity group-hover:opacity-100"
            type="button"
            :aria-label="$t('tenant.ai.agent.detail.removeAvatar')"
            :title="$t('tenant.ai.agent.detail.removeAvatar')"
            @click.stop="removeAvatar"
          >
            <IconifyIcon icon="lucide:x" class="size-3" />
          </button>
        </div>

        <div class="min-w-0 flex-1">
          <h1 class="mb-1 text-xl font-bold text-foreground">
            {{ agent.name }}
          </h1>
          <p class="mb-4 text-sm text-muted-foreground">
            {{ agent.description || $t('tenant.ai.agent.noDescription') }}
          </p>

          <div class="flex flex-wrap items-center gap-2">
            <div
              class="flex items-center gap-1.5 rounded-lg border border-border/50 bg-background px-3 py-1 text-xs text-foreground"
            >
              <IconifyIcon
                :icon="getExecutionModeIcon(agent.execution_mode)"
                class="size-3.5 text-primary/70"
              />
              {{ getExecutionModeText(agent.execution_mode) }}
            </div>
            <Tag :color="getScopeColor(agent.scope)" class="!mr-0 !text-xs">
              <div class="flex items-center gap-1">
                <IconifyIcon :icon="getScopeIcon(agent.scope)" class="size-3" />
                {{ getScopeText(agent.scope) }}
              </div>
            </Tag>
            <div
              v-if="!isTenantOwned"
              class="flex items-center gap-1.5 rounded-lg border border-warning/30 bg-warning/10 px-3 py-1 text-xs font-medium text-warning"
            >
              <IconifyIcon icon="lucide:lock" class="size-3.5" />
              {{ $t('tenant.ai.agent.readonlyHint') }}
            </div>
            <button
              v-if="isTenantOwned"
              class="flex items-center gap-1.5 rounded-lg border px-3 py-1 text-xs font-medium transition-all duration-200 hover:opacity-80"
              :class="
                isRoutingEnabled
                  ? 'border-green-500/30 bg-green-500/10 text-green-600 dark:text-green-400'
                  : 'border-border/50 bg-background text-muted-foreground'
              "
              @click="onJumpToRoutingTab"
            >
              <IconifyIcon icon="lucide:git-branch" class="size-3.5" />
              <span v-if="isRoutingEnabled">{{
                $t('tenant.ai.agent.routing.statusEnabled')
              }}</span>
              <span v-else>{{
                $t('tenant.ai.agent.routing.statusDisabled')
              }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
