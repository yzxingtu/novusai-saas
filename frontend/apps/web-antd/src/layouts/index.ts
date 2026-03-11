/**
 * Layout components unified export
 * 布局组件统一导出
 */
const BasicLayout = () => import('./basic.vue');
const AuthPageLayout = () => import('./auth.vue');
const UserAuthLayout = () => import('./user-auth.vue');
const UserLayout = () => import('./user.vue');

const IFrameView = () => import('@vben/layouts').then((m) => m.IFrameView);

export { AuthPageLayout, BasicLayout, IFrameView, UserAuthLayout, UserLayout };
