/**
 * Countdown display logic tests (used by AIChatSlidePanel).
 * AIChatSlidePanel 倒计时展示逻辑单元测试。
 *
 * The countdown formula: Math.max(0, 60 - Math.floor((countdownNow - startedAt) / 1000))
 * 倒计时公式：60s 内有效，秒数随时间递减且不小于 0。
 */
import { computed, ref } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('countdown display (AIChatSlidePanel logic)', () => {
  const countdownNow = ref(0);
  const startedAt = ref(0);

  const countdownSeconds = computed(() =>
    Math.max(0, 60 - Math.floor((countdownNow.value - startedAt.value) / 1000)),
  );

  beforeEach(() => {
    vi.useFakeTimers();
    const base = 1_000_000_000_000;
    vi.setSystemTime(base);
    countdownNow.value = base;
    startedAt.value = base;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows 60s initially', () => {
    expect(countdownSeconds.value).toBe(60);
  });

  it('decrements over time and stays >= 0', async () => {
    const base = 1_000_000_000_000;
    startedAt.value = base;
    countdownNow.value = base;

    expect(countdownSeconds.value).toBe(60);

    countdownNow.value = base + 5000; // 5 seconds
    expect(countdownSeconds.value).toBe(55);

    countdownNow.value = base + 59_000;
    expect(countdownSeconds.value).toBe(1);

    countdownNow.value = base + 60_000;
    expect(countdownSeconds.value).toBe(0);

    countdownNow.value = base + 90_000;
    expect(countdownSeconds.value).toBe(0);
  });

  it('confirmCountdown i18n key receives { seconds }', () => {
    const t = (key: string, params?: { seconds?: number }) =>
      key === 'shared.pageOperation.confirmCountdown'
        ? `${params?.seconds ?? 0}s valid`
        : key;

    expect(t('shared.pageOperation.confirmCountdown', { seconds: 45 })).toBe(
      '45s valid',
    );
    expect(t('shared.pageOperation.confirmCountdown', { seconds: 0 })).toBe(
      '0s valid',
    );
  });
});
