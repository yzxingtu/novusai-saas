// Test type: behavioral
// Scope: Announcement API transforms and feedback answer contract.
// Mock strategy: Request transport is mocked; transform and contract logic run real.
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { validateAnnouncementAnswers } from '#/types/announcement';

import { getAnnouncementListApi, getMyAnnouncementApi } from '../announcement';

const { requestGetMock } = vi.hoisted(() => ({
  requestGetMock: vi.fn(),
}));

vi.mock('#/utils/request', () => ({
  requestClient: {
    get: requestGetMock,
  },
}));

describe('announcement admin api transforms', () => {
  beforeEach(() => {
    requestGetMock.mockReset();
  });

  it('normalizes list response from snake_case to camelCase', async () => {
    requestGetMock.mockResolvedValue({
      items: [
        {
          id: 8,
          tenant_id: 0,
          scope: 'admin',
          title: 'Notice',
          content: 'Body',
          status: 'published',
          priority: 'urgent',
          require_response: true,
          form_schema: [{ key: 'agree', type: 'consent', label: 'Agree' }],
          published_at: '2026-04-28T16:56:00Z',
          recipient_count: 3,
          response_count: 2,
          sort_order: 10,
          created_at: '2026-04-28T16:00:00Z',
          updated_at: '2026-04-28T17:00:00Z',
        },
      ],
      page: 1,
      page_size: 20,
      total: 1,
    });

    const result = await getAnnouncementListApi({ 'page[number]': 1 });

    expect(requestGetMock).toHaveBeenCalledWith('/admin/announcements', {
      params: { 'page[number]': 1 },
    });
    expect(result.items[0]).toMatchObject({
      id: 8,
      tenantId: 0,
      scope: 'admin',
      title: 'Notice',
      priority: 'urgent',
      requireResponse: true,
      publishedAt: '2026-04-28T16:56:00Z',
      recipientCount: 3,
      responseCount: 2,
      sortOrder: 10,
    });
  });

  it('normalizes current-recipient announcement detail for notification modal', async () => {
    requestGetMock.mockResolvedValue({
      id: 8,
      tenant_id: 0,
      scope: 'admin',
      title: 'Notice',
      content: 'Body',
      status: 'published',
      priority: 'urgent',
      require_response: true,
      form_schema: [{ key: 'agree', type: 'consent', label: 'Agree' }],
      published_at: '2026-04-28T16:56:00Z',
      recipient_count: 3,
      response_count: 2,
      sort_order: 10,
      delivery_id: 88,
      delivery_status: 'submitted',
      notification_id: 188,
      submitted_at: '2026-04-28T17:00:00Z',
      answers: { agree: true },
      created_at: '2026-04-28T16:00:00Z',
      updated_at: '2026-04-28T17:00:00Z',
    });

    const result = await getMyAnnouncementApi(8);

    expect(requestGetMock).toHaveBeenCalledWith(
      '/admin/announcements/8/mine',
      undefined,
    );
    expect(result).toMatchObject({
      id: 8,
      deliveryId: 88,
      deliveryStatus: 'submitted',
      answers: { agree: true },
      notificationId: 188,
      submittedAt: '2026-04-28T17:00:00Z',
    });
  });
});

describe('announcement answer contract', () => {
  it('rejects missing required answers, invalid options, and false consent', () => {
    const errors = validateAnnouncementAnswers(
      [
        {
          key: 'agree',
          type: 'consent',
          label: 'Agree',
          required: true,
          must_be_true: true,
        },
        {
          key: 'choice',
          type: 'radio',
          label: 'Choice',
          required: true,
          options: [{ label: 'A', value: 'a' }],
        },
        {
          key: 'multi',
          type: 'checkbox',
          label: 'Multi',
          required: true,
          options: [{ label: 'B', value: 'b' }],
        },
      ],
      {
        agree: false,
        choice: 'x',
        multi: [],
      },
    );

    expect(errors).toEqual([
      'agree.must_be_true',
      'choice.invalid_option',
      'multi.required',
    ]);
  });
});
