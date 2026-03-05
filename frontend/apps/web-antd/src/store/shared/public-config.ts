/**
 * 公开配置 Store
 * 存储平台/租户的公开配置（品牌、验证码等）
 */
import type {
  BrandConfig,
  CaptchaConfig,
  PlatformPublicConfig,
  TenantPublicConfig,
} from '#/api/public/config';

import { updatePreferences } from '@vben/preferences';

import { defineStore } from 'pinia';

import {
  getPlatformPublicConfigApi,
  getTenantPublicConfigApi,
} from '#/api/public/config';

/**
 * 更新页面 Head 信息 (Favicon, Meta Description)
 */
function updateHead(brand: BrandConfig) {
  // Update Favicon
  if (brand.favicon) {
    let link = document.querySelector("link[rel~='icon']") as HTMLLinkElement;
    if (!link) {
      link = document.createElement('link');
      link.rel = 'icon';
      document.head.append(link);
    }
    link.href = brand.favicon;
  }

  // Update Meta Description
  if (brand.siteDescription) {
    let meta = document.querySelector(
      "meta[name='description']",
    ) as HTMLMetaElement;
    if (!meta) {
      meta = document.createElement('meta');
      meta.name = 'description';
      document.head.append(meta);
    }
    meta.content = brand.siteDescription;
  }
}

/**
 * 应用品牌配置到全局偏好设置
 */
function applyBrandConfig(brand: BrandConfig) {
  updatePreferences({
    app: {
      name: brand.siteName,
    },
    logo: {
      source: brand.logo,
      sourceDark: brand.logoDark,
    },
    copyright: {
      companyName: brand.copyright,
      icp: brand.icp,
    },
    theme: {
      colorPrimary: brand.primaryColor,
    },
  });
  updateHead(brand);
}

// ============================================================
// 类型定义
// ============================================================

interface PublicConfigState {
  /** 平台公开配置 */
  platformConfig: null | PlatformPublicConfig;
  /** 租户公开配置 */
  tenantConfig: null | TenantPublicConfig;
  /** 平台配置是否已加载 */
  platformConfigLoaded: boolean;
  /** 租户配置是否已加载 */
  tenantConfigLoaded: boolean;
  /** 加载中状态 */
  loading: boolean;
  /** 错误信息 */
  error: null | string;
  /** 平台端登录失败次数 */
  platformLoginFailCount: number;
  /** 租户端登录失败次数 */
  tenantLoginFailCount: number;
  /** 平台端验证码强制要求（来自登录响应） */
  platformCaptchaRequired: boolean;
  /** 租户端验证码强制要求（来自登录响应） */
  tenantCaptchaRequired: boolean;
}

// ============================================================
// Store 定义
// ============================================================

