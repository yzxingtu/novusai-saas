<script lang="ts" setup>
import type {
  AgentKnowledgeBaseBindingSummary,
  AgentSkillBindingSummary,
} from './types';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Popover } from 'ant-design-vue';

import { $t } from '#/locales';
import { toAvatarDisplayUrl } from '#/utils/image';

const props = withDefaults(
  defineProps<{
    agentAvatar?: null | string;
    agentDescription?: null | string;
    agentId?: null | number;
    agentKnowledgeBaseIds?: null | number[];
    agentKnowledgeBases?: AgentKnowledgeBaseBindingSummary[] | null;
    agentName?: null | string;
    agentSkills?: AgentSkillBindingSummary[] | null;
    compact?: boolean;
    modelName?: null | string;
  }>(),
  {
    agentAvatar: null,
    agentDescription: null,
    agentId: null,
    agentKnowledgeBaseIds: null,
    agentKnowledgeBases: null,
    agentName: null,
    agentSkills: null,
    compact: false,
    modelName: null,
  },
);

interface AgentProfileChip {
  id: string;
  label: string;
}

const resolvedAvatarUrl = computed(() =>
  props.agentAvatar ? toAvatarDisplayUrl(props.agentAvatar) : '',
);

const resolvedName = computed(
  () => props.agentName || $t('common.globalAiChat.assistant'),
);

const avatarInitial = computed(() => {
  const name = resolvedName.value.trim();
  return name ? name.charAt(0).toUpperCase() : '';
});

