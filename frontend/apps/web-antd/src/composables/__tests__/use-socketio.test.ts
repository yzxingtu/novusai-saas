// @vitest-environment happy-dom
import { describe, expect, it, vi } from 'vitest';

vi.mock('socket.io-client', () => ({
  io: vi.fn(),
}));

import { withSocketTracePayload } from '../use-socketio';

describe('withSocketTracePayload', () => {
  it('injects trace_id into plain object payloads', () => {
    const payload = withSocketTracePayload<{
      action: string;
      trace_id?: string;
    }>({ action: 'ping' });

    expect(payload).toMatchObject({
      action: 'ping',
      trace_id: expect.any(String),
    });
    expect(payload.trace_id).toHaveLength(36);
  });

  it('preserves explicit trace_id on payload', () => {
    const payload = withSocketTracePayload<{
      action: string;
      trace_id?: string;
    }>({
      action: 'ping',
      trace_id: 'trace-explicit',
    });

    expect(payload).toEqual({
      action: 'ping',
      trace_id: 'trace-explicit',
    });
  });

  it('leaves non-object payloads unchanged', () => {
    expect(withSocketTracePayload('ping')).toBe('ping');
    expect(withSocketTracePayload(123)).toBe(123);
    expect(withSocketTracePayload(['ping'])).toEqual(['ping']);
  });
});
