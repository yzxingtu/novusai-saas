let runtimeEpochFloor = 0;

export function getRuntimeEpochFloor(): number {
  return runtimeEpochFloor;
}

export function setRuntimeEpochFloor(nextEpoch: number): number {
  const normalized = Number.isFinite(nextEpoch)
    ? Math.max(0, Math.floor(nextEpoch))
    : 0;
  runtimeEpochFloor = Math.max(runtimeEpochFloor, normalized);
  return runtimeEpochFloor;
}

export function resetRuntimeEpochFloor(): void {
  runtimeEpochFloor = 0;
}
