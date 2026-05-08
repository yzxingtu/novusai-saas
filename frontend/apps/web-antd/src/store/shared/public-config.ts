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
import { overridesPreferences } from '#/preferences';
import {
  ensureCaptchaPluginReady,
} from '#/utils/captcha-plugin';
import { mergeBrandConfig } from '#/utils/public-branding';

/**
 * Update page head info (Favicon, Meta Description)
 * 更新页面 Head 信息
 */
function updateHead(brand: BrandConfig) {
  // Update Favicon / 更新 Favicon
  if (brand.favicon) {
    let link = document.querySelector("link[rel~='icon']") as HTMLLinkElement;
    if (!link) {
      link = document.createElement('link');
      link.rel = 'icon';
      document.head.append(link);
    }
    link.href = brand.favicon;
  }

  // Update Meta Description / 更新 Meta Description
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

const DEFAULT_BRAND_CONFIG: BrandConfig = {
  copyright: overridesPreferences.copyright?.companyName ?? 'NovusAI',
  siteName:
    overridesPreferences.app?.name ??
    import.meta.env.VITE_APP_TITLE ??
    'NovusAI',
};

/**
 * Apply brand config to global preferences / 应用品牌配置到全局偏好设置
 *
 * Brand identity (logo, name, copyright) is ALWAYS written — these are not
 * user-customizable preferences. Primary color uses a cache check so that
 * a user's custom theme color is not overwritten on every navigation.
 *
 * 品牌标识（logo、站点名、版权）始终写入；主题色使用缓存对比以保留用户自定义。
 */
function applyBrandConfig(brand: BrandConfig) {
  updatePreferences({
    app: { name: brand.siteName },
    logo: { source: brand.logo, sourceDark: brand.logoDark },
    copyright: {
      companyName: brand.copyright,
      companySiteLink: '',
      icp: brand.icp,
    },
  });

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
    if (brand.primaryColor) {
      updatePreferences({ theme: { colorPrimary: brand.primaryColor } });
    }
    localStorage.setItem(BRAND_CONFIG_CACHE_KEY, brandSnapshot);
  }

  updateHead(brand);
}

function resetHead(): void {
  const favicon = document.querySelector(
    "link[rel~='icon']",
  ) as HTMLLinkElement | null;
  if (favicon) {
    favicon.remove();
  }

  const description = document.querySelector(
    "meta[name='description']",
  ) as HTMLMetaElement | null;
  if (description) {
    description.remove();
  }
}

function resetAppliedBrandConfig(): void {
  updatePreferences({
    app: { name: DEFAULT_BRAND_CONFIG.siteName },
    logo: { source: undefined, sourceDark: undefined },
    copyright: {
      companyName: DEFAULT_BRAND_CONFIG.copyright,
      companySiteLink: '',
      icp: '',
    },
  });
  localStorage.removeItem(BRAND_CONFIG_CACHE_KEY);
  resetHead();
}

