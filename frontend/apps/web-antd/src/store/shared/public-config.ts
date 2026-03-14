/**
 * Public config store / 公开配置 Store
 * Stores platform/tenant public configuration (branding, captcha, etc.).
 * 存储平台/企业的公开配置（品牌、验证码等）。
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
 * Update page head info (Favicon, Meta Description)
 * 更新页面 Head 信息
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

const BRAND_CONFIG_CACHE_KEY = '__applied_brand_config__';

/**
 * Apply brand config to global preferences / 应用品牌配置到全局偏好设置
 * Only overrides preferences when backend brand config changes,
 * avoiding overwriting user's custom settings on every page refresh.
 * 仅在后端品牌配置变化时才覆盖。
 */
function applyBrandConfig(brand: BrandConfig) {
  const brandSnapshot = JSON.stringify({
    copyright: brand.copyright,
    icp: brand.icp,
    logo: brand.logo,
    logoDark: brand.logoDark,
    primaryColor: brand.primaryColor,
    siteName: brand.siteName,
  });

  const lastApplied = localStorage.getItem(BRAND_CONFIG_CACHE_KEY);

  if (lastApplied !== brandSnapshot) {
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
      ...(brand.primaryColor
        ? { theme: { colorPrimary: brand.primaryColor } }
        : {}),
    });
    localStorage.setItem(BRAND_CONFIG_CACHE_KEY, brandSnapshot);
  }

  updateHead(brand);
}

// ============================================================
// Type definitions / 类型定义
// ============================================================

interface PublicConfigState {
  /** Platform public config / 平台公开配置 */
  platformConfig: null | PlatformPublicConfig;
  /** Tenant public config / 企业公开配置 */
  tenantConfig: null | TenantPublicConfig;
  /** Whether platform config is loaded / 平台配置是否已加载 */
  platformConfigLoaded: boolean;
  /** Whether tenant config is loaded / 企业配置是否已加载 */
  tenantConfigLoaded: boolean;
  /** Loading state (backward compat, true if any endpoint loading) / 加载中状态 */
  loading: boolean;
  /** Platform config loading / 平台配置加载中 */
  platformLoading: boolean;
  /** Tenant config loading / 企业配置加载中 */
  tenantLoading: boolean;
  /** Error message / 错误信息 */
  error: null | string;
  /** Platform login fail count / 平台端登录失败次数 */
  platformLoginFailCount: number;
  /** Tenant login fail count / 企业端登录失败次数 */
  tenantLoginFailCount: number;
  /** Platform captcha forced (from login response) / 平台端验证码强制要求 */
  platformCaptchaRequired: boolean;
  /** Tenant captcha forced (from login response) / 企业端验证码强制要求 */
  tenantCaptchaRequired: boolean;
  /** User login fail count / 用户端登录失败次数 */
  userLoginFailCount: number;
  /** User captcha forced (from login response) / 用户端验证码强制要求 */
  userCaptchaRequired: boolean;
  /** Whether current domain is tenant domain (null=undetected, true=tenant, false=platform) / 当前域名是否企业域名 */
  isDomainTenantDomain: boolean | null;
  /** Whether domain type detection is complete (marked after 200/404, not on network error to allow retry) / 域名检测是否完成 */
  isDomainDetected: boolean;
}

// ============================================================
// Store definition / Store 定义
// ============================================================

// Promise deduplication: prevent duplicate requests from concurrent calls / Promise 去重
let _platformConfigPromise: Promise<null | PlatformPublicConfig> | null = null;
let _tenantConfigPromise: Promise<null | TenantPublicConfig> | null = null;
let _detectDomainPromise: Promise<void> | null = null;

