import { nextTick, type Ref } from "vue";

import { renderSliderAssets } from "./render-slider-assets";

import type { SliderChallengePayload } from "./types";

interface CanvasRefs {
  boardCanvasRef: Ref<HTMLCanvasElement | null>;
  pieceCanvasRef: Ref<HTMLCanvasElement | null>;
}

/**
 * Teleport + Transition 下首帧 nextTick 时 ref 可能仍未挂载；多帧等待避免静默跳过绘制。
 */
export async function resolveCaptchaCanvases(
  refs: CanvasRefs,
): Promise<{ boardCanvas: HTMLCanvasElement; pieceCanvas: HTMLCanvasElement }> {
  let boardCanvas = refs.boardCanvasRef.value;
  let pieceCanvas = refs.pieceCanvasRef.value;
  if (boardCanvas && pieceCanvas) {
    return { boardCanvas, pieceCanvas };
  }

  await nextTick();
  for (let i = 0; i < 12; i += 1) {
    await new Promise<void>((resolve) => {
      requestAnimationFrame(() => resolve());
    });
    boardCanvas = refs.boardCanvasRef.value;
    pieceCanvas = refs.pieceCanvasRef.value;
    if (boardCanvas && pieceCanvas) {
      return { boardCanvas, pieceCanvas };
    }
  }

  throw new Error("captcha_canvas_not_ready");
}

export async function renderCaptchaToCanvas(
  payload: SliderChallengePayload,
  refs: CanvasRefs,
): Promise<null | number> {
  const { boardCanvas, pieceCanvas } = await resolveCaptchaCanvases(refs);
  return renderSliderAssets(payload, boardCanvas, pieceCanvas);
}

