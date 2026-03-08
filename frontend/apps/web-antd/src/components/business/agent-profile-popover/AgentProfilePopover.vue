<script lang="ts" setup>
/**
 * Agent Profile Popover - Shared component for displaying agent info + skill packages.
 *
 * Reused in ChatMessageItem (slide panel chat) and ConversationDetail (history drawer).
 * Clicking the avatar opens a Popover with:
 *  - Agent name, model, description
 *  - Skill package list (expandable to show individual skills)
 */
import type { ChatSkillBindingInfo, ChatSkillInfo } from '#/api/shared/ai-chat';

import { reactive, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Popover, Spin, Tag } from 'ant-design-vue';

import {
  getChatAgentSkillsApi,
  getChatPackageSkillsApi,
} from '#/api/shared/ai-chat';
import { $t } from '#/locales';
import { getSkillTypeColor, getSkillTypeIcon } from '#/utils/ai-helpers';
import { toAvatarDisplayUrl } from '#/utils/image';

const props = withDefaults(
  defineProps<{
    /** Agent ID — required for loading skill packages */
    agentId?: null | number;
    /** Agent avatar URL (raw, will be resolved via toAvatarDisplayUrl) */
    agentAvatar?: null | string;
    /** Agent description */
    agentDescription?: null | string;
    /** Agent display name */
    agentName?: null | string;
    /** API prefix: '/admin' or '/tenant' */
    apiPrefix?: string;
    /** LLM model name */
    modelName?: null | string;
    /** Avatar size variant */
    size?: 'lg' | 'md' | 'sm';
  }>(),
  {
    agentId: null,
    agentAvatar: null,
    agentDescription: null,
    agentName: null,
    apiPrefix: '',
    modelName: null,
    size: 'md',
  },
);

const avatarUrl = ref<null | string>(null);

watch(
  () => props.agentAvatar,
  (v) => {
    avatarUrl.value = v ? toAvatarDisplayUrl(v) : null;
  },
  { immediate: true },
);

const showProfileCard = ref(false);

// ==================== Agent Skills in Popover ====================
const skillBindings = ref<ChatSkillBindingInfo[]>([]);
const skillBindingsLoaded = ref(false);
const skillBindingsLoading = ref(false);
const expandedPackages = reactive(new Set<number>());
const packageSkills = reactive(new Map<number, ChatSkillInfo[]>());
const packageSkillsLoading = reactive(new Set<number>());

function getSkillTypeText(type: string | undefined): string {
  if (!type) return '-';
  const key = `admin.ai.skill.type_options.${type}`;
  const text = $t(key);
  if (text === key) {
    return type
      .replaceAll('_', ' ')
      .replaceAll(/\b\w/g, (c) => c.toUpperCase());
  }
  return text;
}

async function loadSkillBindings() {
  const agentId = props.agentId;
  if (!agentId || !props.apiPrefix || skillBindingsLoaded.value) return;
  skillBindingsLoading.value = true;
  try {
    const res = await getChatAgentSkillsApi(props.apiPrefix, agentId);
    skillBindings.value = res;
    skillBindingsLoaded.value = true;
  } catch {
    skillBindings.value = [];
  } finally {
    skillBindingsLoading.value = false;
  }
}

async function togglePackageSkills(packageId: number) {
  if (expandedPackages.has(packageId)) {
    expandedPackages.delete(packageId);
    return;
  }
  expandedPackages.add(packageId);
  if (packageSkills.has(packageId)) return;
  if (!props.apiPrefix) return;
  packageSkillsLoading.add(packageId);
  try {
    const res = await getChatPackageSkillsApi(props.apiPrefix, packageId);
    packageSkills.set(packageId, res.items || []);
  } catch {
    packageSkills.set(packageId, []);
  } finally {
    packageSkillsLoading.delete(packageId);
  }
}

watch(showProfileCard, (open) => {
  if (open) loadSkillBindings();
});

/** Size classes */
const sizeClasses = {
  sm: {
    avatar: 'mt-0.5 flex size-6 text-[9px]',
    icon: 'size-3',
  },
  md: {
    avatar: 'mt-0.5 flex size-8 text-xs shadow-sm',
    icon: 'size-3.5',
  },
  lg: {
    avatar: 'flex size-10 text-sm shadow-sm',
    icon: 'size-4',
  },
};
</script>

