import { describe, expect, it, vi } from "vitest";

import { renderSliderAssets } from "../render-slider-assets";

function createCanvasMock() {
  const context = {
    clearRect: vi.fn(),
    drawImage: vi.fn(),
    getImageData: vi.fn(),
  };
  const canvas = {
    getContext: vi.fn(() => context),
    height: 0,
    width: 0,
  } as unknown as HTMLCanvasElement;

  return { canvas, context };
}

describe("render-slider-assets", () => {
  it("rejects when challenge assets are missing", async () => {
    const { canvas: boardCanvas } = createCanvasMock();
    const { canvas: pieceCanvas } = createCanvasMock();

    await expect(
      renderSliderAssets(
        {
          canvas_height: 180,
          canvas_width: 320,
          piece_height: 48,
          piece_top: 42,
          piece_width: 48,
          tolerance_px: 6,
        },
        boardCanvas,
        pieceCanvas,
      ),
    ).rejects.toThrow("challenge_assets_missing");
  });

  it("rejects when vector geometry is missing", async () => {
    const { canvas: boardCanvas } = createCanvasMock();
    const { canvas: pieceCanvas } = createCanvasMock();

    await expect(
      renderSliderAssets(
        {
          board_image: "data:image/png;base64,xx",
          canvas_height: 180,
          canvas_width: 320,
          piece_height: 48,
          piece_top: 42,
          piece_width: 48,
          tolerance_px: 6,
        },
        boardCanvas,
        pieceCanvas,
      ),
    ).rejects.toThrow("challenge_geometry_missing");
  });
});
