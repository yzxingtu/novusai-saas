/**
 * 图标选择器初始化
 * 预加载 Lucide 图标集，确保图标选择器中的图标能够离线显示
 */
import { addCollection } from '@vben/icons';

// 导入 Lucide 图标集数据
import { icons as lucideIcons } from '@iconify-json/lucide';

let initialized = false;

/**
 * 初始化图标选择器所需的图标集
 * 只需调用一次，重复调用会被忽略
 */
export function setupIconPickerIcons() {
  if (initialized) return;

  // 预加载整个 Lucide 图标集（约 1500+ 图标）
  addCollection(lucideIcons);

  initialized = true;
}
