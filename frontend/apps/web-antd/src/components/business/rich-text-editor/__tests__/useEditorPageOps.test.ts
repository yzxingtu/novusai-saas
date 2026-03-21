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
    storage: {
      characterCount: {
        words: () => 2,
      },
    },
  } as unknown as Editor;
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
});
