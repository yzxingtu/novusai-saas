/**
 * NovusDoc Tiptap 扩展集合（免费版）
 *
 * novusdoc-pro 可通过 registerEditorExtension() 注入商业扩展
 */

import type { AnyExtension } from '@tiptap/core'

import { StarterKit } from '@tiptap/starter-kit'
import { Table } from '@tiptap/extension-table'
import { TableRow } from '@tiptap/extension-table-row'
import { TableCell } from '@tiptap/extension-table-cell'
import { TableHeader } from '@tiptap/extension-table-header'
import { Image } from '@tiptap/extension-image'
import { Link } from '@tiptap/extension-link'
import { TaskList } from '@tiptap/extension-task-list'
import { TaskItem } from '@tiptap/extension-task-item'
import { Placeholder } from '@tiptap/extension-placeholder'
import { CharacterCount } from '@tiptap/extension-character-count'
import { CodeBlockLowlight } from '@tiptap/extension-code-block-lowlight'
import { Underline } from '@tiptap/extension-underline'
import { Highlight } from '@tiptap/extension-highlight'
import { TextAlign } from '@tiptap/extension-text-align'
import { Color } from '@tiptap/extension-color'
import { TextStyle } from '@tiptap/extension-text-style'
import { Subscript } from '@tiptap/extension-subscript'
import { Superscript } from '@tiptap/extension-superscript'
import { common, createLowlight } from 'lowlight'

const lowlight = createLowlight(common)

export interface ExtensionOptions {
  /** Disable StarterKit history for Yjs collaboration mode */
  disableHistory?: boolean
}

function buildBuiltinExtensions(opts: ExtensionOptions = {}): AnyExtension[] {
  return [
  StarterKit.configure({
    codeBlock: false,
    link: false,
    underline: false,
    ...(opts.disableHistory ? { history: false } : {}),
  }),
  Table.configure({ resizable: true }),
  TableRow,
  TableCell,
  TableHeader,
  Image.configure({
    allowBase64: true,
    HTMLAttributes: { class: 'nd-image' },
  }),
  Link.configure({
    openOnClick: false,
    HTMLAttributes: { class: 'nd-link' },
  }),
  TaskList,
  TaskItem.configure({ nested: true }),
  Placeholder.configure({
    placeholder: ({ node }: { node: { type: { name: string } } }) => {
      if (node.type.name === 'heading') {
        return ''
      }
      return 'Type / for commands…'
    },
  }),
  CharacterCount,
  CodeBlockLowlight.configure({ lowlight }),
  Underline,
  Highlight.configure({ multicolor: true }),
  TextAlign.configure({ types: ['heading', 'paragraph'] }),
  Color,
  TextStyle,
  Subscript,
  Superscript,
  ]
}

const injectedExtensions: AnyExtension[] = []

export function registerEditorExtension(ext: AnyExtension): void {
  injectedExtensions.push(ext)
}

export function getAllExtensions(opts: ExtensionOptions = {}): AnyExtension[] {
  return [...buildBuiltinExtensions(opts), ...injectedExtensions]
}
