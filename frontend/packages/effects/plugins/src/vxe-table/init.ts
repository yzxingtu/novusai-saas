import type { SetupVxeTable } from './types';

import { defineComponent, watch } from 'vue';

import { i18n } from '@vben/locales';
import { preferences, usePreferences } from '@vben/preferences';

import { useVbenForm } from '@vben-core/form-ui';

import {
  VxeButton,
  VxeCheckbox,

  // 可选表单相关（按需取消注释）/ Optional form pieces from vxe-pc-ui
  // VxeFormGather,
  // VxeForm,
  // VxeFormItem,
  VxeIcon,
  VxeInput,
  VxeLoading,
  VxeMenu,
  VxeModal,
  VxeNumberInput,
  VxePager,
  // 以下组件未打包导入（按需启用）/ More vxe-pc-ui widgets (commented)
  // VxeList,
  // VxeModal,
  // VxeOptgroup,
  // VxeOption,
  // VxePulldown,
  // VxeRadio,
  // VxeRadioButton,
  VxeRadioGroup,
  VxeSelect,
  VxeTooltip,
  VxeUI,
  VxeUpload,
  // 末尾组件（注释）/ Tail widgets not imported
  // VxeSwitch,
  // VxeTextarea,
} from 'vxe-pc-ui';
import enUS from 'vxe-pc-ui/es/language/en-US';
// 导入默认的语言 / Default vxe-pc-ui locale bundles
import zhCN from 'vxe-pc-ui/es/language/zh-CN';
import {
  VxeColgroup,
  VxeColumn,
  VxeGrid,
  VxeTable,
  VxeToolbar,
} from 'vxe-table';

import { extendsDefaultFormatter } from './extends';

// 是否加载过 / One-time VxeUI registration guard
let isInit = false;

// eslint-disable-next-line import/no-mutable-exports / 允许运行时注入表单 / allow runtime injection
export let useTableForm: typeof useVbenForm;

const VXE_LOCALE_MAP = {
  'zh-CN': zhCN,
  'en-US': enUS,
} as const;

type SupportedVxeLocale = keyof typeof VXE_LOCALE_MAP;

function resolveVxeLocale(localeValue?: string): SupportedVxeLocale {
  if (localeValue && localeValue in VXE_LOCALE_MAP) {
    return localeValue as SupportedVxeLocale;
  }

  const fallbackLocale = preferences.app.locale;
  if (fallbackLocale in VXE_LOCALE_MAP) {
    return fallbackLocale as SupportedVxeLocale;
  }

  return 'zh-CN';
}

// 部分组件，如果没注册，vxe-table 会报错，这里实际没用组件，只是为了不报错，同时可以减少打包体积 / Stub unused Vxe types to satisfy runtime
const createVirtualComponent = (name = '') => {
  return defineComponent({
    name,
  });
};

export function initVxeTable() {
  if (isInit) {
    return;
  }

  VxeUI.component(VxeTable);
  VxeUI.component(VxeColumn);
  VxeUI.component(VxeColgroup);
  VxeUI.component(VxeGrid);
  VxeUI.component(VxeToolbar);

  VxeUI.component(VxeButton);
  // 可选注册（减小包体时可保持注释）/ Optional VxeUI registrations
  // VxeUI.component(VxeButtonGroup); / 可选
  VxeUI.component(VxeCheckbox);
  // VxeUI.component(VxeCheckboxGroup); / 可选
  VxeUI.component(createVirtualComponent('VxeForm'));
  // VxeUI.component(VxeFormGather); / 可选
  // VxeUI.component(VxeFormItem); / 可选
  VxeUI.component(VxeIcon);
  VxeUI.component(VxeInput);
  // VxeUI.component(VxeList); / 可选
  VxeUI.component(VxeLoading);
  VxeUI.component(VxeMenu);
  VxeUI.component(VxeModal);
  VxeUI.component(VxeNumberInput);
  // VxeUI.component(VxeOptgroup); / 可选
  // VxeUI.component(VxeOption); / 可选
  VxeUI.component(VxePager);
  // VxeUI.component(VxePulldown); / 可选
  // VxeUI.component(VxeRadio); / 可选
  // VxeUI.component(VxeRadioButton); / 可选
  VxeUI.component(VxeRadioGroup);
  VxeUI.component(VxeSelect);
  // VxeUI.component(VxeSwitch); / 可选
  // VxeUI.component(VxeTextarea); / 可选
  VxeUI.component(VxeTooltip);
  VxeUI.component(VxeUpload);

  isInit = true;
}

export function setupVbenVxeTable(setupOptions: SetupVxeTable) {
  const { configVxeTable, useVbenForm } = setupOptions;

  initVxeTable();
  useTableForm = useVbenForm;

  const { isDark } = usePreferences();

  watch(
    [() => isDark.value, () => resolveVxeLocale(i18n.global.locale.value)],
    ([isDarkValue, localeValue]) => {
      VxeUI.setTheme(isDarkValue ? 'dark' : 'light');
      VxeUI.setI18n(localeValue, VXE_LOCALE_MAP[localeValue]);
      VxeUI.setLanguage(localeValue);
    },
    {
      immediate: true,
    },
  );

  extendsDefaultFormatter(VxeUI);

  configVxeTable(VxeUI);
}
