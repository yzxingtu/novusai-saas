/**
 * 智能体管理（平台端） - 辅助函数、表单 Schema
 */
import type { VbenFormSchema } from '#/adapter/form';

import { inputField, numberField, select, textareaField } from '#/adapter/form';
import { getAIModelSelectApi } from '#/api/admin/ai';
import { getSkillListApi } from '#/api/admin/skills';
import { getSkillPackageSelectApi } from '#/api/admin/skill-packages';
import { useScopeFields } from '#/components/business/scope-select/use-scope-fields';
import { $t } from '#/locales';

// ============ 类型辅助（系统/自定义）============

export function getTypeOptions() {
  return [
    { label: $t('admin.ai.agent.type_options.system'), value: 'true' },
    { label: $t('admin.ai.agent.type_options.custom'), value: 'false' },
  ];
}

function getExecutionModeOptions() {
  return [
    {
      label: $t('admin.ai.agent.mode_options.conversation'),
      value: 'conversation',
    },
    { label: $t('admin.ai.agent.mode_options.task'), value: 'task' },
    { label: $t('admin.ai.agent.mode_options.batch'), value: 'batch' },
    { label: $t('admin.ai.agent.mode_options.api'), value: 'api' },
  ];
}

// ============ Chat 模型下拉 ============

export function getChatModelSelectApi(params?: Record<string, unknown>) {
  return getAIModelSelectApi({ ...params, type: 'chat' });
}

// ============ 表单默认值 ============

export function getAudienceOptions() {
  return [
    { label: $t('admin.ai.agent.audience_options.all'), value: 'all' },
    {
      label: $t('admin.ai.agent.audience_options.admin_only'),
      value: 'admin_only',
    },
    {
      label: $t('admin.ai.agent.audience_options.admin_tenant'),
      value: 'admin_tenant',
    },
  ];
}

export function getAudienceText(audience: string | undefined): string {
  if (!audience) return '-';
  const opt = getAudienceOptions().find((o) => o.value === audience);
  return opt?.label ?? audience;
}

export function getAudienceColor(audience: string | undefined): string {
  switch (audience) {
    case 'admin_only': {
      return 'orange';
    }
    case 'admin_tenant': {
      return 'blue';
    }
    case 'all': {
      return 'green';
    }
    default: {
      return 'default';
    }
  }
}

export function getOwnerTypeOptions() {
  return [
    { label: $t('admin.ai.agent.ownerType.platform'), value: 'platform' },
    { label: $t('admin.ai.agent.ownerType.tenant'), value: 'tenant' },
  ];
}

export function getOwnerTypeText(ownerType: string | undefined): string {
  if (!ownerType) return '-';
  const opt = getOwnerTypeOptions().find((o) => o.value === ownerType);
  return opt?.label ?? ownerType;
}

export function getOwnerTypeColor(ownerType: string | undefined): string {
  switch (ownerType) {
    case 'platform': {
      return 'purple';
    }
    case 'tenant': {
      return 'cyan';
    }
    default: {
      return 'default';
    }
  }
}

export interface AgentScopeFieldsOptions {
  scopeDisabled?: ((values: Record<string, unknown>) => boolean) | boolean;
}

/** 管理端智能体：统一资源作用域 + 分配企业 */
export function useAgentScopeFields(
  options: AgentScopeFieldsOptions = {},
): VbenFormSchema[] {
  const { scopeDisabled = false } = options;
  return useScopeFields({
    scopeDisabled,
    allowedScopes: [
      'global_shared',
      'admin_only',
      'all_tenants',
      'admin_and_selected_tenants',
      'selected_tenants',
    ],
  });
}

export function getFormDefaults() {
  return {
    name: '',
    description: '',
    scope: 'global_shared',
    tenant_id: null,
    tenant_ids: [],
    model_id: undefined,
    execution_mode: 'conversation',
    system_prompt: '',
    temperature: 0.7,
    max_tokens: 4096,
    welcome_message: '',
    suggested_questions: '',
    skill_ids: [],
  };
}

/**
 * 获取技能下拉选项（admin 端所有技能）
 */
interface PkgSelectItem {
  label: string;
  value: number;
  extra?: null | {
    is_system?: boolean;
    source_plugin?: string;
    bind_mode?: string;
  };
}

interface SkillListItem {
  id: number;
  package_id: number;
  name: string;
  type: string;
  is_system: boolean;
  is_active: boolean;
}

export interface SkillOption {
  label: string;
  value: number;
  packageName?: string;
  isSystem?: boolean;
  skillType?: string;
}

