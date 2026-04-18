import type { UIComponentAdapter } from '../types';
import type { CreateVueRouterAdapterOptions } from './vue-router';

import { ANTD_BUTTON_ADAPTER_ID, createAntdButtonAdapter } from './antd-button';
import { ANTD_DRAWER_ADAPTER_ID, createAntdDrawerAdapter } from './antd-drawer';
import { ANTD_MENU_ADAPTER_ID, createAntdMenuAdapter } from './antd-menu';
import { ANTD_MODAL_ADAPTER_ID, createAntdModalAdapter } from './antd-modal';
import {
  ANTD_PAGINATION_ADAPTER_ID,
  createAntdPaginationAdapter,
} from './antd-pagination';
import { ANTD_TABLE_ADAPTER_ID, createAntdTableAdapter } from './antd-table';
import { ANTD_TABS_ADAPTER_ID, createAntdTabsAdapter } from './antd-tabs';
import {
  createVueRouterAdapter,
  routeToPageSurface,
  VUE_ROUTER_ADAPTER_ID,
} from './vue-router';

export {
  ANTD_BUTTON_ADAPTER_ID,
  ANTD_DRAWER_ADAPTER_ID,
  ANTD_MENU_ADAPTER_ID,
  ANTD_MODAL_ADAPTER_ID,
  ANTD_PAGINATION_ADAPTER_ID,
  ANTD_TABLE_ADAPTER_ID,
  ANTD_TABS_ADAPTER_ID,
  VUE_ROUTER_ADAPTER_ID,
};
export {
  createAntdButtonAdapter,
  createAntdDrawerAdapter,
  createAntdMenuAdapter,
  createAntdModalAdapter,
  createAntdPaginationAdapter,
  createAntdTableAdapter,
  createAntdTabsAdapter,
  createVueRouterAdapter,
  routeToPageSurface,
};
export type { CreateVueRouterAdapterOptions };
export { type UIComponentAdapter };

export interface CreateDefaultAdaptersOptions {
  router?: CreateVueRouterAdapterOptions;
}

export const DEFAULT_COMPONENT_ADAPTER_PRIORITIES = {
  [ANTD_BUTTON_ADAPTER_ID]: 50,
  [ANTD_DRAWER_ADAPTER_ID]: 75,
  [ANTD_MENU_ADAPTER_ID]: 65,
  [ANTD_MODAL_ADAPTER_ID]: 80,
  [ANTD_PAGINATION_ADAPTER_ID]: 58,
  [ANTD_TABLE_ADAPTER_ID]: 68,
  [ANTD_TABS_ADAPTER_ID]: 60,
  [VUE_ROUTER_ADAPTER_ID]: 100,
} as const;

export function createDefaultComponentAdapters(
  options: CreateDefaultAdaptersOptions = {},
): UIComponentAdapter[] {
  return [
    createVueRouterAdapter(
      options.router,
      DEFAULT_COMPONENT_ADAPTER_PRIORITIES[VUE_ROUTER_ADAPTER_ID],
    ),
    createAntdModalAdapter(
      DEFAULT_COMPONENT_ADAPTER_PRIORITIES[ANTD_MODAL_ADAPTER_ID],
    ),
    createAntdDrawerAdapter(
      DEFAULT_COMPONENT_ADAPTER_PRIORITIES[ANTD_DRAWER_ADAPTER_ID],
    ),
    createAntdMenuAdapter(
      DEFAULT_COMPONENT_ADAPTER_PRIORITIES[ANTD_MENU_ADAPTER_ID],
    ),
    createAntdTableAdapter(
      DEFAULT_COMPONENT_ADAPTER_PRIORITIES[ANTD_TABLE_ADAPTER_ID],
    ),
    createAntdTabsAdapter(
      DEFAULT_COMPONENT_ADAPTER_PRIORITIES[ANTD_TABS_ADAPTER_ID],
    ),
    createAntdPaginationAdapter(
      DEFAULT_COMPONENT_ADAPTER_PRIORITIES[ANTD_PAGINATION_ADAPTER_ID],
    ),
    createAntdButtonAdapter(
      DEFAULT_COMPONENT_ADAPTER_PRIORITIES[ANTD_BUTTON_ADAPTER_ID],
    ),
  ];
}
