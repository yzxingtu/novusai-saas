import SliderCaptcha from "./SliderCaptcha.vue";
import { enUS, zhCN } from "./locales";
import {
  getSliderCaptchaShared,
  SLIDER_CAPTCHA_LOCALE_PREFIX,
} from "./slider-captcha-shared";

const PROVIDER_CODE = "slider";

export function setup(): void {
  const shared = getSliderCaptchaShared();
  shared?.registerLocale?.("zh-CN", SLIDER_CAPTCHA_LOCALE_PREFIX, zhCN);
  shared?.registerLocale?.("zh", SLIDER_CAPTCHA_LOCALE_PREFIX, zhCN);
  shared?.registerLocale?.("en-US", SLIDER_CAPTCHA_LOCALE_PREFIX, enUS);
  shared?.registerLocale?.("en", SLIDER_CAPTCHA_LOCALE_PREFIX, enUS);
  shared?.registerCaptchaProvider?.(PROVIDER_CODE, SliderCaptcha);
}

export { SliderCaptcha };
