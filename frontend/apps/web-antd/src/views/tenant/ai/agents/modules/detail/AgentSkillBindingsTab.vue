<script lang="ts" setup>
import type { AgentSkillGrantInfo } from '#/api/tenant/agents';

import { ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Empty, Spin, Tag } from 'ant-design-vue';

import { getAgentSkillsApi } from '#/api/tenant/agents';

const props = defineProps<{
  agentId: number;
  active: boolean;
}>();

const bindings = ref<AgentSkillGrantInfo[]>([]);
const bindingsLoading = ref(false);

async function loadBindings() {
  bindingsLoading.value = true;
  try {
    bindings.value = await getAgentSkillsApi(props.agentId);
  } catch {
    bindings.value = [];
  } finally {
    bindingsLoading.value = false;
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
    <Spin :spinning="bindingsLoading">
      <div class="flex flex-col gap-4">
        <div v-if="bindings.length > 0" class="flex flex-col gap-2">
          <div
            v-for="binding in bindings"
            :key="binding.skill_id"
            class="rounded-xl border bg-background px-4 py-3"
          >
            <div class="flex items-center justify-between gap-4">
              <div class="flex min-w-0 flex-1 items-center gap-3">
                <div
                  class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-sm font-bold text-primary"
                >
                  {{
                    (binding.skill_name || binding.package_name || '?')
                      .charAt(0)
                      .toUpperCase()
                  }}
                </div>
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-2">
                    <span class="truncate text-sm font-medium">
                      {{ binding.skill_name || `#${binding.skill_id}` }}
                    </span>
                    <Tag v-if="binding.package_name" class="!mr-0 !text-[10px]">
                      {{ binding.package_name }}
                    </Tag>
                  </div>
                  <p
                    v-if="binding.skill_description || binding.package_description"
                    class="mt-0.5 truncate text-xs text-muted-foreground"
                  >
                    {{ binding.skill_description || binding.package_description }}
                  </p>
                </div>
              </div>
              <Tag
                :color="
                  binding.default_consent_mode === 'auto'
                    ? 'green'
                    : binding.default_consent_mode === 'ask'
                      ? 'orange'
                      : 'red'
                "
                class="!mr-0 !text-[10px]"
              >
                {{
                  $t(
                    `tenant.ai.agent.consentModeOptions.${binding.default_consent_mode}`,
                  )
                }}
              </Tag>
            </div>
          </div>
        </div>

        <Empty v-if="bindings.length === 0 && !bindingsLoading" />
      </div>
    </Spin>
  </div>
</template>