export const usePublicConfigStore = defineStore('publicConfig', {
  state: (): PublicConfigState => ({
    platformConfig: null,
    tenantConfig: null,
    platformConfigLoaded: false,
    tenantConfigLoaded: false,
    loading: false,
    platformLoading: false,
    tenantLoading: false,
    error: null,
    platformLoginFailCount: 0,
    tenantLoginFailCount: 0,
    platformCaptchaRequired: false,
    tenantCaptchaRequired: false,
    userLoginFailCount: 0,
    userCaptchaRequired: false,
    isDomainTenantDomain: null,
    isDomainDetected: false,
  }),

  getters: {
    /** Get platform brand config / 获取平台品牌配置 */
    platformBrand(): BrandConfig | null {
      return this.platformConfig?.brand ?? null;
    },

    /** Get tenant brand config / 获取企业品牌配置 */
    tenantBrand(): BrandConfig | null {
      return this.tenantConfig?.brand ?? null;
    },

    /** Get platform captcha config / 获取平台验证码配置 */
    platformCaptcha(): CaptchaConfig | null {
      return this.platformConfig?.login?.captcha ?? null;
    },

    /** Get tenant captcha config / 获取企业验证码配置 */
    tenantCaptcha(): CaptchaConfig | null {
      return this.tenantConfig?.login?.captcha ?? null;
    },

    /** Whether platform captcha is enabled / 平台验证码是否启用 */
    isPlatformCaptchaEnabled(): boolean {
      return this.platformConfig?.login?.captcha?.enabled ?? false;
    },

    /** Whether tenant captcha is enabled / 企业验证码是否启用 */
    isTenantCaptchaEnabled(): boolean {
      return this.tenantConfig?.login?.captcha?.enabled ?? false;
    },

    /** Whether platform captcha should show (based on switch, threshold, or forced) / 平台验证码是否需显示 */
    shouldShowPlatformCaptcha(): boolean {
      // If backend forces captcha, show immediately (highest priority) / 后端强制验证码
      if (this.platformCaptchaRequired) return true;

      const captcha = this.platformConfig?.login?.captcha;
      if (!captcha?.enabled) return false;

      // If no threshold configured, always show when enabled / 无阈值时启用后总显示
      if (!captcha.failedThreshold || captcha.failedThreshold <= 0) return true;
      // Show when fail count reaches threshold / 失败次数达阈值时显示
      return this.platformLoginFailCount >= captcha.failedThreshold;
    },

    /** Whether tenant captcha should show (based on switch, threshold, or forced) / 企业验证码是否需显示 */
    shouldShowTenantCaptcha(): boolean {
      // If backend forces captcha, show immediately (highest priority) / 后端强制验证码
      if (this.tenantCaptchaRequired) return true;

      const captcha = this.tenantConfig?.login?.captcha;
      if (!captcha?.enabled) return false;

      // If no threshold configured, always show when enabled / 无阈值时启用后总显示
      if (!captcha.failedThreshold || captcha.failedThreshold <= 0) return true;
      // Show when fail count reaches threshold / 失败次数达阈值时显示
      return this.tenantLoginFailCount >= captcha.failedThreshold;
    },

    /** Whether user captcha should show (reuses tenant config, independent count) / 用户端验证码 */
    shouldShowUserCaptcha(): boolean {
      if (this.userCaptchaRequired) return true;

      const captcha = this.tenantConfig?.login?.captcha;
      if (!captcha?.enabled) return false;

      if (!captcha.failedThreshold || captcha.failedThreshold <= 0) return true;
      return this.userLoginFailCount >= captcha.failedThreshold;
    },

    /** Whether registration is enabled (default true) / 是否允许注册 */
    isRegistrationEnabled(): boolean {
      return this.tenantConfig?.features?.allow_registration !== false;
    },

    /** Whether registration requires approval / 注册是否需要审批 */
    isRegistrationApprovalRequired(): boolean {
      return this.tenantConfig?.features?.registration_approval === true;
    },

    /** Whether profile editing is allowed (default true) / 是否允许编辑个人资料 */
    isProfileEditAllowed(): boolean {
      return this.tenantConfig?.features?.allow_profile_edit !== false;
    },
  },

  actions: {
    /**
     * Load platform public config (called only on first access)
     * 加载平台公开配置（仅首次访问时调用）
     */
    async loadPlatformConfig(): Promise<null | PlatformPublicConfig> {
      // If already loaded, return cached / 如果已加载，返回缓存
      if (this.platformConfigLoaded && this.platformConfig) {
        return this.platformConfig;
      }

      // Deduplicate: reuse in-flight request / 去重：复用正在进行的请求
      if (_platformConfigPromise) {
        return _platformConfigPromise;
      }

      _platformConfigPromise = this._doLoadPlatformConfig();
      return _platformConfigPromise.finally(() => {
        _platformConfigPromise = null;
      });
    },

    async _doLoadPlatformConfig(): Promise<null | PlatformPublicConfig> {
      this.platformLoading = true;
      this.loading = true;
      this.error = null;

      try {
        const config = await getPlatformPublicConfigApi();
        this.platformConfig = config;
        this.platformConfigLoaded = true;

        // Apply brand config / 应用品牌配置
        applyBrandConfig(config.brand);

        return config;
      } catch (error) {
        this.error =
          error instanceof Error ? error.message : 'Failed to load config';
        return null;
      } finally {
        this.platformLoading = false;
        this.loading = this.tenantLoading;
      }
    },

    /**
     * Load tenant public config (called only on first access)
     * 加载企业公开配置（首次访问时调用）
     * Tenant is auto-detected by domain middleware, no manual tenant_code needed.
     */
    async loadTenantConfig(): Promise<null | TenantPublicConfig> {
      if (this.tenantConfigLoaded && this.tenantConfig) {
        return this.tenantConfig;
      }

      // Deduplicate: reuse in-flight request / 去重
      if (_tenantConfigPromise) {
        return _tenantConfigPromise;
      }

      _tenantConfigPromise = this._doLoadTenantConfig();
      return _tenantConfigPromise.finally(() => {
        _tenantConfigPromise = null;
      });
    },

    async _doLoadTenantConfig(): Promise<null | TenantPublicConfig> {
      this.tenantLoading = true;
      this.loading = true;
      this.error = null;

      try {
        const config = await getTenantPublicConfigApi();
        this.tenantConfig = config;
        this.tenantConfigLoaded = true;

        applyBrandConfig(config.brand);

        return config;
      } catch (error) {
        this.error =
          error instanceof Error ? error.message : 'Failed to load config';
        return null;
      } finally {
        this.tenantLoading = false;
        this.loading = this.platformLoading;
      }
    },

    /**
     * Three-layer deterministic domain detection / 三层确定性域名检测
     *
     * Layer 1: Env var fast match (zero network requests) / 环境变量快速匹配
     * Layer 2: Platform public config API (1 request, matches platformDomains / tenantDomainSuffix)
     * Layer 3: Tenant config API fallback (custom domain: 200=tenant | 4040=unknown)
     *
     * Idempotent: no repeat after detection. Network errors don't mark complete to allow retry.
     * 幂等：检测完成后不再重复。
     */
    async detectDomainType(): Promise<void> {
      if (this.isDomainDetected) return;

      // Deduplicate: reuse in-flight detection / 去重
      if (_detectDomainPromise) {
        return _detectDomainPromise;
      }

      _detectDomainPromise = this._doDetectDomainType();
      return _detectDomainPromise.finally(() => {
        _detectDomainPromise = null;
      });
    },

    async _doDetectDomainType(): Promise<void> {
      if (this.isDomainDetected) return;

      const hostname = globalThis.location?.hostname ?? '';

      // ── Layer 1: Env var fast match / 环境变量快速匹配 ──────────────
      const envDomains = (
        import.meta.env.VITE_PLATFORM_DOMAINS ?? ''
      )
        .split(',')
        .map((d: string) => d.trim().toLowerCase())
        .filter(Boolean);

      if (envDomains.includes(hostname.toLowerCase())) {
        this.isDomainTenantDomain = false;
        this.isDomainDetected = true;
        return;
      }

      // ── Layer 2: Platform public config API / 平台公开配置 API ───────────
      const platformConfig = await this.loadPlatformConfig();
      if (platformConfig) {
        // 2a: Check platformDomains list / 检查 platformDomains 列表
        const apiDomains = platformConfig.platformDomains.map((d) =>
          d.toLowerCase(),
        );
        if (apiDomains.includes(hostname.toLowerCase())) {
          this.isDomainTenantDomain = false;
          this.isDomainDetected = true;
          return;
        }

        // 2b: Check tenant subdomain suffix match (*.suffix) / 检查企业子域名后缀
        const suffix = platformConfig.domain.suffix?.toLowerCase();
        if (suffix && hostname.toLowerCase().endsWith(suffix)) {
          this.isDomainTenantDomain = true;
          this.isDomainDetected = true;
          // Preload tenant config / 预加载企业配置
          await this.loadTenantConfig();
          return;
        }
      }

      // ── Layer 3: Tenant config API fallback (custom domain) / 企业配置回退 ────
      try {
        const tenantConfig = await getTenantPublicConfigApi();
        this.isDomainTenantDomain = true;
        if (!this.tenantConfig) {
          this.tenantConfig = tenantConfig;
          this.tenantConfigLoaded = true;
          applyBrandConfig(tenantConfig.brand);
        }
        this.isDomainDetected = true;
      } catch (error) {
        const err = error as {
          response?: { data?: { code?: number }; status?: number };
        };
        const httpStatus = err?.response?.status;
        const businessCode = err?.response?.data?.code;

        if (
          httpStatus === 404 ||
          businessCode === 4040
        ) {
          // Tenant not found → platform domain / 企业不存在
          this.isDomainTenantDomain = false;
          this.isDomainDetected = true;
        } else if (httpStatus && httpStatus >= 400 && httpStatus < 500) {
          // Other client errors (e.g. 403) also mark as non-tenant domain / 其他客户端错误
          this.isDomainTenantDomain = false;
          this.isDomainDetected = true;
        }
        // Network/500 errors: isDomainDetected stays false, retry on next nav / 网络错误不标记
      }
    },

    /**
     * Reset platform config (for forced refresh) / 重置平台配置
     */
    resetPlatformConfig() {
      this.platformConfig = null;
      this.platformConfigLoaded = false;
      localStorage.removeItem(BRAND_CONFIG_CACHE_KEY);
    },

    /**
     * Reset tenant config (for forced refresh) / 重置企业配置
     */
    resetTenantConfig() {
      this.tenantConfig = null;
      this.tenantConfigLoaded = false;
      localStorage.removeItem(BRAND_CONFIG_CACHE_KEY);
    },

    /**
     * Reset all configs / 重置所有配置
     */
    resetAll() {
      this.platformConfig = null;
      this.tenantConfig = null;
      this.platformConfigLoaded = false;
      this.tenantConfigLoaded = false;
      this.error = null;
      this.platformLoginFailCount = 0;
      this.tenantLoginFailCount = 0;
      this.userLoginFailCount = 0;
      this.platformCaptchaRequired = false;
      this.tenantCaptchaRequired = false;
      this.userCaptchaRequired = false;
      this.isDomainTenantDomain = null;
      this.isDomainDetected = false;
      localStorage.removeItem(BRAND_CONFIG_CACHE_KEY);
    },

    /**
     * Increment platform login fail count / 增加平台端登录失败次数
     */
    incrementPlatformLoginFail() {
      this.platformLoginFailCount++;
    },

    /**
     * Reset platform login fail count (called after login success) / 重置平台端登录失败次数
     */
    resetPlatformLoginFail() {
      this.platformLoginFailCount = 0;
    },

    /**
     * Increment tenant login fail count / 增加企业端登录失败次数
     */
    incrementTenantLoginFail() {
      this.tenantLoginFailCount++;
    },

    /**
     * Reset tenant login fail count (called after login success) / 重置企业端登录失败次数
     */
    resetTenantLoginFail() {
      this.tenantLoginFailCount = 0;
    },

    /**
     * Set platform captcha forced state / 设置平台端验证码强制状态
     */
    setPlatformCaptchaRequired(required: boolean) {
      this.platformCaptchaRequired = required;
    },

    /**
     * Set tenant captcha forced state / 设置企业端验证码强制状态
     */
    setTenantCaptchaRequired(required: boolean) {
      this.tenantCaptchaRequired = required;
    },

    /**
     * Reset platform login state (called after login success) / 重置平台端登录状态
     */
    resetPlatformLoginState() {
      this.platformLoginFailCount = 0;
      this.platformCaptchaRequired = false;
    },

    /**
     * Reset tenant login state (called after login success) / 重置企业端登录状态
     */
    resetTenantLoginState() {
      this.tenantLoginFailCount = 0;
      this.tenantCaptchaRequired = false;
    },

    /**
     * Increment user login fail count / 增加用户端登录失败次数
     */
    incrementUserLoginFail() {
      this.userLoginFailCount++;
    },

    /**
     * Set user captcha forced state / 设置用户端验证码强制状态
     */
    setUserCaptchaRequired(required: boolean) {
      this.userCaptchaRequired = required;
    },

    /**
     * Reset user login state (called after login success) / 重置用户端登录状态
     */
    resetUserLoginState() {
      this.userLoginFailCount = 0;
      this.userCaptchaRequired = false;
    },

    /**
     * Manually apply brand config (for Router Guard) / 手动应用品牌配置
     */
    applyBrandConfig(brand: BrandConfig) {
      applyBrandConfig(brand);
    },
  },
});
