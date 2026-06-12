import type { TenantAIModelInfo } from '#/api/tenant/ai';

export type TenantAgentSetupState = 'checking' | 'missing-model' | 'normal';

export function hasTenantActiveChatModel(models: TenantAIModelInfo[]): boolean {
  return models.some((model) => model.type === 'chat' && model.is_active);
}

export function resolveTenantAgentSetupState(
  hasActiveChatModel: boolean | null,
  loading: boolean,
  hasError = false,
): TenantAgentSetupState {
  if (hasError) {
    return 'normal';
  }
  if (loading && hasActiveChatModel === null) {
    return 'checking';
  }
  if (hasActiveChatModel === false) {
    return 'missing-model';
  }
  return 'normal';
}
