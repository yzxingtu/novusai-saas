/**
 * 企业端智能体管理 - 表格列、搜索配置、表单 Schema
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { AgentListItem } from '#/api/tenant/agents';

import {
  inputField,
  numberField,
  searchInput,
  select,
  textareaField,
} from '#/adapter/form';
import { getTenantAIModelsApi } from '#/api/tenant/ai';
import { $t } from '#/locales';
import { getScopeOptions } from '#/utils/scope-helpers';

/** 列表/筛选：统一资源作用域选项 */
function getAgentScopeFilterOptions() {
  return getScopeOptions();
}

/** 企业自有智能体可编辑/删除 */
export function isTenantOwnedAgent(row: AgentListItem): boolean {
  return row.owner_type === 'tenant';
}

// ============ 状态辅助 / status helpers ============

/**
 * 获取智能体状态下拉选项
 */
export function getStatusOptions() {
  return [
    { label: $t('tenant.ai.agent.status_options.draft'), value: 'draft' },
    {
      label: $t('tenant.ai.agent.status_options.published'),
      value: 'published',
    },
    { label: $t('tenant.ai.agent.status_options.disabled'), value: 'disabled' },
  ];
}

/**
 * 获取状态文本
 */
export function getStatusText(status: string | undefined): string {
  if (!status) return '-';
  switch (status) {
    case 'disabled': {
      return $t('tenant.ai.agent.status_options.disabled');
    }
    case 'draft': {
      return $t('tenant.ai.agent.status_options.draft');
    }
    case 'published': {
      return $t('tenant.ai.agent.status_options.published');
    }
    default: {
      return status;
    }
  }
}

/**
 * 获取状态颜色
 */
export function getStatusColor(status: string | undefined): string {
  switch (status) {
    case 'disabled': {
      return 'error';
    }
    case 'draft': {
      return 'default';
    }
    case 'published': {
      return 'success';
    }
    default: {
      return 'default';
    }
  }
}

// ============ 执行模式辅助 / execution mode helpers ============

/**
 * 获取执行模式下拉选项
 */
export function getExecutionModeOptions() {
  return [
    {
      label: $t('tenant.ai.agent.mode_options.conversation'),
      value: 'conversation',
    },
    { label: $t('tenant.ai.agent.mode_options.task'), value: 'task' },
    { label: $t('tenant.ai.agent.mode_options.batch'), value: 'batch' },
    { label: $t('tenant.ai.agent.mode_options.api'), value: 'api' },
  ];
}

/**
 * 获取执行模式文本
 */
export function getExecutionModeText(mode: string | undefined): string {
  if (!mode) return '-';
  switch (mode) {
    case 'api': {
      return $t('tenant.ai.agent.mode_options.api');
    }
    case 'batch': {
      return $t('tenant.ai.agent.mode_options.batch');
    }
    case 'conversation': {
      return $t('tenant.ai.agent.mode_options.conversation');
    }
    case 'task': {
      return $t('tenant.ai.agent.mode_options.task');
    }
    default: {
      return mode;
    }
  }
}

// ============ 模型下拉 / model select ============

/**
 * 获取模型下拉选项
 */
export async function getModelSelectOptions() {
  try {
    const models = await getTenantAIModelsApi();
    return models
      .filter((model) => model.type === 'chat' && model.is_active)
      .map((m) => ({
        label: `${m.name} (${m.provider_name || '-'})`,
        value: m.id,
      }));
  } catch {
    return [];
  }
}

// ============ 搜索表单 / search form ============

