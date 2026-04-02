/**
 * Shared plugin runtime contracts / 共享插件运行时契约
 */

/** Plugin slot data / 插件插槽数据 */
export interface PluginSlotData {
  frontend_runtime?: {
    dev_entry?: string;
    release_manifest?: string;
  };
  slot_type: string;
  plugin_name: string;
  name: string;
  component?: string;
  title?: Record<string, string> | string;
  sort_order?: number;
  scope?: string;
  path?: string;
  grid?: Record<string, number>;
  icon?: string;
  position?: string;
  event?: string;
  access_codes?: string[];
  ai?: {
    disabled_capabilities?: string[];
    disabled_operations?: string[];
    mode?: string;
    page_context_key?: string;
  };
  [key: string]: unknown;
}

/** Plugin slots response / 插件插槽响应 */
export interface PluginSlotsResponse {
  header_widgets: PluginSlotData[];
  dashboard_widgets: PluginSlotData[];
  settings_tabs: PluginSlotData[];
  floating_panels: PluginSlotData[];
  pages: PluginSlotData[];
  notification_ui: PluginSlotData[];
}
