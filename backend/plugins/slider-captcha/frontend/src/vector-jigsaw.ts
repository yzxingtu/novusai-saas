/**
 * Jigsaw mask matching backend `SliderCaptchaProvider._build_piece_mask` geometry
 * (rectangle + top/right ellipses − left ellipse). Uses canvas compositing for AA edges.
 */
export function fillJigsawPuzzleMask(
  ctx: CanvasRenderingContext2D,
  originX: number,
  originY: number,
  squareLength: number,
  circleRadius: number,
): void {
  const ox = originX;
  const oy = originY;
  const halfSq = Math.floor(squareLength / 2);
  const right = ox + squareLength;
  const cr = circleRadius;

  ctx.fillStyle = "#ffffff";
  ctx.globalCompositeOperation = "source-over";

  ctx.fillRect(ox, oy, squareLength, squareLength);

  ctx.beginPath();
  ctx.ellipse(
    ox + halfSq,
    oy - circleRadius + 2,
    circleRadius,
    circleRadius,
    0,
    0,
    Math.PI * 2,
  );
  ctx.fill();

  ctx.beginPath();
  ctx.ellipse(
    right + circleRadius - 2,
    oy + halfSq,
    circleRadius,
    circleRadius,
    0,
    0,
    Math.PI * 2,
  );
  ctx.fill();

  ctx.globalCompositeOperation = "destination-out";
  ctx.beginPath();
  ctx.ellipse(
    ox - circleRadius + 2,
    oy + halfSq,
    circleRadius,
    circleRadius,
    0,
    0,
    Math.PI * 2,
  );
  ctx.fill();

  ctx.globalCompositeOperation = "source-over";
}
