import type { Component } from 'vue';

export interface CaptchaRegistryEntry {
  component: Component;
  label?: string;
}

export interface SliderCaptchaRequestClient {
  post<T>(
    url: string,
    data?: unknown,
    options?: Record<string, unknown>,
  ): Promise<T>;
}

export interface SliderCaptchaSharedAPI {
  $t?: (key: string, params?: Record<string, unknown>) => string;
  requestClient?: SliderCaptchaRequestClient;
  registerCaptchaProvider?: (
    type: string,
    entry: CaptchaRegistryEntry | Component,
  ) => void;
  registerLocale?: (
    locale: string,
    prefix: string,
    messages: Record<string, unknown>,
  ) => void;
}
