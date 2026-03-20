import type { RouteRecordRaw } from 'vue-router';

import { LOGIN_PATH } from '@vben/constants';

import { $t } from '#/locales';

const AuthPageLayout = () => import('#/layouts/auth.vue');
/** Global 404 page / 全局 404 页面 */
const fallbackNotFoundRoute: RouteRecordRaw = {
  component: () => import('#/views/_core/fallback/not-found.vue'),
  meta: {
    hideInBreadcrumb: true,
    hideInMenu: true,
    hideInTab: true,
    title: '404',
  },
  name: 'FallbackNotFound',
  path: '/:path(.*)*',
};

/** Maintenance mode page / 维护模式页面 */
const maintenanceRoute: RouteRecordRaw = {
  component: () => import('#/views/_core/fallback/maintenance.vue'),
  meta: {
    hideInBreadcrumb: true,
    hideInMenu: true,
    hideInTab: true,
    title: 'Maintenance',
  },
  name: 'Maintenance',
  path: '/maintenance',
};

/** Core routes, these routes must always exist / 基本路由，这些路由是必须存在的 */
const coreRoutes: RouteRecordRaw[] = [
  maintenanceRoute,
  {
    component: AuthPageLayout,
    meta: {
      hideInTab: true,
      title: 'Authentication',
    },
    name: 'Authentication',
    path: '/auth',
    redirect: LOGIN_PATH,
    children: [
      {
        name: 'Login',
        path: 'login',
        component: () => import('#/views/user/authentication/login.vue'),
        meta: {
          title: $t('page.auth.login'),
        },
      },
      {
        name: 'CodeLogin',
        path: 'code-login',
        component: () => import('#/views/user/authentication/code-login.vue'),
        meta: {
          title: $t('page.auth.codeLogin'),
        },
      },
      {
        name: 'QrCodeLogin',
        path: 'qrcode-login',
        component: () =>
          import('#/views/user/authentication/qrcode-login.vue'),
        meta: {
          title: $t('page.auth.qrcodeLogin'),
        },
      },
      {
        name: 'ForgetPassword',
        path: 'forget-password',
        component: () =>
          import('#/views/user/authentication/forget-password.vue'),
        meta: {
          title: $t('page.auth.forgetPassword'),
        },
      },
      {
        name: 'Register',
        path: 'register',
        component: () => import('#/views/user/authentication/register.vue'),
        meta: {
          title: $t('page.auth.register'),
        },
      },
      {
        name: 'UserLegalPrivacy',
        path: 'legal/privacy',
        component: () =>
          import('#/views/user/authentication/legal-document.vue'),
        meta: {
          title: $t('user.auth.privacyPolicy'),
          /** 使用认证布局的「文档全宽」模式，避免挤在 420px 登录卡片内 */
          authDocumentPage: true,
        },
      },
      {
        name: 'UserLegalTerms',
        path: 'legal/terms',
        component: () =>
          import('#/views/user/authentication/legal-document.vue'),
        meta: {
          title: $t('user.auth.termsOfService'),
          authDocumentPage: true,
        },
      },
    ],
  },
];

export { coreRoutes, fallbackNotFoundRoute };
