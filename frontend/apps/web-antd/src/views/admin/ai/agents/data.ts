/**
 * 智能体管理（平台端） - 辅助函数、表单 Schema
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { AIModelInfo } from '#/api/admin/ai';

import { inputField, numberField, select, textareaField } from '#/adapter/form';
import { getAIModelListApi } from '#/api/admin/ai';
import { getSkillPackageSelectApi } from '#/api/admin/skill-packages';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { $t } from '#/locales';

// ============ 类型辅助（系统/自定义）============

export function getTypeOptions() {
  return [
    { label: $t('admin.ai.agent.type_options.system'), value: 'true' },
    { label: $t('admin.ai.agent.type_options.custom'), value: 'false' },
  ];
}

// ============ Scope 辅助 ============

export function getScopeOptions() {
  return [
    { label: $t('admin.ai.agent.scope.tenant'), value: 'tenant' },
    { label: $t('admin.ai.agent.scope.global'), value: 'global' },
    { label: $t('admin.ai.agent.scope.admin'), value: 'admin' },
  ];
}

export function getScopeColor(scope: string | undefined): string {
  switch (scope) {
    case 'global': return 'blue';
    case 'admin': return 'purple';
    case 'tenant': return 'green';
    default: return 'default';
  }
}

function getExecutionModeOptions() {
  return [
    { label: $t('admin.ai.agent.mode_options.conversation'), value: 'conversation' },
    { label: $t('admin.ai.agent.mode_options.task'), value: 'task' },
    { label: $t('admin.ai.agent.mode_options.batch'), value: 'batch' },
    { label: $t('admin.ai.agent.mode_options.api'), value: 'api' },
  ];
}

// ============ Chat 模型下拉 ============

export async function getChatModelOptions() {
  try {
    const res = await getAIModelListApi({ 'page[size]': 100 });
    return (res.items || [])
      .filter((m: AIModelInfo) => {
        const name = (m.name || '').toLowerCase();
        return !name.includes('embed');
      })
      .map((m: AIModelInfo) => ({
        label: `${m.name} (${m.provider_name || '-'})`,
        value: m.id,
      }));
  } catch {
    return [];
  }
}

// ============ 表单默认值 ============

export function getFormDefaults() {
  return {
    name: '',
    description: '',
    scope: 'global',
    tenant_id: null,
    model_id: undefined,
    execution_mode: 'conversation',
    system_prompt: '',
    temperature: 0.7,
    max_tokens: 4096,
    welcome_message: '',
    suggested_questions: '',
    package_ids: [],
  };
}

/**
 * 获取技能包下拉选项（admin 端所有技能包）
 */
interface PkgSelectItem {
  label: string;
  value: number;
  extra?: {
    scope?: string;
    is_system?: boolean;
    source_plugin?: string;
  } | null;
}

export interface PkgOption {
  label: string;
  value: number;
  scope?: string;
  sourcePlugin?: string;
}

export async function getPackageSelectOptions(): Promise<PkgOption[]> {
  try {
    const resp = await getSkillPackageSelectApi() as unknown as
      | { items: PkgSelectItem[] }
      | PkgSelectItem[];
    const items: PkgSelectItem[] = Array.isArray(resp) ? resp : (resp?.items ?? []);
    return items.map((p) => ({
      label: p.label,
      value: p.value,
      scope: p.extra?.scope,
      sourcePlugin: p.extra?.source_plugin,
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
    case 'draft': {
      return $t('admin.ai.agent.status_options.draft');
    }
    case 'published': {
      return $t('admin.ai.agent.status_options.published');
    }
    case 'disabled': {
      return $t('admin.ai.agent.status_options.disabled');
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
    case 'conversation': {
      return $t('admin.ai.agent.mode_options.conversation');
    }
    case 'task': {
      return $t('admin.ai.agent.mode_options.task');
    }
    case 'batch': {
      return $t('admin.ai.agent.mode_options.batch');
    }
    case 'api': {
      return $t('admin.ai.agent.mode_options.api');
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
export function useFormSchema(_isEdit = false, isSystem = false): VbenFormSchema[] {
  const locked = isSystem
    ? { disabled: true, help: $t('admin.ai.agent.systemFieldLocked') }
    : {};

  return [
    inputField('name', $t('admin.ai.agent.name'), {
      required: true,
      ...locked,
    }),
    {
      component: 'ImageUpload',
      fieldName: 'avatar',
      label: $t('admin.ai.agent.avatar'),
    },
    textareaField('description', $t('admin.ai.agent.description'), {
      rows: 2,
    }),
    {
      ...select('scope', $t('admin.ai.agent.scopeLabel'), {
        options: getScopeOptions(),
        required: true,
        ...locked,
      }),
    },
    {
      ...select('tenant_id', $t('admin.ai.agent.tenantId'), {
        api: getTenantSelectApi,
        params: { is_active: 'true' },
        placeholder: $t('admin.ai.agent.placeholder.tenantId'),
      }),
      ...(isSystem ? { help: $t('admin.ai.agent.systemFieldLocked') } : {}),
      dependencies: {
        show(values: Record<string, unknown>) {
          return values.scope === 'tenant';
        },
        triggerFields: ['scope'],
      },
    },
    {
      ...select('model_id', $t('admin.ai.agent.modelName'), {
        api: getChatModelOptions,
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
    numberField('temperature', $t('admin.ai.agent.temperature'), {
      min: 0,
      max: 2,
      precision: 1,
    }),
    numberField('max_tokens', $t('admin.ai.agent.maxTokens'), {
      min: 1,
      max: 128000,
    }),
    {
      ...numberField('top_p', $t('admin.ai.agent.topP'), {
        min: 0,
        max: 1,
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
      ...textareaField('suggested_questions', $t('admin.ai.agent.suggestedQuestions'), {
        rows: 3,
        placeholder: $t('admin.ai.agent.placeholder.inputSuggestedQuestions'),
      }),
      help: $t('admin.ai.agent.help.suggestedQuestions'),
    },
  ];
}
