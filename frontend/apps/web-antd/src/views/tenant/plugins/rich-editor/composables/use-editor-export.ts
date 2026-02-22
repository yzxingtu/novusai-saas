/**
 * useEditorExport 组合式函数
 *
 * 封装编辑器导出功能：Markdown、HTML、JSON、PDF
 * 利用 tiptap-markdown 扩展的 getMarkdown() 方法
 */
import type { Editor } from '@tiptap/core';
import type { Ref } from 'vue';

export function useEditorExport(editor: Ref<Editor | undefined>) {
  /** 将编辑器内容导出为 HTML 字符串 */
  function exportHTML(): string {
    if (!editor.value) return '';
    return editor.value.getHTML();
  }

  /** 将编辑器内容导出为 TipTap JSON 格式 */
  function exportJSON(): Record<string, unknown> | null {
    if (!editor.value) return null;
    return editor.value.getJSON() as Record<string, unknown>;
  }

  /** 将编辑器内容导出为 Markdown（依赖 tiptap-markdown 扩展） */
  function exportMarkdown(): string {
    if (!editor.value) return '';
    // tiptap-markdown 扩展会在 editor.storage 上添加 markdown 方法
    const storage = editor.value.storage as Record<string, unknown>;
    if (storage.markdown && typeof (storage.markdown as Record<string, unknown>).getMarkdown === 'function') {
      return (storage.markdown as { getMarkdown: () => string }).getMarkdown();
    }
    // fallback: 使用纯文本
    return editor.value.getText();
  }

  /** 通用文件下载（创建 Blob 并触发浏览器下载） */
  function downloadFile(content: string, filename: string, mimeType: string) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  /** 下载为 JSON 文件 */
  function downloadJSON(filename: string) {
    const json = exportJSON();
    if (!json) return;
    downloadFile(JSON.stringify(json, null, 2), filename, 'application/json');
  }

  /** 下载为完整 HTML 文件（含内联样式表） */
  function downloadHTML(filename: string) {
    const html = exportHTML();
    const fullHtml = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${filename.replace('.html', '')}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; line-height: 1.8; color: #1a1a1a; }
    h1 { font-size: 2rem; margin: 1.5rem 0 0.75rem; }
    h2 { font-size: 1.5rem; margin: 1.25rem 0 0.5rem; }
    h3 { font-size: 1.25rem; margin: 1rem 0 0.5rem; }
    blockquote { border-left: 3px solid #6366f1; padding-left: 1rem; color: #666; margin: 1rem 0; }
    code { background: #f4f4f5; padding: 0.15rem 0.4rem; border-radius: 0.25rem; font-size: 0.875em; }
    pre { background: #f4f4f5; padding: 1rem; border-radius: 0.5rem; overflow-x: auto; }
    pre code { background: none; padding: 0; }
    table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
    th, td { border: 1px solid #e5e7eb; padding: 0.5rem 0.75rem; }
    th { background: #f9fafb; font-weight: 600; }
    img { max-width: 100%; border-radius: 0.5rem; }
    hr { border: none; border-top: 1px solid #e5e7eb; margin: 1.5rem 0; }
    a { color: #6366f1; }
    ul[data-type="taskList"] { list-style: none; padding-left: 0; }
    ul[data-type="taskList"] li { display: flex; align-items: flex-start; gap: 0.5rem; }
    mark { border-radius: 0.15rem; padding: 0.05rem 0.15rem; }
  </style>
</head>
<body>
${html}
</body>
</html>`;
    downloadFile(fullHtml, filename, 'text/html');
  }

  /** 下载为 Markdown 文件 */
  function downloadMarkdown(filename: string) {
    const md = exportMarkdown();
    downloadFile(md, filename, 'text/markdown');
  }

  /** 导出为 PDF（通过浏览器打印功能实现） */
  function exportPDF(title?: string) {
    const html = exportHTML();
    const printWindow = window.open('', '_blank');
    if (!printWindow) return;

    printWindow.document.write(`<!DOCTYPE html>
<html>
<head>
  <title>${title || 'Document'}</title>
  <style>
    @media print { @page { margin: 2cm; } }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 100%; line-height: 1.8; color: #1a1a1a; }
    h1 { font-size: 2rem; margin: 1.5rem 0 0.75rem; }
    h2 { font-size: 1.5rem; margin: 1.25rem 0 0.5rem; }
    h3 { font-size: 1.25rem; margin: 1rem 0 0.5rem; }
    blockquote { border-left: 3px solid #6366f1; padding-left: 1rem; color: #666; margin: 1rem 0; }
    code { background: #f4f4f5; padding: 0.15rem 0.4rem; border-radius: 0.25rem; font-size: 0.875em; }
    pre { background: #f4f4f5; padding: 1rem; border-radius: 0.5rem; overflow-x: auto; }
    pre code { background: none; padding: 0; }
    table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
    th, td { border: 1px solid #e5e7eb; padding: 0.5rem 0.75rem; }
    th { background: #f9fafb; font-weight: 600; }
    img { max-width: 100%; border-radius: 0.5rem; }
    hr { border: none; border-top: 1px solid #e5e7eb; margin: 1.5rem 0; }
  </style>
</head>
<body>${html}</body>
</html>`);
    printWindow.document.close();
    printWindow.onload = () => {
      printWindow.print();
      printWindow.close();
    };
  }

  return {
    exportHTML,
    exportJSON,
    exportMarkdown,
    exportPDF,
    downloadHTML,
    downloadJSON,
    downloadMarkdown,
    downloadFile,
  };
}
