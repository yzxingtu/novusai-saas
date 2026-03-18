/**
 * 数据字典选项 / Dict Options
 *
 * 占位实现：当系统无 Dict 模块时返回空数组。
 * 待 Dict 模块就绪后接入真实 API（如 GET /admin/dict-items?dict_code=xxx）。
 *
 * Placeholder: returns empty array when no Dict module. Wire to real API when available.
 */
import { ref } from 'vue';
import type { Ref } from 'vue';

export interface DictOption {
  label: string;
  value: string | number;
}

export type DictOptionsFetcher = () => Promise<DictOption[] | { items: DictOption[] }>;

/**
 * 获取字典选项 API 函数 / Get dict options API function
 *
 * @param dictCode - 字典编码，如 sys_status, gender
 * @returns API 函数，供 ApiSelect 使用
 */
export function getDictOptionsApi(dictCode: string): DictOptionsFetcher {
  return async () => {
    // TODO: 当 Dict 模块就绪后，替换为真实请求，例如：
    // const res = await requestClient.get('/admin/dict-items', { params: { dict_code: dictCode } });
    // return { items: res.items ?? [] };
    if (import.meta.env.DEV && dictCode) {
      console.warn(
        `[useDictOptions] Dict module not yet integrated. dict_code="${dictCode}" returns empty options.`,
      );
    }
    return { items: [] };
  };
}

/**
 * 字典选项 Composable（供页面内使用）/ Dict options composable (for page usage)
 *
 * @param dictCode - 字典编码，支持 Ref
 * @returns 响应式选项列表
 */
export function useDictOptions(
  dictCode: Ref<string> | string,
): Ref<DictOption[]> {
  const code = typeof dictCode === 'string' ? dictCode : (dictCode as Ref<string>).value;
  // 占位：返回空数组。待 Dict 模块就绪后改为请求 API 并返回 computed。
  if (import.meta.env.DEV && code) {
    console.warn(
      `[useDictOptions] Dict module not yet integrated. dict_code="${code}" returns empty options.`,
    );
  }
  return ref<DictOption[]>([]);
}
