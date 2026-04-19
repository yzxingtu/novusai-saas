/**
 * Page-level AI policy composable
 * 页面级 AI 策略 Composable
 *
 * Combines route meta.ai config with RBAC permissions to compute effective AI mode.
 * 结合路由 meta.ai 配置与 RBAC 权限，计算当前页面的有效 AI 模式。
 *
 * Priority (high to low) / 优先级（从高到低）:
 * 1. RBAC permission check (disabled if no permission) / RBAC 权限检查
 * 2. Route meta.ai.mode (page-level config) / 路由 meta.ai.mode
 * 3. Default mode DEFAULT_AI_MODE / 默认模式
 *
 * @example
 * ```ts
 * const { isAIEnabled, effectiveAIMode, pageContextKey } = useCurrentPageAIPolicy();
 * ```
 */
import type { AIPageMode } from '@vben/types';

import type { AIRouteSecurityPolicy } from '#/components/business/ai-runtime/security-policy';

import { computed, ref, watchEffect } from 'vue';
import { useRoute } from 'vue-router';

import {
  normalizeCapabilityKeys,
  normalizeOperationNames,
  normalizePageAIMode,
} from '#/utils/ai-page-capabilities';

import { useAIPermission } from './use-ai-permission';

type RouteAIMeta = {
  act?: string;
  confirm_action_kinds?: string | string[];
  confirmActionKinds?: string | string[];
  data_ai?: 'off' | 'on';
  data_ai_act?: 'allow' | 'off';
  data_ai_read?: 'allow' | 'mask' | 'off';
  data_ai_submit?: 'allow' | 'off';
  dataAi?: 'off' | 'on';
  dataAiAct?: 'allow' | 'off';
  dataAiRead?: 'allow' | 'mask' | 'off';
  dataAiSubmit?: 'allow' | 'off';
  disabled_action_kinds?: string | string[];
  disabledActionKinds?: string | string[];
  disabledCapabilities?: string | string[];
  disabledOperations?: string | string[];
  mode?: AIPageMode;
  pageContextKey?: string;
  read?: string;
  sensitive_field_read?: 'mask' | 'off';
  sensitiveFieldRead?: 'mask' | 'off';
  submit?: string;
};

export interface CurrentPageAIExecutionPolicy {
  disabledCapabilities: string[];
  disabledOperations: string[];
  mode: AIPageMode;
  pageContextKey?: string;
}

/** Default AI mode: page-aware operate mode / 默认 AI 模式：页面感知 operate 模式 */
const DEFAULT_AI_MODE: AIPageMode = 'operate';

export const currentPageAIExecutionPolicy = ref<CurrentPageAIExecutionPolicy>({
  disabledCapabilities: [],
  disabledOperations: [],
  mode: DEFAULT_AI_MODE,
  pageContextKey: undefined,
});

export const currentRouteAISecurityPolicy = ref<AIRouteSecurityPolicy>({
  act: 'allow',
  confirmActionKinds: [],
  disabledActionKinds: [],
  enabled: true,
  read: 'allow',
  sensitiveFieldRead: 'off',
  submit: 'allow',
});

