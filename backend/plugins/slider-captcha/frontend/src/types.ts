import type { Component } from "vue";

export interface CaptchaRegistryEntry {
  component: Component;
  label?: string;
}

export interface SliderCaptchaResult {
  captchaCode: string;
  challengeId: string;
  provider: string;
}

export type SliderCaptchaStatusKey =
  | "default"
  | "loading"
  | "retry"
  | "success";

export interface SliderPieceGeometry {
  circle_radius: number;
  origin_x: number;
  origin_y: number;
  square_length: number;
}

export interface SliderChallengePayload {
  board_image?: string;
  canvas_height: number;
  canvas_width: number;
  /** Board X of puzzle capture rect; equals server expected horizontal offset. */
  piece_capture_left?: number;
  piece_geometry?: SliderPieceGeometry;
  piece_height: number;
  piece_image?: string;
  piece_top: number;
  piece_width: number;
  tolerance_px: number;
}

export interface SliderChallengeResponsePayload {
  challenge_id: string;
  payload: SliderChallengePayload;
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
