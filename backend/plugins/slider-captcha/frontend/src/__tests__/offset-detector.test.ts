import { describe, expect, it } from "vitest";

import { detectTargetOffsetFromImageData } from "../offset-detector";

function createBoardPixels(
  width: number,
  height: number,
  targetLeft: number,
  targetTop: number,
  targetWidth: number,
  targetHeight: number,
) {
  const pixels = new Uint8ClampedArray(width * height * 4);

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const index = (y * width + x) * 4;
      const inTarget =
        x >= targetLeft &&
        x < targetLeft + targetWidth &&
        y >= targetTop &&
        y < targetTop + targetHeight;

      const value = inTarget ? 20 : 220;
      pixels[index] = value;
      pixels[index + 1] = value;
      pixels[index + 2] = value;
      pixels[index + 3] = 255;
    }
  }

  return pixels;
}

function createPiecePixels(width: number, height: number) {
  const pixels = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const index = (y * width + x) * 4;
      pixels[index] = 200;
      pixels[index + 1] = 200;
      pixels[index + 2] = 200;
      pixels[index + 3] = 255;
    }
  }
  return pixels;
}

describe("offset-detector", () => {
  it("detects the darkest matching slot offset", () => {
    const boardWidth = 100;
    const boardHeight = 60;
    const pieceWidth = 20;
    const pieceHeight = 20;
    const pieceTop = 16;
    const targetLeft = 47;

    const offset = detectTargetOffsetFromImageData({
      boardHeight,
      boardPixels: createBoardPixels(
        boardWidth,
        boardHeight,
        targetLeft,
        pieceTop,
        pieceWidth,
        pieceHeight,
      ),
      boardWidth,
      pieceHeight,
      piecePixels: createPiecePixels(pieceWidth, pieceHeight),
      pieceTop,
      pieceWidth,
      sampleStep: 1,
    });

    expect(offset).toBe(targetLeft);
  });

  it("returns null for invalid geometry", () => {
    const offset = detectTargetOffsetFromImageData({
      boardHeight: 40,
      boardPixels: new Uint8ClampedArray(40 * 40 * 4),
      boardWidth: 40,
      pieceHeight: 12,
      piecePixels: new Uint8ClampedArray(12 * 12 * 4),
      pieceTop: 35,
      pieceWidth: 12,
    });

    expect(offset).toBeNull();
  });
});
