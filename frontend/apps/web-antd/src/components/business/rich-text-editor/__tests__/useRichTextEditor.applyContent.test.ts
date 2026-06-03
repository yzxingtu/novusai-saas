// @vitest-environment happy-dom
// 中文: 测试类型 behavioral，验证 AI 增加格式写回后 TipTap 结构不会把列表和引用黏在段落里。
// EN: Test type behavioral; verifies AI format apply writes TipTap lists and quotes instead of glued paragraph text.
import type { JSONContent } from '@tiptap/core';

import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, nextTick } from 'vue';

import { describe, expect, it } from 'vitest';

import { useRichTextEditor } from '../useRichTextEditor';

type RichTextEditorHarness = Pick<
  ReturnType<typeof useRichTextEditor>,
  'applyContent' | 'getHTML' | 'getJSON'
>;

function collectNodes(
  node: JSONContent | null | undefined,
  type: string,
): JSONContent[] {
  const matches: JSONContent[] = [];

  function visit(current: JSONContent | null | undefined) {
    if (!current) return;
    if (current.type === type) {
      matches.push(current);
    }
    for (const child of current.content ?? []) {
      visit(child);
    }
  }

  visit(node);
  return matches;
}

function collectText(node: JSONContent | null | undefined): string {
  if (!node) return '';
  return `${node.text ?? ''}${(node.content ?? []).map((item) => collectText(item)).join('')}`;
}

function collectMarkedText(
  node: JSONContent | null | undefined,
  markType: string,
): string[] {
  const matches: string[] = [];

  function visit(current: JSONContent | null | undefined) {
    if (!current) return;
    if (
      current.type === 'text' &&
      current.text &&
      current.marks?.some((mark) => mark.type === markType)
    ) {
      matches.push(current.text);
    }
    for (const child of current.content ?? []) {
      visit(child);
    }
  }

  visit(node);
  return matches;
}

async function mountEditorHarness(): Promise<{
  editor: RichTextEditorHarness;
  unmount: () => void;
}> {
  const Harness = defineComponent({
    setup(_, { expose }) {
      const editor = useRichTextEditor();
      expose(editor);
      return () => null;
    },
  });

  const wrapper = mount(Harness);
  await flushPromises();
  await nextTick();

  return {
    editor: wrapper.vm as unknown as RichTextEditorHarness,
    unmount: () => wrapper.unmount(),
  };
}

describe('useRichTextEditor applyContent', () => {
  it('normalizes glued AI format output into paragraphs, a bullet list, and blockquote nodes', async () => {
    const { editor, unmount } = await mountEditorHarness();
    const aiFormatOutput = [
      '正确做法胡萝卜仅可作为**极少量、偶尔的零食**，绝不能当作主食。',
      '',
      '',
      '**频率**：每周 ≤1 次- **单次量**：每次 ≤10 克- **核心原则**：少量、低频、非日常化>兔子健康的关键在于：> **无限量供应优质干草 +适量低糖绿叶蔬菜 + 少量高品质兔粮**',
    ].join('\n');

    editor.applyContent(aiFormatOutput, { emitUpdate: false, mode: 'insert' });

    const json = editor.getJSON();
    const html = editor.getHTML();
    const paragraphTexts = collectNodes(json, 'paragraph').map((item) =>
      collectText(item),
    );
    const bulletLists = collectNodes(json, 'bulletList');
    const blockquotes = collectNodes(json, 'blockquote');
    const boldTexts = collectMarkedText(json, 'bold');

    expect(paragraphTexts).toContain(
      '正确做法胡萝卜仅可作为极少量、偶尔的零食，绝不能当作主食。',
    );
    expect(bulletLists).toHaveLength(1);
    expect(
      (bulletLists[0]?.content ?? []).map((item) => collectText(item)),
    ).toEqual([
      '频率：每周 ≤1 次',
      '单次量：每次 ≤10 克',
      '核心原则：少量、低频、非日常化',
    ]);
    expect(blockquotes).toHaveLength(1);
    expect(collectText(blockquotes[0])).toBe(
      '兔子健康的关键在于：无限量供应优质干草 +适量低糖绿叶蔬菜 + 少量高品质兔粮',
    );
    expect(boldTexts).toEqual([
      '极少量、偶尔的零食',
      '频率',
      '单次量',
      '核心原则',
      '无限量供应优质干草 +适量低糖绿叶蔬菜 + 少量高品质兔粮',
    ]);
    expect(html).toContain('<strong>频率</strong>');
    expect(html).toContain('<blockquote>');
    expect(html).not.toContain('**频率**');
    expect(
      paragraphTexts.some(
        (text) => text.includes('- **单次量**') || text.includes('>兔子健康'),
      ),
    ).toBe(false);

    unmount();
  });

  it('keeps URLs, negative numbers, comparisons, and ordinary hyphens inside paragraph text', async () => {
    const { editor, unmount } = await mountEditorHarness();
    const aiFormatOutput =
      '参考 https://example.com/a-b，温度 -10，well-being，中文A-B 和 A - B 都是普通文本，表达式 a>b、1>0、数量>10 保留。提示:> **真正引用**';

    editor.applyContent(aiFormatOutput, { emitUpdate: false, mode: 'insert' });

    const json = editor.getJSON();
    const paragraphTexts = collectNodes(json, 'paragraph').map((item) =>
      collectText(item),
    );
    const bulletLists = collectNodes(json, 'bulletList');
    const blockquotes = collectNodes(json, 'blockquote');
    const boldTexts = collectMarkedText(json, 'bold');

    expect(paragraphTexts).toContain(
      '参考 https://example.com/a-b，温度 -10，well-being，中文A-B 和 A - B 都是普通文本，表达式 a>b、1>0、数量>10 保留。提示:',
    );
    expect(bulletLists).toHaveLength(0);
    expect(blockquotes).toHaveLength(1);
    expect(collectText(blockquotes[0])).toBe('真正引用');
    expect(boldTexts).toEqual(['真正引用']);

    unmount();
  });

  it('keeps unmatched markdown markers as literal text instead of dropping content', async () => {
    const { editor, unmount } = await mountEditorHarness();
    const aiFormatOutput =
      '这个 **粗体没有闭合，代码 `也没有闭合，应该原样保留。';

    editor.applyContent(aiFormatOutput, { emitUpdate: false, mode: 'insert' });

    const json = editor.getJSON();
    const paragraphTexts = collectNodes(json, 'paragraph').map((item) =>
      collectText(item),
    );

    expect(paragraphTexts).toContain(aiFormatOutput);
    expect(collectMarkedText(json, 'bold')).toEqual([]);
    expect(collectMarkedText(json, 'code')).toEqual([]);

    unmount();
  });
});
