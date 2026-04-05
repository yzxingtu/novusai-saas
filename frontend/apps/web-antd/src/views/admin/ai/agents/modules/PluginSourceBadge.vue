<script setup lang="ts">
import { computed } from 'vue';

import { Tag } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'PluginSourceBadge' });

const props = withDefaults(
  defineProps<{
    showDisabledState?: boolean;
    sourcePlugin?: null | string;
    sourcePluginDisplayName?: null | string;
    sourcePluginEnabled?: boolean;
  }>(),
  {
    sourcePlugin: null,
    sourcePluginDisplayName: null,
    sourcePluginEnabled: true,
    showDisabledState: true,
  },
);

const pluginLabel = computed(() => {
  if (!props.sourcePlugin) return '';
  return props.sourcePluginDisplayName || props.sourcePlugin;
});
</script>

<template>
  <div v-if="sourcePlugin" class="flex flex-wrap items-center gap-2">
    <Tag color="purple" class="!mr-0 !text-[11px]">
      {{ $t('admin.ai.skillPackage.sourcePlugin') }} · {{ pluginLabel }}
    </Tag>
    <Tag
      v-if="showDisabledState && sourcePluginEnabled === false"
      color="orange"
      class="!mr-0 !text-[11px]"
    >
      {{ $t('admin.ai.agent.sourcePluginDisabled') }}
    </Tag>
  </div>
</template>
