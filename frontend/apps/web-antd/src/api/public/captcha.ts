/**
 * Captcha API / 验证码 API
 * Public endpoint, no auth required / 公开接口，无需认证
 */
import { baseRequestClient } from '#/utils/request';

// ============================================================
// Type definitions / 类型定义
// ============================================================

/** Captcha type / 验证码类型 */
export type CaptchaType = 'image';

/** Captcha difficulty level / 验证码难度等级 */
export type CaptchaDifficulty = 'easy' | 'hard' | 'medium';

/** Captcha challenge request / 验证码挑战请求 */
export interface CaptchaChallengeRequest {
  /** Action type, e.g. login / 操作类型 */
  action: string;
  /** Endpoint identifier, e.g. admin, tenant / 端点标识 */
  endpoint: string;
  /** Captcha provider code (optional) / 验证码提供方标识 */
  providerCode?: string;
  /** Difficulty level (optional) / 难度等级 */
  difficulty?: CaptchaDifficulty;
}

/** Captcha challenge response / 验证码挑战响应 */
export interface CaptchaChallengeResponse {
  /** Challenge ID / 挑战 ID */
  challengeId: string;
  /** Captcha image Base64 data / 验证码图片 Base64 数据 */
  image: string;
  /** Captcha type / 验证码类型 */
  type: CaptchaType;
  /** Captcha length hint (optional) / 验证码长度提示 */
  length?: number;
}

/** Captcha verify request / 验证码校验请求 */
export interface CaptchaVerifyRequest {
  /** Challenge ID / 挑战 ID */
  challengeId: string;
  /** User input answer / 用户输入的答案 */
  solution: string;
  /** Action type / 操作类型 */
  action: string;
  /** Endpoint identifier / 端点标识 */
  endpoint: string;
  /** Captcha provider code (optional) / 验证码提供方标识 */
  providerCode?: string;
}

/** Captcha verify response / 验证码校验响应 */
export interface CaptchaVerifyResponse {
  /** Whether verification passed / 是否验证通过 */
  valid: boolean;
  /** Verification token (optional, for login) / 验证 Token */
  token?: string;
}

// ============================================================
// Backend raw types (snake_case) / 后端原始类型
// ============================================================

interface CaptchaChallengeRequestRaw {
  action: string;
  endpoint: string;
  provider_code?: string;
  difficulty?: string;
}

interface CaptchaChallengeResponseRaw {
  challenge_id: string;
  image?: string;
  image_base64?: string;
  type: string;
  length?: number;
  /** Backend may put image data in payload / 后端可能将图片数据放在 payload 中 */
  payload?: {
    image_base64?: string;
  };
}

interface CaptchaVerifyRequestRaw {
  challenge_id: string;
  solution: string;
  action: string;
  endpoint: string;
  provider_code?: string;
}

interface CaptchaVerifyResponseRaw {
  valid: boolean;
  token?: string;
}

// ============================================================
// HTTP response wrapper type / HTTP 响应包装类型
// ============================================================

interface HttpResponse<T> {
  code: number;
  data: T;
  message: string;
}

// ============================================================
// API functions / API 函数
// ============================================================

/**
 * Get captcha challenge / 获取验证码挑战
 * POST /api/public/captcha/challenge
 * No auth required / 无需认证
 */
export async function getCaptchaChallengeApi(
  params: CaptchaChallengeRequest,
): Promise<CaptchaChallengeResponse> {
  const requestData: CaptchaChallengeRequestRaw = {
    action: params.action,
    difficulty: params.difficulty,
    endpoint: params.endpoint,
    provider_code: params.providerCode,
  };

  const response = await baseRequestClient.post<
    HttpResponse<CaptchaChallengeResponseRaw>
  >('/api/public/captcha/challenge', requestData);

  const httpResponse = response as unknown as {
    data: HttpResponse<CaptchaChallengeResponseRaw>;
  };
  const responseData = httpResponse.data;

  if (responseData.code !== 0) {
    throw new Error(responseData.message || 'Failed to get captcha challenge');
  }

  const raw = responseData.data;
  // Priority: payload.image_base64 > image_base64 > image / 优先从 payload 获取
  const imageData =
    raw.payload?.image_base64 || raw.image_base64 || raw.image || '';
  return {
    challengeId: raw.challenge_id,
    image: imageData,
    length: raw.length,
    type: raw.type as CaptchaType,
  };
}

/**
 * Verify captcha / 校验验证码
 * POST /api/public/captcha/verify
 * No auth required / 无需认证
 */
export async function verifyCaptchaApi(
  params: CaptchaVerifyRequest,
): Promise<CaptchaVerifyResponse> {
  const requestData: CaptchaVerifyRequestRaw = {
    action: params.action,
    challenge_id: params.challengeId,
    endpoint: params.endpoint,
    provider_code: params.providerCode,
    solution: params.solution,
  };

  const response = await baseRequestClient.post<
    HttpResponse<CaptchaVerifyResponseRaw>
  >('/api/public/captcha/verify', requestData);

  const httpResponse = response as unknown as {
    data: HttpResponse<CaptchaVerifyResponseRaw>;
  };
  const responseData = httpResponse.data;

  if (responseData.code !== 0) {
    throw new Error(responseData.message || 'Captcha verification failed');
  }

  return {
    token: responseData.data.token,
    valid: responseData.data.valid,
  };
}
