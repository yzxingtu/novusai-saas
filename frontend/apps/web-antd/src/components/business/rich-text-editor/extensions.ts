/**
 * Platform-level Tiptap extensions collection
 * / 平台级 Tiptap 扩展集合
 */

import type { AnyExtension } from '@tiptap/core';

import { CharacterCount } from '@tiptap/extension-character-count';
import { CodeBlockLowlight } from '@tiptap/extension-code-block-lowlight';
import { Color } from '@tiptap/extension-color';
import { FontFamily } from '@tiptap/extension-font-family';
import { Highlight } from '@tiptap/extension-highlight';
import { Image } from '@tiptap/extension-image';
import { Link } from '@tiptap/extension-link';
import { Placeholder } from '@tiptap/extension-placeholder';
import { Subscript } from '@tiptap/extension-subscript';
import { Superscript } from '@tiptap/extension-superscript';
import { Table } from '@tiptap/extension-table';
import { TableCell } from '@tiptap/extension-table-cell';
import { TableHeader } from '@tiptap/extension-table-header';
import { TableRow } from '@tiptap/extension-table-row';
import { TaskItem } from '@tiptap/extension-task-item';
import { TaskList } from '@tiptap/extension-task-list';
import { TextAlign } from '@tiptap/extension-text-align';
import { TextStyle } from '@tiptap/extension-text-style';
import { Underline } from '@tiptap/extension-underline';
import { StarterKit } from '@tiptap/starter-kit';
import { common, createLowlight } from 'lowlight';

const lowlight = createLowlight(common);

export interface ExtensionBuildOptions {
  placeholder?: string;
}

export function buildExtensions(
  opts: ExtensionBuildOptions = {},
): AnyExtension[] {
  return [
    StarterKit.configure({
      codeBlock: false,
    }),
    Underline,
    Link.configure({ openOnClick: false }),
    Image.configure({
      allowBase64: false,
      HTMLAttributes: { class: 'rte-image' },
    }),
    Table.configure({ resizable: true }),
    TableRow,
    TableCell,
    TableHeader,
    TaskList,
    TaskItem.configure({ nested: true }),
    Placeholder.configure({
      placeholder: ({ node }: { node: { type: { name: string } } }) => {
        if (node.type.name === 'heading') return '';
        return opts.placeholder || '';
      },
    }),
    CharacterCount,
    CodeBlockLowlight.configure({ lowlight }),
    Highlight.configure({ multicolor: true }),
    TextAlign.configure({ types: ['heading', 'paragraph'] }),
    Color,
    TextStyle,
    FontFamily,
    Subscript,
    Superscript,
  ];
}
