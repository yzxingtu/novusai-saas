import type { SourceEditorRegistration } from '../types';

import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  registerSourceEditor,
  resolveSourceEditor,
  sourceEditorRegistryVersion,
  subscribeSourceEditorRevision,
  updateSourceEditorRevision,
} from '../sourceEditorRegistry';

const cleanups: Array<() => void> = [];

function createRegistration(
  pageKey: string,
  editorInstanceId: string,
  revision = 1,
  setRevision?: (revision: number) => void,
): SourceEditorRegistration {
  return {
    pageKey,
    editorInstanceId,
    revision,
    setRevision,
    appendToEnd: () => true,
    focus: () => {},
    getHTML: () => '<p>Hello</p>',
    getRevision: () => revision,
    getText: () => 'Hello',
    insertAfterRange: () => true,
    isMounted: () => true,
    replaceRange: () => true,
    undo: () => true,
  };
}

afterEach(() => {
  while (cleanups.length > 0) {
    cleanups.pop()?.();
  }
});

describe('sourceEditorRegistry', () => {
  it('registers and unregisters source editors with normalized page keys', () => {
    const beforeVersion = sourceEditorRegistryVersion.value;
    const registration = createRegistration(
      '/tenant/docs/detail',
      'editor-register',
    );
    const unregister = registerSourceEditor(registration);
    cleanups.push(unregister);

    const resolved = resolveSourceEditor(
      'tenant.docs.detail',
      registration.editorInstanceId,
    );

    expect(resolved).toMatchObject({
      editorInstanceId: 'editor-register',
      pageKey: '/tenant/docs/detail',
      revision: 1,
    });
    expect(sourceEditorRegistryVersion.value).toBe(beforeVersion + 1);

    unregister();

    expect(
      resolveSourceEditor('tenant.docs.detail', registration.editorInstanceId),
    ).toBeNull();
    expect(sourceEditorRegistryVersion.value).toBe(beforeVersion + 2);
  });

  it('updates revisions once and notifies the registered listeners', () => {
    const setRevision = vi.fn();
    const listener = vi.fn();
    const registration = createRegistration(
      'tenant/docs/revision',
      'editor-revision',
      1,
      setRevision,
    );
    const unregister = registerSourceEditor(registration);
    cleanups.push(unregister);

    const unsubscribe = subscribeSourceEditorRevision(
      'tenant.docs.revision',
      registration.editorInstanceId,
      listener,
    );
    cleanups.push(unsubscribe);

    const beforeVersion = sourceEditorRegistryVersion.value;

    updateSourceEditorRevision(
      '/tenant/docs/revision',
      registration.editorInstanceId,
      2,
    );

    expect(
      resolveSourceEditor('tenant.docs.revision', registration.editorInstanceId)
        ?.revision,
    ).toBe(2);
    expect(setRevision).toHaveBeenCalledOnce();
    expect(setRevision).toHaveBeenCalledWith(2);
    expect(listener).toHaveBeenCalledOnce();
    expect(listener).toHaveBeenCalledWith(2);
    expect(sourceEditorRegistryVersion.value).toBe(beforeVersion + 1);

    updateSourceEditorRevision(
      'tenant.docs.revision',
      registration.editorInstanceId,
      2,
    );

    expect(setRevision).toHaveBeenCalledTimes(1);
    expect(listener).toHaveBeenCalledTimes(1);
    expect(sourceEditorRegistryVersion.value).toBe(beforeVersion + 1);
  });

  it('keeps the latest registration when a stale cleanup runs after replacement', () => {
    const first = createRegistration('tenant/docs/rebind', 'editor-rebind', 1);
    const second = createRegistration('tenant/docs/rebind', 'editor-rebind', 3);

    const unregisterFirst = registerSourceEditor(first);
    const unregisterSecond = registerSourceEditor(second);
    cleanups.push(unregisterSecond);

    unregisterFirst();

    expect(
      resolveSourceEditor('tenant.docs.rebind', 'editor-rebind'),
    ).toMatchObject({
      editorInstanceId: 'editor-rebind',
      revision: 3,
    });

    unregisterSecond();

    expect(
      resolveSourceEditor('tenant.docs.rebind', 'editor-rebind'),
    ).toBeNull();
  });
});
