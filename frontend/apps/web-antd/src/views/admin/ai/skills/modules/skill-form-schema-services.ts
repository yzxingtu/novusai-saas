import type { SkillFormValues } from './skill-form-types';

import {
  inputField,
  numberField,
  select,
  switchField,
  textareaField,
} from '#/adapter/form';
import { $t } from '#/locales';

function isHttp(values: SkillFormValues) {
  return values.type === 'http';
}

function isEmail(values: SkillFormValues) {
  return values.type === 'email';
}

function isCodeExecution(values: SkillFormValues) {
  return values.type === 'code_execution';
}

function isHttpBearer(values: SkillFormValues) {
  return values.type === 'http' && values.http_auth_type === 'bearer';
}

function isHttpApiKey(values: SkillFormValues) {
  return values.type === 'http' && values.http_auth_type === 'api_key';
}

function isHttpBasic(values: SkillFormValues) {
  return values.type === 'http' && values.http_auth_type === 'basic';
}

function getHttpMethodOptions() {
  return [
    { label: 'GET', value: 'GET' },
    { label: 'POST', value: 'POST' },
    { label: 'PUT', value: 'PUT' },
    { label: 'PATCH', value: 'PATCH' },
    { label: 'DELETE', value: 'DELETE' },
  ];
}

function getAuthTypeOptions() {
  return [
    {
      label: $t('admin.ai.skill.httpConfig.authTypeOptions.none'),
      value: 'none',
    },
    {
      label: $t('admin.ai.skill.httpConfig.authTypeOptions.bearer'),
      value: 'bearer',
    },
    {
      label: $t('admin.ai.skill.httpConfig.authTypeOptions.api_key'),
      value: 'api_key',
    },
    {
      label: $t('admin.ai.skill.httpConfig.authTypeOptions.basic'),
      value: 'basic',
    },
  ];
}

function buildBuiltinSchema() {
  return [
    {
      component: 'Divider',
      fieldName: '_builtin_divider',
      label: '',
      hideLabel: true,
      componentProps: { orientation: 'left', dashed: true },
      renderComponentContent: () => ({
        default: () => $t('admin.ai.skill.builtinTools.title'),
      }),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => values.type === 'builtin',
      },
    },
    {
      component: 'Alert',
      fieldName: '_builtin_tools_info',
      label: '',
      hideLabel: true,
      componentProps: {
        type: 'info',
        showIcon: true,
        message: $t('admin.ai.skill.builtinTools.hint'),
      },
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => values.type === 'builtin',
      },
    },
  ];
}

function buildHttpSchema() {
  return [
    {
      component: 'Divider',
      fieldName: '_http_divider',
      label: '',
      hideLabel: true,
      componentProps: { orientation: 'left', dashed: true },
      renderComponentContent: () => ({
        default: () => $t('admin.ai.skill.httpConfig.title'),
      }),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isHttp(values),
      },
    },
    {
      ...inputField('http_url', $t('admin.ai.skill.httpConfig.url'), {
        required: true,
        placeholder: $t('admin.ai.skill.httpConfig.urlPlaceholder'),
      }),
      help: $t('admin.ai.skill.httpConfig.urlHelp'),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isHttp(values),
      },
    },
    {
      ...select('http_method', $t('admin.ai.skill.httpConfig.method'), {
        options: getHttpMethodOptions(),
      }),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isHttp(values),
      },
    },
    {
      ...textareaField(
        'http_headers',
        $t('admin.ai.skill.httpConfig.headers'),
        {
          placeholder: $t('admin.ai.skill.httpConfig.headersPlaceholder'),
          rows: 3,
        },
      ),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isHttp(values),
      },
    },
    {
      ...textareaField(
        'http_body_template',
        $t('admin.ai.skill.httpConfig.bodyTemplate'),
        {
          placeholder: $t('admin.ai.skill.httpConfig.bodyTemplatePlaceholder'),
          rows: 4,
        },
      ),
      help: $t('admin.ai.skill.httpConfig.bodyTemplateHelp'),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isHttp(values),
      },
    },
    {
      ...textareaField(
        'http_query_params',
        $t('admin.ai.skill.httpConfig.queryParams'),
        {
          placeholder: $t('admin.ai.skill.httpConfig.queryParamsPlaceholder'),
          rows: 2,
        },
      ),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isHttp(values),
      },
    },
    {
      ...select('http_auth_type', $t('admin.ai.skill.httpConfig.authType'), {
        options: getAuthTypeOptions(),
      }),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isHttp(values),
      },
    },
    {
      ...inputField(
        'http_auth_token',
        $t('admin.ai.skill.httpConfig.authToken'),
        {
          placeholder: $t('admin.ai.skill.httpConfig.authTokenPlaceholder'),
        },
      ),
      dependencies: {
        triggerFields: ['type', 'http_auth_type'],
        if: (values: SkillFormValues) => isHttpBearer(values),
      },
    },
    {
      ...inputField(
        'http_auth_key_name',
        $t('admin.ai.skill.httpConfig.authKeyName'),
        {
          placeholder: $t('admin.ai.skill.httpConfig.authKeyNamePlaceholder'),
        },
      ),
      dependencies: {
        triggerFields: ['type', 'http_auth_type'],
        if: (values: SkillFormValues) => isHttpApiKey(values),
      },
    },
    {
      ...inputField(
        'http_auth_key_value',
        $t('admin.ai.skill.httpConfig.authKeyValue'),
      ),
      dependencies: {
        triggerFields: ['type', 'http_auth_type'],
        if: (values: SkillFormValues) => isHttpApiKey(values),
      },
    },
    {
      ...inputField(
        'http_auth_username',
        $t('admin.ai.skill.httpConfig.authUsername'),
      ),
      dependencies: {
        triggerFields: ['type', 'http_auth_type'],
        if: (values: SkillFormValues) => isHttpBasic(values),
      },
    },
    {
      ...inputField(
        'http_auth_password',
        $t('admin.ai.skill.httpConfig.authPassword'),
      ),
      dependencies: {
        triggerFields: ['type', 'http_auth_type'],
        if: (values: SkillFormValues) => isHttpBasic(values),
      },
    },
    {
      ...inputField(
        'http_response_path',
        $t('admin.ai.skill.httpConfig.responsePath'),
        {
          placeholder: $t('admin.ai.skill.httpConfig.responsePathPlaceholder'),
        },
      ),
      help: $t('admin.ai.skill.httpConfig.responsePathHelp'),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isHttp(values),
      },
    },
  ];
}

