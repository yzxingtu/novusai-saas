<script lang="ts" setup>
import type { BuiltinToolInfo } from './skill-form-types';

import type { PluginToolDefinition } from '#/api/admin/skills';

import { Divider, Tag } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'AdminSkillFormToolPanels' });

defineProps<{
  builtinTools: BuiltinToolInfo[];
  pluginTools: PluginToolDefinition[];
}>();
</script>

<template>
  <template v-if="builtinTools.length > 0">
    <Divider orientation="left" dashed>
      {{ $t('admin.ai.skill.builtinTools.toolList') }}
      <Tag color="blue" class="ml-2">{{ builtinTools.length }}</Tag>
    </Divider>
    <div class="flex flex-col gap-2">
      <div
        v-for="tool in builtinTools"
        :key="tool.name"
        class="rounded-lg border border-border/60 p-3"
      >
        <div class="mb-1 flex items-center gap-2">
          <Tag color="processing">{{ tool.name }}</Tag>
        </div>
        <p class="mb-0 text-xs text-muted-foreground">
          {{ tool.description }}
        </p>
        <div
          v-if="tool.parameters?.properties"
          class="mt-2 flex flex-wrap gap-1"
        >
          <Tag
            v-for="(parameterInfo, parameterName) in tool.parameters.properties"
            :key="String(parameterName)"
            class="!text-[10px]"
          >
            {{ parameterName }}: {{ parameterInfo.type || 'string' }}
          </Tag>
        </div>
      </div>
    </div>
  </template>

  <template v-if="pluginTools.length > 0">
    <Divider orientation="left" dashed>
      {{ $t('admin.ai.skill.pluginTools.toolList') }}
      <Tag color="blue" class="ml-2">{{ pluginTools.length }}</Tag>
    </Divider>
    <div class="flex flex-col gap-2">
      <div
        v-for="tool in pluginTools"
        :key="tool.name"
        class="rounded-lg border border-border/60 p-3"
      >
        <div class="mb-1 flex items-center gap-2">
          <Tag color="processing">{{ tool.name }}</Tag>
          <span v-if="tool.timeout" class="text-[10px] text-muted-foreground">
            {{ tool.timeout }}s
          </span>
        </div>
        <p class="mb-0 text-xs text-muted-foreground">
          {{ tool.description }}
        </p>
        <div v-if="tool.parameters?.length" class="mt-2 flex flex-wrap gap-1">
          <Tag
            v-for="param in tool.parameters"
            :key="param.name"
            :color="param.required ? 'orange' : 'default'"
            class="!text-[10px]"
          >
            {{ param.name }}: {{ param.type }}
          </Tag>
        </div>
      </div>
    </div>
  </template>
</template>
