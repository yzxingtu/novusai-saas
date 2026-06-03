import type { Component, DefineComponent } from 'vue';

import type {
  AccessModeType,
  GenerateMenuAndRoutesOptions,
  RouteRecordRaw,
} from '@vben/types';

import { defineComponent, h } from 'vue';

import {
  cloneDeep,
  generateMenus,
  generateRoutesByBackend,
  generateRoutesByFrontend,
  isFunction,
  isString,
  mapTree,
} from '@vben/utils';

async function generateAccessible(
  mode: AccessModeType,
  options: GenerateMenuAndRoutesOptions,
) {
  const { router } = options;

  options.routes = cloneDeep(options.routes);
  // 生成路由 / Build accessible route tree
  const accessibleRoutes = await generateRoutes(mode, options);

  // 多端根路由前缀 / Multi-endpoint: pick parent root from first dynamic path (/admin, /tenant, /)
  // Multi-endpoint support: determine the correct parent root route based on
  // the dynamic routes' path prefix. For /admin/* routes use AdminRoot,
  // for /tenant/* routes use TenantRoot, otherwise use the default root at '/'.
  let rootPath = '/';
  if (accessibleRoutes.length > 0) {
    const firstRoutePath = accessibleRoutes[0]?.path ?? '';
    if (firstRoutePath.startsWith('/admin')) {
      rootPath = '/admin';
    } else if (firstRoutePath.startsWith('/tenant')) {
      rootPath = '/tenant';
    }
  }
  const root = router.getRoutes().find((item) => item.path === rootPath);

  // 获取已有的路由名称列表
  const names = root?.children?.map((item) => item.name) ?? [];

  // 递归剔除无 component 的叶子路由，返回新对象（不修改原 accessibleRoutes，
  // 保证 generateMenus 仍能从原数组生成侧边栏菜单项）。
  // 场景：插件菜单挂载在 system_maintenance 等父级下，是嵌套子路由；
  //       其 component 为 undefined，若直接注册进 router 会触发
  //       "missing component" 警告并覆盖 registerPluginPageRoutes 注册的真实路由。
  function stripComponentlessLeaves(route: RouteRecordRaw): RouteRecordRaw {
    if (!route.children || route.children.length === 0) {
      return route;
    }
    const cleanedChildren = (route.children as RouteRecordRaw[])
      .filter((child) => {
        const isLeaf = !child.children || child.children.length === 0;
        return !isLeaf || !!child.component;
      })
      .map((child) => stripComponentlessLeaves(child));
    return { ...route, children: cleanedChildren };
  }

  // 动态添加到 router 实例内 / Register dynamic routes
  accessibleRoutes.forEach((route) => {
    if (root && !route.meta?.noBasicLayout) {
      // 为了兼容之前的版本用法，如果包含子路由，则将component移除，以免出现多层BasicLayout
      // 如果你的项目已经跟进了本次修改，移除了所有自定义菜单首级的BasicLayout，可以将这段if代码删除
      if (route.children && route.children.length > 0) {
        delete route.component;
      }
      // 无 component 且无子路由（如插件菜单）：跳过向 router 注册 / Skip bare group nodes
      const isComponentlessLeaf =
        !route.component && (!route.children || route.children.length === 0);
      if (isComponentlessLeaf) {
        return;
      }

      // 向 router 注册时，用剔除了无 component 叶子节点的副本 / Sanitized tree for addRoute
      const routeForRouter = stripComponentlessLeaves(route);

      // 根据 router name 判断，如果路由已经存在，则更新而非重复添加 / Upsert by name
      if (names?.includes(route.name)) {
        // 找到已存在的路由索引并更新；否则切换用户时一级菜单 stale 会 404 / Replace child at index
        const index = root.children?.findIndex(
          (item) => item.name === route.name,
        );
        if (index !== undefined && index !== -1 && root.children) {
          root.children[index] = routeForRouter;
        }
      } else {
        root.children?.push(routeForRouter);
      }
    } else {
      router.addRoute(route);
    }
  });

  if (root) {
    if (root.name) {
      router.removeRoute(root.name);
    }
    router.addRoute(root);
  }

  // 生成菜单 / Sidebar menus from raw routes
  const accessibleMenus = generateMenus(accessibleRoutes, options.router);

  return { accessibleMenus, accessibleRoutes };
}

/**
 * Generate routes
 * @param mode
 * @param options
 */
async function generateRoutes(
  mode: AccessModeType,
  options: GenerateMenuAndRoutesOptions,
) {
  const { forbiddenComponent, roles, routes } = options;

  let resultRoutes: RouteRecordRaw[] = routes;
  switch (mode) {
    case 'backend': {
      resultRoutes = await generateRoutesByBackend(options);
      break;
    }
    case 'frontend': {
      resultRoutes = await generateRoutesByFrontend(
        routes,
        roles || [],
        forbiddenComponent,
      );
      break;
    }
    case 'mixed': {
      const [frontend_resultRoutes, backend_resultRoutes] = await Promise.all([
        generateRoutesByFrontend(routes, roles || [], forbiddenComponent),
        generateRoutesByBackend(options),
      ]);

      resultRoutes = [...frontend_resultRoutes, ...backend_resultRoutes];
      break;
    }
  }

  /**
   * 调整路由树，做以下处理：
   * 1. 对未添加redirect的路由添加redirect
   * 2. 将懒加载的组件名称修改为当前路由的名称（如果启用了keep-alive的话）
   */
  resultRoutes = mapTree(resultRoutes, (route) => {
    // 重新包装 component，使用与路由名称相同的 name 以支持 keep-alive 条件缓存 / Align component name for KeepAlive
    if (
      route.meta?.keepAlive &&
      isFunction(route.component) &&
      route.name &&
      isString(route.name)
    ) {
      const originalComponent = route.component as () => Promise<{
        default: Component | DefineComponent;
      }>;
      route.component = async () => {
        const component = await originalComponent();
        if (!component.default) return component;
        return defineComponent({
          name: route.name as string,
          setup(props, { attrs, slots }) {
            return () => h(component.default, { ...props, ...attrs }, slots);
          },
        });
      };
    }

    // 如果有 redirect 或者没有子路由，则直接返回 / No redirect inference needed
    if (route.redirect || !route.children || route.children.length === 0) {
      return route;
    }
    const firstChild = route.children[0];

    // 子路由非绝对路径则跳过（需拼接父 path）/ Skip relative child paths
    if (!firstChild?.path || !firstChild.path.startsWith('/')) {
      return route;
    }

    route.redirect = firstChild.path;
    return route;
  });

  return resultRoutes;
}

export { generateAccessible };
