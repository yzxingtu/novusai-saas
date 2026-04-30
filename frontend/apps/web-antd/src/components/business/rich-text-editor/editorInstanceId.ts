let editorInstanceCounter = 0;

export function createEditorInstanceId(): string {
  editorInstanceCounter += 1;
  return `rich-text-editor-${Date.now().toString(36)}-${editorInstanceCounter}`;
}