export async function getSkillSelectOptions(): Promise<SkillOption[]> {
  try {
    const [skillResp, pkgResp] = await Promise.all([
      getSkillListApi({ 'page[size]': 500 }),
      getSkillPackageSelectApi({ include_system: true }),
    ]);
    const packages = pkgResp as PkgSelectItem[];
    const packageNameMap = new Map(
      packages.map((pkg) => [pkg.value, pkg.label]),
    );

    return (skillResp.items as SkillListItem[])
      .filter((skill) => skill.is_active)
      .map((skill) => ({
        label: packageNameMap.get(skill.package_id)
          ? `${skill.name} · ${packageNameMap.get(skill.package_id)}`
          : skill.name,
        value: skill.id,
        packageName: packageNameMap.get(skill.package_id),
        isSystem: skill.is_system,
        skillType: skill.type,
      }));
  } catch {
    return [];
  }
}

/**
 * 获取状态文本
 */
export function getStatusText(status: string | undefined): string {
  if (!status) return '-';
  switch (status) {
    case 'disabled': {
      return $t('admin.ai.agent.status_options.disabled');
    }
    case 'draft': {
      return $t('admin.ai.agent.status_options.draft');
    }
    case 'published': {
      return $t('admin.ai.agent.status_options.published');
    }
    default: {
      return status;
    }
  }
}

/**
 * 获取执行模式文本
 */
export function getExecutionModeText(mode: string | undefined): string {
  if (!mode) return '-';
  switch (mode) {
    case 'api': {
      return $t('admin.ai.agent.mode_options.api');
    }
    case 'batch': {
      return $t('admin.ai.agent.mode_options.batch');
    }
    case 'conversation': {
      return $t('admin.ai.agent.mode_options.conversation');
    }
    case 'task': {
      return $t('admin.ai.agent.mode_options.task');
    }
    default: {
      return mode;
    }
  }
}

// ============ 编辑表单 ============

/**
 * 编辑表单 Schema
 * @param _isEdit 是否编辑模式
 * @param isSystem 是否系统智能体（锁定核心字段）
 */
export function useFormSchema(
  _isEdit = false,
  isSystem = false,
  isCreate = false,
  resolveModelMaxOutputTokens?: (
    modelId: null | number | undefined,
  ) => number | undefined,
): VbenFormSchema[] {
  const locked = isSystem
    ? { disabled: true, help: $t('admin.ai.agent.systemFieldLocked') }
    : {};

  return [
    inputField('name', $t('admin.ai.agent.name'), {
      required: true,
      ...locked,
    }),
    ...(!isCreate ? [{
      component: 'ImageUpload' as const,
      fieldName: 'avatar',
      label: $t('admin.ai.agent.avatar'),
    }] : []),
    textareaField('description', $t('admin.ai.agent.description'), {
      rows: 2,
    }),
    ...useAgentScopeFields({
      scopeDisabled: isSystem ? () => true : false,
    }),
    {
      ...select('model_id', $t('admin.ai.agent.modelName'), {
        api: getChatModelSelectApi,
        required: true,
      }),
    },
    {
      ...select('execution_mode', $t('admin.ai.agent.executionMode'), {
        options: getExecutionModeOptions(),
        required: true,
        ...locked,
      }),
    },
    textareaField('system_prompt', $t('admin.ai.agent.systemPrompt'), {
      rows: 5,
    }),
    ...(isCreate ? [] : [
      {
        ...numberField('temperature', $t('admin.ai.agent.temperature'), {
          min: 0,
          max: 2,
          precision: 1,
          placeholder: $t('admin.ai.agent.placeholder.inputTemperature'),
        }),
        help: $t('admin.ai.agent.help.temperature'),
      },
      {
        ...numberField('max_tokens', $t('admin.ai.agent.maxTokens'), {
          min: 1,
          placeholder: $t('admin.ai.agent.placeholder.inputMaxTokens'),
        }),
        componentProps: (values: Record<string, unknown>) => ({
          style: { width: '100%' },
          min: 1,
          max:
            resolveModelMaxOutputTokens?.(
              values.model_id as null | number | undefined,
            ) ?? 128_000,
          placeholder: $t('admin.ai.agent.placeholder.inputMaxTokens'),
        }),
        help: $t('admin.ai.agent.help.maxTokens'),
      },
      {
        ...numberField('top_p', $t('admin.ai.agent.topP'), {
          min: 0,
          max: 1,
          placeholder: $t('admin.ai.agent.placeholder.inputTopP'),
        }),
        help: $t('admin.ai.agent.help.topP'),
      },
      {
        ...textareaField('welcome_message', $t('admin.ai.agent.welcomeMessage'), {
          rows: 3,
          placeholder: $t('admin.ai.agent.placeholder.inputWelcomeMessage'),
        }),
        help: $t('admin.ai.agent.help.welcomeMessage'),
      },
      {
        ...textareaField(
          'suggested_questions',
          $t('admin.ai.agent.suggestedQuestions'),
          {
            rows: 4,
            placeholder: $t('admin.ai.agent.placeholder.inputSuggestedQuestions'),
          },
        ),
        help: $t('admin.ai.agent.help.suggestedQuestions'),
      },
    ]),
  ];
}
