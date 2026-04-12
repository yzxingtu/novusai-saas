import type {
  RichTextEditorSetContentOptions,
  SourceEditorRegistration,
} from './types';

import { ref } from 'vue';

import DOMPurify from 'dompurify';
import MarkdownIt from 'markdown-it';

import { normalizePageKey } from '#/components/business/ai-runtime/page-key-utils';

const markdown = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  typographer: false,
});

type RegistryListener = (revision: number) => void;

interface SourceEditorEntry extends SourceEditorRegistration {
  listeners: Set<RegistryListener>;
  registrationRef: SourceEditorRegistration;
}

function registryKey(pageKey: string, editorInstanceId: string): string {
  return `${normalizePageKey(pageKey)}::${editorInstanceId}`;
}

const sourceEditors = new Map<string, SourceEditorEntry>();
export const sourceEditorRegistryVersion = ref(0);

function bumpRegistryVersion() {
  sourceEditorRegistryVersion.value += 1;
}

export function createEditorInstanceId(): string {
  if (
    typeof crypto !== 'undefined' &&
    typeof crypto.randomUUID === 'function'
  ) {
    return crypto.randomUUID();
  }
  return `rich-text-editor-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function prepareRichTextContent(
  content: string,
  options: RichTextEditorSetContentOptions & {
    mode?: 'formatted' | 'plain';
  } = {},
): string {
  if (options.mode !== 'formatted') {
    return content;
  }
  return DOMPurify.sanitize(markdown.render(content))
    .replaceAll(/>\s+</g, '><')
    .trim();
}

export function registerSourceEditor(
  sourceEditor: SourceEditorRegistration,
): () => void {
  const key = registryKey(sourceEditor.pageKey, sourceEditor.editorInstanceId);
  const existing = sourceEditors.get(key);
  if (existing) {
    existing.listeners.clear();
  }
  sourceEditors.set(key, {
    ...sourceEditor,
    listeners: new Set<RegistryListener>(),
    registrationRef: sourceEditor,
  });
  bumpRegistryVersion();
  return () => {
    unregisterSourceEditor(
      sourceEditor.pageKey,
      sourceEditor.editorInstanceId,
      sourceEditor,
    );
  };
}

export function resolveSourceEditor(
  pageKey: string,
  editorInstanceId: string,
): null | SourceEditorRegistration {
  const entry = sourceEditors.get(registryKey(pageKey, editorInstanceId));
  return entry ?? null;
}

export function subscribeSourceEditorRevision(
  pageKey: string,
  editorInstanceId: string,
  listener: RegistryListener,
): () => void {
  const entry = sourceEditors.get(registryKey(pageKey, editorInstanceId));
  if (!entry) {
    return () => {};
  }
  entry.listeners.add(listener);
  return () => {
    entry.listeners.delete(listener);
  };
}

export function updateSourceEditorRevision(
  pageKey: string,
  editorInstanceId: string,
  revision: number,
) {
  const entry = sourceEditors.get(registryKey(pageKey, editorInstanceId));
  if (!entry || entry.revision === revision) {
    return;
  }
  entry.revision = revision;
  entry.setRevision?.(revision);
  for (const listener of entry.listeners) {
    listener(revision);
  }
  bumpRegistryVersion();
}

export function unregisterSourceEditor(
  pageKey: string,
  editorInstanceId: string,
  sourceEditor?: SourceEditorRegistration,
) {
  const key = registryKey(pageKey, editorInstanceId);
  const entry = sourceEditors.get(key);
  if (!entry) {
    return;
  }
  if (sourceEditor && entry.registrationRef !== sourceEditor) {
    return;
  }
  entry.listeners.clear();
  sourceEditors.delete(key);
  bumpRegistryVersion();
}
