/**
 * vxe-table built-in renderers: CellImage, CellLink, CellTag, CellSwitch, CellOperation, DragHandle
 * vxe-table 内置渲染器：包含 CellImage, CellLink, CellTag, CellSwitch, CellOperation, DragHandle
 */
import type { Recordable } from '@vben/types';

import { h } from 'vue';

import { IconifyIcon } from '@vben/icons';
import { $te } from '@vben/locales';
import { useAccessStore } from '@vben/stores';
import { get, isFunction, isString } from '@vben/utils';

import { objectOmit } from '@vueuse/core';
import {
  Button,
  Image,
  Popconfirm,
  Switch,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';
import { checkPermission } from '#/utils/access';

/**
 * Register all built-in renderers / 注册所有内置渲染器
 */
export function registerRenderers(vxeUI: any) {
  // Fix potential HMR errors / 解决热更新时可能会出错的问题
  vxeUI.renderer.forEach((_item: any, key: string) => {
    if (key.startsWith('Cell') || key === 'DragHandle') {
      vxeUI.renderer.delete(key);
    }
  });

  // Drag handle renderer / 拖拽手柄渲染器
  vxeUI.renderer.add('DragHandle', {
    renderTableDefault() {
      // Wrap with div to ensure .drag-handle class is on clickable element / 用 div 包裹确保 .drag-handle 类在可点击元素上
      return h(
        'div',
        {
          class:
            'drag-handle cursor-move flex items-center justify-center w-full h-full py-2',
        },
        [
          h(IconifyIcon, {
            icon: 'lucide:grip-vertical',
            class: 'text-gray-400 hover:text-gray-600 size-5',
          }),
        ],
      );
    },
  });

  // Image renderer / 图片渲染器
  vxeUI.renderer.add('CellImage', {
    renderTableDefault(renderOpts: any, params: any) {
      const { props } = renderOpts;
      const { column, row } = params;
      return h(Image, { src: row[column.field], ...props });
    },
  });

  // Link renderer / 链接渲染器
  vxeUI.renderer.add('CellLink', {
    renderTableDefault(renderOpts: any) {
      const { props } = renderOpts;
      return h(
        Button,
        { size: 'small', type: 'link' },
        { default: () => props?.text },
      );
    },
  });

  // Tag renderer / Tag 渲染器
  vxeUI.renderer.add('CellTag', {
    renderTableDefault({ options, props }: any, { column, row }: any) {
      const value = get(row, column.field);
      const tagOptions = options ?? [
        { color: 'success', label: $t('common.enabled'), value: 1 },
        { color: 'error', label: $t('common.disabled'), value: 0 },
      ];
      const tagItem = tagOptions.find((item: any) => item.value === value);
      return h(
        Tag,
        {
          ...props,
          ...objectOmit(tagItem ?? {}, ['label']),
        },
        { default: () => tagItem?.label ?? value },
      );
    },
  });

  // Switch renderer / Switch 渲染器
  vxeUI.renderer.add('CellSwitch', {
    renderTableDefault({ attrs, props }: any, { column, row }: any) {
      const loadingKey = `__loading_${column.field}`;
      const finallyProps = {
        checkedChildren: $t('common.enabled'),
        checkedValue: true,
        unCheckedChildren: $t('common.disabled'),
        unCheckedValue: false,
        ...props,
        ...attrs,
        checked: row[column.field],
        loading: row[loadingKey] ?? false,
        'onUpdate:checked': onChange,
      };
      async function onChange(newVal: any) {
        row[loadingKey] = true;
        try {
          const result = await attrs?.beforeChange?.(newVal, row);
          if (result !== false) {
            row[column.field] = newVal;
          }
        } finally {
          row[loadingKey] = false;
        }
      }
      return h(Switch, finallyProps);
    },
  });

  // Operation button renderer (with permission control) / 操作按钮渲染器（带权限控制）
  vxeUI.renderer.add('CellOperation', {
    renderTableDefault({ attrs, options }: any, { column, row }: any) {
      let align = 'end';
      switch (column.align) {
        case 'center': {
          align = 'center';
          break;
        }
        case 'left': {
          align = 'start';
          break;
        }
        default: {
          align = 'end';
          break;
        }
      }

      // Standard CRUD operation to permission action mapping / 标准 CRUD 操作与权限动作的映射
      const crudActionMap: Record<string, string> = {
        edit: 'update',
        delete: 'delete',
        create: 'create',
        view: 'read',
        detail: 'read',
      };

      // Preset operation config / 预设操作配置
      const presets: Recordable<Recordable<any>> = {
        delete: {
          danger: true,
          text: $t('common.delete'),
          icon: 'lucide:trash-2',
        },
        detail: {
          text: $t('common.detail'),
          icon: 'lucide:eye',
        },
        edit: {
          text: $t('common.edit'),
          icon: 'lucide:pencil',
        },
        resetPassword: {
          text: $t('common.resetPassword'),
          icon: 'lucide:key-round',
        },
      };

      // Get current user's permission codes / 获取当前用户的权限码
      const accessStore = useAccessStore();
      const userCodes = accessStore.accessCodes;
      const resource = attrs?.resource as string | undefined;

      // Calculate actual permission codes for operation buttons / 计算操作按钮的实际权限码
      function getAccessCodes(opt: Recordable<any>): string[] | undefined {
        if (opt.accessCodes) {
          return opt.accessCodes;
        }
        if (resource && crudActionMap[opt.code]) {
          return [`${resource}:${crudActionMap[opt.code]}`];
        }
        return undefined;
      }

      const operations: Array<Recordable<any>> = (options || ['edit', 'delete'])
        .map((opt: any) => {
          if (isString(opt)) {
            return presets[opt]
              ? { code: opt, ...presets[opt] }
              : {
                  code: opt,
                  text: $te(`common.${opt}`) ? $t(`common.${opt}`) : opt,
                };
          } else {
            return { ...presets[opt.code], ...opt };
          }
        })
        .map((opt: any) => {
          const optBtn: Recordable<any> = {};
          Object.keys(opt).forEach((key) => {
            optBtn[key] = isFunction(opt[key]) ? opt[key](row) : opt[key];
          });
          return optBtn;
        })
        .filter((opt: any) => opt.show !== false)
        .filter((opt: any) => checkPermission(getAccessCodes(opt), userCodes));

      // Render icon button (with Tooltip) / 渲染图标按钮（带 Tooltip）
      function renderIconBtn(opt: Recordable<any>, listen = true) {
        const iconBtn = h(
          Button,
          {
            type: 'text',
            size: 'small',
            danger: opt.danger,
            class: 'action-icon-btn',
            onClick: listen
              ? () => attrs?.onClick?.({ code: opt.code, row })
              : undefined,
          },
          {
            default: () =>
              h(IconifyIcon, {
                icon: opt.icon || 'lucide:circle',
                class: 'text-base',
              }),
          },
        );

        return h(
          Tooltip,
          { title: opt.text, placement: 'top' },
          { default: () => iconBtn },
        );
      }

      function renderConfirm(opt: Recordable<any>) {
        let viewportWrapper: HTMLElement | null = null;
        const iconBtn = h(
          Button,
          {
            type: 'text',
            size: 'small',
            danger: true,
            class: 'action-icon-btn',
          },
          {
            default: () =>
              h(IconifyIcon, {
                icon: opt.icon || 'lucide:trash-2',
                class: 'text-base',
              }),
          },
        );

        return h(
          Popconfirm,
          {
            getPopupContainer(el: HTMLElement) {
              viewportWrapper = el.closest('.vxe-table--viewport-wrapper');
              return document.body;
            },
            placement: 'topLeft',
            title: $t('ui.actionTitle.delete', [attrs?.nameTitle || '']),
            onOpenChange: (open: boolean) => {
              if (open) {
                viewportWrapper?.style.setProperty('pointer-events', 'none');
              } else {
                viewportWrapper?.style.removeProperty('pointer-events');
              }
            },
            onConfirm: () => {
              attrs?.onClick?.({ code: opt.code, row });
            },
          },
          {
            default: () =>
              h(
                Tooltip,
                { title: opt.text, placement: 'top' },
                { default: () => iconBtn },
              ),
            description: () =>
              h(
                'div',
                { class: 'truncate' },
                $t('ui.actionMessage.deleteConfirm', [
                  row[attrs?.nameField || 'name'],
                ]),
              ),
          },
        );
      }

      const btns = operations.map((opt) =>
        opt.code === 'delete' ? renderConfirm(opt) : renderIconBtn(opt),
      );

      return h(
        'div',
        {
          class: 'flex items-center gap-1 table-operations',
          style: { justifyContent: align },
        },
        btns,
      );
    },
  });
}
