import { describe, expect, it } from 'vitest';

import { resolveIdentityOption } from '../identity-option';

describe('resolveIdentityOption', () => {
  it('reads identity fields from extra payloads', () => {
    expect(
      resolveIdentityOption({
        label: 'fallback',
        value: 7,
        extra: {
          avatar: '12',
          nickname: 'Yudi',
          orgNodeName: 'Headquarters',
          username: 'yudi',
        },
      }),
    ).toMatchObject({
      avatar: '12',
      architectureLabel: 'Headquarters',
      displayName: 'Yudi',
      secondaryText: 'yudi',
      value: 7,
    });
  });

  it('prefers root fields over extra fields', () => {
    expect(
      resolveIdentityOption({
        label: 'fallback',
        nickname: 'Root Name',
        orgNodeName: 'Root Org',
        username: 'root-user',
        extra: {
          nickname: 'Extra Name',
          orgNodeName: 'Extra Org',
          username: 'extra-user',
        },
      }),
    ).toMatchObject({
      architectureLabel: 'Root Org',
      displayName: 'Root Name',
      secondaryText: 'root-user',
    });
  });

  it('suppresses duplicate secondary text and falls back to label', () => {
    expect(
      resolveIdentityOption({
        label: 'Only Label',
        username: 'Only Label',
      }),
    ).toMatchObject({
      displayName: 'Only Label',
      secondaryText: '',
    });
  });

  it('falls back to display_name and org_node_name from remote select payloads', () => {
    expect(
      resolveIdentityOption({
        value: 'alice',
        extra: {
          display_name: 'Alice Zhang',
          org_node_name: 'North Hub',
          username: 'alice',
        },
      }),
    ).toMatchObject({
      architectureLabel: 'North Hub',
      displayName: 'Alice Zhang',
      secondaryText: 'alice',
      value: 'alice',
    });
  });
});
