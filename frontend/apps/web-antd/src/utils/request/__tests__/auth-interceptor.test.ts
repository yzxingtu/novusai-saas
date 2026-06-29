// @vitest-environment happy-dom
import { describe, expect, it, vi } from 'vitest';

import { createAuthInterceptor } from '../interceptors';
import { RequestClient } from '../request-client';

describe('auth interceptor', () => {
  it('keeps host re-authentication disabled for opted-out plugin requests', async () => {
    const client = new RequestClient();
    const doRefreshToken = vi.fn<() => Promise<string>>();
    const doReAuthenticate = vi.fn<() => Promise<void>>();
    const interceptor = createAuthInterceptor(
      client,
      {
        getRefreshToken: () => null,
        getToken: () => null,
      },
      {
        doRefreshToken,
        doReAuthenticate,
      },
    );
    const error = {
      config: {
        __options: { skipAuthRecovery: true },
        url: '/admin/plugins/weather-widget/api/config',
      },
      response: {
        data: { code: 4010, message: '无效令牌' },
        status: 401,
      },
    };

    await expect(interceptor.rejected(error)).rejects.toBe(error);
    expect(doReAuthenticate).not.toHaveBeenCalled();
    expect(doRefreshToken).not.toHaveBeenCalled();
  });

  it('keeps the default re-authentication behavior for normal 4010 requests', async () => {
    const client = new RequestClient();
    const doRefreshToken = vi.fn<() => Promise<string>>();
    const doReAuthenticate = vi.fn<() => Promise<void>>().mockResolvedValue();
    const interceptor = createAuthInterceptor(
      client,
      {
        getRefreshToken: () => null,
        getToken: () => null,
      },
      {
        doRefreshToken,
        doReAuthenticate,
      },
    );
    const error = {
      config: {
        __options: {},
        url: '/admin/operation-logs',
      },
      response: {
        data: { code: 4010, message: '无效令牌' },
        status: 401,
      },
    };

    await expect(interceptor.rejected(error)).rejects.toBe(error);
    expect(doReAuthenticate).toHaveBeenCalledOnce();
    expect(doRefreshToken).not.toHaveBeenCalled();
  });
});
