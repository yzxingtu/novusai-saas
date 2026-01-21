/**
 * Excel 导出弹窗 Composable
 *
 * 提供表格导出弹窗功能，与 ExportModal 组件配合使用
 *
 * @example
 * ```ts
 * const { ExportModal, openExportModal } = useExportModal(() => gridApi.grid);
 *
 * // 在模板中使用
 * <ExportModal />
 *
 * // 打开弹窗
 * openExportModal();
 * ```
 */
import type { VxeGridInstance } from 'vxe-table';

import { defineComponent, h, ref } from 'vue';

import ExportModalVue from './export-modal.vue';

type GridGetter = () => undefined | VxeGridInstance;

/**
 * 导出弹窗 Composable
 * @param gridGetter Grid 实例获取函数
 */
export function useExportModal(gridGetter: GridGetter) {
  // 存储 open 方法的引用
  const openFnRef = ref<(() => void) | null>(null);

  // 创建包装组件，传递 gridGetter 和 onRegister 回调
  const ExportModal = defineComponent({
    name: 'ExportModalWrapper',
    setup() {
      return () =>
        h(ExportModalVue, {
          gridGetter,
          onRegister: (openFn: () => void) => {
            openFnRef.value = openFn;
          },
        });
    },
  });

  /** 打开导出弹窗 */
  function openExportModal() {
    if (openFnRef.value) {
      openFnRef.value();
    } else {
      console.warn('[useExportModal] open function is not registered yet');
    }
  }

  return {
    /** 导出弹窗组件 */
    ExportModal,
    /** 打开导出弹窗 */
    openExportModal,
  };
}
