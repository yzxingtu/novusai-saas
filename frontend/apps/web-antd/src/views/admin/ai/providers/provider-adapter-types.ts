import type { AdapterTypeInfo } from '#/api/admin/ai-providers';

import { ref } from 'vue';

import { getAdapterTypesApi } from '#/api/admin/ai-providers';
import { $t } from '#/locales';

/** 缓存适配器类型列表 / Cached adapter type list */
const adapterTypesCache = ref<AdapterTypeInfo[]>([]);

function getFallbackAdapterTypes(): AdapterTypeInfo[] {
  return [
    {
      type: 'openai_compatible',
      source: 'builtin',
      display_name: $t('admin.ai.provider.type_options.openai_compatible'),
    },
  ];
}

function getResolvedAdapterTypes(): AdapterTypeInfo[] {
  return adapterTypesCache.value.length > 0
    ? adapterTypesCache.value
    : getFallbackAdapterTypes();
}

/** 加载适配器类型（含插件注册的） / Load adapter types (including plugin-registered) */
export async function loadAdapterTypes(): Promise<AdapterTypeInfo[]> {
  if (adapterTypesCache.value.length > 0) return adapterTypesCache.value;
  try {
    const data = await getAdapterTypesApi();
    adapterTypesCache.value = data;
    return data;
  } catch {
    const fallbackTypes = getFallbackAdapterTypes();
    adapterTypesCache.value = fallbackTypes;
    return fallbackTypes;
  }
}

export function getProviderTypeOptions() {
  return getResolvedAdapterTypes().map((adapterType) => ({
    label:
      adapterType.source === 'plugin'
        ? `${getProviderTypeText(adapterType.type)} (Plugin)`
        : getProviderTypeText(adapterType.type),
    value: adapterType.type,
  }));
}

export function hasMultipleAdapterTypeOptions(): boolean {
  return getProviderTypeOptions().length > 1;
}

export function getDefaultProviderType(): string {
  return getResolvedAdapterTypes()[0]?.type || 'openai_compatible';
}

/**
 * 获取供应商类型文本
 */
export function getProviderTypeText(type: string | undefined): string {
  if (!type) return '-';
  const cached = getResolvedAdapterTypes().find((item) => item.type === type);
  const cachedDisplayName = String(cached?.display_name || '').trim();
  if (cachedDisplayName && cachedDisplayName !== type) {
    return cachedDisplayName;
  }
  switch (type) {
    case 'openai_compatible': {
      return $t('admin.ai.provider.type_options.openai_compatible');
    }
    default: {
      return type;
    }
  }
}