<template>
  <Popover
    v-model:open="showProfileCard"
    trigger="click"
    placement="rightTop"
    overlay-class-name="agent-profile-popover"
  >
    <template #content>
      <div class="w-[280px]">
        <!-- Profile header -->
        <div class="flex items-center gap-3 border-b border-border/30 pb-3">
          <div
            class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary/20 to-primary/5 text-sm font-semibold text-primary shadow-sm"
          >
            <img
              v-if="avatarUrl"
              :src="avatarUrl"
              :alt="agentName || ''"
              class="size-full rounded-xl object-cover"
            />
            <span v-else-if="agentName">{{ agentName.charAt(0).toUpperCase() }}</span>
            <IconifyIcon v-else icon="lucide:bot" class="size-4" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="truncate text-sm font-semibold text-foreground">
              {{ agentName || $t('common.globalAiChat.assistant') }}
            </div>
            <div
              v-if="modelName"
              class="mt-0.5 flex items-center gap-1 text-[11px] text-muted-foreground"
            >
              <IconifyIcon icon="lucide:cpu" class="size-3 shrink-0" />
              <span class="truncate">{{ modelName }}</span>
            </div>
          </div>
        </div>
        <!-- Description -->
        <div
          v-if="agentDescription"
          class="pt-2.5 text-xs leading-relaxed text-muted-foreground"
        >
          {{ agentDescription }}
        </div>
        <div
          v-else
          class="pt-2.5 text-xs italic text-muted-foreground/50"
        >
          {{ $t('common.globalAiChat.noDescription') }}
        </div>
        <!-- Skill Packages -->
        <div
          v-if="apiPrefix && agentId"
          class="mt-2.5 border-t border-border/30 pt-2.5"
        >
          <div class="mb-1.5 flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
            <IconifyIcon icon="lucide:puzzle" class="size-3" />
            <span>{{ $t('common.globalAiChat.skillPackages') }}</span>
          </div>
          <Spin
            v-if="skillBindingsLoading"
            size="small"
            class="flex justify-center py-2"
          />
          <div
            v-else-if="skillBindings.length === 0 && skillBindingsLoaded"
            class="py-1.5 text-center text-[11px] italic text-muted-foreground/50"
          >
            {{ $t('common.globalAiChat.noSkillPackages') }}
          </div>
          <div v-else class="max-h-[240px] space-y-1 overflow-y-auto">
            <div
              v-for="binding in skillBindings"
              :key="binding.package_id"
              class="overflow-hidden rounded-lg border border-border/30"
            >
              <div
                class="flex cursor-pointer items-center gap-2 px-2.5 py-1.5 transition-colors hover:bg-accent/30"
                @click="togglePackageSkills(binding.package_id)"
              >
                <IconifyIcon
                  icon="lucide:package"
                  class="size-3 shrink-0 text-primary/60"
                />
                <span class="min-w-0 flex-1 truncate text-[11px] font-medium text-foreground">
                  {{ binding.package_name || `#${binding.package_id}` }}
                </span>
                <Tag
                  v-if="binding.package_is_system"
                  color="red"
                  class="!mr-0 !text-[9px] !leading-tight"
                >
                  {{ $t('admin.ai.skillPackage.system') }}
                </Tag>
                <IconifyIcon
                  :icon="expandedPackages.has(binding.package_id) ? 'lucide:chevron-up' : 'lucide:chevron-down'"
                  class="size-3 shrink-0 text-muted-foreground/50"
                />
              </div>
              <!-- Skills within package -->
              <div
                v-if="expandedPackages.has(binding.package_id)"
                class="border-t border-border/20 bg-accent/10 px-2 py-1"
              >
                <Spin
                  v-if="packageSkillsLoading.has(binding.package_id)"
                  size="small"
                  class="flex justify-center py-1.5"
                />
                <div
                  v-else-if="packageSkills.get(binding.package_id)?.length === 0"
                  class="py-1.5 text-center text-[10px] italic text-muted-foreground/50"
                >
                  {{ $t('common.globalAiChat.noSkillsInPackage') }}
                </div>
                <div v-else class="space-y-px">
                  <div
                    v-for="skill in packageSkills.get(binding.package_id)"
                    :key="skill.id"
                    class="flex items-center gap-1.5 rounded-md px-1.5 py-1 transition-colors hover:bg-accent/30"
                  >
                    <IconifyIcon
                      :icon="getSkillTypeIcon(skill.type)"
                      class="size-3 shrink-0"
                      :style="{ color: `var(--ant-color-${getSkillTypeColor(skill.type)})` }"
                    />
                    <span class="min-w-0 flex-1 truncate text-[10px] text-foreground/80">
                      {{ skill.name }}
                    </span>
                    <Tag
                      :color="getSkillTypeColor(skill.type)"
                      class="!mr-0 !text-[9px] !leading-tight"
                    >
                      {{ getSkillTypeText(skill.type) }}
                    </Tag>
                    <span
                      :class="skill.is_active ? 'bg-green-500' : 'bg-muted-foreground/30'"
                      class="inline-block size-1.5 shrink-0 rounded-full"
                    ></span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
    <!-- Avatar trigger -->
    <div
      class="shrink-0 cursor-pointer items-center justify-center rounded-xl bg-gradient-to-br from-primary/15 to-primary/5 font-medium text-primary transition-all hover:shadow-md hover:ring-2 hover:ring-primary/20"
      :class="sizeClasses[size].avatar"
    >
      <img
        v-if="avatarUrl"
        :src="avatarUrl"
        :alt="agentName || ''"
        class="size-full rounded-xl object-cover"
      />
      <span v-else-if="agentName">{{ agentName.charAt(0).toUpperCase() }}</span>
      <IconifyIcon v-else icon="lucide:bot" :class="sizeClasses[size].icon" />
    </div>
  </Popover>
</template>
