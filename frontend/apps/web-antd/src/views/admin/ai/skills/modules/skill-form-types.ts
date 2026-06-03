import type { Ref } from 'vue';

import type { PluginToolDefinition } from '#/api/admin/skills';

export interface BuiltinToolInfo {
  description: string;
  name: string;
  parameters?: {
    properties?: Record<string, { description?: string; type?: string }>;
  };
}

export interface SkillFormSharedState {
  builtinTools: Ref<BuiltinToolInfo[]>;
  currentValvesSchema: Ref<null | Record<string, unknown>>;
  isPluginSkill: Ref<boolean>;
  pluginSourceName: Ref<string>;
  pluginTools: Ref<PluginToolDefinition[]>;
}

export type SkillFormValues = Record<string, unknown>;
