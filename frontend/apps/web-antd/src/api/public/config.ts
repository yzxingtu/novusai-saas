/**
 * Public config API / 公开配置 API
 * Get platform/tenant public config, no auth required / 获取平台/企业公开配置，无需认证
 */
import { getProcessedImageUrl } from '#/utils/image';
import { baseRequestClient } from '#/utils/request';

interface HttpResponse<T = unknown> {
  code: number;
  data: T;
  message: string;
}

/**
 * Extract business data from baseRequestClient response / 从 baseRequestClient 响应中提取业务数据
 * baseRequestClient TS type returns T, but runtime returns AxiosResponse with .data as HttpResponse
 */
function extractResponseData<T>(response: unknown): HttpResponse<T> {
  return (response as { data: HttpResponse<T> }).data;
}

/**
 * Pick non-null/undefined fields from source object / 从源对象中提取非空字段
 * Used for building optional feature configs, avoids overwriting defaults with null
 */
function pickDefined<T, K extends keyof T>(
  source: T,
  keys: K[],
): Record<string, NonNullable<T[K]>> {
  const result: Record<string, NonNullable<T[K]>> = {};
  for (const key of keys) {
    const val = source[key];
    if (val !== null && val !== undefined) {
      result[key as string] = val as NonNullable<T[K]>;
    }
  }
  return result;
}

/**
 * Convert attachment ID string to image URL / 将附件 ID 字符串转为图片访问 URL
 * Config stores attachment IDs (e.g. "10"), needs conversion to /api/public/attachments/{id}/image
 */
function attachmentIdToUrl(idStr: string | undefined): string | undefined {
  if (!idStr) return undefined;
  const id = Number(idStr);
  if (!Number.isFinite(id) || id <= 0) return idStr;
  return getProcessedImageUrl(id);
}

// ============================================================
// Type definitions / 类型定义
// ============================================================

/** Brand config / 品牌配置 */
export interface BrandConfig {
  /** Site name / 站点名称 */
  siteName?: string;
  /** Site description / 站点描述 */
  siteDescription?: string;
  /** Logo URL / Logo 地址 */
  logo?: string;
  /** Dark mode Logo URL / 深色模式 Logo */
  logoDark?: string;
  /** Favicon URL / 网站图标地址 */
  favicon?: string;
  /** Primary color (platform only) / 主题色（仅平台端） */
  primaryColor?: string;
  /** Login page background image / 登录页背景图 */
  loginBg?: string;
  /** Copyright info / 版权信息 */
  copyright?: string;
  /** ICP filing number / ICP 备案号 */
  icp?: string;
}

/** Captcha config / 验证码配置 */
export interface CaptchaConfig {
  /** Whether captcha is enabled / 是否启用验证码 */
  enabled: boolean;
  /** Captcha type: image | slider | click / 验证码类型 */
  type: string;
  /** Difficulty: easy | medium | hard / 难度等级 */
  difficulty: string;
  /** Show captcha after N failures / 失败多少次后显示验证码 */
  failedThreshold: number;
  /** Captcha provider (backend driver type) / 验证码提供方标识 */
  provider?: string;
}

/** Login config / 登录配置 */
export interface LoginConfig {
  /** Captcha config / 验证码配置 */
  captcha: CaptchaConfig;
  /** Allowed login methods / 允许的登录方式 */
  allowedMethods: string[];
  /** Max attempts / 最大尝试次数 */
  maxAttempts?: number;
  /** Lockout duration (minutes) / 锁定时间（分钟） */
  lockoutMinutes?: number;
}

/** Password policy / 密码策略 */
export interface PasswordPolicy {
  minLength?: number;
  complexity?: string;
  expiryDays?: number;
}

/** Session policy / 会话策略 */
export interface SessionPolicy {
  timeoutMinutes?: number;
  maxDevices?: number;
}

/** Security config / 安全配置 */
export interface SecurityConfig {
  password: PasswordPolicy;
  session: SessionPolicy;
}

/** Maintenance config / 维护配置 */
export interface MaintenanceConfig {
  enabled: boolean;
  message?: string;
}

/** Domain config / 域名配置 */
export interface DomainConfig {
  suffix: string;
  verificationPrefix: string;
}

