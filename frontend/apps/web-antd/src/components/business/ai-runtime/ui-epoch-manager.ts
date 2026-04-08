import type { UIEpochReason, UIEpochRecord } from './types';

const DEFAULT_HISTORY_LIMIT = 30;

export class UIEpochManager {
  private epoch: number;

  private readonly historyLimit: number;

  private readonly records: UIEpochRecord[];

  constructor(initialEpoch = 0, historyLimit = DEFAULT_HISTORY_LIMIT) {
    this.epoch = initialEpoch;
    this.historyLimit = Math.max(1, historyLimit);
    this.records = [];
  }

  bump(
    reason: UIEpochReason,
    metadata?: Record<string, unknown>,
  ): UIEpochRecord {
    this.epoch += 1;
    const record: UIEpochRecord = {
      epoch: this.epoch,
      reason,
      timestamp: Date.now(),
      ...(metadata ? { metadata } : {}),
    };
    this.records.push(record);
    if (this.records.length > this.historyLimit) {
      this.records.splice(0, this.records.length - this.historyLimit);
    }
    return record;
  }

  current(): number {
    return this.epoch;
  }

  history(): UIEpochRecord[] {
    return this.records.map((record) => ({ ...record }));
  }

  reset(value = 0): void {
    this.epoch = Math.max(0, value);
    this.records.splice(0, this.records.length);
  }
}
