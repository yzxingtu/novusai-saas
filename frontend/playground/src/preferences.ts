import { defineOverridesPreferences } from '@vben/preferences';

/**
 * @description 项目配置文件 / Project preference overrides
 * 只需要覆盖项目中的一部分配置，不需要的配置不用覆盖，会自动使用默认配置 / Merge with defaults; omit keys you do not override
 * !!! 更改配置后请清空缓存，否则可能不生效 / Clear cache after edits or changes may not apply
 */
export const overridesPreferences = defineOverridesPreferences({
  // overrides / 仅覆盖部分偏好 / partial preference overrides
  app: {
    name: import.meta.env.VITE_APP_TITLE,
  },
});
