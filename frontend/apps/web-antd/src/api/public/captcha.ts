/**
 * 验证码 API
 * 公开接口，无需认证
 */
import { baseRequestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 验证码类型 */
export type CaptchaType = 'image';

/** 验证码难度等级 */
export type CaptchaDifficulty = 'easy' | 'hard' | 'medium';

/** 验证码挑战请求 */
export interface CaptchaChallengeRequest {
  /** 操作类型，如 login */
  action: string;
  /** 端点标识，如 admin、tenant */
  endpoint: string;
  /** 验证码提供方标识（可选） */
  providerCode?: string;
  /** 难度等级（可选） */
  difficulty?: CaptchaDifficulty;
}

/** 验证码挑战响应 */
export interface CaptchaChallengeResponse {
  /** 挑战 ID */
  challengeId: string;
  /** 验证码图片 Base64 数据 */
  image: string;
  /** 验证码类型 */
  type: CaptchaType;
  /** 验证码长度提示（可选） */
  length?: number;
}

/** 验证码校验请求 */
export interface CaptchaVerifyRequest {
  /** 挑战 ID */
  challengeId: string;
  /** 用户输入的答案 */
  solution: string;
  /** 操作类型 */
  action: string;
  /** 端点标识 */
  endpoint: string;
  /** 验证码提供方标识（可选） */
  providerCode?: string;
}

/** 验证码校验响应 */
export interface CaptchaVerifyResponse {
  /** 是否验证通过 */
  valid: boolean;
  /** 验证 Token（可选，用于登录时携带） */
  token?: string;
}

// ============================================================
// 后端原始类型 (snake_case)
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
  /** 后端可能将图片数据放在 payload 中 */
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
// HTTP 响应包装类型
// ============================================================

interface HttpResponse<T> {
  code: number;
  data: T;
  message: string;
}

// ============================================================
// API 函数
// ============================================================

/**
 * 获取验证码挑战
 * POST /api/public/captcha/challenge
 * 无需认证
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
  // 优先从 payload.image_base64 获取，其次 image_base64，最后 image
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
 * 校验验证码
 * POST /api/public/captcha/verify
 * 无需认证
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
