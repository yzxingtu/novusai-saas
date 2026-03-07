/**
 * 验证码可扩展架构 — 类型定义
 */
import type { Component } from 'vue';

import type { CaptchaDifficulty } from '#/api/public/captcha';

/** 验证码端点类型 */
export type CaptchaEndpoint = 'admin' | 'tenant' | 'user';

/** 验证码提供商类型（内置 + 插件扩展） */
export type CaptchaProviderType =
  | 'hcaptcha'
  | 'image'
  | 'puzzle'
  | 'recaptcha'
  | 'slider'
  | 'turnstile'
  | (string & {});

/** 验证码操作类型 */
export type CaptchaAction = 'login' | 'register' | 'reset_password' | (string & {});

/** 验证码统一输出结果 */
export interface CaptchaResult {
  /** 挑战 ID（后端生成） */
  challengeId: string;
  /** 用户输入的验证码（图片类型）或 token（第三方类型） */
  captchaCode: string;
  /** 验证码提供商类型 */
  provider: CaptchaProviderType;
}

/** CaptchaProvider 组件 Props */
export interface CaptchaProviderProps {
  /** 端点标识 */
  endpoint: CaptchaEndpoint;
  /** 验证码提供商类型（从配置读取，默认 'image'） */
  provider?: CaptchaProviderType;
  /** 难度等级 */
  difficulty?: CaptchaDifficulty;
  /** 操作类型 */
  action?: CaptchaAction;
  /** 是否禁用 */
  disabled?: boolean;
}

/** 验证码适配器组件需要实现的接口 */
export interface CaptchaAdapterExpose {
  /** 刷新验证码 */
  refresh: () => void;
  /** 获取验证结果 */
  getResult: () => CaptchaResult | null;
}

/** 验证码注册表项 */
export interface CaptchaRegistryEntry {
  /** 组件 */
  component: Component;
  /** 显示名称（i18n key） */
  label?: string;
}
