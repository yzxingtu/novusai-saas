/**
 * 公开配置 API
 * 获取平台/租户公开配置，无需认证
 */
import { getProcessedImageUrl } from '#/utils/image';
import { baseRequestClient } from '#/utils/request';

/**
 * 将附件 ID 字符串转为图片访问 URL
 * 配置项存储的是附件 ID（如 "10"），需转为 /api/public/attachments/{id}/image
 */
function attachmentIdToUrl(idStr: string | undefined): string | undefined {
  if (!idStr) return undefined;
  const id = Number(idStr);
  if (!Number.isFinite(id) || id <= 0) return idStr;
  return getProcessedImageUrl(id);
}

// ============================================================
// 类型定义
// ============================================================

/** 品牌配置 */
export interface BrandConfig {
  /** 站点名称 */
  siteName?: string;
  /** 站点描述 */
  siteDescription?: string;
  /** Logo URL */
  logo?: string;
  /** 深色模式 Logo URL */
  logoDark?: string;
  /** Favicon URL */
  favicon?: string;
  /** 主题色 */
  primaryColor?: string;
  /** 版权信息 */
  copyright?: string;
  /** ICP 备案号 */
  icp?: string;
}

/** 验证码配置 */
export interface CaptchaConfig {
  /** 是否启用验证码 */
  enabled: boolean;
  /** 验证码类型: image | slider | click */
  type: string;
  /** 难度等级: easy | medium | hard */
  difficulty: string;
  /** 失败多少次后显示验证码 */
  failedThreshold: number;
  /** 验证码提供方标识（后端驱动类型） */
  provider?: string;
}

/** 登录配置 */
export interface LoginConfig {
  /** 验证码配置 */
  captcha: CaptchaConfig;
  /** 允许的登录方式 */
  allowedMethods: string[];
  /** 最大尝试次数 */
  maxAttempts?: number;
  /** 锁定时间（分钟） */
  lockoutMinutes?: number;
}

/** 密码策略 */
export interface PasswordPolicy {
  minLength?: number;
  complexity?: string;
  expiryDays?: number;
}

/** 会话策略 */
export interface SessionPolicy {
  timeoutMinutes?: number;
  maxDevices?: number;
}

/** 安全配置 */
export interface SecurityConfig {
  password: PasswordPolicy;
  session: SessionPolicy;
}

/** 维护配置 */
export interface MaintenanceConfig {
  enabled: boolean;
  message?: string;
}

/** 域名配置 */
export interface DomainConfig {
  suffix: string;
  verificationPrefix: string;
}

/** 平台公开配置 */
export interface PlatformPublicConfig {
  /** 品牌配置 */
  brand: BrandConfig;
  /** 登录配置 */
  login: LoginConfig;
  /** 安全配置 */
  security: SecurityConfig;
  /** 维护配置 */
  maintenance: MaintenanceConfig;
  /** 域名配置 */
  domain: DomainConfig;
}

/** 租户公开配置 */
export interface TenantPublicConfig {
  /** 租户 ID */
  tenantId: number;
  /** 租户编码 */
  tenantCode: string;
  /** 租户名称 */
  tenantName: string;
  /** 品牌配置 */
  brand: BrandConfig;
  /** 登录配置 */
  login: LoginConfig;
  /** 安全配置 */
  security: SecurityConfig;
  /** 维护配置 */
  maintenance: MaintenanceConfig;
  /** 域名配置 */
  domain: DomainConfig;
  /** 功能开关 */
  features?: Record<string, boolean>;
}

// ============================================================
// 后端原始类型 (snake_case)
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

  // Features
  features?: Record<string, boolean>;
}

// ============================================================
// 转换函数
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
  };
}

function transformTenantConfig(raw: TenantPublicConfigRaw): TenantPublicConfig {
  return {
    tenantId: raw.tenant_id,
    tenantCode: raw.tenant_code,
    tenantName: raw.tenant_name,
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
    features: raw.features,
  };
}

// ============================================================
// API 函数
// ============================================================

/** HTTP 响应包装类型 */
interface HttpResponse<T> {
  code: number;
  data: T;
  message: string;
}

/**
 * 获取平台公开配置
 * GET /api/public/platform/config
 * 无需认证
 */
export async function getPlatformPublicConfigApi(): Promise<PlatformPublicConfig> {
  // baseRequestClient 无拦截器，返回原始 AxiosResponse
  // AxiosResponse.data = HttpResponse { code, message, data }
  const response = await baseRequestClient.get<
    HttpResponse<PlatformPublicConfigRaw>
  >('/api/public/platform/config');

  // response 是 AxiosResponse，response.data 是 HttpResponse
  const httpResponse = response as unknown as {
    data: HttpResponse<PlatformPublicConfigRaw>;
  };
  const responseData = httpResponse.data;

  if (responseData.code !== 0) {
    throw new Error(responseData.message || 'Failed to get platform config');
  }

  return transformPlatformConfig(responseData.data);
}

/**
 * 获取租户公开配置
 * GET /api/public/tenant/config
 * 无需认证，根据域名自动识别租户
 * 开发环境支持通过 tenantCode 参数指定租户
 */
export async function getTenantPublicConfigApi(
  tenantCode?: string,
): Promise<TenantPublicConfig> {
  const params: Record<string, string> = {};
  if (tenantCode) {
    params.tenant_code = tenantCode;
  }

  const response = await baseRequestClient.get<
    HttpResponse<TenantPublicConfigRaw>
  >('/api/public/tenant/config', { params });

  // response 是 AxiosResponse，response.data 是 HttpResponse
  const httpResponse = response as unknown as {
    data: HttpResponse<TenantPublicConfigRaw>;
  };
  const responseData = httpResponse.data;

  if (responseData.code !== 0) {
    throw new Error(responseData.message || 'Failed to get tenant config');
  }

  return transformTenantConfig(responseData.data);
}
