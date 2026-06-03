export interface OffsetDetectorInput {
  boardHeight: number;
  boardPixels: Uint8ClampedArray;
  boardWidth: number;
  pieceHeight: number;
  piecePixels: Uint8ClampedArray;
  pieceTop: number;
  pieceWidth: number;
  sampleStep?: number;
}

export function detectTargetOffsetFromImageData(
  input: OffsetDetectorInput,
): null | number {
  const {
    boardHeight,
    boardPixels,
    boardWidth,
    pieceHeight,
    piecePixels,
    pieceTop,
    pieceWidth,
    sampleStep = 2,
  } = input;

  if (
    boardWidth <= 0 ||
    boardHeight <= 0 ||
    pieceWidth <= 0 ||
    pieceHeight <= 0 ||
    pieceTop < 0 ||
    pieceTop + pieceHeight > boardHeight
  ) {
    return null;
  }

  let bestOffset: null | number = null;
  let bestScore = Number.NEGATIVE_INFINITY;

  for (let offset = 0; offset <= boardWidth - pieceWidth; offset++) {
    let activeSamples = 0;
    let darknessScore = 0;

    for (let py = 0; py < pieceHeight; py += sampleStep) {
      const boardY = pieceTop + py;
      for (let px = 0; px < pieceWidth; px += sampleStep) {
        const pieceIndex = (py * pieceWidth + px) * 4;
        const alpha = piecePixels[pieceIndex + 3] ?? 0;
        if (alpha < 28) {
          continue;
        }

        const boardIndex = (boardY * boardWidth + offset + px) * 4;
        const red = boardPixels[boardIndex] ?? 0;
        const green = boardPixels[boardIndex + 1] ?? 0;
        const blue = boardPixels[boardIndex + 2] ?? 0;
        const luminance = red * 0.299 + green * 0.587 + blue * 0.114;
        darknessScore += (255 - luminance) * (alpha / 255);
        activeSamples += 1;
      }
    }

    if (activeSamples === 0) {
      continue;
    }

    const normalizedScore = darknessScore / activeSamples;
    if (normalizedScore > bestScore) {
      bestScore = normalizedScore;
      bestOffset = offset;
    }
  }

  return bestOffset;
}
