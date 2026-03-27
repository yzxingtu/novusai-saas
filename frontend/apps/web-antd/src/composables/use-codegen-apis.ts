/**
 * 代码生成器用 API / Codegen APIs
 *
 * UserSelect、DeptSelect 等组件使用的 API。
 * 根据当前 URL（admin/tenant）自动选择对应端点。
 *
 * APIs for UserSelect, DeptSelect etc. Auto-selects endpoint by current URL (admin/tenant).
 */
import { getAdminListApi } from '#/api/admin/admin-user';
import { getOrganizationRootNodesApi as getAdminOrgRootsApi } from '#/api/admin/organization';
import { getTenantOrganizationRootNodesApi as getTenantOrgRootsApi } from '#/api/tenant/organization';
import { getTenantUserListApi } from '#/api/tenant/tenant-users';

function getApiPrefix(): 'admin' | 'tenant' {
  if (typeof window === 'undefined') return 'admin';
  const path = window.location?.pathname || '';
  return path.includes('/tenant') ? 'tenant' : 'admin';
}

/**
 * 用户下拉 API / User select API
 *
 * Admin: GET /admin/admins (平台管理员)
 * Tenant: GET /tenant/users (企业用户)
 */
export async function getUserSelectApi(params?: { search?: string }) {
  const prefix = getApiPrefix();
  try {
    if (prefix === 'admin') {
      const res = await getAdminListApi({
        page: 1,
        page_size: 500,
        ...params,
      } as Record<string, unknown>);
      return {
        items: (res.items || []).map(
          (u: { id: number; nickname?: string; username?: string }) => ({
            id: u.id,
            value: u.id,
            label:
              (u as { nickname?: string }).nickname ||
              (u as { username?: string }).username ||
              String(u.id),
          }),
        ),
      };
    }
    const res = await getTenantUserListApi({
      page: 1,
      page_size: 500,
      ...params,
    } as Record<string, unknown>);
    return {
      items: (res.items || []).map(
        (u: { id: number; nickname?: string; username?: string }) => ({
          id: u.id,
          value: u.id,
          label:
            (u as { nickname?: string }).nickname ||
            (u as { username?: string }).username ||
            String(u.id),
        }),
      ),
    };
  } catch (error) {
    if (import.meta.env.DEV) {
      console.warn('[getUserSelectApi]', error);
    }
    return { items: [] };
  }
}

/**
 * 部门/组织树 API / Dept/Org tree API
 *
 * Admin: GET /admin/organization (平台组织架构根节点)
 * Tenant: GET /tenant/organization (企业组织架构根节点)
 */
export async function getDeptTreeApi() {
  const prefix = getApiPrefix();
  try {
    const roots =
      prefix === 'admin'
        ? await getAdminOrgRootsApi()
        : await getTenantOrgRootsApi();
    return {
      items: (roots || []).map((n: { id: number; name?: string }) => ({
        id: n.id,
        value: n.id,
        label: (n as { name?: string }).name || String(n.id),
      })),
    };
  } catch (error) {
    if (import.meta.env.DEV) {
      console.warn('[getDeptTreeApi]', error);
    }
    return { items: [] };
  }
}