/** Platform public config / 平台公开配置 */
export interface PlatformPublicConfig {
  /** Brand config / 品牌配置 */
  brand: BrandConfig;
  /** Login config / 登录配置 */
  login: LoginConfig;
  /** Security config / 安全配置 */
  security: SecurityConfig;
  /** Maintenance config / 维护配置 */
  maintenance: MaintenanceConfig;
  /** Domain config / 域名配置 */
  domain: DomainConfig;
  /** Platform admin domain list (for domain detection) / 平台管理端域名列表 */
  platformDomains: string[];
}

/** Tenant public config / 企业公开配置 */
export interface TenantPublicConfig {
  /** Tenant ID / 企业 ID */
  tenantId: number;
  /** Tenant code / 企业编码 */
  tenantCode: string;
  /** Tenant name / 企业名称 */
  tenantName: string;
  /** Brand config / 品牌配置 */
  brand: BrandConfig;
  /** Login config / 登录配置 */
  login: LoginConfig;
  /** Security config / 安全配置 */
  security: SecurityConfig;
  /** Maintenance config / 维护配置 */
  maintenance: MaintenanceConfig;
  /** Domain config / 域名配置 */
  domain: DomainConfig;
  /** Feature toggles / 功能开关 */
  features?: Record<string, boolean>;
  /** Registration privacy policy URL / 注册页隐私政策链接 */
  privacyPolicyUrl?: string;
  /** Registration terms of service URL / 注册页服务条款链接 */
  termsUrl?: string;
}

// ============================================================
// Backend raw types (snake_case) / 后端原始类型
// ============================================================

interface PlatformPublicConfigRaw {
  // Brand
  site_name?: string;
  site_description?: string;
  site_logo?: string;
  site_favicon?: string;
  site_copyright?: string;
  site_icp?: string;
  primary_color?: string;
  logo_dark?: string;

  // Domain
  tenant_domain_suffix?: string;
  domain_verification_prefix?: string;
  platform_domains?: string[];

  // Maintenance
  maintenance_mode?: boolean;
  maintenance_message?: string;

  // Login / Captcha
  login_captcha_enabled?: boolean;
  captcha_type?: string;
  captcha_difficulty?: string;
  captcha_enable_threshold_admin?: number;
  captcha_provider?: string;
  login_max_attempts?: number;
  login_lockout_minutes?: number;
  allowed_methods?: string[];

  // Password
  password_min_length?: number;
  password_complexity?: string;
  password_expiry_days?: number;

  // Session
  session_timeout_minutes?: number;
  session_max_devices?: number;
}

interface TenantPublicConfigRaw {
  tenant_id: number;
  tenant_code: string;
  tenant_name: string;

  // Brand (backend returns these field names from TenantPublicConfig schema)
  logo_url?: string;
  favicon_url?: string;
  login_bg?: string;
  login_title?: string;
  login_subtitle?: string;
  footer_copyright?: string;

  // Domain
  subdomain?: string;
  subdomain_url?: string;

  // Maintenance (from platform fallback)
  maintenance_mode?: boolean;
  maintenance_message?: string;

  // Login / Captcha
  captcha_enabled?: boolean;
  captcha_provider?: string;
  captcha_difficulty?: string;
  captcha_enable_threshold?: number;
  login_methods?: string[];
  login_max_attempts?: number;
  login_lockout_minutes?: number;

  // Password
  password_min_length?: number;
  password_complexity?: string;

  // Session
  session_timeout?: number;

  // Features
  allow_registration?: boolean;
  registration_approval?: boolean;
  allow_profile_edit?: boolean;
  email_notification?: boolean;
  sms_notification?: boolean;
  api_access?: boolean;
  file_upload?: boolean;

  // Registration links
  privacy_policy_url?: string;
  terms_url?: string;

  // Storage
  storage?: {
    allowed_extensions?: string;
    base_url?: string;
    chunk_size_mb?: number;
    driver?: string;
    max_file_size_mb?: number;
  };
}

// ============================================================
// Transform functions / 转换函数
// ============================================================

