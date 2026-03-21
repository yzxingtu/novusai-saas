import type { Editor } from '@tiptap/core';

import { computed, effectScope, nextTick, ref, shallowRef } from 'vue';

import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  clearPageContextRegistry,
  registerPageContext,
  resolvePageContext,
} from '#/components/business/ai-slide-panel/page-context-registry';
import {
  clearPageOperationRegistry,
  listPageOperations,
} from '#/components/business/ai-slide-panel/page-operation-registry';

vi.mock('vue-router', () => ({
  useRoute: () => ({
    meta: {},
    path: '/tenant/editor-demo',
  }),
}));

vi.mock('@vben/locales', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@vben/locales')>();
  return {
    ...actual,
    $t: (key: string) => key,
  };
});

import { useEditorPageOps } from '../useEditorPageOps';

function createEditorStub(): Editor {
  return {
    getHTML: () => '<p>Hello editor</p>',
    getText: () => 'Hello editor',
    state: {
      doc: {
        content: {
          size: 18,
        },
        textBetween: () => '',
      },
      selection: {
        from: 0,
        to: 0,
      },
    },
    storage: {
      characterCount: {
        words: () => 2,
      },
    },
  } as unknown as Editor;
}

function createMutableEditorStub() {
  const insertions = {
    appendHtml: '',
    appendPos: -1,
    insertHtml: '',
  };

  const commandCalls = {
    align: '',
    formats: [] as string[],
    headingLevel: 0,
    linkAction: '',
    linkHref: '',
    listType: '',
    table: {
      cols: 0,
      rows: 0,
      withHeaderRow: false,
    },
  };

  const chainApi = {
    focus: () => chainApi,
    insertContent: (html: string) => {
      insertions.insertHtml = html;
      return chainApi;
    },
    insertContentAt: (pos: number, html: string) => {
      insertions.appendPos = pos;
      insertions.appendHtml = html;
      return chainApi;
    },
    toggleBold: () => {
      commandCalls.formats.push('bold');
      return chainApi;
    },
    toggleItalic: () => {
      commandCalls.formats.push('italic');
      return chainApi;
    },
    toggleUnderline: () => {
      commandCalls.formats.push('underline');
      return chainApi;
    },
    toggleStrike: () => {
      commandCalls.formats.push('strike');
      return chainApi;
    },
    toggleCode: () => {
      commandCalls.formats.push('code');
      return chainApi;
    },
    toggleHighlight: () => {
      commandCalls.formats.push('highlight');
      return chainApi;
    },
    toggleHeading: ({ level }: { level: number }) => {
      commandCalls.headingLevel = level;
      return chainApi;
    },
    toggleOrderedList: () => {
      commandCalls.listType = 'ordered';
      return chainApi;
    },
    toggleBulletList: () => {
      commandCalls.listType = 'bullet';
      return chainApi;
    },
    setTextAlign: (align: string) => {
      commandCalls.align = align;
      return chainApi;
    },
    extendMarkRange: () => chainApi,
    unsetLink: () => {
      commandCalls.linkAction = 'unset';
      commandCalls.linkHref = '';
      return chainApi;
    },
    setLink: ({ href }: { href: string }) => {
      commandCalls.linkAction = 'set';
      commandCalls.linkHref = href;
      return chainApi;
    },
    insertTable: (payload: {
      cols: number;
      rows: number;
      withHeaderRow: boolean;
    }) => {
      commandCalls.table = payload;
      return chainApi;
    },
    run: () => true,
  };

  const editor = {
    ...createEditorStub(),
    chain: () => chainApi,
    commands: {
      selectAll: vi.fn(),
      setContent: vi.fn(),
    },
  } as unknown as Editor;

  return { editor, insertions, commandCalls };
}