function normalizePolicyPageKey(raw?: string): string | undefined {
  const value = String(raw ?? '').trim();
  if (!value) return undefined;
  return value.replace(/^\//, '').replaceAll('/', '.');
}

function normalizeRouteList(values?: string | string[]): string[] {
  if (!values) return [];
  if (Array.isArray(values)) {
    return [...new Set(values.map((item) => String(item).trim()))].filter(
      Boolean,
    );
  }
  return [
    ...new Set(
      String(values)
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  ];
}

function normalizeRead(value?: string): AIRouteSecurityPolicy['read'] {
  const normalized = String(value ?? '')
    .trim()
    .toLowerCase();
  if (normalized === 'off') return 'off';
  if (normalized === 'mask') return 'mask';
  return 'allow';
}

function normalizeToggle(value?: string): 'allow' | 'off' {
  return String(value ?? '')
    .trim()
    .toLowerCase() === 'off'
    ? 'off'
    : 'allow';
}

export function useCurrentPageAIPolicy() {
  const route = useRoute();
  const { canChat, canViewHistory, canRoute, resource } = useAIPermission();
  const rawAIMeta = computed<RouteAIMeta>(
    () => (route.meta?.ai as RouteAIMeta | undefined) ?? {},
  );

  /** Effective AI mode: route config > default / 生效的 AI 模式：路由配置 > 默认值 */
  const pageMode = computed<AIPageMode>(() =>
    normalizePageAIMode(rawAIMeta.value.mode, DEFAULT_AI_MODE),
  );

  /** Disabled capability keys / 禁用的能力键 */
  const disabledCapabilities = computed(() =>
    normalizeCapabilityKeys(rawAIMeta.value.disabledCapabilities),
  );

  /** Disabled operation names / 禁用的操作名 */
  const disabledOperations = computed(() =>
    normalizeOperationNames(rawAIMeta.value.disabledOperations),
  );

  /**
   * Current page context key in canonical dot-notation (e.g. 'admin.ai.agents')
   * 当前页面上下文标识（规范点号格式，如 'admin.ai.agents'）
   *
   * Priority: route.meta.ai.pageContextKey > normalizePageKey(route.path)
   * Used for precise matching with registered page contexts / 用于精确匹配注册表
   */
  const pageContextKey = computed<string | undefined>(
    () =>
      (rawAIMeta.value.pageContextKey
        ? normalizePolicyPageKey(rawAIMeta.value.pageContextKey)
        : undefined) ??
      (route.path ? normalizePolicyPageKey(route.path) : undefined),
  );

  /** Page AI disabled flag / 页面 AI 禁用标志 */
  const pageDisabled = computed(() => pageMode.value === 'disabled');

  /**
   * Final AI availability (permission + config) / 最终 AI 可用性（权限 + 配置）
   * Only true when RBAC allows and page is not disabled / 仅当 RBAC 允许且页面未禁用时为 true
   */
  const aiEnabled = computed(() => canChat.value && !pageDisabled.value);

  /**
   * Effective AI mode for current page / 当前页面生效的 AI 模式
   * No AI permission: disabled / 无 AI 权限：禁用
   * Has AI permission: page config mode / 有 AI 权限：页面配置模式
   */
  const effectiveMode = computed<AIPageMode>(() => {
    if (!canChat.value) return 'disabled';
    return pageMode.value;
  });

  const runtimeRouteSecurityPolicy = computed<AIRouteSecurityPolicy>(() => {
    const meta = rawAIMeta.value;
    const legacyDisabledOperations = normalizeOperationNames(
      meta.disabledOperations,
    );
    const explicitDisabledActionKinds = normalizeRouteList(
      meta.disabledActionKinds ?? meta.disabled_action_kinds,
    );
    const disabledActionKinds = [
      ...legacyDisabledOperations,
      ...explicitDisabledActionKinds,
    ];

    const disabledCapabilitySet = new Set(disabledCapabilities.value);
    if (disabledCapabilitySet.has('form')) {
      disabledActionKinds.push(
        'create_record',
        'edit_record',
        'ui_set_field',
        'ui_fill_form',
        'ui_submit_form',
      );
    }
    if (disabledCapabilitySet.has('submit')) {
      disabledActionKinds.push('ui_submit_form');
    }
    if (disabledCapabilitySet.has('editor')) {
      disabledActionKinds.push(
        'append_content',
        'insert_content',
        'replace_content',
        'replace_section',
      );
    }

    const mode = effectiveMode.value;
    const modeDisabledActionKinds: string[] = [];
    let modeSubmit: 'allow' | 'off' = 'allow';
    let modeAct: 'allow' | 'off' = 'allow';
    if (mode === 'context_only') {
      modeAct = 'off';
      modeSubmit = 'off';
    } else if (mode === 'navigation_only') {
      modeSubmit = 'off';
      modeDisabledActionKinds.push(
        'create_record',
        'delete_record',
        'edit_record',
        'ui_set_field',
        'ui_fill_form',
        'replace_content',
        'replace_section',
        'ui_submit_form',
      );
    }

    const dataAi =
      (meta.dataAi ?? meta.data_ai)?.toString().trim().toLowerCase() || '';
    const routeEnabled =
      canChat.value && mode !== 'disabled' && dataAi !== 'off';

    const confirmActionKinds = normalizeRouteList(
      meta.confirmActionKinds ?? meta.confirm_action_kinds,
    );

    return {
      pageContextKey: pageContextKey.value,
      enabled: routeEnabled,
      read: normalizeRead(
        meta.dataAiRead ?? meta.data_ai_read ?? meta.read ?? undefined,
      ),
      act:
        modeAct === 'off'
          ? 'off'
          : normalizeToggle(
              meta.dataAiAct ?? meta.data_ai_act ?? meta.act ?? undefined,
            ),
      submit:
        modeSubmit === 'off'
          ? 'off'
          : normalizeToggle(
              meta.dataAiSubmit ??
                meta.data_ai_submit ??
                meta.submit ??
                undefined,
            ),
      sensitiveFieldRead:
        meta.sensitiveFieldRead ?? meta.sensitive_field_read ?? 'off',
      disabledActionKinds: [
        ...new Set([...disabledActionKinds, ...modeDisabledActionKinds]),
      ],
      confirmActionKinds,
    };
  });

  watchEffect(() => {
    currentPageAIExecutionPolicy.value = {
      disabledCapabilities: [...disabledCapabilities.value],
      disabledOperations: [...disabledOperations.value],
      mode: effectiveMode.value,
      pageContextKey: pageContextKey.value,
    };
    currentRouteAISecurityPolicy.value = {
      ...runtimeRouteSecurityPolicy.value,
      disabledActionKinds: [
        ...(runtimeRouteSecurityPolicy.value.disabledActionKinds ?? []),
      ],
      confirmActionKinds: [
        ...(runtimeRouteSecurityPolicy.value.confirmActionKinds ?? []),
      ],
    };
  });

  return {
    /** AI total switch (permission + config) / AI 总开关（权限 + 配置） */
    aiEnabled,
    /** Whether has AI chat permission (pure RBAC) / 是否有 AI 聊天权限（纯 RBAC） */
    canChat,
    /** Whether can view conversation history (pure RBAC) / 是否可查看对话历史（纯 RBAC） */
    canViewHistory,
    /** Whether can execute route (pure RBAC) / 是否可执行路由（纯 RBAC） */
    canRoute,
    /** Disabled capability keys / 禁用的能力键 */
    disabledCapabilities,
    /** Disabled operation names / 禁用的操作名 */
    disabledOperations,
    /** Effective AI mode for current page / 当前页面生效的 AI 模式 */
    effectiveMode,
    /** Page AI disabled flag / 页面 AI 禁用标志 */
    pageDisabled,
    /** Current page context key / 页面上下文标识 */
    pageContextKey,
    /** Page AI mode / 页面 AI 模式 */
    pageMode,
    /** Current resource name / 当前资源名 */
    resource,
    /** Route-level runtime security policy bridge / route 级 runtime 安全策略桥接 */
    routeSecurityPolicy: runtimeRouteSecurityPolicy,
  };
}
