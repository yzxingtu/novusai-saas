import SliderCaptcha from './SliderCaptcha.vue';
import { enUS, zhCN } from './locales';
import type { SliderCaptchaSharedAPI } from './types';

const PROVIDER_CODE = 'slider';
const LOCALE_PREFIX = 'plugin.slider-captcha';

function getShared(): SliderCaptchaSharedAPI | undefined {
  return (window as unknown as { NovusPluginShared?: SliderCaptchaSharedAPI })
    .NovusPluginShared;
}

export function setup(): void {
  const shared = getShared();
  shared?.registerLocale?.('zh-CN', LOCALE_PREFIX, zhCN);
  shared?.registerLocale?.('zh', LOCALE_PREFIX, zhCN);
  shared?.registerLocale?.('en-US', LOCALE_PREFIX, enUS);
  shared?.registerLocale?.('en', LOCALE_PREFIX, enUS);
  shared?.registerCaptchaProvider?.(PROVIDER_CODE, SliderCaptcha);
}

export { SliderCaptcha };