export const usePublicConfigStore = defineStore('publicConfig', {
  state: (): PublicConfigState => ({
    platformConfig: null,
    tenantConfig: null,
    platformConfigLoaded: false,
    tenantConfigLoaded: false,
    loading: false,
    error: null,
    platformLoginFailCount: 0,
    tenantLoginFailCount: 0,
    platformCaptchaRequired: false,
    tenantCaptchaRequired: false,
  }),

  getters: {
    /** 获取平台品牌配置 */
    platformBrand(): BrandConfig | null {
      return this.platformConfig?.brand ?? null;
    },

    /** 获取租户品牌配置 */
    tenantBrand(): BrandConfig | null {
      return this.tenantConfig?.brand ?? null;
    },

    /** 获取平台验证码配置 */
    platformCaptcha(): CaptchaConfig | null {
      return this.platformConfig?.login?.captcha ?? null;
    },

    /** 获取租户验证码配置 */
    tenantCaptcha(): CaptchaConfig | null {
      return this.tenantConfig?.login?.captcha ?? null;
    },

    /** 平台验证码是否启用 */
    isPlatformCaptchaEnabled(): boolean {
      return this.platformConfig?.login?.captcha?.enabled ?? false;
    },

    /** 租户验证码是否启用 */
    isTenantCaptchaEnabled(): boolean {
      return this.tenantConfig?.login?.captcha?.enabled ?? false;
    },

    /** 平台验证码是否需要显示（基于开关、失败阈值或强制要求） */
    shouldShowPlatformCaptcha(): boolean {
      // 如果后端强制要求验证码，直接显示（优先级最高）
      if (this.platformCaptchaRequired) return true;

      const captcha = this.platformConfig?.login?.captcha;
      if (!captcha?.enabled) return false;

      // 如果没有配置阈值，默认启用后总是显示
      if (!captcha.failedThreshold || captcha.failedThreshold <= 0) return true;
      // 失败次数达到阈值时显示
      return this.platformLoginFailCount >= captcha.failedThreshold;
    },

    /** 租户验证码是否需要显示（基于开关、失败阈值或强制要求） */
    shouldShowTenantCaptcha(): boolean {
      // 如果后端强制要求验证码，直接显示（优先级最高）
      if (this.tenantCaptchaRequired) return true;

      const captcha = this.tenantConfig?.login?.captcha;
      if (!captcha?.enabled) return false;

      // 如果没有配置阈值，默认启用后总是显示
      if (!captcha.failedThreshold || captcha.failedThreshold <= 0) return true;
      // 失败次数达到阈值时显示
      return this.tenantLoginFailCount >= captcha.failedThreshold;
    },
  },

  actions: {
    /**
     * 加载平台公开配置
     * 仅首次访问时调用
     */
    async loadPlatformConfig(): Promise<null | PlatformPublicConfig> {
      // 如果已加载，直接返回缓存
      if (this.platformConfigLoaded && this.platformConfig) {
        return this.platformConfig;
      }

      this.loading = true;
      this.error = null;

      try {
        const config = await getPlatformPublicConfigApi();
        this.platformConfig = config;
        this.platformConfigLoaded = true;

        // 应用品牌配置
        applyBrandConfig(config.brand);

        return config;
      } catch (error) {
        this.error =
          error instanceof Error ? error.message : 'Failed to load config';
        // 错误已存储在 state.error 中，由调用方决定如何处理
        return null;
      } finally {
        this.loading = false;
      }
    },

    /**
     * 加载租户公开配置
     * 仅首次访问时调用
     * 开发环境支持通过 URL 参数 tenant_code 指定租户
     */
    async loadTenantConfig(): Promise<null | TenantPublicConfig> {
      if (this.tenantConfigLoaded && this.tenantConfig) {
        return this.tenantConfig;
      }

      this.loading = true;
      this.error = null;

      try {
        let tenantCode: string | undefined;

        // 从 URL 参数读取 tenant_code（所有环境通用）
        const urlParams = new URLSearchParams(window.location.search);
        const fromUrl = urlParams.get('tenant_code');
        if (fromUrl) {
          localStorage.setItem('__tenant_code__', fromUrl);
          tenantCode = fromUrl;
        } else {
          // 从 localStorage 读取（支持一键登录后的品牌配置加载）
          tenantCode =
            localStorage.getItem('__tenant_code__') ?? undefined;
        }

        // 开发环境额外支持环境变量兜底
        if (!tenantCode && import.meta.env.DEV) {
          tenantCode = import.meta.env.VITE_DEV_TENANT_CODE ?? undefined;
        }

        const config = await getTenantPublicConfigApi(tenantCode);
        this.tenantConfig = config;
        this.tenantConfigLoaded = true;

        applyBrandConfig(config.brand);

        return config;
      } catch (error) {
        this.error =
          error instanceof Error ? error.message : 'Failed to load config';
        return null;
      } finally {
        this.loading = false;
      }
    },

    /**
     * 重置平台配置（用于强制刷新）
     */
    resetPlatformConfig() {
      this.platformConfig = null;
      this.platformConfigLoaded = false;
    },

    /**
     * 重置租户配置（用于强制刷新）
     */
    resetTenantConfig() {
      this.tenantConfig = null;
      this.tenantConfigLoaded = false;
    },

    /**
     * 重置所有配置
     */
    resetAll() {
      this.platformConfig = null;
      this.tenantConfig = null;
      this.platformConfigLoaded = false;
      this.tenantConfigLoaded = false;
      this.error = null;
      this.platformLoginFailCount = 0;
      this.tenantLoginFailCount = 0;
      this.platformCaptchaRequired = false;
      this.tenantCaptchaRequired = false;
    },

    /**
     * 增加平台端登录失败次数
     */
    incrementPlatformLoginFail() {
      this.platformLoginFailCount++;
    },

    /**
     * 重置平台端登录失败次数（登录成功后调用）
     */
    resetPlatformLoginFail() {
      this.platformLoginFailCount = 0;
    },

    /**
     * 增加租户端登录失败次数
     */
    incrementTenantLoginFail() {
      this.tenantLoginFailCount++;
    },

    /**
     * 重置租户端登录失败次数（登录成功后调用）
     */
    resetTenantLoginFail() {
      this.tenantLoginFailCount = 0;
    },

    /**
     * 设置平台端验证码强制要求状态
     */
    setPlatformCaptchaRequired(required: boolean) {
      this.platformCaptchaRequired = required;
    },

    /**
     * 设置租户端验证码强制要求状态
     */
    setTenantCaptchaRequired(required: boolean) {
      this.tenantCaptchaRequired = required;
    },

    /**
     * 重置平台端登录状态（登录成功后调用）
     */
    resetPlatformLoginState() {
      this.platformLoginFailCount = 0;
      this.platformCaptchaRequired = false;
    },

    /**
     * 重置租户端登录状态（登录成功后调用）
     */
    resetTenantLoginState() {
      this.tenantLoginFailCount = 0;
      this.tenantCaptchaRequired = false;
    },
    /**
     * 手动应用品牌配置（用于 Router Guard）
     */
    applyBrandConfig(brand: BrandConfig) {
      applyBrandConfig(brand);
    },
  },
});
