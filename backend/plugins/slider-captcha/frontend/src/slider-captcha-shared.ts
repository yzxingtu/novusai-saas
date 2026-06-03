import type { SliderCaptchaSharedAPI } from "./types";

export const SLIDER_CAPTCHA_LOCALE_PREFIX = "plugin.slider-captcha";

export function getSliderCaptchaShared(): SliderCaptchaSharedAPI | undefined {
  return (window as unknown as { NovusPluginShared?: SliderCaptchaSharedAPI })
    .NovusPluginShared;
}
