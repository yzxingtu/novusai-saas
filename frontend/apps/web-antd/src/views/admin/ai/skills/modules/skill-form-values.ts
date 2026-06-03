import type { BuiltinToolInfo, SkillFormSharedState } from './skill-form-types';

import type { AdminSkillInfo } from '#/api/admin/skills';

interface SkillFormValueOptions extends SkillFormSharedState {
  loadPluginTools?: (skillId: number) => void;
}

export function getSkillFormDefaults(
  state: SkillFormSharedState,
): Record<string, unknown> {
  state.isPluginSkill.value = false;
  state.pluginSourceName.value = '';
  state.pluginTools.value = [];
  state.builtinTools.value = [];
  return {
    type: 'toolkit',
    timeout: 30,
    status: 'active',
    is_active: true,
    toolkit_content: '',
    valves_config: {},
    kb_ids: [],
    rag_enabled: true,
    rag_top_k: 5,
    rag_score_threshold: 0.5,
    rag_search_mode: 'hybrid',
    rag_rewrite_strategy: 'none',
    rag_reranker_enabled: false,
    rag_context_token_ratio: 0.3,
    http_url: '',
    http_method: 'GET',
    http_headers: '',
    http_body_template: '',
    http_query_params: '',
    http_auth_type: 'none',
    http_auth_token: '',
    http_auth_key_name: 'X-API-Key',
    http_auth_key_value: '',
    http_auth_username: '',
    http_auth_password: '',
    http_response_path: '',
    email_subject_prefix: '',
    email_allowed_domains: '',
    email_max_recipients: 5,
    email_require_confirmation: true,
    email_allow_cc: true,
    code_language: 'python',
    code_memory_limit_mb: 256,
    code_allowed_modules:
      'math,json,datetime,re,collections,itertools,functools,statistics,random,string',
  };
}

export function buildSkillFormPayload(values: Record<string, unknown>) {
  let config: null | Record<string, unknown> = null;
  const type = values.type as string;

  switch (type) {
    case 'code_execution': {
      const modulesRaw = (values.code_allowed_modules as string) || '';
      config = {
        language: values.code_language || 'python',
        memory_limit_mb: values.code_memory_limit_mb ?? 256,
        allowed_modules: modulesRaw
          ? modulesRaw
              .split(',')
              .map((moduleName: string) => moduleName.trim())
              .filter(Boolean)
          : [],
      };
      break;
    }
    case 'email': {
      const domainsRaw = (values.email_allowed_domains as string) || '';
      config = {
        subject_prefix: values.email_subject_prefix || '',
        allowed_domains: domainsRaw
          ? domainsRaw
              .split(',')
              .map((domain: string) => domain.trim())
              .filter(Boolean)
          : [],
        max_recipients: values.email_max_recipients ?? 5,
        require_confirmation: values.email_require_confirmation ?? true,
        allow_cc: values.email_allow_cc ?? true,
      };
      break;
    }
    case 'http': {
      let headers: Record<string, string> = {};
      let queryParams: Record<string, string> = {};
      try {
        headers = JSON.parse((values.http_headers as string) || '{}');
      } catch {
        /* empty */
      }
      try {
        queryParams = JSON.parse((values.http_query_params as string) || '{}');
      } catch {
        /* empty */
      }
      const authConfig: Record<string, string> = {};
      const authType = (values.http_auth_type as string) || 'none';
      if (authType === 'bearer') {
        authConfig.token = (values.http_auth_token as string) || '';
      }
      if (authType === 'api_key') {
        authConfig.key_name =
          (values.http_auth_key_name as string) || 'X-API-Key';
        authConfig.key_value = (values.http_auth_key_value as string) || '';
      }
      if (authType === 'basic') {
        authConfig.username = (values.http_auth_username as string) || '';
        authConfig.password = (values.http_auth_password as string) || '';
      }
      config = {
        url: values.http_url || '',
        method: values.http_method || 'GET',
        headers,
        body_template: values.http_body_template || '',
        query_params: queryParams,
        auth_type: authType,
        auth_config: authConfig,
        response_path: values.http_response_path || '',
      };
      break;
    }
    case 'toolkit': {
      const valvesConfig = values.valves_config as
        | Record<string, unknown>
        | undefined;
      config =
        valvesConfig && Object.keys(valvesConfig).length > 0
          ? { valves: valvesConfig }
          : null;
      break;
    }
    default: {
      break;
    }
  }

  const result: Record<string, unknown> = {
    status: values.is_active === false ? 'disabled' : 'active',
    package_id: values.package_id,
    name: values.name,
    type,
    description: values.description || null,
    timeout: values.timeout ?? 30,
    is_active: values.is_active ?? true,
    config,
  };

  if (type === 'toolkit') {
    result.toolkit_content = values.toolkit_content || '';
  }

  return result;
}

