import type { AIAgentBootstrapStatus } from '#/api/admin/ai-agents';

export type AdminAgentSetupState =
  | 'checking'
  | 'error'
  | 'missing-model'
  | 'missing-provider'
  | 'normal'
  | 'seed-system';

export function resolveAdminAgentSetupState(
  status: AIAgentBootstrapStatus | null,
  loading: boolean,
  hasError = false,
): AdminAgentSetupState {
  if (hasError && !status) {
    return 'error';
  }
  if (loading && !status) {
    return 'checking';
  }
  if (!status) {
    return 'checking';
  }
  if (!status.has_active_provider) {
    return 'missing-provider';
  }
  if (!status.has_active_chat_model) {
    return 'missing-model';
  }
  if (status.runtime_ready && (status.needs_seed || !status.system_agents_ready)) {
    return 'seed-system';
  }
  return 'normal';
}
