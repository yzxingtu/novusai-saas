<script lang="ts" setup>
import type { AIAgentSkillGrantInfo } from '#/api/admin/ai';
import type { AgentSkillBindingDraftItem } from '#/components/business/agent-skill-binding-picker';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
  message,
  Popconfirm,
  Spin,
  Switch,
  Tag,
} from 'ant-design-vue';

import {
  batchBindAIAgentSkillsApi,
  getAIAgentSkillsApi,
  unbindAIAgentSkillApi,
  updateAIAgentSkillGrantApi,
} from '#/api/admin/ai';
import {
  AgentSkillBindingPicker,
  draftsToBatchPayload,
  grantsToDrafts,
} from '#/components/business/agent-skill-binding-picker';
import { $t } from '#/locales';
import { getSkillTypeColor, getSkillTypeIcon } from '#/utils/ai-helpers';
import { showRequestError } from '#/utils/error-helpers';

const props = defineProps<{
  active: boolean;
  agentId: number;
}>();

const bindings = ref<AIAgentSkillGrantInfo[]>([]);
const bindingsLoading = ref(false);
const skillPickerOpen = ref(false);
const skillPickerDrafts = ref<AgentSkillBindingDraftItem[]>([]);
const bindingPackageCount = computed(() => {
  const keys = new Set(
    bindings.value.map(
      (binding) => binding.package_name || `skill:${binding.skill_id}`,
    ),
  );
  return keys.size;
});

function getSkillSourceTag(
  binding: AIAgentSkillGrantInfo,
): null | { color: string; text: string } {
  if (binding.skill_source_type === 'plugin') {
    return { text: $t('admin.ai.skillPackage.sourcePlugin'), color: 'purple' };
  }
  if (binding.package_is_system) {
    return { text: $t('admin.ai.skillPackage.system'), color: 'red' };
  }
  return null;
}

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

async function loadBindings() {
  bindingsLoading.value = true;
  try {
    bindings.value = await getAIAgentSkillsApi(props.agentId);
  } catch (error) {
    bindings.value = [];
    showRequestError(error, 'common.loadFailed');
  } finally {
    bindingsLoading.value = false;
  }
}

function openSkillBindingPicker() {
  skillPickerDrafts.value = grantsToDrafts(bindings.value);
  skillPickerOpen.value = true;
}

async function onSkillBindingPickerConfirm(
  drafts: AgentSkillBindingDraftItem[],
) {
  try {
    await batchBindAIAgentSkillsApi(
      props.agentId,
      draftsToBatchPayload(drafts),
    );
    message.success($t('admin.ai.agent.detail.saveSuccess'));
    await loadBindings();
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
  }
}

async function unbindSkill(skillId: number) {
  try {
    await unbindAIAgentSkillApi(props.agentId, skillId);
    await loadBindings();
    message.success($t('admin.ai.agent.detail.saveSuccess'));
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
  }
}

async function toggleSkillEnabled(binding: AIAgentSkillGrantInfo) {
  if (binding.id === null || binding.id === undefined) return;
  try {
    await updateAIAgentSkillGrantApi(props.agentId, binding.id, {
      enabled: !binding.enabled,
    });
    await loadBindings();
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
  }
}

watch(
  () => props.active,
  (active) => {
    if (active) {
      void loadBindings();
    }
  },
  { immediate: true },
);

watch(
  () => props.agentId,
  () => {
    if (props.active) {
      void loadBindings();
    }
  },
);
</script>

