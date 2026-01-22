/**
 * Vue 文件类型声明
 * 用于 TypeScript 识别 .vue 文件的导入
 */
declare module '*.vue' {
  import type { DefineComponent } from 'vue';

  const component: DefineComponent<object, object, any>;
  export default component;
}
