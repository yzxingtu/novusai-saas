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
        class="agent-profile-popover w-[336px] max-w-[calc(100vw-28px)]"
      >
        <div class="agent-profile-hero rounded-[22px] px-3 py-3">
          <div class="flex min-w-0 items-start gap-3">
            <div
              class="agent-profile-avatar flex size-12 shrink-0 items-center justify-center rounded-[18px] text-sm font-semibold text-primary"
            >
              <img
                v-if="resolvedAvatarUrl"
                :src="resolvedAvatarUrl"
                :alt="resolvedName"
                class="size-full rounded-[18px] object-cover"
              />
              <span v-else-if="avatarInitial">{{ avatarInitial }}</span>
              <IconifyIcon v-else icon="lucide:bot" class="size-4" />
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex min-w-0 items-center gap-1.5">
                <div
                  class="truncate text-[13px] font-semibold tracking-[0.01em] text-foreground/90"
                >
                  {{ resolvedName }}
                </div>
                <div
                  v-if="modelName"
                  class="agent-model-chip inline-flex min-w-0 items-center gap-1 rounded-full px-2 py-0.5 text-[9px]"
                >
                  <IconifyIcon icon="lucide:cpu" class="size-2.5 shrink-0" />
                  <span class="truncate">{{ modelName }}</span>
                </div>
              </div>
              <div class="mt-2 grid grid-cols-3 gap-1.5">
                <div
                  v-for="stat in summaryStats"
                  :key="stat.key"
                  class="agent-profile-stat-card"
                >
                  <div class="flex items-center gap-1 text-primary/70">
                    <IconifyIcon :icon="stat.icon" class="size-3 shrink-0" />
                    <span class="agent-profile-stat-label truncate">{{
                      stat.label
                    }}</span>
                  </div>
                  <strong class="agent-profile-stat-value">{{ stat.value }}</strong>
                </div>
              </div>
            </div>
          </div>
        </div>

        <p
          class="agent-profile-description mt-3 rounded-[18px] border px-3 py-2.5 text-[10.5px] leading-5"
          :class="agentDescription ? '' : 'italic'"
        >
          {{ agentDescription || $t('common.globalAiChat.noDescription') }}
        </p>

        <div class="mt-3 grid gap-2.5">
          <section
            class="agent-profile-section rounded-[18px] p-2.5"
            data-testid="agent-profile-skills-section"
          >
            <div
              class="agent-profile-section-title mb-2 flex items-center justify-between gap-2"
            >
              <span class="inline-flex items-center gap-1.5">
                <IconifyIcon icon="lucide:package" class="size-3" />
                <span>{{ $t('common.globalAiChat.skillPackages') }}</span>
              </span>
              <span class="agent-profile-count-badge">
                {{ skillPackageChips.length + skillEntryChips.length }}
              </span>
            </div>
            <div class="space-y-2">
              <div
                class="agent-profile-subsection"
                data-testid="agent-profile-skill-packages-section"
              >
                <div class="agent-profile-subtitle">
                  {{ $t('common.globalAiChat.skillPackages') }}
                </div>
                <div
                  v-if="skillPackageChips.length > 0"
                  class="flex flex-wrap gap-1.5"
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
                class="agent-profile-subsection"
                data-testid="agent-profile-skill-entries-section"
              >
                <div class="agent-profile-subtitle">
                  {{ $t('common.globalAiChat.skillEntries') }}
                </div>
                <div
                  v-if="skillEntryChips.length > 0"
                  class="flex flex-wrap gap-1.5"
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
            </div>
          </section>

          <section
            class="agent-profile-section rounded-[18px] p-2.5"
            data-testid="agent-profile-kb-section"
          >
            <div
              class="agent-profile-section-title mb-2 flex items-center justify-between gap-2"
            >
              <span class="inline-flex items-center gap-1.5">
                <IconifyIcon icon="lucide:book-open" class="size-3" />
                <span>{{ $t('common.globalAiChat.mentionSectionKbs') }}</span>
              </span>
              <span class="agent-profile-count-badge">
                {{ knowledgeBaseChips.length }}
              </span>
            </div>
            <div
              v-if="knowledgeBaseChips.length > 0"
              class="flex flex-wrap gap-1.5"
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
          class="agent-profile-footer mt-3 flex items-center justify-between rounded-[16px] px-2.5 py-2 text-[9.5px]"
        >
          <span>{{ $t('common.globalAiChat.agentProfileHint') }}</span>
          <span v-if="agentId" class="font-mono">#{{ agentId }}</span>
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
    hsl(var(--background)) 0%,
    hsl(var(--muted) / 0.42) 100%
  );
  border: 1px solid hsl(var(--border) / 0.5);
  box-shadow:
    0 16px 28px -24px hsl(var(--foreground) / 0.14),
    0 1px 0 hsl(var(--background) / 0.84) inset;
}

