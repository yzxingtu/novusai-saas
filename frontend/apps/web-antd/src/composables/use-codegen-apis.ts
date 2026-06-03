/**
 * Codegen select APIs.
 *
 * UserSelect and DeptSelect generated fields use these ordinary data helpers.
 * They must stay available for generated pages.
 */
import {
  getNodeMembersApi as getAdminNodeMembersApi,
  getOrganizationRootNodesApi as getAdminOrgRootsApi,
} from '#/api/admin/organization';
import { getTenantOrganizationRootNodesApi as getTenantOrgRootsApi } from '#/api/tenant/organization';
import { getTenantUserListApi } from '#/api/tenant/tenant-users';

const ADMIN_USER_SELECT_PAGE_SIZE = 500;

type SelectableUser = {
  id: number;
  nickname?: string;
  username?: string;
};

function getApiPrefix(): 'admin' | 'tenant' {
  if (typeof window === 'undefined') return 'admin';
  const path = window.location?.pathname || '';
  return path.includes('/tenant') ? 'tenant' : 'admin';
}

export async function getUserSelectApi(params?: { search?: string }) {
  const prefix = getApiPrefix();
  try {
    if (prefix === 'admin') {
      const roots = await getAdminOrgRootsApi();
      const userMap = new Map<number, SelectableUser>();

      for (const root of roots || []) {
        let page = 1;

        while (true) {
          const response = await getAdminNodeMembersApi(root.id, {
            page,
            pageSize: ADMIN_USER_SELECT_PAGE_SIZE,
            includeDescendants: true,
            search: params?.search,
          });

          for (const user of response.items || []) {
            userMap.set(user.id, {
              id: user.id,
              nickname: user.nickname,
              username: user.username,
            });
          }

          const loadedCount = page * ADMIN_USER_SELECT_PAGE_SIZE;
          if (loadedCount >= response.total || response.items.length === 0) {
            break;
          }
          page += 1;
        }
      }

      return {
        items: [...userMap.values()].map((user) => ({
          id: user.id,
          value: user.id,
          label: user.nickname || user.username || String(user.id),
        })),
      };
    }

    const res = await getTenantUserListApi({
      page: 1,
      page_size: 500,
      ...params,
    } as Record<string, unknown>);
    return {
      items: (res.items || []).map(
        (user: { id: number; nickname?: string; username?: string }) => ({
          id: user.id,
          value: user.id,
          label: user.nickname || user.username || String(user.id),
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

export async function getDeptTreeApi() {
  const prefix = getApiPrefix();
  try {
    const roots =
      prefix === 'admin'
        ? await getAdminOrgRootsApi()
        : await getTenantOrgRootsApi();
    return {
      items: (roots || []).map((node: { id: number; name?: string }) => ({
        id: node.id,
        value: node.id,
        label: node.name || String(node.id),
      })),
    };
  } catch (error) {
    if (import.meta.env.DEV) {
      console.warn('[getDeptTreeApi]', error);
    }
    return { items: [] };
  }
}