export const transformSkillFormValues = buildSkillFormPayload;

export function toSkillFormValues(
  data: AdminSkillInfo,
  options: SkillFormValueOptions,
) {
  const cfg = (data.config ?? {}) as Record<string, unknown>;

  options.isPluginSkill.value = !!data.source_plugin;
  options.pluginSourceName.value = data.source_plugin || '';

  options.builtinTools.value =
    data.type === 'builtin' && Array.isArray(cfg.tools)
      ? (cfg.tools as BuiltinToolInfo[])
      : [];

  if (data.source_plugin && Array.isArray(data.plugin_tools)) {
    options.pluginTools.value = data.plugin_tools;
  } else {
    const standardTypes = new Set([
      'builtin',
      'code_execution',
      'email',
      'http',
      'toolkit',
    ]);
    if (typeof data.id === 'number' && !standardTypes.has(data.type)) {
      if (options.loadPluginTools) {
        options.loadPluginTools(data.id);
      } else {
        options.pluginTools.value = [];
      }
    } else {
      options.pluginTools.value = [];
    }
  }

  return {
    package_id: data.package_id,
    name: data.name,
    type: data.type,
    description: data.description,
    timeout: data.timeout,
    status: (data as AdminSkillInfo & { status?: string }).status ?? 'active',
    is_active: data.is_active,
    toolkit_content: data.toolkit_content || '',
    valves_config: (cfg.valves as Record<string, unknown>) || {},
    http_url: (cfg.url as string) || '',
    http_method: (cfg.method as string) || 'GET',
    http_headers: cfg.headers ? JSON.stringify(cfg.headers, null, 2) : '',
    http_body_template: (cfg.body_template as string) || '',
    http_query_params: cfg.query_params
      ? JSON.stringify(cfg.query_params, null, 2)
      : '',
    http_auth_type: (cfg.auth_type as string) || 'none',
    http_auth_token: (cfg.auth_config as Record<string, string>)?.token || '',
    http_auth_key_name:
      (cfg.auth_config as Record<string, string>)?.key_name || 'X-API-Key',
    http_auth_key_value:
      (cfg.auth_config as Record<string, string>)?.key_value || '',
    http_auth_username:
      (cfg.auth_config as Record<string, string>)?.username || '',
    http_auth_password:
      (cfg.auth_config as Record<string, string>)?.password || '',
    http_response_path: (cfg.response_path as string) || '',
    email_subject_prefix: (cfg.subject_prefix as string) || '',
    email_allowed_domains: Array.isArray(cfg.allowed_domains)
      ? (cfg.allowed_domains as string[]).join(', ')
      : '',
    email_max_recipients: (cfg.max_recipients as number) ?? 5,
    email_require_confirmation: (cfg.require_confirmation as boolean) ?? true,
    email_allow_cc: (cfg.allow_cc as boolean) ?? true,
    code_language: (cfg.language as string) || 'python',
    code_memory_limit_mb: (cfg.memory_limit_mb as number) ?? 256,
    code_allowed_modules: Array.isArray(cfg.allowed_modules)
      ? (cfg.allowed_modules as string[]).join(',')
      : '',
  };
}