function normalizeLabel(value: null | string | undefined): null | string {
  if (typeof value !== 'string') {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function appendChip(
  chips: AgentProfileChip[],
  seen: Set<string>,
  chip: AgentProfileChip,
) {
  const key = chip.id.toLowerCase();
  if (seen.has(key)) {
    return;
  }
  seen.add(key);
  chips.push(chip);
}

function resolveSkillId(binding: AgentSkillBindingSummary): null | number {
  if (typeof binding.skill_id === 'number') {
    return binding.skill_id;
  }
  if (typeof binding.id === 'number') {
    return binding.id;
  }
  return null;
}

function resolveKnowledgeBaseId(
  binding: AgentKnowledgeBaseBindingSummary,
): null | number {
  if (typeof binding.knowledge_base_id === 'number') {
    return binding.knowledge_base_id;
  }
  if (typeof binding.id === 'number') {
    return binding.id;
  }
  return null;
}

const skillPackageChips = computed<AgentProfileChip[]>(() => {
  const seen = new Set<string>();
  const chips: AgentProfileChip[] = [];
  const bindings = Array.isArray(props.agentSkills) ? props.agentSkills : [];

  for (const binding of bindings) {
    if (binding.enabled === false) {
      continue;
    }

    const packageName = normalizeLabel(binding.package_name);
    const packageId =
      typeof binding.package_id === 'number' ? binding.package_id : null;
    if (!packageName) {
      continue;
    }

    appendChip(chips, seen, {
      id:
        packageId === null ? `package:${packageName}` : `package:${packageId}`,
      label: packageName,
    });
  }

  return chips;
});

const skillEntryChips = computed<AgentProfileChip[]>(() => {
  const seen = new Set<string>();
  const chips: AgentProfileChip[] = [];
  const bindings = Array.isArray(props.agentSkills) ? props.agentSkills : [];

  for (const binding of bindings) {
    if (binding.enabled === false) {
      continue;
    }

    const skillName =
      normalizeLabel(binding.name) ??
      normalizeLabel(binding.skill_name) ??
      normalizeLabel(binding.skill_key);
    const skillId = resolveSkillId(binding);
    const label =
      skillName ??
      (skillId
        ? $t('common.globalAiChat.skillBindingFallback', { id: skillId })
        : null);

    if (!label) {
      continue;
    }

    appendChip(chips, seen, {
      id: skillId === null ? `skill:${label}` : `skill:${skillId}`,
      label,
    });
  }

  return chips;
});

const knowledgeBaseChips = computed<AgentProfileChip[]>(() => {
  const seen = new Set<string>();
  const chips: AgentProfileChip[] = [];
  const bindings = Array.isArray(props.agentKnowledgeBases)
    ? props.agentKnowledgeBases
    : [];

  for (const binding of bindings) {
    if (binding.enabled === false) {
      continue;
    }

    const kbId = resolveKnowledgeBaseId(binding);
    const label =
      normalizeLabel(binding.kb_name) ??
      normalizeLabel(binding.name) ??
      (kbId
        ? $t('common.globalAiChat.knowledgeBaseFallback', { id: kbId })
        : null);

    if (!label) {
      continue;
    }

    appendChip(chips, seen, {
      id: kbId === null ? `kb:${label}` : `kb:${kbId}`,
      label,
    });
  }

  const kbIds = Array.isArray(props.agentKnowledgeBaseIds)
    ? props.agentKnowledgeBaseIds
    : [];
  for (const kbId of kbIds) {
    if (typeof kbId !== 'number' || !Number.isFinite(kbId)) {
      continue;
    }
    appendChip(chips, seen, {
      id: `kb:${kbId}`,
      label: $t('common.globalAiChat.knowledgeBaseFallback', { id: kbId }),
    });
  }

  return chips;
});

const summaryStats = computed(() => {
  return [
    {
      icon: 'lucide:package',
      key: 'packages',
      label: $t('common.globalAiChat.skillPackages'),
      value: skillPackageChips.value.length,
    },
    {
      icon: 'lucide:wrench',
      key: 'skills',
      label: $t('common.globalAiChat.skillEntries'),
      value: skillEntryChips.value.length,
    },
    {
      icon: 'lucide:book-open',
      key: 'knowledgeBases',
      label: $t('common.globalAiChat.mentionSectionKbs'),
      value: knowledgeBaseChips.value.length,
    },
  ];
});
</script>

<template>
  <Popover
    :trigger="['hover', 'click']"
    placement="rightTop"
    overlay-class-name="ai-message-agent-popover"
    :mouse-enter-delay="0.12"
  >
    <template #content>
      <div
        data-testid="agent-profile-popover-content"
        class="agent-profile-popover w-[292px] max-w-[calc(100vw-28px)]"
      >
        <div class="agent-profile-panel px-3 py-2.5">
          <div class="flex min-w-0 items-start gap-3">
            <div
              class="agent-profile-avatar flex size-11 shrink-0 items-center justify-center rounded-[16px] text-sm font-semibold text-primary"
            >
              <img
                v-if="resolvedAvatarUrl"
                :src="resolvedAvatarUrl"
                :alt="resolvedName"
                class="size-full rounded-[16px] object-cover"
              />
              <span v-else-if="avatarInitial">{{ avatarInitial }}</span>
              <IconifyIcon v-else icon="lucide:bot" class="size-4" />
            </div>
            <div class="min-w-0 flex-1">
              <div
                class="truncate text-[13px] font-semibold tracking-[0.01em] text-foreground/90"
              >
                {{ resolvedName }}
              </div>
              <div
                v-if="modelName"
                class="agent-model-chip mt-1 inline-flex min-w-0 max-w-full items-center gap-1 rounded-full px-2 py-0.5 text-[9px]"
                data-testid="agent-profile-model-chip"
              >
                <IconifyIcon icon="lucide:cpu" class="size-2.5 shrink-0" />
                <span class="truncate">{{ modelName }}</span>
              </div>
              <p
                data-testid="agent-profile-description"
                class="agent-profile-description mt-1.5 text-[10.5px] leading-5"
                :class="agentDescription ? '' : 'italic'"
                :title="
                  agentDescription || $t('common.globalAiChat.noDescription')
                "
              >
                {{
                  agentDescription || $t('common.globalAiChat.noDescription')
                }}
              </p>
            </div>
          </div>

          <div class="agent-profile-summary mt-3">
            <div
              v-for="stat in summaryStats"
              :key="stat.key"
              class="agent-profile-stat-pill"
            >
              <IconifyIcon
                :icon="stat.icon"
                class="text-primary/72 size-3 shrink-0"
              />
              <span class="agent-profile-stat-label">{{ stat.label }}</span>
              <strong class="agent-profile-stat-value">{{ stat.value }}</strong>
            </div>
          </div>

          <div class="mt-3 space-y-2.5">
            <section
              class="agent-profile-section"
              data-testid="agent-profile-skills-section"
            >
              <div
                class="agent-profile-row"
                data-testid="agent-profile-skill-packages-section"
              >
                <div class="agent-profile-section-title">
                  <span class="inline-flex min-w-0 items-center gap-1.5">
                    <IconifyIcon
                      icon="lucide:package"
                      class="size-3 shrink-0"
                    />
                    <span class="truncate">{{
                      $t('common.globalAiChat.skillPackages')
                    }}</span>
                  </span>
                  <span class="agent-profile-count-badge">
                    {{ skillPackageChips.length }}
                  </span>
                </div>
                <div
                  v-if="skillPackageChips.length > 0"
                  class="agent-profile-chip-list"
                >
                  <span
                    v-for="chip in skillPackageChips"
                    :key="chip.id"
                    data-testid="agent-profile-skill-package-chip"
                    class="agent-profile-chip"
                  >
                    {{ chip.label }}
                  </span>
                </div>
                <div
                  v-else
                  data-testid="agent-profile-skill-empty"
                  class="agent-profile-empty"
                >
                  {{ $t('common.globalAiChat.noSkillPackages') }}
                </div>
              </div>

              <div
                class="agent-profile-row"
                data-testid="agent-profile-skill-entries-section"
              >
                <div class="agent-profile-section-title">
                  <span class="inline-flex min-w-0 items-center gap-1.5">
                    <IconifyIcon icon="lucide:wrench" class="size-3 shrink-0" />
                    <span class="truncate">{{
                      $t('common.globalAiChat.skillEntries')
                    }}</span>
                  </span>
                  <span class="agent-profile-count-badge">
                    {{ skillEntryChips.length }}
                  </span>
                </div>
                <div
                  v-if="skillEntryChips.length > 0"
                  class="agent-profile-chip-list"
                >
                  <span
                    v-for="chip in skillEntryChips"
                    :key="chip.id"
                    data-testid="agent-profile-skill-entry-chip"
                    class="agent-profile-chip"
                  >
                    {{ chip.label }}
                  </span>
                </div>
                <div
                  v-else
                  data-testid="agent-profile-skill-entry-empty"
                  class="agent-profile-empty"
                >
                  {{ $t('common.globalAiChat.noSkillsInPackage') }}
                </div>
              </div>
            </section>

            <section
              class="agent-profile-section"
              data-testid="agent-profile-kb-section"
            >
              <div class="agent-profile-section-title">
                <span class="inline-flex min-w-0 items-center gap-1.5">
                  <IconifyIcon
                    icon="lucide:book-open"
                    class="size-3 shrink-0"
                  />
                  <span class="truncate">{{
                    $t('common.globalAiChat.mentionSectionKbs')
                  }}</span>
                </span>
                <span class="agent-profile-count-badge">
                  {{ knowledgeBaseChips.length }}
                </span>
              </div>
              <div
                v-if="knowledgeBaseChips.length > 0"
                class="agent-profile-chip-list"
              >
                <span
                  v-for="chip in knowledgeBaseChips"
                  :key="chip.id"
                  data-testid="agent-profile-kb-chip"
                  class="agent-profile-chip"
                >
                  {{ chip.label }}
                </span>
              </div>
              <div
                v-else
                data-testid="agent-profile-kb-empty"
                class="agent-profile-empty"
              >
                {{ $t('common.globalAiChat.noKnowledgeBases') }}
              </div>
            </section>
          </div>

          <div
            data-testid="agent-profile-footer"
            class="agent-profile-footer mt-3 flex items-center justify-between gap-2"
          >
            <span class="truncate">{{
              $t('common.globalAiChat.agentProfileHint')
            }}</span>
            <span v-if="agentId" class="agent-profile-id">#{{ agentId }}</span>
          </div>
        </div>
      </div>
    </template>

    <button
      type="button"
      data-testid="assistant-agent-avatar"
      class="assistant-agent-avatar group/avatar flex shrink-0 items-center justify-center rounded-[18px] text-primary transition-all duration-200"
      :class="compact ? 'size-7 text-[10px]' : 'size-8 text-[11px]'"
      :aria-label="
        $t('common.globalAiChat.agentProfileAria', { agent: resolvedName })
      "
    >
      <img
        v-if="resolvedAvatarUrl"
        :src="resolvedAvatarUrl"
        :alt="resolvedName"
        class="size-full rounded-2xl object-cover"
      />
      <span v-else-if="avatarInitial" class="font-semibold">
        {{ avatarInitial }}
      </span>
      <IconifyIcon v-else icon="lucide:bot" class="size-3.5" />
    </button>
  </Popover>
</template>

<style scoped>
.assistant-agent-avatar,
.agent-profile-avatar {
  position: relative;
  overflow: hidden;
  background: linear-gradient(
    180deg,
    hsl(var(--background) / 0.98),
    hsl(var(--muted) / 0.16)
  );
  border: 1px solid hsl(var(--border) / 0.32);
  box-shadow: 0 10px 18px -28px hsl(var(--foreground) / 0.08);
  transition:
    transform 160ms ease,
    box-shadow 160ms ease,
    border-color 160ms ease,
    background-color 160ms ease;
}

.assistant-agent-avatar {
  touch-action: manipulation;
}

.assistant-agent-avatar:hover,
.assistant-agent-avatar:focus-visible {
  transform: translateY(-1px);
  box-shadow: 0 12px 22px -30px hsl(var(--foreground) / 0.1);
  border-color: hsl(var(--primary) / 0.2);
}

.assistant-agent-avatar:focus-visible {
  outline: none;
  box-shadow:
    0 0 0 3px hsl(var(--primary) / 0.14),
    0 12px 22px -30px hsl(var(--foreground) / 0.1);
}

.agent-profile-popover {
  color: hsl(var(--foreground) / 0.86);
}

.agent-profile-panel {
  max-height: min(64vh, 30rem);
  overflow-y: auto;
  border: 1px solid hsl(var(--border) / 0.2);
  border-radius: 18px;
  background: hsl(var(--background) / 0.98);
  box-shadow: 0 18px 30px -38px hsl(var(--foreground) / 0.1);
}

.agent-profile-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.45rem;
}

.agent-profile-stat-pill {
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.15rem;
  padding: 0.45rem 0.55rem;
  border: 1px solid hsl(var(--border) / 0.14);
  border-radius: 12px;
  background: hsl(var(--muted) / 0.12);
}

.agent-profile-stat-label {
  color: hsl(var(--muted-foreground) / 0.68);
  font-size: 9px;
  line-height: 1rem;
}

.agent-profile-stat-value {
  color: hsl(var(--foreground) / 0.9);
  font-size: 11px;
  line-height: 1rem;
}

.agent-model-chip {
  color: hsl(var(--foreground) / 0.7);
  border: 1px solid hsl(var(--border) / 0.16);
  background: hsl(var(--muted) / 0.12);
}

.agent-profile-description {
  color: hsl(var(--muted-foreground) / 0.76);
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.agent-profile-section {
  display: grid;
  gap: 0.65rem;
}

.agent-profile-row + .agent-profile-row,
.agent-profile-section + .agent-profile-section {
  padding-top: 0.65rem;
  border-top: 1px solid hsl(var(--border) / 0.18);
}

.agent-profile-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  color: hsl(var(--muted-foreground) / 0.74);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.agent-profile-count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.5rem;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  color: hsl(var(--muted-foreground) / 0.72);
  background: hsl(var(--muted) / 0.16);
  font-size: 9px;
  font-weight: 700;
}

.agent-profile-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.35rem;
}

.agent-profile-chip {
  display: inline-flex;
  min-width: 0;
  max-width: 100%;
  align-items: center;
  padding: 2px 7px;
  overflow: hidden;
  font-size: 10px;
  line-height: 17px;
  color: hsl(var(--foreground) / 0.82);
  text-overflow: ellipsis;
  white-space: nowrap;
  background: hsl(var(--muted) / 0.12);
  border: 1px solid hsl(var(--border) / 0.16);
  border-radius: 999px;
}

.agent-profile-empty {
  color: hsl(var(--muted-foreground) / 0.48);
  font-size: 10px;
  font-style: italic;
}

.agent-profile-footer {
  color: hsl(var(--muted-foreground) / 0.64);
  padding-top: 0.65rem;
  border-top: 1px solid hsl(var(--border) / 0.18);
  font-size: 9.5px;
}

.agent-profile-id {
  color: hsl(var(--foreground) / 0.7);
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
}
</style>
