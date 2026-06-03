import type { BuiltinToolInfo, SkillFormSharedState } from './skill-form-types';

import type { AdminSkillInfo, PluginToolDefinition } from '#/api/admin/skills';

import { computed, ref, watch } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { getSkillDetailApi } from '#/api/admin/skills';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { createSkillFormSchema } from './skill-form-schema';
import {
  getSkillFormDefaults,
  toSkillFormValues,
  transformSkillFormValues,
} from './skill-form-values';

interface UseSkillFormShellOptions {
  onSuccess: () => void;
}

export function useSkillFormShell(options: UseSkillFormShellOptions) {
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

  const useFormSchema = createSkillFormSchema(sharedState);
  const [Form, formApi] = useVbenForm({
    schema: useFormSchema(),
    showDefaultActions: false,
  });

  const { Drawer, isEdit } = useCrudDrawer<AdminSkillInfo>({
    formApi,
    schema: useFormSchema,
    defaults: () => getSkillFormDefaults(sharedState),
    apiPath: '/admin/ai/skills',
    transform: transformSkillFormValues,
    toFormValues: (data) => toSkillFormValues(data, sharedState),
    onSuccess: options.onSuccess,
    detailApi: async (id) => await getSkillDetailApi(id as number),
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

  return {
    Drawer,
    Form,
    builtinTools,
    drawerWidthClass,
    pluginTools,
    title,
  };
}
