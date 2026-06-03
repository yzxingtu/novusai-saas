import type { SkillFormSharedState, SkillFormValues } from './skill-form-types';

import {
  inputField,
  numberField,
  select,
  switchField,
  textareaField,
} from '#/adapter/form';
import { getSkillPackageSelectApi } from '#/api/admin/skill-packages';
import { parseToolkitApi } from '#/api/admin/skills';
import { $t } from '#/locales';

function getSkillTypeOptions(currentType?: string) {
  const predefined = [
    { label: $t('admin.ai.skill.type_options.toolkit'), value: 'toolkit' },
    { label: $t('admin.ai.skill.type_options.builtin'), value: 'builtin' },
    { label: $t('admin.ai.skill.type_options.http'), value: 'http' },
    { label: $t('admin.ai.skill.type_options.email'), value: 'email' },
    {
      label: $t('admin.ai.skill.type_options.code_execution'),
      value: 'code_execution',
    },
  ];

  if (
    currentType &&
    !predefined.some((option) => option.value === currentType)
  ) {
    const key = `admin.ai.skill.type_options.${currentType}`;
    const translated = $t(key);
    const fallbackLabel = currentType
      .replaceAll('_', ' ')
      .replaceAll(/\b\w/g, (character) => character.toUpperCase());

    predefined.push({
      label: translated === key ? fallbackLabel : translated,
      value: currentType,
    });
  }

  return predefined;
}

async function getSkillPackageSelectOptions(params?: Record<string, unknown>) {
  try {
    return await getSkillPackageSelectApi(params);
  } catch {
    return [];
  }
}

function isToolkit(values: SkillFormValues, state: SkillFormSharedState) {
  return values.type === 'toolkit' && !state.isPluginSkill.value;
}

export function buildSkillFormCoreSchema(state: SkillFormSharedState) {
  return [
    {
      component: 'Alert',
      fieldName: '_create_guide',
      label: '',
      hideLabel: true,
      componentProps: {
        type: 'info',
        showIcon: true,
        banner: true,
        message: $t('admin.ai.skill.createGuide'),
      },
      dependencies: {
        triggerFields: ['_mode'],
        if: (values: SkillFormValues) => values._mode !== 'edit',
      },
    },
    {
      ...select('package_id', $t('admin.ai.skillPackage.name'), {
        api: getSkillPackageSelectOptions,
        required: true,
        placeholder: $t('admin.ai.skillPackage.placeholder.searchName'),
      }),
    },
    inputField('name', $t('admin.ai.skill.name'), {
      required: true,
      placeholder: $t('admin.ai.skill.placeholder.inputName'),
    }),
    {
      ...select('type', $t('admin.ai.skill.type'), {
        options: getSkillTypeOptions(),
        required: true,
        placeholder: $t('admin.ai.skill.placeholder.selectType'),
      }),
      help: $t('admin.ai.skill.help.type'),
      dependencies: {
        triggerFields: ['type'],
        componentProps: (values: SkillFormValues) => ({
          disabled: state.isPluginSkill.value,
          options: getSkillTypeOptions(String(values.type || '')),
        }),
      },
    },
    {
      component: 'Alert',
      fieldName: '_type_desc',
      label: '',
      componentProps: {
        type: 'info',
        showIcon: true,
        message: '',
      },
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) =>
          !!values.type && !state.isPluginSkill.value,
        componentProps: (values: SkillFormValues) => {
          const key = `admin.ai.skill.typeDesc.${String(values.type || '')}`;
          const translated = $t(key);

          return {
            type: 'info',
            showIcon: true,
            message: translated === key ? '' : translated,
          };
        },
      },
    },
    {
      component: 'Alert',
      fieldName: '_plugin_source',
      label: '',
      hideLabel: true,
      componentProps: {
        type: 'warning',
        showIcon: true,
        message: '',
      },
      dependencies: {
        triggerFields: ['type'],
        if: () => state.isPluginSkill.value,
        componentProps: () => ({
          type: 'warning',
          showIcon: true,
          message: $t('admin.ai.skill.pluginTools.managedBy', {
            plugin: state.pluginSourceName.value,
          }),
        }),
      },
    },
    textareaField('description', $t('admin.ai.skill.description'), {
      placeholder: $t('admin.ai.skill.placeholder.inputDescription'),
    }),
    {
      ...numberField('timeout', $t('admin.ai.skill.timeout'), {
        min: 1,
        max: 300,
        placeholder: $t('admin.ai.skill.placeholder.inputTimeout'),
      }),
      help: $t('admin.ai.skill.help.timeout'),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => values.type !== 'builtin',
      },
    },
    switchField('is_active', $t('admin.ai.skill.isActive'), {
      defaultValue: true,
    }),
  ];
}

export function buildSkillFormToolkitSchema(state: SkillFormSharedState) {
  return [
    {
      component: 'Divider',
      fieldName: '_toolkit_divider',
      label: '',
      hideLabel: true,
      componentProps: { orientation: 'left', dashed: true },
      renderComponentContent: () => ({
        default: () => $t('admin.ai.skill.toolkitEditor.title'),
      }),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isToolkit(values, state),
      },
    },
    {
      component: 'ToolkitEditor',
      fieldName: 'toolkit_content',
      label: $t('admin.ai.skill.toolkitEditor.sourceCode'),
      componentProps: {
        parseApi: parseToolkitApi,
        localePrefix: 'admin.ai.skill',
        onParseComplete: (schema: null | Record<string, unknown>) => {
          state.currentValvesSchema.value = schema;
        },
      },
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isToolkit(values, state),
      },
    },
    {
      component: 'ValvesConfigForm',
      fieldName: 'valves_config',
      label: $t('admin.ai.skill.toolkitEditor.valves'),
      componentProps: () => ({
        schema: state.currentValvesSchema.value,
        localePrefix: 'admin.ai.skill',
      }),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isToolkit(values, state),
      },
    },
  ];
}
