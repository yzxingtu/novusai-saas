<script lang="ts" setup>
/**
 * Agent Profile Popover - Shared component for displaying agent info + granted skills / 智能体资料气泡卡片
 *
 * Reused in ChatMessageItem (slide panel chat) and ConversationDetail (history drawer).
 * Clicking the avatar opens a Popover with:
 *  - Agent name, model, description
 *  - Directly granted skills grouped by package
 */
import type { ChatSkillBindingInfo } from '#/api/shared/ai-chat';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Popover, Spin, Tag } from 'ant-design-vue';

import { getChatAgentSkillsApi } from '#/api/shared/ai-chat';
import { $t } from '#/locales';
import { getSkillTypeColor, getSkillTypeIcon } from '#/utils/ai-helpers';
import { toAvatarDisplayUrl } from '#/utils/image';

const props = withDefaults(
  defineProps<{
    /** Agent ID — required for loading skill packages / 智能体 ID，加载技能包必填 */
    agentId?: null | number;
    /** Agent avatar URL (raw, will be resolved via toAvatarDisplayUrl) / 智能体头像 URL */
    agentAvatar?: null | string;
    /** Agent description / 智能体描述 */
    agentDescription?: null | string;
    /** Agent display name / 智能体展示名称 */
    agentName?: null | string;
    /** API prefix: '/admin' or '/tenant' / API 前缀 */
    apiPrefix?: string;
    /** LLM model name / 模型名称 */
    modelName?: null | string;
    /** Avatar size variant / 头像尺寸 */
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
const groupedSkillBindings = computed(() => {
  const groups = new Map<
    string,
    {
      package_id: null | number;
      package_is_system: boolean;
      package_name: null | string;
      skills: ChatSkillBindingInfo[];
    }
  >();

  for (const binding of skillBindings.value) {
    const key =
      binding.package_id != null
        ? `pkg:${binding.package_id}`
        : `name:${binding.package_name ?? 'ungrouped'}`;
    let group = groups.get(key);
    if (!group) {
      group = {
        package_id: binding.package_id,
        package_name: binding.package_name,
        package_is_system: binding.package_is_system,
        skills: [],
      };
      groups.set(key, group);
    }
    if (!group.skills.some((item) => item.skill_id === binding.skill_id)) {
      group.skills.push(binding);
    }
  }

  return [...groups.values()];
});
const grantedSkillCount = computed(() => skillBindings.value.length);

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

watch(showProfileCard, (open) => {
  if (open) loadSkillBindings();
});

/** Size classes / 尺寸样式类 */
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

function getPackageDisplayName(bindingGroup: {
  package_name: null | string;
}) {
  return bindingGroup.package_name || $t('common.globalAiChat.ungroupedPackage');
}
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
        <!-- Granted skills grouped by package -->
        <div
          v-if="apiPrefix && agentId"
          class="mt-2.5 border-t border-border/30 pt-2.5"
        >
          <div class="mb-1.5 flex items-center justify-between gap-2 text-[11px] font-medium text-muted-foreground">
            <div class="flex items-center gap-1.5">
              <IconifyIcon icon="lucide:puzzle" class="size-3" />
              <span>{{ $t('common.globalAiChat.skillPackages') }}</span>
            </div>
            <span>
              {{
                $t('common.globalAiChat.skillPackageSummary', {
                  packages: groupedSkillBindings.length,
                  skills: grantedSkillCount,
                })
              }}
            </span>
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
              v-for="group in groupedSkillBindings"
              :key="
                group.package_id != null
                  ? `package-${group.package_id}`
                  : `package-name-${group.package_name ?? 'ungrouped'}`
              "
              class="overflow-hidden rounded-lg border border-border/30"
            >
              <div
                class="flex items-center gap-2 border-b border-border/20 bg-accent/10 px-2.5 py-1.5"
              >
                <IconifyIcon
                  icon="lucide:package"
                  class="size-3 shrink-0 text-primary/60"
                />
                <span class="min-w-0 flex-1 truncate text-[11px] font-medium text-foreground">
                  {{ getPackageDisplayName(group) }}
                </span>
                <Tag
                  v-if="group.package_is_system"
                  color="red"
                  class="!mr-0 !text-[9px] !leading-tight"
                >
                  {{ $t('admin.ai.skillPackage.system') }}
                </Tag>
                <Tag class="!mr-0 !text-[9px] !leading-tight">
                  {{ group.skills.length }}
                </Tag>
              </div>
              <div class="space-y-px bg-background px-2 py-1.5">
                <div
                  v-for="skill in group.skills"
                  :key="skill.skill_id"
                  class="flex items-start gap-1.5 rounded-md px-1.5 py-1.5 transition-colors hover:bg-accent/30"
                >
                  <IconifyIcon
                    :icon="getSkillTypeIcon(skill.skill_type || 'toolkit')"
                    class="mt-0.5 size-3 shrink-0"
                    :style="{
                      color: `var(--ant-color-${getSkillTypeColor(skill.skill_type || 'toolkit')})`,
                    }"
                  />
                  <div class="min-w-0 flex-1">
                    <div class="truncate text-[10px] font-medium text-foreground/85">
                      {{
                        skill.skill_name ||
                        skill.skill_key ||
                        `#${skill.skill_id}`
                      }}
                    </div>
                    <div
                      v-if="skill.skill_description"
                      class="mt-0.5 line-clamp-2 text-[9px] leading-relaxed text-muted-foreground"
                    >
                      {{ skill.skill_description }}
                    </div>
                  </div>
                  <Tag
                    v-if="skill.skill_type"
                    :color="getSkillTypeColor(skill.skill_type)"
                    class="!mr-0 !text-[9px] !leading-tight"
                  >
                    {{ getSkillTypeText(skill.skill_type) }}
                  </Tag>
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
