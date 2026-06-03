import type { SliderChallengePayload, SliderPieceGeometry } from "./types";
import { fillJigsawPuzzleMask } from "./vector-jigsaw";

function readPayloadRecord(payload: SliderChallengePayload): Record<string, unknown> {
  return payload as unknown as Record<string, unknown>;
}

/** Accept snake_case (API) or camelCase (defensive) for nested geometry. */
function resolvePieceGeometry(rawPayload: SliderChallengePayload): SliderPieceGeometry | null {
  const p = readPayloadRecord(rawPayload);
  const raw = p.piece_geometry ?? p.pieceGeometry;
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const g = raw as Record<string, unknown>;
  const square_length = Number(g.square_length ?? g.squareLength);
  const circle_radius = Number(g.circle_radius ?? g.circleRadius);
  const origin_x = Number(g.origin_x ?? g.originX);
  const origin_y = Number(g.origin_y ?? g.originY);
  if (
    [square_length, circle_radius, origin_x, origin_y].some(
      (n) => !Number.isFinite(n),
    )
  ) {
    return null;
  }
  return {
    circle_radius,
    origin_x,
    origin_y,
    square_length,
  };
}

function resolveCaptureLeft(rawPayload: SliderChallengePayload): number | null {
  const p = readPayloadRecord(rawPayload);
  const v = p.piece_capture_left ?? p.pieceCaptureLeft;
  if (v == null) {
    return null;
  }
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function getBitmapDevicePixelRatio(hostCanvas: HTMLCanvasElement): number {
  const doc =
    hostCanvas.ownerDocument ??
    (typeof document !== "undefined" ? document : undefined);
  const win = doc?.defaultView;
  const raw = win?.devicePixelRatio ?? 1;
  return Math.min(2.5, Math.max(1, Number.isFinite(raw) ? raw : 1));
}

function loadImageElement(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("image_load_failed"));
    image.src = src;
  });
}

function createOffscreenCanvas(
  hostCanvas: HTMLCanvasElement,
  width: number,
  height: number,
): HTMLCanvasElement {
  const doc = hostCanvas.ownerDocument ?? document;
  const canvas = doc.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  return canvas;
}

function getCanvasContext(
  canvas: HTMLCanvasElement,
): CanvasRenderingContext2D | null {
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
  }
  return ctx;
}

function scaleGeometry(
  g: SliderPieceGeometry,
  dpr: number,
): {
  circleRadius: number;
  originX: number;
  originY: number;
  squareLength: number;
} {
  return {
    circleRadius: g.circle_radius * dpr,
    originX: g.origin_x * dpr,
    originY: g.origin_y * dpr,
    squareLength: g.square_length * dpr,
  };
}

function createLayer(
  hostCanvas: HTMLCanvasElement,
  w: number,
  h: number,
): { canvas: HTMLCanvasElement; ctx: CanvasRenderingContext2D } {
  const canvas = createOffscreenCanvas(hostCanvas, w, h);
  const ctx = getCanvasContext(canvas);
  if (!ctx) {
    throw new Error("canvas_context_unavailable");
  }
  return { canvas, ctx };
}

/**
 * Create a ring of pixels at the inner boundary of the mask.
 *   ring = mask − erode(mask, thickness)
 * Erosion is approximated by intersecting axis-shifted copies.
 */
function createInnerRing(
  hostCanvas: HTMLCanvasElement,
  maskCanvas: HTMLCanvasElement,
  w: number,
  h: number,
  thickness: number,
): HTMLCanvasElement {
  const t = Math.max(1, Math.round(thickness));
  const eroded = createLayer(hostCanvas, w, h);
  eroded.ctx.drawImage(maskCanvas, 0, 0);
  eroded.ctx.globalCompositeOperation = "destination-in";
  for (const [dx, dy] of [
    [t, 0],
    [-t, 0],
    [0, t],
    [0, -t],
  ] as [number, number][]) {
    eroded.ctx.drawImage(maskCanvas, dx, dy);
  }

  const ring = createLayer(hostCanvas, w, h);
  ring.ctx.drawImage(maskCanvas, 0, 0);
  ring.ctx.globalCompositeOperation = "destination-out";
  ring.ctx.drawImage(eroded.canvas, 0, 0);
  return ring.canvas;
}

/**
 * 矢量拼图渲染（GeeTest 风格凹凸 3D 效果）。
 *
 * Slot (凹)：半透明暗色底 → 方向性内阴影 → 反向亮边 → 边缘轮廓线
 * Piece (凸)：底图裁切 → 渐变高光/暗部斜面边框 → 微弱光影洗色
 */
