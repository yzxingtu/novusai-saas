// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest';

import { RequestClient } from '../request-client';

describe('request client headers', () => {
  it('does not attach browser cache-control headers by default', () => {
    const client = new RequestClient({ baseURL: 'http://test' });
    const defaults = JSON.stringify(client.instance.defaults.headers);

    expect(defaults).not.toContain('Cache-Control');
    expect(defaults).not.toContain('cache-control');
    expect(defaults).not.toContain('Pragma');
    expect(defaults).not.toContain('pragma');
  });
});