function transformPlatformConfig(
  raw: PlatformPublicConfigRaw,
): PlatformPublicConfig {
  return {
    brand: {
      siteName: raw.site_name,
      siteDescription: raw.site_description,
      logo: attachmentIdToUrl(raw.site_logo),
      logoDark: attachmentIdToUrl(raw.logo_dark),
      favicon: attachmentIdToUrl(raw.site_favicon),
      primaryColor: raw.primary_color,
      copyright: raw.site_copyright,
      icp: raw.site_icp,
    },
    login: {
      captcha: {
        enabled: raw.login_captcha_enabled ?? false,
        type: raw.captcha_type ?? 'image',
        difficulty: raw.captcha_difficulty ?? 'medium',
        failedThreshold: raw.captcha_enable_threshold_admin ?? 0,
        provider: raw.captcha_provider ?? 'image',
      },
      allowedMethods: raw.allowed_methods ?? [],
      maxAttempts: raw.login_max_attempts,
      lockoutMinutes: raw.login_lockout_minutes,
    },
    security: {
      password: {
        minLength: raw.password_min_length,
        complexity: raw.password_complexity,
        expiryDays: raw.password_expiry_days,
      },
      session: {
        timeoutMinutes: raw.session_timeout_minutes,
        maxDevices: raw.session_max_devices,
      },
    },
    maintenance: {
      enabled: raw.maintenance_mode ?? false,
      message: raw.maintenance_message,
    },
    domain: {
      suffix: raw.tenant_domain_suffix ?? '',
      verificationPrefix: raw.domain_verification_prefix ?? '',
    },
    platformDomains: raw.platform_domains ?? [],
  };
}

function transformTenantConfig(raw: TenantPublicConfigRaw): TenantPublicConfig {
  return {
    tenantId: raw.tenant_id,
    tenantCode: raw.tenant_code,
    tenantName: raw.tenant_name,
    brand: {
      siteName: raw.login_title || raw.tenant_name,
      siteDescription: raw.login_subtitle,
      logo: attachmentIdToUrl(raw.logo_url),
      favicon: attachmentIdToUrl(raw.favicon_url),
      loginBg: attachmentIdToUrl(raw.login_bg),
      copyright: raw.footer_copyright,
    },
    login: {
      captcha: {
        enabled: raw.captcha_enabled ?? false,
        type: raw.captcha_provider ?? 'image',
        difficulty: raw.captcha_difficulty ?? 'medium',
        failedThreshold: raw.captcha_enable_threshold ?? 0,
        provider: raw.captcha_provider ?? 'image',
      },
      allowedMethods: raw.login_methods ?? ['password'],
      maxAttempts: raw.login_max_attempts,
      lockoutMinutes: raw.login_lockout_minutes,
    },
    security: {
      password: {
        minLength: raw.password_min_length,
        complexity: raw.password_complexity,
      },
      session: {
        timeoutMinutes: raw.session_timeout,
      },
    },
    maintenance: {
      enabled: raw.maintenance_mode ?? false,
      message: raw.maintenance_message,
    },
    domain: {
      suffix: '',
      verificationPrefix: '',
    },
    privacyPolicyUrl: raw.privacy_policy_url || undefined,
    termsUrl: raw.terms_url || undefined,
    features: pickDefined(raw, [
      'allow_registration',
      'registration_approval',
      'api_access',
      'file_upload',
      'allow_profile_edit',
      'email_notification',
      'sms_notification',
    ]),
  };
}

// ============================================================
// API functions / API 函数
// ============================================================

/** HTTP response wrapper type / HTTP 响应包装类型 */
interface HttpResponse<T> {
  code: number;
  data: T;
  message: string;
}

/**
 * Get platform public config / 获取平台公开配置
 * GET /api/public/platform/config
 * No auth required / 无需认证
 */
export async function getPlatformPublicConfigApi(): Promise<PlatformPublicConfig> {
  // baseRequestClient has no interceptor, returns raw AxiosResponse
  // AxiosResponse.data = HttpResponse { code, message, data }
  const response = await baseRequestClient.get<
    HttpResponse<PlatformPublicConfigRaw>
  >('/api/public/platform/config');

  const responseData = extractResponseData<PlatformPublicConfigRaw>(response);

  if (responseData.code !== 0) {
    throw new Error(responseData.message || 'Failed to get platform config');
  }

  return transformPlatformConfig(responseData.data);
}

/**
 * Get tenant public config / 获取企业公开配置
 * GET /api/public/tenant/config
 * No auth required, tenant auto-detected by domain middleware / 无需认证，自动识别企业
 */
export async function getTenantPublicConfigApi(): Promise<TenantPublicConfig> {
  const response = await baseRequestClient.get<
    HttpResponse<TenantPublicConfigRaw>
  >('/api/public/tenant/config');

  const responseData = extractResponseData<TenantPublicConfigRaw>(response);

  if (responseData.code !== 0) {
    throw new Error(responseData.message || 'Failed to get tenant config');
  }

  return transformTenantConfig(responseData.data);
}
