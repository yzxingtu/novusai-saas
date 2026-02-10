/**
 * 租户端智能体管理 - 表格列、搜索配置、表单 Schema
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
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

// ============ 状态辅助 ============

/**
 * 获取智能体状态下拉选项
 */
export function getStatusOptions() {
  return [
    { label: $t('tenant.ai.agent.status_options.draft'), value: 'draft' },
    { label: $t('tenant.ai.agent.status_options.published'), value: 'published' },
    { label: $t('tenant.ai.agent.status_options.disabled'), value: 'disabled' },
  ];
}

/**
 * 获取状态文本
 */
export function getStatusText(status: string | undefined): string {
  if (!status) return '-';
  switch (status) {
    case 'draft': return $t('tenant.ai.agent.status_options.draft');
    case 'published': return $t('tenant.ai.agent.status_options.published');
    case 'disabled': return $t('tenant.ai.agent.status_options.disabled');
    default: return status;
  }
}

/**
 * 获取状态颜色
 */
export function getStatusColor(status: string | undefined): string {
  switch (status) {
    case 'draft': return 'default';
    case 'published': return 'success';
    case 'disabled': return 'error';
    default: return 'default';
  }
}

// ============ 可见性辅助 ============

/**
 * 获取可见性下拉选项
 */
export function getVisibilityOptions() {
  return [
    { label: $t('tenant.ai.agent.access.visibility_options.public'), value: 'public' },
    { label: $t('tenant.ai.agent.access.visibility_options.private'), value: 'private' },
  ];
}

/**
 * 获取可见性文本
 */
export function getVisibilityText(visibility: string | undefined): string {
  if (!visibility) return '-';
  switch (visibility) {
    case 'public': return $t('tenant.ai.agent.access.visibility_options.public');
    case 'private': return $t('tenant.ai.agent.access.visibility_options.private');
    default: return visibility;
  }
}

/**
 * 获取可见性颜色
 */
export function getVisibilityColor(visibility: string | undefined): string {
  switch (visibility) {
    case 'public': return 'green';
    case 'private': return 'orange';
    default: return 'default';
  }
}

// ============ 执行模式辅助 ============

/**
 * 获取执行模式下拉选项
 */
export function getExecutionModeOptions() {
  return [
    { label: $t('tenant.ai.agent.mode_options.conversation'), value: 'conversation' },
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
    case 'conversation': return $t('tenant.ai.agent.mode_options.conversation');
    case 'task': return $t('tenant.ai.agent.mode_options.task');
    case 'batch': return $t('tenant.ai.agent.mode_options.batch');
    case 'api': return $t('tenant.ai.agent.mode_options.api');
    default: return mode;
  }
}

/**
 * 获取执行模式颜色
 */
export function getExecutionModeColor(mode: string | undefined): string {
  switch (mode) {
    case 'conversation': return 'blue';
    case 'task': return 'orange';
    case 'batch': return 'purple';
    case 'api': return 'cyan';
    default: return 'default';
  }
}

// ============ 模型下拉 ============

/**
 * 获取模型下拉选项
 */
export async function getModelSelectOptions() {
  try {
    const models = await getTenantAIModelsApi();
    return models.map((m) => ({
      label: `${m.name} (${m.provider_name || '-'})`,
      value: m.id,
    }));
  } catch {
    return [];
  }
}

// ============ 表格列 ============

/**
 * 表格列定义
 */
export function useColumns<T = AgentListItem>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'name',
      title: $t('tenant.ai.agent.name'),
      minWidth: 180,
      slots: { default: 'name_cell' },
    },
    {
      field: 'status',
      title: $t('tenant.ai.agent.status'),
      width: 110,
      align: 'center',
      slots: { default: 'status_cell' },
    },
    {
      field: 'execution_mode',
      title: $t('tenant.ai.agent.executionMode'),
      width: 120,
      align: 'center',
      slots: { default: 'mode_cell' },
    },
    {
      field: 'model_name',
      title: $t('tenant.ai.agent.modelName'),
      width: 180,
      slots: { default: 'model_cell' },
    },
    {
      field: 'visibility',
      title: $t('tenant.ai.agent.access.visibility'),
      width: 100,
      align: 'center',
      slots: { default: 'visibility_cell' },
    },
    {
      field: 'description',
      title: $t('tenant.ai.agent.description'),
      minWidth: 200,
      slots: { default: 'description_cell' },
    },
    {
      field: 'created_at',
      title: $t('tenant.ai.agent.createdAt'),
      width: 170,
      sortable: true,
      slots: { default: 'createdAt_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'agent',
          nameField: 'name',
          nameTitle: $t('tenant.ai.agent.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'access',
            text: $t('tenant.ai.agent.access.title'),
            icon: 'lucide:shield',
            accessCodes: ['agent:update'],
          },
          {
            code: 'test',
            text: $t('tenant.ai.agent.test.title'),
            icon: 'lucide:play',
            accessCodes: ['agent:list'],
          },
          {
            code: 'publish',
            text: $t('tenant.ai.agent.publish'),
            icon: 'lucide:rocket',
            accessCodes: ['agent:update'],
          },
          {
            code: 'versions',
            text: $t('tenant.ai.agent.version.title'),
            icon: 'lucide:history',
            accessCodes: ['agent:list'],
          },
          'edit',
          'delete',
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('tenant.common.operation'),
      width: 300,
    },
  ];
}

// ============ 搜索表单 ============

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
  ];
}