async function prepareTenantCaptchaPlugin(
  config: TenantPublicConfig,
): Promise<TenantPublicConfig> {
  if (!(await ensureCaptchaPluginReady(config.login.captcha))) {
    throw new Error('Configured tenant captcha plugin is unavailable');
  }
  return config;
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

interface LoadTenantConfigOptions {
  /** Skip domain guard when domain detection already proved the host is tenant-facing. / 已确认当前域名属于企业侧时跳过域名守卫 */
  skipDomainCheck?: boolean;
}

interface LoadPlatformConfigOptions {
  /** Apply brand config after loading / 加载后是否应用品牌配置 */
  applyBrand?: boolean;
}

// ============================================================
// Store definition / Store 定义
// ============================================================

// Promise deduplication: prevent duplicate requests from concurrent calls / Promise 去重
let _platformConfigPromise: null | Promise<null | PlatformPublicConfig> = null;
let _tenantConfigPromise: null | Promise<null | TenantPublicConfig> = null;
let _detectDomainPromise: null | Promise<void> = null;
const E2E_DOMAIN_TYPE_OVERRIDE_KEY = '__novusai_e2e_domain_type';

function readE2EDomainTypeOverride(): 'platform' | 'tenant' | null {
  if (!import.meta.env.DEV || typeof window === 'undefined') {
    return null;
  }
  try {
    const raw = window.sessionStorage
      .getItem(E2E_DOMAIN_TYPE_OVERRIDE_KEY)
      ?.trim()
      .toLowerCase();
    if (raw === 'platform' || raw === 'tenant') {
      return raw;
    }
  } catch {
    // Ignore storage access failures in non-browser/test contexts.
  }
  return null;
}

export const usePublicConfigStore = defineStore('publicConfig', {
  state: (): PublicConfigState => ({
    platformConfig: null,
    tenantConfig: null,
    platformConfigLoaded: false,
    tenantConfigLoaded: false,
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

    /** Whether user login captcha is enabled / 用户端登录验证码是否启用 */
    isUserLoginCaptchaEnabled(): boolean {
      return (
        this.tenantConfig?.userLoginCaptchaEnabled ??
        this.tenantConfig?.login?.captcha?.enabled ??
        false
      );
    },

    /** Whether user registration captcha is enabled / 用户端注册验证码是否启用 */
    isUserRegistrationCaptchaEnabled(): boolean {
      return (
        this.tenantConfig?.userRegistrationCaptchaEnabled ??
        this.tenantConfig?.login?.captcha?.enabled ??
        false
      );
    },

    /** User login captcha threshold / 用户端登录验证码阈值 */
    userLoginCaptchaThreshold(): number {
      return (
        this.tenantConfig?.userLoginCaptchaEnableThreshold ??
        this.tenantConfig?.login?.captcha?.failedThreshold ??
        0
      );
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

      if (!this.isUserLoginCaptchaEnabled) return false;

      const threshold = this.userLoginCaptchaThreshold;
      if (!threshold || threshold <= 0) return true;
      return this.userLoginFailCount >= threshold;
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
    async loadPlatformConfig(
      options: LoadPlatformConfigOptions = {},
    ): Promise<null | PlatformPublicConfig> {
      const { applyBrand = true } = options;
      // If already loaded, return cached / 如果已加载，返回缓存
      if (this.platformConfigLoaded && this.platformConfig) {
        if (applyBrand) {
          applyBrandConfig(this.platformConfig.brand);
        }
        return this.platformConfig;
      }

      // Deduplicate: reuse in-flight request / 去重：复用正在进行的请求
      if (_platformConfigPromise) {
        const config = await _platformConfigPromise;
        if (config && applyBrand) {
          applyBrandConfig(config.brand);
        }
        return config;
      }

      _platformConfigPromise = this._doLoadPlatformConfig();
      const config = await _platformConfigPromise.finally(() => {
        _platformConfigPromise = null;
      });
      if (config && applyBrand) {
        applyBrandConfig(config.brand);
      }
      return config;
    },

    async _doLoadPlatformConfig(): Promise<null | PlatformPublicConfig> {
      this.platformLoading = true;
      this.error = null;

      try {
        const config = await getPlatformPublicConfigApi();
        if (!(await ensureCaptchaPluginReady(config.login.captcha))) {
          throw new Error('Configured platform captcha plugin is unavailable');
        }
        this.platformConfig = config;
        this.platformConfigLoaded = true;

        return config;
      } catch (error) {
        this.error =
          error instanceof Error ? error.message : 'Failed to load config';
        return null;
      } finally {
        this.platformLoading = false;
      }
    },

    /**
     * Load tenant public config (called only on first access)
     * 加载企业公开配置（首次访问时调用）
     * Tenant is auto-detected by domain middleware, no manual tenant_code needed.
     */
    async loadTenantConfig(
      options: LoadTenantConfigOptions = {},
    ): Promise<null | TenantPublicConfig> {
      const { skipDomainCheck = false } = options;

      if (this.tenantConfigLoaded && this.tenantConfig) {
        return this.tenantConfig;
      }

      if (!skipDomainCheck) {
        await this.detectDomainType().catch(() => {});

        if (this.tenantConfigLoaded && this.tenantConfig) {
          return this.tenantConfig;
        }

        // Platform-domain tenant/admin routes should keep using platform public config.
        // / 平台域企业端管理页面应继续使用平台公开配置，避免误打 tenant public config。
        if (this.isDomainDetected && this.isDomainTenantDomain === false) {
          return null;
        }
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
      this.error = null;

      try {
        const platformConfig =
          this.platformConfig ??
          (await this.loadPlatformConfig({ applyBrand: false }));
        const config = await prepareTenantCaptchaPlugin(
          await getTenantPublicConfigApi(),
        );
        const mergedConfig: TenantPublicConfig = {
          ...config,
          brand: mergeBrandConfig(platformConfig?.brand, config.brand),
        };
        this.tenantConfig = mergedConfig;
        this.tenantConfigLoaded = true;

        applyBrandConfig(mergedConfig.brand);

        return mergedConfig;
      } catch (error) {
        this.error =
          error instanceof Error ? error.message : 'Failed to load config';
        return null;
      } finally {
        this.tenantLoading = false;
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
      const e2eDomainTypeOverride = readE2EDomainTypeOverride();

      if (e2eDomainTypeOverride) {
        this.isDomainTenantDomain = e2eDomainTypeOverride === 'tenant';
        this.isDomainDetected = true;
        return;
      }

      // ── Layer 1: Env var fast match / 环境变量快速匹配 ──────────────
      const envDomains = (import.meta.env.VITE_PLATFORM_DOMAINS ?? '')
        .split(',')
        .map((d: string) => d.trim().toLowerCase())
        .filter(Boolean);

      if (envDomains.includes(hostname.toLowerCase())) {
        this.isDomainTenantDomain = false;
        this.isDomainDetected = true;
        return;
      }

      // ── Layer 2: Platform public config API / 平台公开配置 API ───────────
      const platformConfig = await this.loadPlatformConfig({
        applyBrand: false,
      });
      if (platformConfig) {
        // 2a: Check platformDomains list / 检查 platformDomains 列表
        const apiDomains = platformConfig.platformDomains.map((d) =>
          d.toLowerCase(),
        );
        if (apiDomains.includes(hostname.toLowerCase())) {
          this.isDomainTenantDomain = false;
          this.isDomainDetected = true;
          applyBrandConfig(platformConfig.brand);
          return;
        }

        // 2b: Check tenant subdomain suffix match (*.suffix) / 检查企业子域名后缀
        const suffix = platformConfig.domain.suffix?.toLowerCase();
        if (suffix && hostname.toLowerCase().endsWith(suffix)) {
          this.isDomainTenantDomain = true;
          this.isDomainDetected = true;
          // Preload tenant config / 预加载企业配置
          await this.loadTenantConfig({ skipDomainCheck: true });
          return;
        }
      }

      // ── Layer 3: Tenant config API fallback (custom domain) / 企业配置回退 ────
      try {
        const tenantConfig = await prepareTenantCaptchaPlugin(
          await getTenantPublicConfigApi(),
        );
        this.isDomainTenantDomain = true;
        if (!this.tenantConfig) {
          this.tenantConfig = {
            ...tenantConfig,
            brand: mergeBrandConfig(platformConfig?.brand, tenantConfig.brand),
          };
          this.tenantConfigLoaded = true;
          applyBrandConfig(this.tenantConfig.brand);
        }
        this.isDomainDetected = true;
      } catch (error) {
        const err = error as {
          response?: { data?: { code?: number }; status?: number };
        };
        const httpStatus = err?.response?.status;
        const businessCode = err?.response?.data?.code;

        if (httpStatus === 404 || businessCode === 4040) {
          // Tenant not found → platform domain / 企业不存在
          this.isDomainTenantDomain = false;
          this.isDomainDetected = true;
          if (platformConfig) {
            applyBrandConfig(platformConfig.brand);
          }
        } else if (httpStatus && httpStatus >= 400 && httpStatus < 500) {
          // Other client errors (e.g. 403) also mark as non-tenant domain / 其他客户端错误
          this.isDomainTenantDomain = false;
          this.isDomainDetected = true;
          if (platformConfig) {
            applyBrandConfig(platformConfig.brand);
          }
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
      if (this.tenantConfigLoaded && this.tenantConfig) {
        applyBrandConfig(this.tenantConfig.brand);
        return;
      }
      resetAppliedBrandConfig();
    },

    /**
     * Reset tenant config (for forced refresh) / 重置企业配置
     */
    resetTenantConfig() {
      this.tenantConfig = null;
      this.tenantConfigLoaded = false;
      localStorage.removeItem(BRAND_CONFIG_CACHE_KEY);
      if (this.platformConfigLoaded && this.platformConfig) {
        applyBrandConfig(this.platformConfig.brand);
        return;
      }
      resetAppliedBrandConfig();
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
      resetAppliedBrandConfig();
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
