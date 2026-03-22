// @vitest-environment happy-dom
/**
 * Page context editor ops tests / 页面上下文与富文本操作测试
 *
 * 验证富文本专用 tools 整改：
 * - available_operations 含 params（供 PageToolExpander 展开 pageop_*）
 * - registerPageContextExtras 合并不覆盖主 context
 * - entity_description_append 正确追加
 */
import { afterEach, describe, expect, it } from 'vitest';

import {
  clearPageContextRegistry,
  registerPageContext,
  registerPageContextExtras,
  resolvePageContext,
} from '../page-context-registry';
import {
  appendPageOperations,
  clearPageOperationRegistry,
  listPageOperations,
  registerPageOperations,
} from '../page-operation-registry';

describe('Page context editor ops', () => {
  const EDITOR_KEY = 'tenant.plugins.novusdoc.editor.42';

  afterEach(() => {
    clearPageContextRegistry();
    clearPageOperationRegistry();
  });

  it('available_operations includes params when op has params', () => {
    registerPageOperations(EDITOR_KEY, [
      {
        name: 'replace_section',
        label: 'Replace Section',
        description: 'Replace HTML section',
        readonly: false,
        params: {
          old_html: { type: 'string', description: 'Existing HTML snippet' },
          new_html: { type: 'string', description: 'Replacement HTML' },
          content_format: { type: 'string', enum: ['html', 'markdown'] },
        },
      },
    ]);

    const ops = listPageOperations(EDITOR_KEY);
    const replaceSection = ops.find((o) => o.name === 'replace_section');
    expect(replaceSection).toBeDefined();
    expect(replaceSection!.params).toBeDefined();
    expect(replaceSection!.params!.old_html).toBeDefined();
    expect(replaceSection!.params!.content_format).toEqual({ type: 'string', enum: ['html', 'markdown'] });
  });

  it('provides default page read operations for unregistered pages', () => {
    const ops = listPageOperations('admin.dashboard');
    expect(ops.map((op) => op.name)).toContain('read_current_view');
    expect(ops.map((op) => op.name)).toContain('read_current_sections');
  });

  it('page-specific registrations override same-named default operations', () => {
    registerPageOperations('admin.dashboard', [
      {
        name: 'read_current_view',
        label: 'Custom Current View',
        description: 'Custom read view implementation',
        readonly: true,
        handler: async () => ({ success: true, message: 'custom' }),
      },
    ]);

    const operation = listPageOperations('admin.dashboard').find(
      (item) => item.name === 'read_current_view',
    );
    expect(operation?.label).toBe('Custom Current View');
  });

  it('registerPageContextExtras merges without overwriting primary entity_description', () => {
    const primaryDesc = 'Primary editor context. Use get_editor_html, replace_section.';
    registerPageContext(EDITOR_KEY, () => ({
      page_key: EDITOR_KEY,
      page_title: 'Editor',
      page_data: {
        entity_description: primaryDesc,
        has_editor: true,
      },
    }));

    registerPageContextExtras(EDITOR_KEY, () => ({
      page_key: EDITOR_KEY,
      page_data: {
        entity_description_append: 'update_title modifies document metadata title, not body H1.',
        document_id: 42,
      },
    }));

    const resolved = resolvePageContext(EDITOR_KEY);
    expect(resolved).not.toBeNull();
    const desc = resolved!.page_data?.entity_description;
    expect(desc).toContain(primaryDesc);
    expect(desc).toContain('update_title modifies document metadata title');
    expect(resolved!.page_data?.document_id).toBe(42);
  });

  it('enriched available_operations includes params when ops have params (payload shape for AIChatSlidePanel)', () => {
    registerPageOperations(EDITOR_KEY, [
      {
        name: 'replace_content',
        label: 'Replace Content',
        description: 'Replace editor content',
        readonly: false,
        params: {
          content: { type: 'string', description: 'HTML or Markdown content' },
          content_format: { type: 'string', enum: ['html', 'markdown'] },
        },
      },
    ]);

    const ops = listPageOperations(EDITOR_KEY);
    // Same mapping as AIChatSlidePanel enrichPageContextWithOperations
    const available_operations = ops.map((op) => ({
      name: op.name,
      label: op.label,
      description: op.description,
      readonly: op.readonly,
      ...(op.params ? { params: op.params } : {}),
    }));

    const replaceOp = available_operations.find((o) => o.name === 'replace_content');
    expect(replaceOp).toBeDefined();
    expect(replaceOp!.params).toBeDefined();
    expect((replaceOp!.params as Record<string, unknown>).content).toBeDefined();
    expect((replaceOp!.params as Record<string, unknown>).content_format).toEqual({
      type: 'string',
      enum: ['html', 'markdown'],
    });
  });

  it('DocumentEditor appendPageOperations: platform editor ops preserved, document ops appended', () => {
    // Platform (useEditorPageOps) registers editor ops first
    registerPageOperations(EDITOR_KEY, [
      { name: 'get_editor_html', label: 'Get HTML', description: 'Read', readonly: true, handler: async () => ({ success: true, message: '' }) },
      { name: 'replace_section', label: 'Replace', description: 'Replace', readonly: false, handler: async () => ({ success: true, message: '' }) },
    ]);

    // DocumentEditor appends document ops (save_document, update_title, etc.) without replacing
    const cleanupAppend = appendPageOperations(EDITOR_KEY, [
      { name: 'save_document', label: 'Save', description: 'Save document', readonly: false, handler: async () => ({ success: true, message: '' }) },
      { name: 'update_title', label: 'Update title', description: 'Change title', readonly: false, params: { title: { type: 'string' } }, handler: async () => ({ success: true, message: '' }) },
    ]);

    const ops = listPageOperations(EDITOR_KEY);
    const names = ops.map((o) => o.name);
    expect(names).toContain('get_editor_html');
    expect(names).toContain('replace_section');
    expect(names).toContain('save_document');
    expect(names).toContain('update_title');
    expect(ops.find((o) => o.name === 'update_title')?.params?.title).toBeDefined();

    cleanupAppend();
    const afterCleanup = listPageOperations(EDITOR_KEY).map((o) => o.name);
    expect(afterCleanup).toContain('get_editor_html');
    expect(afterCleanup).toContain('replace_section');
    expect(afterCleanup).not.toContain('save_document');
    expect(afterCleanup).not.toContain('update_title');
  });

  it('appendPageOperations survives later primary register and can override thin legacy ops', () => {
    const cleanupAppend = appendPageOperations(EDITOR_KEY, [
      {
        name: 'search',
        label: 'Structured Search',
        description: 'Schema-driven search',
        readonly: true,
        params: {
          status: { type: 'string' },
        },
        handler: async () => ({ success: true, message: '' }),
      },
      {
        name: 'next_page',
        label: 'Next Page',
        description: 'Go to next page',
        readonly: true,
        handler: async () => ({ success: true, message: '' }),
      },
    ]);

    registerPageOperations(EDITOR_KEY, [
      {
        name: 'refresh_list',
        label: 'Refresh',
        description: 'Refresh list',
        readonly: true,
        handler: async () => ({ success: true, message: '' }),
      },
      {
        name: 'search',
        label: 'Legacy Search',
        description: 'Keyword only',
        readonly: true,
        handler: async () => ({ success: true, message: '' }),
      },
    ]);

    const ops = listPageOperations(EDITOR_KEY);
    expect(ops.map((op) => op.name)).toEqual([
      'read_current_view',
      'read_current_sections',
      'refresh_list',
      'search',
      'next_page',
    ]);
    expect(ops.find((op) => op.name === 'search')?.label).toBe('Structured Search');

    cleanupAppend();
    const afterCleanup = listPageOperations(EDITOR_KEY);
    expect(afterCleanup.map((op) => op.name)).toEqual([
      'read_current_view',
      'read_current_sections',
      'refresh_list',
      'search',
    ]);
    expect(afterCleanup.find((op) => op.name === 'search')?.label).toBe('Legacy Search');
  });

  it('DocumentEditor-style extras: merge does not overwrite platform entity_description', () => {
    const baseDesc = 'Base description from platform';
    registerPageContext(EDITOR_KEY, () => ({
      page_key: EDITOR_KEY,
      page_data: { entity_description: baseDesc },
    }));

    registerPageContextExtras(EDITOR_KEY, () => ({
      page_key: EDITOR_KEY,
      page_data: {
        entity_description_append: 'Appended by DocumentEditor.',
        document_title: 'Doc Title',
      },
    }));

    const resolved = resolvePageContext(EDITOR_KEY);
    expect(resolved!.page_data?.entity_description).toBe(baseDesc + '\n\nAppended by DocumentEditor.');
    expect(resolved!.page_data?.document_title).toBe('Doc Title');
  });

  it('extras also merge into DOM fallback context when no primary resolver exists', () => {
    registerPageContextExtras(EDITOR_KEY, () => ({
      page_key: EDITOR_KEY,
      page_data: {
        document_id: 42,
        entity_description_append: 'Editor extras merged into fallback.',
      },
    }));

    const resolved = resolvePageContext(EDITOR_KEY);
    expect(resolved).not.toBeNull();
    expect(resolved!.page_key).toBe(EDITOR_KEY);
    expect(resolved!.page_data?.document_id).toBe(42);
    expect(String(resolved!.page_data?.entity_description ?? '')).toContain(
      'Editor extras merged into fallback.',
    );
  });
});
