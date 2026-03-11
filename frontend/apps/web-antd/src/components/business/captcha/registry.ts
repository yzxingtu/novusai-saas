/**
 * Captcha Type Registry
 * Built-in image type; plugins can register new types (slider/puzzle/recaptcha, etc.)
 * 验证码类型注册表
 * 内置 image 类型，插件可注册新类型（slider/puzzle/recaptcha 等）
 */
import type { Component } from 'vue';

import type { CaptchaProviderType, CaptchaRegistryEntry } from './types';

const captchaRegistry = new Map<CaptchaProviderType, CaptchaRegistryEntry>();

/**
 * Register a captcha provider component
 * 注册验证码提供商组件
 * @param type - Captcha type identifier / 验证码类型标识
 * @param entry - Registry entry (component + optional label) / 注册项（组件 + 可选标签）
 */
export function registerCaptchaProvider(
  type: CaptchaProviderType,
  entry: CaptchaRegistryEntry | Component,
) {
  if ('component' in (entry as CaptchaRegistryEntry)) {
    captchaRegistry.set(type, entry as CaptchaRegistryEntry);
  } else {
    captchaRegistry.set(type, { component: entry as Component });
  }
}

/**
 * Get a captcha provider component
 * 获取验证码提供商组件
 * @param type - Captcha type identifier / 验证码类型标识
 * @returns Registry entry, undefined if not registered / 注册项，未注册返回 undefined
 */
export function getCaptchaProvider(
  type: CaptchaProviderType,
): CaptchaRegistryEntry | undefined {
  return captchaRegistry.get(type);
}

/**
 * Check if a captcha type is registered
 * 检查验证码类型是否已注册
 */
export function hasCaptchaProvider(type: CaptchaProviderType): boolean {
  return captchaRegistry.has(type);
}

/**
 * Get all registered captcha types
 * 获取所有已注册的验证码类型
 */
export function getRegisteredCaptchaTypes(): CaptchaProviderType[] {
  return [...captchaRegistry.keys()];
}
