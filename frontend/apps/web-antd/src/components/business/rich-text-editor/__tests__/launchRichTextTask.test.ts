// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { launchRichTextTask } from '../ai/launchRichTextTask';

const mocks = vi.hoisted(() => ({
  message: {
    error: vi.fn(),
    warning: vi.fn(),
  },
  open: vi.fn(),
  resolveAgentAssignmentApi: vi.fn(),
  setPendingRichTextTask: vi.fn(),
}));

vi.mock('ant-design-vue', () => ({
  message: mocks.message,
}));

vi.mock('#/api/shared/agent-assignments', () => ({
  resolveAgentAssignmentApi: mocks.resolveAgentAssignmentApi,
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/store', () => ({
  useAIPanelStore: () => ({
    open: mocks.open,
    setPendingRichTextTask: mocks.setPendingRichTextTask,
  }),
}));

describe('launchRichTextTask', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/tenant/documents/demo');
    mocks.message.error.mockReset();
    mocks.message.warning.mockReset();
    mocks.open.mockReset();
    mocks.resolveAgentAssignmentApi.mockReset();
    mocks.setPendingRichTextTask.mockReset();
    mocks.resolveAgentAssignmentApi.mockResolvedValue({
      agent_id: 42,
      agent_name: 'Writer',
      is_active: true,
    });
  });

  it('captures selection excerpts with document positions instead of string slices', async () => {
    const textBetween = vi.fn((from: number, to: number) => {
      if (from === 0 && to === 7) {
        return 'before-block';
      }
      if (from === 7 && to === 11) {
        return 'chosen text';
      }
      if (from === 11 && to === 29) {
        return 'after-block';
      }
      return `range:${from}-${to}`;
    });

    const editor = {
      getText: vi.fn(() => 'tiny'),
      state: {
        doc: {
          content: {
            size: 29,
          },
          textBetween,
        },
        selection: {
          from: 7,
          to: 11,
        },
      },
    };

    const launched = await launchRichTextTask({
      contextTitle: 'Document A',
      editor: editor as never,
      editorInstanceId: 'editor-1',
      feature: 'rewrite',
      getRevision: () => 5,
      pageKey: '/tenant/documents/detail',
    });

    expect(launched).toBe(true);
    expect(editor.getText).not.toHaveBeenCalled();
    expect(textBetween).toHaveBeenNthCalledWith(1, 7, 11, '\n');
    expect(textBetween).toHaveBeenNthCalledWith(2, 0, 7, '\n');
    expect(textBetween).toHaveBeenNthCalledWith(3, 11, 29, '\n');
    expect(mocks.setPendingRichTextTask).toHaveBeenCalledWith(
      expect.objectContaining({
        agentId: 42,
        editorInstanceId: 'editor-1',
        pageKey: 'tenant.documents.detail',
        selectionSnapshot: expect.objectContaining({
          afterTextExcerpt: 'after-block',
          beforeTextExcerpt: 'before-block',
          editorRevision: 5,
          from: 7,
          pageKey: 'tenant.documents.detail',
          selectedText: 'chosen text',
          to: 11,
        }),
      }),
    );
    expect(mocks.setPendingRichTextTask.mock.calls[0]?.[0]?.message).toContain(
      'Before selection:\nbefore-block',
    );
    expect(mocks.setPendingRichTextTask.mock.calls[0]?.[0]?.message).toContain(
      'After selection:\nafter-block',
    );
    expect(mocks.open).toHaveBeenCalledOnce();
  });
});
