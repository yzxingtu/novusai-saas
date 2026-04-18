<script lang="ts" setup>
import type { BuiltinToolInfo, SkillFormSharedState } from './skill-form-types';

import type { AdminSkillInfo, PluginToolDefinition } from '#/api/admin/skills';

import { computed, ref, watch } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { getSkillDetailApi, getSkillToolsApi } from '#/api/admin/skills';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { createSkillFormSchema } from './skill-form-schema';
import {
  buildSkillFormPayload,
  getSkillFormDefaults,
  toSkillFormValues,
} from './skill-form-values';
import SkillFormToolPanels from './SkillFormToolPanels.vue';

defineOptions({ name: 'AdminSkillFormContent' });

const emits = defineEmits<{ success: [] }>();

const currentValvesSchema = ref<null | Record<string, unknown>>(null);
const builtinTools = ref<BuiltinToolInfo[]>([]);
const pluginTools = ref<PluginToolDefinition[]>([]);
const isPluginSkill = ref(false);
const pluginSourceName = ref('');

const sharedState: SkillFormSharedState = {
  builtinTools,
  currentValvesSchema,
  isPluginSkill,
  pluginSourceName,
  pluginTools,
};

const getSchema = createSkillFormSchema(sharedState);

const [Form, formApi] = useVbenForm({
  schema: getSchema(),
  showDefaultActions: false,
});

async function loadPluginTools(skillId: number) {
  try {
    pluginTools.value = await getSkillToolsApi(skillId);
  } catch {
    pluginTools.value = [];
  }
}

const { Drawer, isEdit } = useCrudDrawer<AdminSkillInfo>({
  formApi,
  schema: getSchema,
  defaults: () => getSkillFormDefaults(sharedState),
  apiPath: '/admin/ai/skills',
  transform: buildSkillFormPayload,
  toFormValues: (data) =>
    toSkillFormValues(data, {
      ...sharedState,
      loadPluginTools,
    }),
  onSuccess: () => {
    emits('success');
  },
  detailApi: async (id) => {
    return await getSkillDetailApi(id as number);
  },
});

const title = computed(() =>
  isEdit.value ? $t('admin.common.edit') : $t('admin.ai.skill.create'),
);

const currentSkillType = ref('');
watch(
  () => formApi.form?.values?.type,
  (value) => {
    currentSkillType.value = (value as string) || '';
  },
  { immediate: true },
);

const drawerWidthClass = computed(() =>
  currentSkillType.value === 'toolkit' && !isPluginSkill.value
    ? 'w-[900px]'
    : 'w-[600px]',
);
</script>

<template>
  <Drawer :title="title" :class="drawerWidthClass">
    <Form />
    <SkillFormToolPanels
      :builtin-tools="builtinTools"
      :plugin-tools="pluginTools"
    />
  </Drawer>
</template>
