import type { InjectionKey } from 'vue';

import type { usePluginConfigDrawer } from './use-plugin-config-drawer';

import { inject, provide } from 'vue';

type PluginConfigDrawerContext = ReturnType<typeof usePluginConfigDrawer>;

const pluginConfigDrawerContextSymbol: InjectionKey<PluginConfigDrawerContext> =
  Symbol('plugin-config-drawer-context');

export function providePluginConfigDrawerContext(
  context: PluginConfigDrawerContext,
) {
  provide(pluginConfigDrawerContextSymbol, context);
}

export function usePluginConfigDrawerContext() {
  const context = inject(pluginConfigDrawerContextSymbol);
  if (!context) {
    throw new Error('Plugin config drawer context is not provided');
  }
  return context;
}