.assistant-agent-avatar:hover {
  transform: translateY(-1px);
  box-shadow:
    0 22px 32px -26px hsl(var(--foreground) / 0.16),
    0 1px 0 hsl(var(--background) / 0.84) inset;
  border-color: hsl(var(--primary) / 0.24);
}

.agent-profile-popover {
  color: hsl(var(--foreground) / 0.86);
}

.agent-profile-hero {
  border: 1px solid hsl(var(--primary) / 0.12);
  background:
    radial-gradient(
      circle at top left,
      hsl(var(--primary) / 0.1),
      transparent 42%
    ),
    linear-gradient(
      180deg,
      hsl(var(--background) / 0.98) 0%,
      hsl(var(--muted) / 0.12) 100%
    );
  box-shadow: 0 18px 32px -30px hsl(var(--foreground) / 0.12);
}

.agent-profile-stat-card {
  min-width: 0;
  padding: 0.55rem 0.6rem;
  border: 1px solid hsl(var(--border) / 0.28);
  border-radius: 16px;
  background: hsl(var(--background) / 0.82);
}

.agent-profile-stat-label {
  color: hsl(var(--muted-foreground) / 0.68);
  font-size: 9px;
  line-height: 0.9rem;
}

.agent-profile-stat-value {
  display: block;
  margin-top: 0.35rem;
  color: hsl(var(--foreground) / 0.9);
  font-size: 13px;
  line-height: 1rem;
}

.agent-model-chip {
  color: hsl(var(--foreground) / 0.7);
  border: 1px solid hsl(var(--primary) / 0.12);
  background: hsl(var(--primary) / 0.05);
}

.agent-profile-description {
  color: hsl(var(--muted-foreground) / 0.76);
  border-color: hsl(var(--border) / 0.36);
  background: hsl(var(--background) / 0.9);
}

.agent-profile-section {
  border: 1px solid hsl(var(--border) / 0.36);
  background: hsl(var(--background) / 0.92);
  box-shadow: 0 12px 24px -28px hsl(var(--foreground) / 0.12);
}

.agent-profile-section-title {
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
  color: hsl(var(--primary) / 0.78);
  background: hsl(var(--primary) / 0.08);
  font-size: 9px;
  font-weight: 700;
}

.agent-profile-chip {
  display: inline-flex;
  min-width: 0;
  max-width: 100%;
  align-items: center;
  padding: 2px 8px;
  overflow: hidden;
  font-size: 10px;
  line-height: 18px;
  color: hsl(var(--foreground) / 0.82);
  text-overflow: ellipsis;
  white-space: nowrap;
  background: hsl(var(--muted) / 0.36);
  border: 1px solid hsl(var(--border) / 0.34);
  border-radius: 999px;
}

.agent-profile-subsection + .agent-profile-subsection {
  padding-top: 8px;
  border-top: 1px solid hsl(var(--border) / 0.12);
}

.agent-profile-subtitle {
  margin-bottom: 0.4rem;
  color: hsl(var(--muted-foreground) / 0.66);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.agent-profile-empty {
  color: hsl(var(--muted-foreground) / 0.48);
  font-size: 10px;
  font-style: italic;
}

.agent-profile-footer {
  border: 1px solid hsl(var(--border) / 0.3);
  background: hsl(var(--muted) / 0.28);
  color: hsl(var(--muted-foreground) / 0.64);
}
</style>