<template>
  <div class="p-5 pt-3">
    <AgentSkillBindingPicker
      :agent-id="agentId"
      v-model:open="skillPickerOpen"
      v-model="skillPickerDrafts"
      @confirm="onSkillBindingPickerConfirm"
    />
    <Spin :spinning="bindingsLoading">
      <div class="flex flex-col gap-4">
        <div class="rounded-2xl border border-border/70 bg-muted/20 p-4">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-sm font-semibold text-foreground">
                  {{ $t('admin.ai.agent.detail.skillBindings') }}
                </span>
                <Tag class="!mr-0 !rounded-full !px-2 !text-[11px]">
                  {{
                    $t('admin.ai.agent.skillPicker.selectedCount', {
                      count: bindings.length,
                    })
                  }}
                </Tag>
                <Tag class="!mr-0 !rounded-full !px-2 !text-[11px]">
                  {{
                    $t('admin.ai.agent.skillPicker.selectionSummary', {
                      skills: bindings.length,
                      packages: bindingPackageCount,
                    })
                  }}
                </Tag>
              </div>
              <p class="mt-1 text-xs leading-5 text-muted-foreground">
                {{ $t('admin.ai.agent.help.skillBindings') }}
              </p>
            </div>
            <Button type="primary" @click="openSkillBindingPicker">
              <IconifyIcon icon="lucide:settings-2" class="mr-1 size-4" />
              {{ $t('admin.ai.agent.skillPicker.manageBindings') }}
            </Button>
          </div>
        </div>

        <div v-if="bindings.length > 0" class="flex flex-col gap-2">
          <div
            v-for="binding in bindings"
            :key="binding.skill_id"
            class="rounded-xl border bg-background px-4 py-3 transition-colors"
          >
            <div class="flex items-center justify-between gap-4">
              <div class="flex min-w-0 flex-1 items-center gap-3">
                <div
                  class="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10"
                >
                  <IconifyIcon
                    :icon="getSkillTypeIcon(binding.skill_type || 'toolkit')"
                    class="size-4"
                    :style="{
                      color: `var(--ant-color-${getSkillTypeColor(binding.skill_type || 'toolkit')})`,
                    }"
                  />
                </div>
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-2">
                    <span class="truncate text-sm font-medium">
                      {{ binding.skill_name || `#${binding.skill_id}` }}
                    </span>
                    <Tag
                      :color="
                        getSkillTypeColor(binding.skill_type || 'toolkit')
                      "
                      class="!mr-0 !text-[10px]"
                    >
                      {{ getSkillTypeText(binding.skill_type || undefined) }}
                    </Tag>
                    <Tag
                      v-if="getSkillSourceTag(binding)"
                      :color="getSkillSourceTag(binding)?.color"
                      class="!mr-0 !text-[10px]"
                    >
                      {{ getSkillSourceTag(binding)?.text }}
                    </Tag>
                  </div>
                  <div class="mt-1 text-xs text-muted-foreground">
                    <span>
                      {{ binding.package_name || '-' }}
                    </span>
                  </div>
                </div>
              </div>
              <div class="flex items-center gap-3">
                <Switch
                  :checked="binding.enabled"
                  size="small"
                  :aria-label="`${$t('admin.ai.agent.detail.skillEnabled')}: ${
                    binding.skill_name || binding.skill_id
                  }`"
                  @change="toggleSkillEnabled(binding)"
                />
                <Popconfirm
                  :title="$t('common.confirmDelete')"
                  @confirm="unbindSkill(binding.skill_id)"
                >
                  <Button size="small" danger type="text">
                    <IconifyIcon icon="lucide:unlink" class="size-3.5" />
                  </Button>
                </Popconfirm>
              </div>
            </div>
          </div>
        </div>

        <div
          v-if="bindings.length === 0 && !bindingsLoading"
          class="rounded-2xl border border-dashed border-border/70 bg-background px-6 py-10 text-center"
        >
          <div
            class="mx-auto flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary"
          >
            <IconifyIcon icon="lucide:puzzle" class="size-6" />
          </div>
          <div class="mt-4 text-sm font-semibold text-foreground">
            {{ $t('admin.ai.agent.skillPicker.emptySelected') }}
          </div>
          <div
            class="mx-auto mt-2 max-w-xl text-xs leading-6 text-muted-foreground"
          >
            {{ $t('admin.ai.agent.skillPicker.detailEmptyHint') }}
          </div>
          <Button class="mt-5" type="primary" @click="openSkillBindingPicker">
            <IconifyIcon icon="lucide:sparkles" class="mr-1 size-4" />
            {{ $t('admin.ai.agent.skillPicker.manageBindings') }}
          </Button>
        </div>
      </div>
    </Spin>
  </div>
</template>
