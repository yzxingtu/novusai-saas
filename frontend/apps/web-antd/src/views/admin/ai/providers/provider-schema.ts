import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { AIProviderInfo } from '#/api/admin/ai';

import {
  inputField,
  searchInput,
  select,
  switchField,
  textareaField,
  z,
} from '#/adapter/form';
import { dragColumn } from '#/adapter/vxe-table';
import { $t } from '#/locales';

import {
  getDefaultProviderType,
  getProviderTypeOptions,
  hasMultipleAdapterTypeOptions,
} from './provider-adapter-types';
import { getProviderWireApiOptions } from './provider-connection';
import {
  getProviderWebSearchPublicProviderOptions,
  getProviderWebSearchStrategyOptions,
  WEB_SEARCH_DEFAULTS,
} from './provider-web-search';

function isValidProviderBaseUrl(value: string): boolean {
  const trimmedValue = value.trim();
  if (!trimmedValue) return true;

  try {
    const url = new URL(trimmedValue);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

function resolveSchemaProviderType(values: Record<string, unknown>): string {
  return typeof values.type === 'string' && values.type.trim()
    ? values.type
    : getDefaultProviderType();
}

/**
 * 表格列定义
 */
export function useColumns<T = AIProviderInfo>(
  onActionClick: OnActionClickFn<T>,
  _onToggleStatus?: unknown,
  options?: {
    showProviderTypeColumn?: boolean;
  },
): VxeTableGridOptions['columns'] {
  const showProviderTypeColumn =
    options?.showProviderTypeColumn ?? hasMultipleAdapterTypeOptions();

  return [
    dragColumn,
    {
      field: 'name',
      title: $t('admin.ai.provider.name'),
      minWidth: 280,
      slots: { default: 'name_cell' },
    },
    ...(showProviderTypeColumn
      ? [
          {
            field: 'type',
            title: $t('admin.ai.provider.type'),
            width: 160,
            align: 'center' as const,
            slots: { default: 'type_cell' },
          },
          {
            field: 'wire_api',
            title: $t('admin.ai.provider.wireApi'),
            width: 180,
            align: 'center' as const,
            slots: { default: 'wireApi_cell' },
          },
        ]
      : [
          {
            field: 'connection_mode',
            title: $t('admin.ai.provider.connectionMode'),
            minWidth: 220,
            align: 'center' as const,
            slots: { default: 'connection_cell' },
          },
        ]),
    {
      field: 'web_search',
      title: $t('admin.ai.provider.webSearch.title'),
      minWidth: 260,
      slots: { default: 'webSearch_cell' },
    },
    {
      field: 'model_count',
      title: $t('admin.ai.provider.modelCount'),
      width: 100,
      align: 'center' as const,
      slots: { default: 'modelCount_cell' },
    },
    {
      field: 'is_active',
      title: $t('admin.ai.provider.isActive'),
      width: 130,
      align: 'center' as const,
      slots: { default: 'isActive_cell' },
    },
    {
      align: 'center' as const,
      cellRender: {
        attrs: {
          resource: 'ai_provider',
          nameField: 'name',
          nameTitle: $t('admin.ai.provider.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: ['edit', 'delete'],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('admin.common.operation'),
      width: 160,
    },
  ];
}

/**
 * 搜索表单 Schema
 */
export function useGridFormSchema(): VbenFormSchema[] {
  const schema: VbenFormSchema[] = [
    searchInput('name', $t('admin.ai.provider.name'), {
      placeholder: $t('admin.ai.provider.placeholder.searchName'),
    }),
  ];
  if (hasMultipleAdapterTypeOptions()) {
    schema.push(
      select('filter[type][eq]', $t('admin.ai.provider.type'), {
        options: getProviderTypeOptions(),
        placeholder: $t('admin.ai.provider.type'),
      }),
    );
  }
  return schema;
}

/**
 * 表单 Schema
 */
export function useFormSchema(isEdit = false): VbenFormSchema[] {
  const schema: VbenFormSchema[] = [
    inputField('name', $t('admin.ai.provider.name'), {
      required: true,
      placeholder: $t('admin.ai.provider.placeholder.inputName'),
    }),
    ...(isEdit
      ? [
          inputField('code', $t('admin.ai.provider.code'), {
            disabled: true,
          }),
        ]
      : []),
  ];
  if (hasMultipleAdapterTypeOptions()) {
    schema.push({
      ...select('type', $t('admin.ai.provider.type'), {
        options: getProviderTypeOptions(),
        required: true,
        placeholder: $t('admin.ai.provider.placeholder.selectType'),
      }),
      help: $t('admin.ai.provider.help.type'),
    });
  }
  schema.push(
    {
      component: 'Input',
      componentProps: {
        maxLength: 500,
        placeholder: $t('admin.ai.provider.placeholder.inputBaseUrl'),
      },
      fieldName: 'base_url',
      label: $t('admin.ai.provider.baseUrl'),
      rules: z
        .union([z.string(), z.undefined()])
        .refine(
          (value: string | undefined) =>
            value === undefined ||
            value === '' ||
            isValidProviderBaseUrl(value),
          { message: $t('admin.ai.provider.validation.baseUrlInvalid') },
        ),
      help: $t('admin.ai.provider.help.baseUrl'),
    } as VbenFormSchema,
    {
      ...select('wire_api', $t('admin.ai.provider.wireApi'), {
        options: getProviderWireApiOptions(),
        placeholder: $t('admin.ai.provider.placeholder.selectWireApi'),
        required: true,
      }),
      dependencies: {
        triggerFields: ['type'],
        show: (values: Record<string, unknown>) =>
          resolveSchemaProviderType(values) === 'openai_compatible',
      },
      help: $t('admin.ai.provider.help.wireApi'),
    },
    {
      ...switchField(
        'responses_tool_history_compat',
        $t('admin.ai.provider.responsesToolHistoryCompat'),
        {
          defaultValue: false,
        },
      ),
      dependencies: {
        triggerFields: ['type', 'wire_api'],
        show: (values: Record<string, unknown>) =>
          resolveSchemaProviderType(values) === 'openai_compatible' &&
          values.wire_api === 'responses',
      },
      help: $t('admin.ai.provider.help.responsesToolHistoryCompat'),
    },
    {
      ...switchField(
        'web_search_enabled',
        $t('admin.ai.provider.webSearch.enabled'),
        {
          defaultValue: WEB_SEARCH_DEFAULTS.enabled,
        },
      ),
      help: $t('admin.ai.provider.webSearch.help.enabled'),
    },
    {
      ...select(
        'web_search_strategy',
        $t('admin.ai.provider.webSearch.strategy'),
        {
          options: getProviderWebSearchStrategyOptions(),
          required: true,
        },
      ),
      help: $t('admin.ai.provider.webSearch.help.strategy'),
    },
    {
      component: 'InputNumber',
      componentProps: {
        min: 1,
        max: 10,
        precision: 0,
        style: { width: '100%' },
      },
      fieldName: 'web_search_max_results_cap',
      label: $t('admin.ai.provider.webSearch.maxResultsCap'),
      rules: z
        .union([z.number(), z.null(), z.undefined()])
        .refine(
          (value: null | number | undefined) =>
            value === null ||
            value === undefined ||
            (Number.isInteger(value) && value >= 1 && value <= 10),
          {
            message: $t('admin.ai.provider.webSearch.validation.maxResultsCap'),
          },
        ),
      help: $t('admin.ai.provider.webSearch.help.maxResultsCap'),
    } as VbenFormSchema,
    {
      component: 'InputNumber',
      componentProps: {
        min: 1,
        max: 120,
        precision: 0,
        style: { width: '100%' },
      },
      fieldName: 'web_search_native_timeout_seconds',
      label: $t('admin.ai.provider.webSearch.nativeTimeoutSeconds'),
      rules: z
        .union([z.number(), z.null(), z.undefined()])
        .refine(
          (value: null | number | undefined) =>
            value === null ||
            value === undefined ||
            (Number.isInteger(value) && value >= 1 && value <= 120),
          {
            message: $t(
              'admin.ai.provider.webSearch.validation.nativeTimeoutSeconds',
            ),
          },
        ),
      help: $t('admin.ai.provider.webSearch.help.nativeTimeoutSeconds'),
    } as VbenFormSchema,
    {
      component: 'InputNumber',
      componentProps: {
        min: 1,
        max: 120,
        precision: 0,
        style: { width: '100%' },
      },
      fieldName: 'web_search_public_timeout_seconds',
      label: $t('admin.ai.provider.webSearch.publicTimeoutSeconds'),
      rules: z
        .union([z.number(), z.null(), z.undefined()])
        .refine(
          (value: null | number | undefined) =>
            value === null ||
            value === undefined ||
            (Number.isInteger(value) && value >= 1 && value <= 120),
          {
            message: $t(
              'admin.ai.provider.webSearch.validation.publicTimeoutSeconds',
            ),
          },
        ),
      help: $t('admin.ai.provider.webSearch.help.publicTimeoutSeconds'),
    } as VbenFormSchema,
    {
      ...select(
        'web_search_public_providers',
        $t('admin.ai.provider.webSearch.publicProviders'),
        {
          options: getProviderWebSearchPublicProviderOptions(),
          componentProps: {
            mode: 'multiple',
            maxTagCount: 'responsive',
          },
        },
      ),
      help: $t('admin.ai.provider.webSearch.help.publicProviders'),
    },
    {
      ...switchField(
        'web_search_allow_unverified_runtime_target',
        $t('admin.ai.provider.webSearch.allowUnverifiedRuntimeTarget'),
        {
          defaultValue: false,
        },
      ),
      dependencies: {
        triggerFields: ['type', 'web_search_enabled'],
        show: (values: Record<string, unknown>) =>
          resolveSchemaProviderType(values) === 'openai_compatible' &&
          values.web_search_enabled !== false,
      },
      help: $t('admin.ai.provider.webSearch.help.allowUnverifiedRuntimeTarget'),
    },
    {
      ...inputField(
        'web_search_verified_provider_code',
        $t('admin.ai.provider.webSearch.verifiedProviderCode'),
        {
          placeholder: $t(
            'admin.ai.provider.webSearch.placeholder.verifiedProviderCode',
          ),
        },
      ),
      dependencies: {
        triggerFields: ['type', 'web_search_enabled'],
        show: (values: Record<string, unknown>) =>
          resolveSchemaProviderType(values) === 'openai_compatible' &&
          values.web_search_enabled !== false,
      },
      help: $t('admin.ai.provider.webSearch.help.verifiedProviderCode'),
    },
    {
      ...inputField(
        'web_search_verified_model_code',
        $t('admin.ai.provider.webSearch.verifiedModelCode'),
        {
          placeholder: $t(
            'admin.ai.provider.webSearch.placeholder.verifiedModelCode',
          ),
        },
      ),
      dependencies: {
        triggerFields: ['type', 'web_search_enabled'],
        show: (values: Record<string, unknown>) =>
          resolveSchemaProviderType(values) === 'openai_compatible' &&
          values.web_search_enabled !== false,
      },
      help: $t('admin.ai.provider.webSearch.help.verifiedModelCode'),
    },
    textareaField('description', $t('admin.ai.provider.description'), {
      placeholder: $t('admin.ai.provider.placeholder.inputDescription'),
    }),
    {
      component: 'ImageUpload' as const,
      fieldName: 'icon',
      label: $t('admin.ai.provider.icon'),
    },
    {
      ...switchField('is_active', $t('admin.ai.provider.isActive'), {
        defaultValue: true,
      }),
      help: $t('admin.ai.provider.help.isActive'),
    },
  );
  return schema;
}

/**
 * 表单默认值
 */
export function getFormDefaults(): Record<string, unknown> {
  return {
    type: getDefaultProviderType(),
    wire_api: 'chat_completions',
    responses_tool_history_compat: false,
    web_search_enabled: WEB_SEARCH_DEFAULTS.enabled,
    web_search_strategy: WEB_SEARCH_DEFAULTS.strategy,
    web_search_max_results_cap: WEB_SEARCH_DEFAULTS.max_results_cap,
    web_search_native_timeout_seconds:
      WEB_SEARCH_DEFAULTS.native_timeout_seconds,
    web_search_public_timeout_seconds:
      WEB_SEARCH_DEFAULTS.public_timeout_seconds,
    web_search_public_providers: [...WEB_SEARCH_DEFAULTS.public_providers],
    web_search_allow_unverified_runtime_target: false,
    web_search_verified_provider_code: '',
    web_search_verified_model_code: '',
    is_active: true,
    sort_order: 0,
  };
}