export async function renderSliderAssets(
  payload: SliderChallengePayload,
  boardCanvas: HTMLCanvasElement,
  pieceCanvas: HTMLCanvasElement,
): Promise<null | number> {
  if (!payload.board_image) {
    throw new Error("challenge_assets_missing");
  }

  const geom = resolvePieceGeometry(payload);
  const captureLeft = resolveCaptureLeft(payload);
  if (!geom || captureLeft == null) {
    throw new Error("challenge_geometry_missing");
  }

  const boardImage = await loadImageElement(payload.board_image);

  const dpr = getBitmapDevicePixelRatio(boardCanvas);
  const cw = Number(payload.canvas_width);
  const ch = Number(payload.canvas_height);
  const pw = Number(payload.piece_width);
  const ph = Number(payload.piece_height);
  const pt = Number(payload.piece_top);
  if (
    ![cw, ch, pw, ph].every((n) => Number.isFinite(n) && n > 0) ||
    !Number.isFinite(pt) ||
    pt < 0
  ) {
    throw new Error("challenge_canvas_invalid");
  }

  const boardW = Math.round(cw * dpr);
  const boardH = Math.round(ch * dpr);
  const pieceW = Math.round(pw * dpr);
  const pieceH = Math.round(ph * dpr);
  const pieceTop = Math.round(pt * dpr);
  const captureLeftPx = Math.round(captureLeft * dpr);

  const sg = scaleGeometry(geom, dpr);

  boardCanvas.width = boardW;
  boardCanvas.height = boardH;
  pieceCanvas.width = pieceW;
  pieceCanvas.height = pieceH;

  const boardCtx = getCanvasContext(boardCanvas);
  const pieceCtx = getCanvasContext(pieceCanvas);
  if (!boardCtx || !pieceCtx) {
    throw new Error("canvas_context_unavailable");
  }

  // ── Background ──
  boardCtx.clearRect(0, 0, boardW, boardH);
  boardCtx.drawImage(boardImage, 0, 0, boardW, boardH);

  // ── Jigsaw mask ──
  const maskCanvas = createOffscreenCanvas(boardCanvas, pieceW, pieceH);
  const maskCtx = getCanvasContext(maskCanvas);
  if (!maskCtx) {
    throw new Error("canvas_mask_context_unavailable");
  }
  maskCtx.clearRect(0, 0, pieceW, pieceH);
  fillJigsawPuzzleMask(
    maskCtx,
    sg.originX,
    sg.originY,
    sg.squareLength,
    sg.circleRadius,
  );

  // ================================================================
  // SLOT – 凹 concave hole
  // ================================================================

  // S-1  Semi-transparent dark fill (masked)
  const slotFill = createLayer(boardCanvas, pieceW, pieceH);
  slotFill.ctx.fillStyle = "rgba(0, 0, 0, 0.25)";
  slotFill.ctx.fillRect(0, 0, pieceW, pieceH);
  slotFill.ctx.globalCompositeOperation = "destination-in";
  slotFill.ctx.drawImage(maskCanvas, 0, 0);
  boardCtx.drawImage(slotFill.canvas, captureLeftPx, pieceTop);

  const ringThick = Math.max(1, Math.round(3 * dpr));
  const ringRim = Math.max(1, Math.round(2 * dpr));

  // S-2  Edge shadow (ambient): thick inner ring + blur → darkens near edge only
  const ambientRing = createInnerRing(
    boardCanvas,
    maskCanvas,
    pieceW,
    pieceH,
    ringThick,
  );
  const ambientColored = createLayer(boardCanvas, pieceW, pieceH);
  ambientColored.ctx.drawImage(ambientRing, 0, 0);
  ambientColored.ctx.globalCompositeOperation = "source-in";
  ambientColored.ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
  ambientColored.ctx.fillRect(0, 0, pieceW, pieceH);
  ambientColored.ctx.globalCompositeOperation = "source-over";

  const ambientBlurred = createLayer(boardCanvas, pieceW, pieceH);
  const blurAmbientPx = Math.round(5 * dpr);
  ambientBlurred.ctx.filter = `blur(${blurAmbientPx}px)`;
  ambientBlurred.ctx.drawImage(ambientColored.canvas, 0, 0);
  ambientBlurred.ctx.filter = "none";
  ambientBlurred.ctx.globalCompositeOperation = "destination-in";
  ambientBlurred.ctx.drawImage(maskCanvas, 0, 0);
  boardCtx.drawImage(ambientBlurred.canvas, captureLeftPx, pieceTop);

  // S-3  Edge shadow (directional): shifted ring + stronger blur (light from top-left)
  const dirRing = createInnerRing(
    boardCanvas,
    maskCanvas,
    pieceW,
    pieceH,
    ringThick,
  );
  const dirColored = createLayer(boardCanvas, pieceW, pieceH);
  const dirShift = Math.round(2 * dpr);
  dirColored.ctx.drawImage(dirRing, dirShift, dirShift);
  dirColored.ctx.globalCompositeOperation = "source-in";
  dirColored.ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
  dirColored.ctx.fillRect(0, 0, pieceW, pieceH);
  dirColored.ctx.globalCompositeOperation = "source-over";

  const dirBlurred = createLayer(boardCanvas, pieceW, pieceH);
  const blurDirPx = Math.round(7 * dpr);
  dirBlurred.ctx.filter = `blur(${blurDirPx}px)`;
  dirBlurred.ctx.drawImage(dirColored.canvas, 0, 0);
  dirBlurred.ctx.filter = "none";
  dirBlurred.ctx.globalCompositeOperation = "destination-in";
  dirBlurred.ctx.drawImage(maskCanvas, 0, 0);
  boardCtx.save();
  boardCtx.globalAlpha = 0.5;
  boardCtx.drawImage(dirBlurred.canvas, captureLeftPx, pieceTop);
  boardCtx.restore();

  // S-4  Rim light: thin bright ring, shifted toward bottom-right interior
  const rimRing = createInnerRing(
    boardCanvas,
    maskCanvas,
    pieceW,
    pieceH,
    ringRim,
  );
  const rimColored = createLayer(boardCanvas, pieceW, pieceH);
  const rimShift = Math.round(1.5 * dpr);
  rimColored.ctx.drawImage(rimRing, -rimShift, -rimShift);
  rimColored.ctx.globalCompositeOperation = "source-in";
  rimColored.ctx.fillStyle = "rgba(255, 255, 255, 0.5)";
  rimColored.ctx.fillRect(0, 0, pieceW, pieceH);
  rimColored.ctx.globalCompositeOperation = "source-over";

  const rimBlurred = createLayer(boardCanvas, pieceW, pieceH);
  const blurRimPx = Math.round(3 * dpr);
  rimBlurred.ctx.filter = `blur(${blurRimPx}px)`;
  rimBlurred.ctx.drawImage(rimColored.canvas, 0, 0);
  rimBlurred.ctx.filter = "none";
  rimBlurred.ctx.globalCompositeOperation = "destination-in";
  rimBlurred.ctx.drawImage(maskCanvas, 0, 0);
  boardCtx.save();
  boardCtx.globalAlpha = 0.35;
  boardCtx.drawImage(rimBlurred.canvas, captureLeftPx, pieceTop);
  boardCtx.restore();

  // S-5  Thin edge outline for crispness (no blur)
  const edgeThickness = Math.max(1, Math.round(0.9 * dpr));
  const edgeRing = createInnerRing(
    boardCanvas,
    maskCanvas,
    pieceW,
    pieceH,
    edgeThickness,
  );
  const edgeColored = createLayer(boardCanvas, pieceW, pieceH);
  edgeColored.ctx.drawImage(edgeRing, 0, 0);
  edgeColored.ctx.globalCompositeOperation = "source-in";
  edgeColored.ctx.fillStyle = "rgba(0, 0, 0, 0.2)";
  edgeColored.ctx.fillRect(0, 0, pieceW, pieceH);
  boardCtx.drawImage(edgeColored.canvas, captureLeftPx, pieceTop);

  // ================================================================
  // PIECE – 凸 convex sliding block
  // ================================================================

  // P-1  Cut piece from background
  pieceCtx.clearRect(0, 0, pieceW, pieceH);
  pieceCtx.drawImage(boardImage, -captureLeftPx, -pieceTop, boardW, boardH);
  pieceCtx.save();
  pieceCtx.globalCompositeOperation = "destination-in";
  pieceCtx.drawImage(maskCanvas, 0, 0);
  pieceCtx.restore();

  // P-2  Bevel border (bright top-left → dark bottom-right)
  const bevelThickness = Math.max(1, Math.round(1.0 * dpr));
  const bevelRing = createInnerRing(
    boardCanvas,
    maskCanvas,
    pieceW,
    pieceH,
    bevelThickness,
  );
  const bevelColored = createLayer(boardCanvas, pieceW, pieceH);
  bevelColored.ctx.drawImage(bevelRing, 0, 0);
  bevelColored.ctx.globalCompositeOperation = "source-in";
  const bevelGrad = bevelColored.ctx.createLinearGradient(0, 0, pieceW, pieceH);
  bevelGrad.addColorStop(0, "rgba(255, 255, 255, 0.55)");
  bevelGrad.addColorStop(0.35, "rgba(255, 255, 255, 0.28)");
  bevelGrad.addColorStop(0.65, "rgba(180, 180, 180, 0.12)");
  bevelGrad.addColorStop(1, "rgba(0, 0, 0, 0.15)");
  bevelColored.ctx.fillStyle = bevelGrad;
  bevelColored.ctx.fillRect(0, 0, pieceW, pieceH);
  pieceCtx.drawImage(bevelColored.canvas, 0, 0);

  return captureLeft;
}
