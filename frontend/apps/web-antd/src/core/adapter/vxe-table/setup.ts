/**
 * vxe-table 全局配置和初始化
 */
import type { VxeTableGridOptions } from '@vben/plugins/vxe-table';

import { setupVbenVxeTable } from '@vben/plugins/vxe-table';

import { useVbenForm } from '../form';
import { registerRenderers } from './renderers';

/**
 * 初始化 vxe-table
 * 在应用启动时调用
 */
export function setupVxeTable() {
  setupVbenVxeTable({
    configVxeTable: (vxeUI) => {
      // 全局配置
      vxeUI.setConfig({
        grid: {
          align: 'center',
          border: false,
          stripe: true,
          columnConfig: {
            resizable: true,
          },
          minHeight: 180,
          formConfig: {
            enabled: false,
          },
          pagerConfig: {
            pageSize: 15,
            pageSizes: [10, 15, 20, 50, 100],
          },
          proxyConfig: {
            autoLoad: true,
            response: {
              result: 'items',
              total: 'total',
              list: 'items',
            },
            showActiveMsg: true,
            showResponseMsg: false,
          },
          exportConfig: {
            type: 'csv',
          },
          round: true,
          showOverflow: true,
          size: 'medium',
        } as VxeTableGridOptions,
      });

      // 注册所有渲染器
      registerRenderers(vxeUI);
    },
    useVbenForm,
  });
}