function buildEmailSchema() {
  return [
    {
      component: 'Divider',
      fieldName: '_email_divider',
      label: '',
      hideLabel: true,
      componentProps: { orientation: 'left', dashed: true },
      renderComponentContent: () => ({
        default: () => $t('admin.ai.skill.emailConfig.title'),
      }),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isEmail(values),
      },
    },
    {
      component: 'Alert',
      fieldName: '_email_smtp_hint',
      label: '',
      hideLabel: true,
      componentProps: {
        type: 'info',
        showIcon: true,
        message: $t('admin.ai.skill.emailConfig.smtpHint'),
      },
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isEmail(values),
      },
    },
    {
      ...inputField(
        'email_subject_prefix',
        $t('admin.ai.skill.emailConfig.subjectPrefix'),
        {
          placeholder: $t(
            'admin.ai.skill.emailConfig.subjectPrefixPlaceholder',
          ),
        },
      ),
      help: $t('admin.ai.skill.emailConfig.subjectPrefixHelp'),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isEmail(values),
      },
    },
    {
      ...inputField(
        'email_allowed_domains',
        $t('admin.ai.skill.emailConfig.allowedDomains'),
        {
          placeholder: $t(
            'admin.ai.skill.emailConfig.allowedDomainsPlaceholder',
          ),
        },
      ),
      help: $t('admin.ai.skill.emailConfig.allowedDomainsHelp'),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isEmail(values),
      },
    },
    {
      ...numberField(
        'email_max_recipients',
        $t('admin.ai.skill.emailConfig.maxRecipients'),
        {
          min: 1,
          max: 50,
        },
      ),
      help: $t('admin.ai.skill.emailConfig.maxRecipientsHelp'),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isEmail(values),
      },
    },
    {
      ...switchField(
        'email_require_confirmation',
        $t('admin.ai.skill.emailConfig.requireConfirmation'),
      ),
      help: $t('admin.ai.skill.emailConfig.requireConfirmationHelp'),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isEmail(values),
      },
    },
    {
      ...switchField(
        'email_allow_cc',
        $t('admin.ai.skill.emailConfig.allowCc'),
      ),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isEmail(values),
      },
    },
  ];
}

function buildCodeExecutionSchema() {
  return [
    {
      component: 'Divider',
      fieldName: '_code_divider',
      label: '',
      hideLabel: true,
      componentProps: { orientation: 'left', dashed: true },
      renderComponentContent: () => ({
        default: () => $t('admin.ai.skill.codeExecutionConfig.title'),
      }),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isCodeExecution(values),
      },
    },
    {
      component: 'Alert',
      fieldName: '_code_sandbox_hint',
      label: '',
      hideLabel: true,
      componentProps: {
        type: 'info',
        showIcon: true,
        message: $t('admin.ai.skill.codeExecutionConfig.sandboxHint'),
      },
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isCodeExecution(values),
      },
    },
    {
      ...select(
        'code_language',
        $t('admin.ai.skill.codeExecutionConfig.language'),
        {
          options: [
            {
              label: $t(
                'admin.ai.skill.codeExecutionConfig.languageOptions.python',
              ),
              value: 'python',
            },
          ],
        },
      ),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isCodeExecution(values),
      },
    },
    {
      ...numberField(
        'code_memory_limit_mb',
        $t('admin.ai.skill.codeExecutionConfig.memoryLimitMb'),
        {
          min: 64,
          max: 1024,
        },
      ),
      help: $t('admin.ai.skill.codeExecutionConfig.memoryLimitHelp'),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isCodeExecution(values),
      },
    },
    {
      ...inputField(
        'code_allowed_modules',
        $t('admin.ai.skill.codeExecutionConfig.allowedModules'),
        {
          placeholder: $t(
            'admin.ai.skill.codeExecutionConfig.allowedModulesPlaceholder',
          ),
        },
      ),
      help: $t('admin.ai.skill.codeExecutionConfig.allowedModulesHelp'),
      dependencies: {
        triggerFields: ['type'],
        if: (values: SkillFormValues) => isCodeExecution(values),
      },
    },
  ];
}

export function buildSkillFormServiceSchema() {
  return [
    ...buildBuiltinSchema(),
    ...buildHttpSchema(),
    ...buildEmailSchema(),
    ...buildCodeExecutionSchema(),
  ];
}
