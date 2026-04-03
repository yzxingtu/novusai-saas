import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useNotificationToast } from '../use-notification-toast';

describe('useNotificationToast', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useNotificationToast().clearAll();
  });

  afterEach(() => {
    useNotificationToast().clearAll();
    vi.useRealTimers();
  });

  it('auto-dismisses normal priority toasts after the default timeout', () => {
    const toast = useNotificationToast();

    toast.pushToast({
      category: 'system',
      title: 'Hello',
    });

    expect(toast.toasts.value).toHaveLength(1);
    vi.advanceTimersByTime(5000);
    expect(toast.toasts.value).toHaveLength(0);
  });

  it('queues overflow toasts and promotes the next item when one is removed', () => {
    const toast = useNotificationToast();

    for (let idx = 1; idx <= 4; idx += 1) {
      toast.pushToast({
        category: 'system',
        title: `Toast ${idx}`,
      });
    }

    expect(toast.toasts.value.map((item) => item.title)).toEqual([
      'Toast 1',
      'Toast 2',
      'Toast 3',
    ]);

    toast.removeToast(toast.toasts.value[0]!.id);

    expect(toast.toasts.value).toHaveLength(3);
    expect(toast.toasts.value.map((item) => item.title)).toContain('Toast 4');
  });

  it('keeps urgent toasts open without auto-close timers', () => {
    const toast = useNotificationToast();

    toast.pushToast({
      category: 'system',
      priority: 'urgent',
      title: 'Urgent',
    });

    vi.advanceTimersByTime(10000);
    expect(toast.toasts.value.map((item) => item.title)).toEqual(['Urgent']);
  });
});