describe('useEditorPageOps', () => {
  afterEach(() => {
    clearPageContextRegistry();
    clearPageOperationRegistry();
  });

  it('appends editor extras without overriding the primary page entity context', () => {
    registerPageContext('tenant.docs.detail', () => ({
      page_key: 'tenant.docs.detail',
      page_title: 'Document Detail',
      page_data: {
        entity_description: 'Primary document detail context.',
        entity_name: 'Document',
        resource: '/tenant/docs',
      },
    }));

    const scope = effectScope();
    scope.run(() => {
      useEditorPageOps(shallowRef(createEditorStub()), {
        editable: true,
        enabled: true,
        pageKey: 'tenant.docs.detail',
      });
    });

    const context = resolvePageContext('tenant.docs.detail');
    expect(context).not.toBeNull();
    expect(context!.page_data?.entity_name).toBe('Document');
    expect(context!.page_data?.resource).toBe('/tenant/docs');
    expect(String(context!.page_data?.entity_description ?? '')).toContain(
      'Primary document detail context.',
    );
    expect(String(context!.page_data?.entity_description ?? '')).toContain(
      'HTML 富文本编辑器',
    );
    expect(context!.page_data?.has_editor).toBe(true);
    expect(context!.page_data?.editor_editable).toBe(true);

    scope.stop();
  });

  it('only exposes readonly editor operations when editor is not editable', () => {
    const scope = effectScope();
    scope.run(() => {
      useEditorPageOps(shallowRef(createEditorStub()), {
        editable: false,
        enabled: true,
        pageKey: 'tenant.docs.editor',
      });
    });

    const names = listPageOperations('tenant.docs.editor').map((op) => op.name);
    expect(names).toContain('get_editor_html');
    expect(names).toContain('get_editor_text');
    expect(names).toContain('get_selection');
    expect(names).not.toContain('replace_content');
    expect(names).not.toContain('append_content');
    expect(names).not.toContain('format_text');

    scope.stop();
  });

  it('reactively unregisters editor operations when AI exposure is disabled', async () => {
    const enabled = ref(true);

    const scope = effectScope();
    scope.run(() => {
      useEditorPageOps(shallowRef(createEditorStub()), {
        editable: true,
        enabled: computed(() => enabled.value),
        pageKey: 'tenant.docs.toggle',
      });
    });

    expect(listPageOperations('tenant.docs.toggle').length).toBeGreaterThan(0);

    enabled.value = false;
    await nextTick();

    const names = listPageOperations('tenant.docs.toggle').map((op) => op.name);
    expect(names).toContain('read_current_view');
    expect(names).toContain('read_current_sections');
    expect(names).not.toContain('get_editor_html');
    expect(names).not.toContain('replace_content');

    scope.stop();
  });

  it('reuses the shared content mutation builder for insert and append commands', async () => {
    const { editor, insertions } = createMutableEditorStub();

    const scope = effectScope();
    scope.run(() => {
      useEditorPageOps(shallowRef(editor), {
        editable: true,
        enabled: true,
        pageKey: 'tenant.docs.mutation',
      });
    });

    const operations = listPageOperations('tenant.docs.mutation');
    const insertOp = operations.find((op) => op.name === 'insert_content');
    const appendOp = operations.find((op) => op.name === 'append_content');

    const insertResult = await insertOp?.handler?.({
      content: '# Heading',
      content_format: 'markdown',
    });
    const appendResult = await appendOp?.handler?.({
      content: '<p>Tail</p>',
      content_format: 'html',
    });

    expect(insertions.insertHtml).toContain('<h1>Heading</h1>');
    expect(insertions.appendPos).toBe(18);
    expect(insertions.appendHtml).toBe('<p>Tail</p>');
    expect(insertResult).toEqual({
      success: true,
      message: 'common.editorOp.insertedChars',
    });
    expect(appendResult).toEqual({
      success: true,
      message: 'common.editorOp.appendedChars',
    });

    scope.stop();
  });

  it('reuses shared command helpers for enum and numeric editor operations', async () => {
    const { editor, commandCalls } = createMutableEditorStub();

    const scope = effectScope();
    scope.run(() => {
      useEditorPageOps(shallowRef(editor), {
        editable: true,
        enabled: true,
        pageKey: 'tenant.docs.commands',
      });
    });

    const operations = listPageOperations('tenant.docs.commands');
    const formatOp = operations.find((op) => op.name === 'format_text');
    const headingOp = operations.find((op) => op.name === 'set_heading');
    const listOp = operations.find((op) => op.name === 'toggle_list');
    const alignOp = operations.find((op) => op.name === 'set_text_align');
    const linkOp = operations.find((op) => op.name === 'manage_link');
    const tableOp = operations.find((op) => op.name === 'insert_table');

    const formatResult = await formatOp?.handler?.({ command: ' italic ' });
    const headingResult = await headingOp?.handler?.({ level: 9 });
    const listResult = await listOp?.handler?.({ type: 'unknown' });
    const alignResult = await alignOp?.handler?.({ align: 'CENTER' });
    const linkResult = await linkOp?.handler?.({
      action: 'SET',
      href: 'https://example.com',
    });
    const tableResult = await tableOp?.handler?.({ rows: 20, cols: 0 });

    expect(commandCalls.formats).toEqual(['italic']);
    expect(commandCalls.headingLevel).toBe(3);
    expect(commandCalls.listType).toBe('bullet');
    expect(commandCalls.align).toBe('center');
    expect(commandCalls.linkAction).toBe('set');
    expect(commandCalls.linkHref).toBe('https://example.com');
    expect(commandCalls.table).toEqual({
      rows: 10,
      cols: 1,
      withHeaderRow: true,
    });
    expect(formatResult).toEqual({
      success: true,
      message: 'common.editorOp.toggledFormat',
    });
    expect(headingResult).toEqual({
      success: true,
      message: 'common.editorOp.headingApplied',
    });
    expect(listResult).toEqual({
      success: true,
      message: 'common.editorOp.listToggled',
    });
    expect(alignResult).toEqual({
      success: true,
      message: 'common.editorOp.alignApplied',
    });
    expect(linkResult).toEqual({
      success: true,
      message: 'common.editorOp.linkSet',
    });
    expect(tableResult).toEqual({
      success: true,
      message: 'common.editorOp.tableInserted',
    });

    scope.stop();
  });
});
