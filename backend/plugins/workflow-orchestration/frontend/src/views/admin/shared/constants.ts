export const ADMIN_BASE_PATH = '/admin/plugins/workflow-orchestration';
export const ADMIN_I18N_PREFIX = 'plugin.workflow-orchestration.admin';

export function buildAdminPath(segment = ''): string {
  const normalized = segment.replace(/^\/+/, '');
  return normalized ? `${ADMIN_BASE_PATH}/${normalized}` : ADMIN_BASE_PATH;
}
