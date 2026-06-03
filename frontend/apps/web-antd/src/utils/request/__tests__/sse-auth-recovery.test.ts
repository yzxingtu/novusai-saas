// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

type RequestClientType = import('../request-client').RequestClient;

vi.mock('#/utils/common', () => ({
  generateUUID: () => 'test-trace-id',
}));

vi.mock('#/constants/endpoints', () => ({
  resolveEndpointByPath: () => 'admin',
}));

function json401(code: number, message: string = 'Token error') {
  return Response.json(
    { code, message },
    {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    },
  );
}

function json200Sse() {
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode('data: {"ok":true}\n\n'));
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  });
}

describe('sse 401 auth recovery', () => {
  let client: RequestClientType;
  const doRefreshToken = vi.fn<() => Promise<string>>();
  const doReAuthenticate = vi.fn<() => Promise<void>>();
  const getToken = vi.fn<(endpoint: string) => null | string>();

  beforeEach(async () => {
    const { RequestClient } = await import('../request-client');
    client = new RequestClient({ baseURL: 'http://test' });
    client.setTokenGetter(getToken as any);
    client.setRefreshTokenHandler(doRefreshToken);
    client.setReAuthenticateHandler(doReAuthenticate);
    getToken.mockReturnValue('old-token');
    doRefreshToken.mockResolvedValue('new-token');
    doReAuthenticate.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('refreshes token and retries on 4011 (TOKEN_EXPIRED)', async () => {
    let callCount = 0;
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(() => {
      callCount++;
      if (callCount === 1) return Promise.resolve(json401(4011));
      getToken.mockReturnValue('new-token');
      return Promise.resolve(json200Sse());
    });

    const messages: string[] = [];
    await client.requestSSE('/chat/stream', { text: 'hi' }, {
      method: 'POST',
      onMessage: (chunk: string) => {
        messages.push(chunk);
      },
      onEnd: () => {},
      onError: () => {},
      abortController: new AbortController(),
    } as any);

    expect(doRefreshToken).toHaveBeenCalledOnce();
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(messages.length).toBeGreaterThan(0);

    fetchSpy.mockRestore();
  });

  it('refreshes token and retries on 4012 (TOKEN_INVALID)', async () => {
    let callCount = 0;
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(() => {
      callCount++;
      if (callCount === 1) return Promise.resolve(json401(4012));
      return Promise.resolve(json200Sse());
    });

    await client.requestSSE('/chat/stream', { text: 'hi' }, {
      method: 'POST',
      onMessage: () => {},
      onEnd: () => {},
      onError: () => {},
      abortController: new AbortController(),
    } as any);

    expect(doRefreshToken).toHaveBeenCalledOnce();
    expect(fetchSpy).toHaveBeenCalledTimes(2);

    fetchSpy.mockRestore();
  });

  it('calls doReAuthenticate on 4010 (UNAUTHORIZED) without refresh', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(json401(4010));
    const errors: Error[] = [];

    await client.requestSSE('/chat/stream', {}, {
      method: 'POST',
      onMessage: () => {},
      onEnd: () => {},
      onError: (err: Error) => {
        errors.push(err);
      },
      abortController: new AbortController(),
    } as any);

    expect(doReAuthenticate).toHaveBeenCalledOnce();
    expect(doRefreshToken).not.toHaveBeenCalled();
    expect(errors).toHaveLength(1);

    fetchSpy.mockRestore();
  });

  it('calls doReAuthenticate when refresh token fails', async () => {
    doRefreshToken.mockRejectedValue(new Error('refresh failed'));
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(json401(4011));
    const errors: Error[] = [];

    await client.requestSSE('/chat/stream', {}, {
      method: 'POST',
      onMessage: () => {},
      onEnd: () => {},
      onError: (err: Error) => {
        errors.push(err);
      },
      abortController: new AbortController(),
    } as any);

    expect(doRefreshToken).toHaveBeenCalledOnce();
    expect(doReAuthenticate).toHaveBeenCalledOnce();
    expect(errors).toHaveLength(1);

    fetchSpy.mockRestore();
  });

  it('sets Accept-Language header when locale getter is configured', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(json200Sse());
    client.setLocaleGetter(() => 'zh-CN');

    await client.requestSSE('/chat/stream', {}, {
      method: 'POST',
      onMessage: () => {},
      onEnd: () => {},
      onError: () => {},
      abortController: new AbortController(),
    } as any);

    const calledHeaders = fetchSpy.mock.calls[0]?.[1]?.headers as Headers;
    expect(calledHeaders?.get('Accept-Language')).toBe('zh-CN');

    fetchSpy.mockRestore();
  });

  it('handles string business code (e.g. "4011") gracefully', async () => {
    let callCount = 0;
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return Promise.resolve(
          Response.json(
            { code: '4011', message: 'expired' },
            {
              status: 401,
              headers: { 'Content-Type': 'application/json' },
            },
          ),
        );
      }
      return Promise.resolve(json200Sse());
    });

    await client.requestSSE('/chat/stream', {}, {
      method: 'POST',
      onMessage: () => {},
      onEnd: () => {},
      onError: () => {},
      abortController: new AbortController(),
    } as any);

    expect(doRefreshToken).toHaveBeenCalledOnce();
    expect(fetchSpy).toHaveBeenCalledTimes(2);

    fetchSpy.mockRestore();
  });

  it('does not call doReAuthenticate when refresh succeeds but retry fails', async () => {
    let callCount = 0;
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(() => {
      callCount++;
      if (callCount === 1) return Promise.resolve(json401(4011));
      return Promise.reject(new TypeError('Network error'));
    });
    const errors: Error[] = [];

    await client.requestSSE('/chat/stream', {}, {
      method: 'POST',
      onMessage: () => {},
      onEnd: () => {},
      onError: (err: Error) => {
        errors.push(err);
      },
      abortController: new AbortController(),
    } as any);

    expect(doRefreshToken).toHaveBeenCalledOnce();
    expect(doReAuthenticate).not.toHaveBeenCalled();
    expect(errors).toHaveLength(1);

    fetchSpy.mockRestore();
  });
});
