/**
 * Excel export modal composable, works with ExportModal component
 * Excel 导出弹窗 Composable，与 ExportModal 组件配合使用
 *
 * @example
 * ```ts
 * const { ExportModal, openExportModal } = useExportModal(() => gridApi.grid);
 *
 * // Use in template / 在模板中使用
 * <ExportModal />
 *
 * // Open modal / 打开弹窗
 * openExportModal();
 * ```
 */
import type { VxeGridInstance } from 'vxe-table';

import { defineComponent, h, ref } from 'vue';

import ExportModalVue from './export-modal.vue';

type GridGetter = () => undefined | VxeGridInstance;

/**
 * Export modal composable / 导出弹窗 Composable
 * @param gridGetter Grid instance getter function / Grid 实例获取函数
 */
export function useExportModal(gridGetter: GridGetter) {
  // Store reference to open method / 存储 open 方法的引用
  const openFnRef = ref<(() => void) | null>(null);

  // Create wrapper component, pass gridGetter and onRegister callback / 创建包装组件，传递 gridGetter 和 onRegister 回调
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

  /** Open export modal / 打开导出弹窗 */
  function openExportModal() {
    if (openFnRef.value) {
      openFnRef.value();
    } else {
      console.warn('[useExportModal] open function is not registered yet');
    }
  }

  return {
    /** Export modal component / 导出弹窗组件 */
    ExportModal,
    /** Open export modal / 打开导出弹窗 */
    openExportModal,
  };
}