/**
 * 搜索表单 Schema
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('name', $t('tenant.ai.agent.name'), {
      placeholder: $t('tenant.ai.agent.placeholder.searchName'),
    }),
    select('filter[status][eq]', $t('tenant.ai.agent.status'), {
      options: getStatusOptions(),
      placeholder: $t('tenant.ai.agent.placeholder.allStatuses'),
    }),
    select('filter[execution_mode][eq]', $t('tenant.ai.agent.executionMode'), {
      options: getExecutionModeOptions(),
      placeholder: $t('tenant.ai.agent.placeholder.allModes'),
    }),
    select('filter[scope][eq]', $t('common.scope.label'), {
      options: getAgentScopeFilterOptions(),
      placeholder: $t('common.scope.allScopes'),
    }),
  ];
}

// ============ 编辑表单 / edit form ============

export function useFormSchema(
  isCreate = false,
  resolveModelMaxOutputTokens?: (
    modelId: null | number | undefined,
  ) => number | undefined,
): VbenFormSchema[] {
  return [
    inputField('name', $t('tenant.ai.agent.name'), {
      required: true,
      placeholder: $t('tenant.ai.agent.placeholder.inputName'),
    }),
    ...(isCreate
      ? []
      : [
          {
            component: 'ImageUpload' as const,
            fieldName: 'avatar',
            label: $t('tenant.ai.agent.avatar'),
          },
        ]),
    select('model_id', $t('tenant.ai.agent.modelName'), {
      api: getModelSelectOptions,
      required: true,
      placeholder: $t('tenant.ai.agent.placeholder.selectModel'),
    }),
    select('execution_mode', $t('tenant.ai.agent.executionMode'), {
      options: getExecutionModeOptions(),
      required: true,
      placeholder: $t('tenant.ai.agent.placeholder.selectMode'),
    }),
    textareaField('system_prompt', $t('tenant.ai.agent.systemPrompt'), {
      required: true,
      placeholder: $t('tenant.ai.agent.placeholder.inputSystemPrompt'),
      rows: 6,
    }),
    textareaField('description', $t('tenant.ai.agent.description'), {
      placeholder: $t('tenant.ai.agent.placeholder.inputDescription'),
    }),
    ...(isCreate
      ? []
      : [
          {
            ...numberField('temperature', $t('tenant.ai.agent.temperature'), {
              min: 0,
              max: 2,
              placeholder: $t('tenant.ai.agent.placeholder.inputTemperature'),
            }),
            help: $t('tenant.ai.agent.help.temperature'),
          },
          {
            ...numberField('max_tokens', $t('tenant.ai.agent.maxTokens'), {
              min: 1,
              placeholder: $t('tenant.ai.agent.placeholder.inputMaxTokens'),
            }),
            componentProps: (values: Record<string, unknown>) => ({
              style: { width: '100%' },
              min: 1,
              max:
                resolveModelMaxOutputTokens?.(
                  values.model_id as null | number | undefined,
                ) ?? 128_000,
              placeholder: $t('tenant.ai.agent.placeholder.inputMaxTokens'),
            }),
            help: $t('tenant.ai.agent.help.maxTokens'),
          },
          {
            ...numberField('top_p', $t('tenant.ai.agent.topP'), {
              min: 0,
              max: 1,
              placeholder: $t('tenant.ai.agent.placeholder.inputTopP'),
            }),
            help: $t('tenant.ai.agent.help.topP'),
          },
          {
            ...textareaField(
              'welcome_message',
              $t('tenant.ai.agent.welcomeMessage'),
              {
                placeholder: $t(
                  'tenant.ai.agent.placeholder.inputWelcomeMessage',
                ),
              },
            ),
            help: $t('tenant.ai.agent.help.welcomeMessage'),
          },
          {
            ...textareaField(
              'suggested_questions_str',
              $t('tenant.ai.agent.suggestedQuestions'),
              {
                placeholder: $t(
                  'tenant.ai.agent.placeholder.inputSuggestedQuestions',
                ),
                rows: 4,
              },
            ),
            help: $t('tenant.ai.agent.help.suggestedQuestions'),
          },
        ]),
  ];
}

// ============ 向导模式 / wizard mode ============

/**
 * 向导步骤定义
 */
export function getWizardSteps() {
  return [
    {
      title: $t('tenant.ai.agent.wizard.step1'),
      description: $t('tenant.ai.agent.wizard.step1Desc'),
    },
    {
      title: $t('tenant.ai.agent.wizard.step2'),
      description: $t('tenant.ai.agent.wizard.step2Desc'),
    },
  ];
}

/**
 * 字段 → 步骤映射
 */
const FIELD_STEP_MAP: Record<string, number> = {
  name: 0,
  avatar: 0,
  model_id: 0,
  execution_mode: 0,
  system_prompt: 0,
  description: 0,
  temperature: 1,
  max_tokens: 1,
  top_p: 1,
  welcome_message: 1,
  suggested_questions_str: 1,
};

/**
 * 向导模式某步骤的表单 Schema — 直接返回该步骤对应的字段，无需 triggerFields 机制
 */
export function getWizardStepSchema(
  step: number,
  resolveModelMaxOutputTokens?: (
    modelId: null | number | undefined,
  ) => number | undefined,
): VbenFormSchema[] {
  return useFormSchema(false, resolveModelMaxOutputTokens).filter(
    (field) => (FIELD_STEP_MAP[field.fieldName] ?? 0) === step,
  );
}

/**
 * 智能体表单默认值
 */
export function getFormDefaults(): Record<string, unknown> {
  return {
    execution_mode: 'conversation',
    temperature: 0.7,
    suggested_questions_str: '',
    skill_ids: [],
  };
}
