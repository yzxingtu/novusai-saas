/**
 * 租户端可用模型列表 - 表格列、搜索配置（只读）
 */
import { $t } from '#/locales';

/**
 * 获取模型类型文本
 */
export function getModelTypeText(type: string | undefined): string {
  if (!type) return '-';
  switch (type) {
    case 'chat': {
      return $t('tenant.ai.model.type_options.chat');
    }
    case 'embedding': {
      return $t('tenant.ai.model.type_options.embedding');
    }
    case 'image': {
      return $t('tenant.ai.model.type_options.image');
    }
    default: {
      return type;
    }
  }
}

/**
 * 格式化价格
 */
export function formatPrice(price: null | number | undefined): string {
  if (price === null || price === undefined) return '-';
  return `$${price}`;
}

export { formatTokens } from '#/utils/format';
