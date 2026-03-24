import type { Router } from 'vue-router';

import type { ApiEndpoint } from '#/api';

import { preferences } from '@vben/preferences';
import { useAccessStore, useTabbarStore, useUserStore } from '@vben/stores';
import { startProgress, stopProgress } from '@vben/utils';

import {
  HOME_PATHS,
  LOGIN_PATHS,
  normalizeEndpointNavigationPath,
  resolveEndpointByPath,
  resolveHomePathByPath,
  resolveLoginPathByPath,
} from '#/constants/endpoints';
import { accessRoutes, coreRouteNames } from '#/router/routes';
import { TokenStorage, useMultiAuthStore, usePublicConfigStore } from '#/store';
import { shouldRequestTenantPublicConfig } from '#/utils/public-config-domain';

import { generateAccess } from './access';

/** Get login path for the endpoint matching the route path / 根据路由路径获取对应端的登录路径 */
function getLoginPathByRoute(path: string): string {
  return resolveLoginPathByPath(path);
}

/** Get home path for the endpoint matching the route path / 根据路由路径获取对应端的首页路径 */
function getHomePathByRoute(path: string): string {
  return resolveHomePathByPath(path);
}

/** Resolve endpoint with optional domain detection override for root path / 根路径结合域名检测结果解析端 */
function resolveEndpointForPath(
  path: string,
  isDomainDetected: boolean,
  isDomainTenantDomain: boolean | null,
): ApiEndpoint {
  const [pathname = ''] = String(path || '').split(/[?#]/, 1);
  const normalizedPath = pathname || '/';
  if (normalizedPath === '/' && isDomainDetected) {
    return isDomainTenantDomain ? 'user' : 'admin';
  }
  return resolveEndpointByPath(normalizedPath);
}

/** Check if the path is a login page / 判断是否是登录页面 */
function isLoginPath(path: string): boolean {
  return Object.values(LOGIN_PATHS).includes(path);
}

/**
 * Common guard configuration
 * 通用守卫配置
 * @param router
 */
function setupCommonGuard(router: Router) {
  // 记录已经加载的页面 / track loaded paths for transition skip
  const loadedPaths = new Set<string>();

  router.beforeEach((to) => {
    to.meta.loaded = loadedPaths.has(to.path);

    // 页面加载进度条 / NProgress on first paint
    if (!to.meta.loaded && preferences.transition.progress) {
      startProgress();
    }
    return true;
  });

  router.afterEach((to) => {
    // 记录页面是否加载,如果已经加载，后续的页面切换动画等效果不在重复执行 / mark visited; skip repeat enter effects

    loadedPaths.add(to.path);

    // 关闭页面加载进度条 / stop NProgress
    if (preferences.transition.progress) {
      stopProgress();
    }
  });
}

// Record last endpoint type for detecting endpoint switches / 记录上一次的端类型，用于检测端切换
let lastEndpoint: ApiEndpoint | null = null;

function pluginLeafRouteNeedsBootstrap(to: {
  matched: Array<{ components?: null | Record<string, unknown> }>;
}): boolean {
  const leafRecord = to.matched.at(-1);
  if (!leafRecord) {
    return true;
  }
  const components = leafRecord.components;
  if (!components) {
    return true;
  }
  return Object.values(components).every((component) => !component);
}

/**
 * Reset endpoint type record (called on logout to avoid stale state during HMR or session switching)
 * 重置端类型记录（登出时调用，避免 HMR 或会话切换时的残留状态）
 */
export function resetLastEndpoint() {
  lastEndpoint = null;
}

/**
 * Access permission guard configuration
 * 权限访问守卫配置
 * @param router
 */
function setupAccessGuard(router: Router) {
  router.beforeEach(async (to, from) => {
    const accessStore = useAccessStore();
    const userStore = useUserStore();
    const multiAuthStore = useMultiAuthStore();
    const publicConfigStore = usePublicConfigStore();
    const requiredAccessCodes = Array.isArray(to.meta.accessCodes)
      ? to.meta.accessCodes.filter(Boolean)
      : [];
    const hasRouteAccess = () => {
      if (requiredAccessCodes.length === 0) {
        return true;
      }
      const codes = accessStore.accessCodes;
      // Super admin wildcard — consistent with checkPermission() / 超管通配符，与 checkPermission() 保持一致
      if (codes.includes('*')) {
        return true;
      }
      const codeSet = new Set(codes);
      const mode = to.meta.accessCodesMode === 'all' ? 'all' : 'any';
      return mode === 'all'
        ? requiredAccessCodes.every((code) => codeSet.has(code))
        : requiredAccessCodes.some((code) => codeSet.has(code));
    };
    const resetEndpointSession = (endpoint: ApiEndpoint) => {
      TokenStorage.clearToken(endpoint);
      accessStore.setAccessToken(null);
      accessStore.setRefreshToken(null);
      accessStore.setLoginExpired(false);
      accessStore.setAccessMenus([]);
      accessStore.setAccessRoutes([]);
      accessStore.setAccessCodes([]);
      accessStore.setIsAccessChecked(false);
      userStore.setUserInfo(null);
    };

    // 获取当前路由对应的端类型、登录路径和首页路径 / resolve endpoint + login/home paths
    let currentEndpoint: ApiEndpoint = resolveEndpointByPath(to.path);
    let currentLoginPath = getLoginPathByRoute(to.path);
    let currentHomePath = getHomePathByRoute(to.path);

    // ── 域名类型检测（幂等，仅首次导航发一次请求） / domain detect (once) ──
    await publicConfigStore.detectDomainType().catch(() => {});

    currentEndpoint = resolveEndpointForPath(
      to.path,
      publicConfigStore.isDomainDetected,
      publicConfigStore.isDomainTenantDomain,
    );
    currentLoginPath = LOGIN_PATHS[currentEndpoint];
    currentHomePath = normalizeEndpointNavigationPath(
      HOME_PATHS[currentEndpoint],
      currentEndpoint,
    );

    const isPlatformDomain =
      publicConfigStore.isDomainDetected &&
      publicConfigStore.isDomainTenantDomain === false;
    if (currentEndpoint === 'user' && isPlatformDomain) {
      return { path: '/', replace: true };
    }

    // 首次访问时加载对应端的公开配置（品牌、验证码等） / load public config per endpoint
    if (currentEndpoint === 'admin') {
      if (!publicConfigStore.platformConfigLoaded) {
        // 平台端：加载平台公开配置 / admin: platform public config
        await publicConfigStore.loadPlatformConfig().catch((error) => {
          console.warn('[Router Guard] 加载平台公开配置失败:', error);
        });
      } else if (publicConfigStore.platformConfig?.brand) {
        // 如果已加载，确保应用当前端的品牌配置（处理端切换时的缓存问题） / re-apply brand on endpoint switch
        publicConfigStore.applyBrandConfig(
          publicConfigStore.platformConfig.brand,
        );
      }
    } else if (
      (currentEndpoint === 'tenant' || currentEndpoint === 'user') &&
      shouldRequestTenantPublicConfig(
        publicConfigStore.isDomainDetected,
        publicConfigStore.isDomainTenantDomain,
      )
    ) {
      if (!publicConfigStore.tenantConfigLoaded) {
        // 企业端 / 用户端：加载企业公开配置（用户属于企业，复用企业配置） / tenant+user: tenant public config
        await publicConfigStore.loadTenantConfig().catch((error) => {
          console.warn('[Router Guard] 加载企业公开配置失败:', error);
        });
      } else if (publicConfigStore.tenantConfig?.brand) {
        // 如果已加载，确保应用当前端的品牌配置（处理端切换时的缓存问题） / re-apply tenant brand
        publicConfigStore.applyBrandConfig(
          publicConfigStore.tenantConfig.brand,
        );
      }
    }

    // 维护模式检查：配置加载后检查是否处于维护状态
    // 管理端（/admin/*）始终放行，确保管理员可以登录后台关闭维护模式
    const isMaintenancePage = to.path === '/maintenance';
    const maintenanceEnabled =
      publicConfigStore.platformConfig?.maintenance?.enabled ||
      publicConfigStore.tenantConfig?.maintenance?.enabled;
    const isAdminRoute = currentEndpoint === 'admin';

    if (
      maintenanceEnabled &&
      !isMaintenancePage &&
      !isAdminRoute &&
      !isLoginPath(to.path)
    ) {
      return {
        path: '/maintenance',
        query: { from: currentEndpoint },
        replace: true,
      };
    }
    // 维护模式已关闭但用户仍在维护页面，重定向回首页 / maintenance off → leave maintenance page
    if (!maintenanceEnabled && isMaintenancePage) {
      const fromEndpoint = (to.query.from as string) || '';
      const homePath =
        fromEndpoint && HOME_PATHS[fromEndpoint as ApiEndpoint]
          ? normalizeEndpointNavigationPath(
              HOME_PATHS[fromEndpoint as ApiEndpoint],
              fromEndpoint as ApiEndpoint,
            )
          : currentHomePath;
      return { path: homePath, replace: true };
    }

    // 检测端切换：如果端类型变化，需要重新生成路由和权限 / endpoint switch → reset access
    if (lastEndpoint && lastEndpoint !== currentEndpoint) {
      accessStore.setIsAccessChecked(false);
      accessStore.setAccessMenus([]);
      accessStore.setAccessRoutes([]);
      // 清除权限码，避免使用旧端的权限 / drop stale access codes
      accessStore.setAccessCodes([]);

      const { resetPluginRoutesReady } =
        await import('#/composables/use-plugin-frontend-init');
      resetPluginRoutesReady(router);
    }
    lastEndpoint = currentEndpoint;

    // 从 TokenStorage 获取当前端的 Token（多端分离存储）
    const currentToken = TokenStorage.getToken(currentEndpoint);

    // 基本路由，这些路由不需要进入权限拦截 / core routes bypass full access pipeline
    if (coreRouteNames.includes(to.name as string)) {
      // 如果当前端已登录且访问登录页，重定向到对应端的首页 / logged-in → skip login shell
      if (isLoginPath(to.path) && currentToken) {
        const redirectPath = to.query?.redirect as string | undefined;
        if (redirectPath) {
          const normalizedRedirectPath = normalizeEndpointNavigationPath(
            redirectPath,
            currentEndpoint,
          );
          // 防止跨端重定向死循环：如果重定向目标属于另一个端且该端没有 Token，
          // 则留在登录页（允许用户登录目标端），而不是跟随 redirect 导致死循环
          const redirectEndpoint = resolveEndpointForPath(
            normalizedRedirectPath,
            publicConfigStore.isDomainDetected,
            publicConfigStore.isDomainTenantDomain,
          );
          if (
            redirectEndpoint !== currentEndpoint &&
            !TokenStorage.getToken(redirectEndpoint)
          ) {
            return true;
          }
          return normalizedRedirectPath;
        }
        return normalizeEndpointNavigationPath(
          userStore.userInfo?.homePath,
          currentEndpoint,
        );
      }
      return true;
    }

    // Token 检查（使用当前端的 Token）
    if (!currentToken) {
      // 明确声明忽略权限访问权限，则可以访问 / ignoreAccess meta bypass
      if (to.meta.ignoreAccess) {
        return true;
      }

      // 没有访问权限，跳转到对应端的登录页面 / no token → login
      if (!isLoginPath(to.path)) {
        return {
          path: currentLoginPath,
          query:
            to.fullPath === currentHomePath ? {} : { redirect: to.fullPath },
          replace: true,
        };
      }
      return to;
    }

    // 同步 Token 到 accessStore（兼容 vben 框架组件）
    if (accessStore.accessToken !== currentToken) {
      accessStore.setAccessToken(currentToken);
      const refreshToken = TokenStorage.getRefreshToken(currentEndpoint);
      if (refreshToken) {
        accessStore.setRefreshToken(refreshToken);
      }
    }

    // 是否已经生成过动态路由 / dynamic routes already built
    if (accessStore.isAccessChecked) {
      // 插件路由可能还未注册（layout onMounted 异步注册），
      // 如果目标是插件 URL，但当前仍是占位菜单路由或 404，在 guard 中同步注册插件路由
      const isPluginPath = /\/(?:tenant|admin)\/plugins\//.test(to.path);
      if (
        isPluginPath &&
        (to.name === 'FallbackNotFound' || pluginLeafRouteNeedsBootstrap(to))
      ) {
        const { ensurePluginRoutes } =
          await import('#/composables/use-plugin-frontend-init');
        await ensurePluginRoutes(router, to.path);
        // 路由注册后重新解析 / re-resolve after plugin routes
        const resolved = router.resolve(to.fullPath);
        if (resolved.name !== 'FallbackNotFound') {
          return { ...resolved, replace: true };
        }
      }
      if (!hasRouteAccess()) {
        return { path: currentHomePath, replace: true };
      }
      return true;
    }

    // 生成路由表
    // 当前登录用户拥有的角色标识列表
    // 注意：必须传入 endpoint 参数，因为 route.path 可能还是旧路由
    let userInfo;
    try {
      userInfo =
        userStore.userInfo ||
        (await multiAuthStore.fetchUserInfo(currentEndpoint));
    } catch (error) {
      // 获取用户信息失败（可能是 Token 过期），清除 Token 并跳转到登录页
      console.error('[Router Guard] 获取用户信息失败:', error);
      resetEndpointSession(currentEndpoint);
      if (to.meta.ignoreAccess) {
        return true;
      }
      return {
        path: currentLoginPath,
        query: { redirect: to.fullPath },
        replace: true,
      };
    }

    const userRoles = userInfo.roles ?? [];

    // 生成菜单和路由（根据端类型获取对应的菜单） / build menus+routes for endpoint
    let accessibleMenus;
    let accessibleRoutes;
    try {
      const result = await generateAccess(
        {
          roles: userRoles,
          router,
          routes: accessRoutes,
        },
        currentEndpoint,
      );
      accessibleMenus = result.accessibleMenus;
      accessibleRoutes = result.accessibleRoutes;
    } catch (error) {
      console.error('[Router Guard] 生成菜单路由失败:', error);
      // 菜单 API 可能返回 401 触发 doReAuthenticate；
      // 此处兜底：清 token 并跳登录，避免死循环
      resetEndpointSession(currentEndpoint);
      if (to.meta.ignoreAccess) {
        return true;
      }
      return {
        path: currentLoginPath,
        query: to.fullPath === currentHomePath ? {} : { redirect: to.fullPath },
        replace: true,
      };
    }

    // 保存菜单信息和路由信息 / persist menus + routes
    accessStore.setAccessMenus(accessibleMenus);
    accessStore.setAccessRoutes(accessibleRoutes);
    accessStore.setIsAccessChecked(true);
    if (!hasRouteAccess()) {
      return { path: currentHomePath, replace: true };
    }

    const redirectPath = normalizeEndpointNavigationPath(
      (from.query.redirect ??
        (to.path === currentHomePath
          ? userInfo.homePath
          : to.fullPath)) as string,
      currentEndpoint,
    );

    // 插件路由在 guard 中同步注册（无感方式，不跳转首页）
    const isPluginRedirect = /\/(?:tenant|admin)\/plugins\//.test(redirectPath);
    if (isPluginRedirect) {
      try {
        const { ensurePluginRoutes } =
          await import('#/composables/use-plugin-frontend-init');
        await ensurePluginRoutes(router, redirectPath);
      } catch (error) {
        console.warn(
          '[Router Guard] ensurePluginRoutes failed, redirecting to home:',
          error,
        );
        return { path: currentHomePath, replace: true };
      }
    }

    return {
      ...router.resolve(redirectPath),
      replace: true,
    };
  });
}

/**
 * Tabbar guard configuration
 * Handles multi-endpoint tab isolation
 * 标签页守卫配置
 * 处理多端标签页隔离
 * @param router
 */
function setupTabbarGuard(router: Router) {
  router.beforeEach(async (to) => {
    const tabbarStore = useTabbarStore();
    const publicConfigStore = usePublicConfigStore();

    await publicConfigStore.detectDomainType().catch(() => {});

    const currentEndpoint = resolveEndpointForPath(
      to.path,
      publicConfigStore.isDomainDetected,
      publicConfigStore.isDomainTenantDomain,
    );

    // 获取当前不需要显示的标签页（非当前端） / tabs from other endpoints
    const tabs = tabbarStore.getTabs;
    const invalidTabs = tabs.filter((tab) => {
      const tabEndpoint = resolveEndpointForPath(
        tab.path,
        publicConfigStore.isDomainDetected,
        publicConfigStore.isDomainTenantDomain,
      );
      // 忽略 core 路由（如 login, 404 等），它们可能被视为 'user' 但在各端都可能出现
      // 但实际上 login 页面有明确的端路径 (/admin/login, /tenant/login)
      // 只有 404 或 root 可能是通用的
      // 这里简单判断：如果 tabEndpoint 不等于 currentEndpoint，且不是公共路由，则关闭
      return tabEndpoint !== currentEndpoint;
    });

    // 批量关闭非当前端的标签页 / bulk close foreign tabs
    if (invalidTabs.length > 0) {
      const keys = invalidTabs.map((tab) => tab.key as string).filter(Boolean);
      if (keys.length > 0) {
        await tabbarStore._bulkCloseByKeys(keys);
      }
    }

    return true;
  });
}

/**
 * Project guard configuration
 * 项目守卫配置
 * @param router
 */
function createRouterGuard(router: Router) {
  /** Common / 通用 */
  setupCommonGuard(router);
  /** Access permission / 权限访问 */
  setupAccessGuard(router);
  /** Tab isolation / 标签页隔离 */
  setupTabbarGuard(router);
}

export { createRouterGuard };
