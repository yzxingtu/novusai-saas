// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  bindRichTextConversation: vi.fn(),
  getRichTextConversationBinding: vi.fn(),
  resolveAgentAssignmentApi: vi.fn(),
  sendChatStreamApi: vi.fn(),
}));

vi.mock('@vben/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('dompurify', () => ({
  default: {
    sanitize: (html: string) => html,
  },
}));

vi.mock('@tiptap/core', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tiptap/core')>();

  return {
    ...actual,
    generateHTML: vi.fn((json: Record<string, any>) => {
      const text = String(
        json.content?.[0]?.content?.[0]?.text ??
          json.content?.[0]?.attrs?.source ??
          '',
      );
      return `<p>${text}</p>`;
    }),
    generateJSON: vi.fn((html: string) => ({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [{ type: 'text', text: String(html).trim() }],
        },
      ],
    })),
    generateText: vi.fn((json: Record<string, any>) =>
      String(
        json.content?.[0]?.content?.[0]?.text ??
          json.content?.[0]?.attrs?.source ??
          '',
      ).trim(),
    ),
  };
});

vi.mock('#/api/shared/agent-assignments', () => ({
  resolveAgentAssignmentApi: mocks.resolveAgentAssignmentApi,
}));

vi.mock('#/api/shared/ai-chat', () => ({
  sendChatStreamApi: mocks.sendChatStreamApi,
}));

vi.mock('#/store/shared/ai-panel', () => ({
  useAIPanelStore: () => ({
    bindRichTextConversation: mocks.bindRichTextConversation,
    getRichTextConversationBinding: mocks.getRichTextConversationBinding,
  }),
}));

function createEditorStub(revision: { value: number }) {
  const insertContentAt = vi.fn();
  const undo = vi.fn();
  const run = vi.fn(() => true);

  const chainApi = {
    focus: vi.fn(() => chainApi),
    insertContentAt: vi.fn((position, content) => {
      insertContentAt(position, content);
      return chainApi;
    }),
    undo: vi.fn(() => {
      undo();
      return chainApi;
    }),
    run,
  };

  const editor = {
    chain: () => chainApi,
    extensionManager: {
      extensions: [],
    },
    getJSON: () => ({
      type: 'doc',
      content: [{ type: 'paragraph' }],
    }),
    isEditable: true,
    state: {
      doc: {
        content: {
          size: 36,
        },
        cut: vi.fn(() => ({
          toJSON: () => ({
            type: 'doc',
            content: [
              {
                type: 'paragraph',
                content: [{ type: 'text', text: 'Selected text' }],
              },
            ],
          }),
        })),
        textBetween: vi.fn((from: number, to: number) => {
          if (from === 10 && to === 23) {
            return 'Selected text';
          }
          if (from === 0 && to === 10) {
            return 'Intro text ';
          }
          if (from === 23 && to === 36) {
            return ' trailing text';
          }
          return '';
        }),
      },
      selection: {
        from: 10,
        to: 23,
      },
    },
  };

  return {
    editor,
    focus: chainApi.focus,
    insertContentAt,
    run,
    undo,
    getRevision: () => revision.value,
  };
}

describe('createTiptapEditorAIAdapter', () => {
  beforeEach(() => {
    mocks.resolveAgentAssignmentApi.mockReset();
    mocks.sendChatStreamApi.mockReset();
    mocks.getRichTextConversationBinding.mockReset();
    mocks.bindRichTextConversation.mockReset();
    window.history.replaceState({}, '', '/tenant/docs/detail');
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('supports preview, apply, and undo for selection-aware operations', async () => {
    const { createTiptapEditorAIAdapter } = await import('../tiptap-adapter');
    const revision = { value: 7 };
    const editorHarness = createEditorStub(revision);

    mocks.resolveAgentAssignmentApi.mockResolvedValue({
      agent_id: 42,
      is_active: true,
    });
    mocks.getRichTextConversationBinding.mockReturnValue(null);
    mocks.sendChatStreamApi.mockImplementation(
      async (_prefix, _agentId, _body, callbacks) => {
        await callbacks.onMessage?.(
          'data: {"conversation_id":66,"event":"message","delta":"Polished answer"}\n',
        );
        await callbacks.onMessage?.(
          'data: {"conversation_id":66,"event":"done","content":"Polished answer"}\n',
        );
        callbacks.onEnd?.();
      },
    );

    const adapter = createTiptapEditorAIAdapter({
      contextTitle: 'Tenant Doc',
      editor: editorHarness.editor as never,
      editorInstanceId: 'editor-under-test',
      getRevision: editorHarness.getRevision,
      pageKey: 'tenant.docs.detail',
    });

    const preview = await adapter.previewOperation({
      feature: 'rewrite',
    });

    expect(preview.selection.selectedText).toBe('Selected text');
    expect(preview.selection.beforeTextExcerpt).toBe('Intro text ');
    expect(preview.selection.afterTextExcerpt).toBe(' trailing text');
    expect(preview.draft.raw).toBe('Polished answer');
    expect(preview.conversationId).toBe(66);
    expect(mocks.resolveAgentAssignmentApi).toHaveBeenCalledWith(
      '/tenant',
      'system.ai_writing',
    );
    expect(mocks.sendChatStreamApi).toHaveBeenCalledWith(
      '/tenant',
      42,
      expect.objectContaining({
        conversation_id: null,
        interaction_mode: 'trusted_auto',
        route_source: 'rich_text_ai',
      }),
      expect.any(Object),
    );
    expect(mocks.bindRichTextConversation).toHaveBeenCalledWith(
      expect.objectContaining({
        agentId: 42,
        conversationId: 66,
        editorInstanceId: 'editor-under-test',
        pageKey: 'tenant.docs.detail',
      }),
    );

    const applyResult = await adapter.applyOperation({
      feature: 'rewrite',
      selection: preview.selection,
    });

    expect(applyResult).toEqual({ applied: true });
    expect(editorHarness.insertContentAt).toHaveBeenCalledWith(
      { from: 10, to: 23 },
      expect.any(Array),
    );
    expect(editorHarness.focus).toHaveBeenCalled();
    expect(editorHarness.run).toHaveBeenCalled();
    expect(adapter.canUndoLastOperation()).toBe(true);
    expect(adapter.undoLastAIOperation()).toBe(true);
    expect(editorHarness.undo).toHaveBeenCalledOnce();
  });
});
