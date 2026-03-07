export { default as CaptchaImage } from './CaptchaImage.vue';
export { default as CaptchaImageForm } from './CaptchaImageForm.vue';
export { default as CaptchaProvider } from './CaptchaProvider.vue';
export {
  getCaptchaProvider,
  getRegisteredCaptchaTypes,
  hasCaptchaProvider,
  registerCaptchaProvider,
} from './registry';
export type {
  CaptchaAction,
  CaptchaAdapterExpose,
  CaptchaEndpoint,
  CaptchaProviderProps,
  CaptchaProviderType,
  CaptchaRegistryEntry,
  CaptchaResult,
} from './types';