// ============ 编辑表单 ============

/**
 * 智能体表单 Schema
 */
export function useFormSchema(): VbenFormSchema[] {
  return [
    inputField('name', $t('tenant.ai.agent.name'), {
      required: true,
      placeholder: $t('tenant.ai.agent.placeholder.inputName'),
    }),
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
    numberField('temperature', $t('tenant.ai.agent.temperature'), {
      min: 0,
      max: 2,
      placeholder: $t('tenant.ai.agent.placeholder.inputTemperature'),
    }),
    numberField('max_tokens', $t('tenant.ai.agent.maxTokens'), {
      min: 1,
      placeholder: $t('tenant.ai.agent.placeholder.inputMaxTokens'),
    }),
    numberField('top_p', $t('tenant.ai.agent.topP'), {
      min: 0,
      max: 1,
      placeholder: $t('tenant.ai.agent.placeholder.inputTopP'),
    }),
    textareaField('welcome_message', $t('tenant.ai.agent.welcomeMessage'), {
      placeholder: $t('tenant.ai.agent.placeholder.inputWelcomeMessage'),
    }),
    {
      ...textareaField('suggested_questions_str', $t('tenant.ai.agent.suggestedQuestions'), {
        placeholder: $t('tenant.ai.agent.placeholder.inputSuggestedQuestions'),
        rows: 4,
      }),
      help: $t('tenant.ai.agent.help.suggestedQuestions'),
    },
    {
      ...textareaField('tool_bindings_str', $t('tenant.ai.agent.toolBindings'), {
        placeholder: $t('tenant.ai.agent.placeholder.inputToolBindings'),
        rows: 4,
      }),
      help: $t('tenant.ai.agent.help.toolBindings'),
    },
    // ============ 输入变量 ============
    {
      component: 'Divider',
      fieldName: '_input_variables_divider',
      label: '',
      componentProps: {
        children: $t('tenant.ai.agent.inputVariables.title'),
        orientation: 'left',
        dashed: true,
      },
    },
    {
      ...textareaField('input_variables_str', $t('tenant.ai.agent.inputVariables.label'), {
        placeholder: $t('tenant.ai.agent.inputVariables.placeholder'),
        rows: 5,
      }),
      help: $t('tenant.ai.agent.help.inputVariables'),
    },
    // ============ 上下文窗口 ============
    {
      component: 'Divider',
      fieldName: '_context_divider',
      label: '',
      componentProps: {
        children: $t('tenant.ai.agent.contextConfig.title'),
        orientation: 'left',
        dashed: true,
      },
    },
    numberField('context_max_history_messages', $t('tenant.ai.agent.contextConfig.maxHistoryMessages'), {
      min: 0,
      placeholder: $t('tenant.ai.agent.contextConfig.placeholder.maxHistoryMessages'),
    }),
    numberField('context_max_history_tokens', $t('tenant.ai.agent.contextConfig.maxHistoryTokens'), {
      min: 0,
      placeholder: $t('tenant.ai.agent.contextConfig.placeholder.maxHistoryTokens'),
    }),
    // ============ 配额设置 ============
    {
      component: 'Divider',
      fieldName: '_quota_divider',
      label: '',
      componentProps: {
        children: $t('tenant.ai.agent.quotaConfig.title'),
        orientation: 'left',
        dashed: true,
      },
    },
    numberField('quota_conversations_per_day', $t('tenant.ai.agent.quotaConfig.conversationsPerDay'), {
      min: 0,
      placeholder: $t('tenant.ai.agent.quotaConfig.placeholder.conversationsPerDay'),
    }),
    numberField('quota_tokens_per_day', $t('tenant.ai.agent.quotaConfig.tokensPerDay'), {
      min: 0,
      placeholder: $t('tenant.ai.agent.quotaConfig.placeholder.tokensPerDay'),
    }),
    numberField('quota_tokens_per_month', $t('tenant.ai.agent.quotaConfig.tokensPerMonth'), {
      min: 0,
      placeholder: $t('tenant.ai.agent.quotaConfig.placeholder.tokensPerMonth'),
    }),
    numberField('quota_max_turns', $t('tenant.ai.agent.quotaConfig.maxTurnsPerConversation'), {
      min: 0,
      placeholder: $t('tenant.ai.agent.quotaConfig.placeholder.maxTurnsPerConversation'),
    }),
    numberField('quota_max_concurrent', $t('tenant.ai.agent.quotaConfig.maxConcurrent'), {
      min: 0,
      placeholder: $t('tenant.ai.agent.quotaConfig.placeholder.maxConcurrent'),
    }),
    numberField('quota_user_conversations_per_day', $t('tenant.ai.agent.quotaConfig.userConversationsPerDay'), {
      min: 0,
      placeholder: $t('tenant.ai.agent.quotaConfig.placeholder.userConversationsPerDay'),
    }),
  ];
}

/**
 * 智能体表单默认值
 */
export function getFormDefaults(): Record<string, unknown> {
  return {
    execution_mode: 'conversation',
    temperature: 0.7,
    suggested_questions_str: '[]',
    tool_bindings_str: '[]',
    input_variables_str: '[]',
    context_max_history_messages: 20,
    context_max_history_tokens: 0,
    quota_conversations_per_day: 0,
    quota_tokens_per_day: 0,
    quota_tokens_per_month: 0,
    quota_max_turns: 50,
    quota_max_concurrent: 10,
    quota_user_conversations_per_day: 0,
  };
}
