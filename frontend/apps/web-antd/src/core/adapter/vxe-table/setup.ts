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
          stripe: true, // 默认启用斑马纹（交替行背景色）
          columnConfig: {
            resizable: true,
          },
          minHeight: 180,
          formConfig: {
            // 全局禁用 vxe-table 的表单配置，使用 formOptions
            enabled: false,
          },
          pagerConfig: {
            pageSize: 10,
            pageSizes: [10, 20, 50, 100],
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
          // 导出配置（仅支持 csv）
          exportConfig: {
            type: 'csv',
          },
          round: true,
          showOverflow: true,
          size: 'small',
        } as VxeTableGridOptions,
      });

      // 注册所有渲染器
      registerRenderers(vxeUI);
    },
    useVbenForm,
  });
}
