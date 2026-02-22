<script setup lang="ts">
/**
 * 编辑器工具栏组件
 *
 * 分组布局（格式组、段落组、插入组）
 * 按钮状态与编辑器同步（active/disabled）
 * Tooltip 显示操作名 + 快捷键
 * Lucide 图标
 */
import type { Editor } from '@tiptap/vue-3';

import { computed, ref } from 'vue';

import { Divider, Dropdown, Popover, Select, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

import EmojiPicker from './EmojiPicker.vue';

const props = defineProps<{
  editor: Editor;
  aiEnabled?: boolean;
}>();

const emit = defineEmits<{
  toggleFullscreen: [];
  exportMarkdown: [];
  exportHtml: [];
  exportJson: [];
  exportPdf: [];
  aiAction: [action: string];
}>();

// ==================== 格式刷状态 ====================
const isFormatPainterActive = ref(false);
let storedMarks: Record<string, unknown>[] = [];

function activateFormatPainter() {
  const marks = props.editor.state.selection.$from.marks();
  storedMarks = marks.map((m) => ({
    type: m.type.name,
    attrs: m.attrs,
  }));
  isFormatPainterActive.value = true;
}

function applyFormatPainter() {
  if (!isFormatPainterActive.value) return;
  const chain = props.editor.chain().focus().unsetAllMarks();
  for (const mark of storedMarks) {
    chain.setMark(mark.type as string, mark.attrs as Record<string, unknown>);
  }
  chain.run();
  isFormatPainterActive.value = false;
  storedMarks = [];
}

function clearFormat() {
  props.editor.chain().focus().clearNodes().unsetAllMarks().run();
}

// ==================== 工具栏按钮定义 ====================

interface ToolbarButton {
  key: string;
  icon: string;
  title: string;
  shortcut?: string;
  action: () => void;
  isActive?: () => boolean;
  isDisabled?: () => boolean;
}

const formatButtons = computed<ToolbarButton[]>(() => [
  {
    key: 'bold',
    icon: 'icon-[lucide--bold]',
    title: $t('tenant.richEditor.toolbar.bold'),
    shortcut: 'Ctrl+B',
    action: () => props.editor.chain().focus().toggleBold().run(),
    isActive: () => props.editor.isActive('bold'),
  },
  {
    key: 'italic',
    icon: 'icon-[lucide--italic]',
    title: $t('tenant.richEditor.toolbar.italic'),
    shortcut: 'Ctrl+I',
    action: () => props.editor.chain().focus().toggleItalic().run(),
    isActive: () => props.editor.isActive('italic'),
  },
  {
    key: 'underline',
    icon: 'icon-[lucide--underline]',
    title: $t('tenant.richEditor.toolbar.underline'),
    shortcut: 'Ctrl+U',
    action: () => props.editor.chain().focus().toggleUnderline().run(),
    isActive: () => props.editor.isActive('underline'),
  },
  {
    key: 'strike',
    icon: 'icon-[lucide--strikethrough]',
    title: $t('tenant.richEditor.toolbar.strikethrough'),
    shortcut: 'Ctrl+Shift+S',
    action: () => props.editor.chain().focus().toggleStrike().run(),
    isActive: () => props.editor.isActive('strike'),
  },
  {
    key: 'code',
    icon: 'icon-[lucide--code]',
    title: $t('tenant.richEditor.toolbar.inlineCode'),
    shortcut: 'Ctrl+E',
    action: () => props.editor.chain().focus().toggleCode().run(),
    isActive: () => props.editor.isActive('code'),
  },
  {
    key: 'superscript',
    icon: 'icon-[lucide--superscript]',
    title: $t('tenant.richEditor.toolbar.superscript'),
    action: () => props.editor.chain().focus().toggleSuperscript().run(),
    isActive: () => props.editor.isActive('superscript'),
  },
  {
    key: 'subscript',
    icon: 'icon-[lucide--subscript]',
    title: $t('tenant.richEditor.toolbar.subscript'),
    action: () => props.editor.chain().focus().toggleSubscript().run(),
    isActive: () => props.editor.isActive('subscript'),
  },
]);

const paragraphButtons = computed<ToolbarButton[]>(() => [
  {
    key: 'bulletList',
    icon: 'icon-[lucide--list]',
    title: $t('tenant.richEditor.toolbar.bulletList'),
    action: () => props.editor.chain().focus().toggleBulletList().run(),
    isActive: () => props.editor.isActive('bulletList'),
  },
  {
    key: 'orderedList',
    icon: 'icon-[lucide--list-ordered]',
    title: $t('tenant.richEditor.toolbar.orderedList'),
    action: () => props.editor.chain().focus().toggleOrderedList().run(),
    isActive: () => props.editor.isActive('orderedList'),
  },
  {
    key: 'blockquote',
    icon: 'icon-[lucide--quote]',
    title: $t('tenant.richEditor.toolbar.blockquote'),
    action: () => props.editor.chain().focus().toggleBlockquote().run(),
    isActive: () => props.editor.isActive('blockquote'),
  },
  {
    key: 'horizontalRule',
    icon: 'icon-[lucide--minus]',
    title: $t('tenant.richEditor.toolbar.horizontalRule'),
    action: () => props.editor.chain().focus().setHorizontalRule().run(),
  },
]);

const historyButtons = computed<ToolbarButton[]>(() => [
  {
    key: 'undo',
    icon: 'icon-[lucide--undo-2]',
    title: $t('tenant.richEditor.toolbar.undo'),
    shortcut: 'Ctrl+Z',
    action: () => props.editor.chain().focus().undo().run(),
    isDisabled: () => !props.editor.can().undo(),
  },
  {
    key: 'redo',
    icon: 'icon-[lucide--redo-2]',
    title: $t('tenant.richEditor.toolbar.redo'),
    shortcut: 'Ctrl+Shift+Z',
    action: () => props.editor.chain().focus().redo().run(),
    isDisabled: () => !props.editor.can().redo(),
  },
]);

// ==================== 标题选择 ====================

const headingOptions = [
  { label: $t('tenant.richEditor.toolbar.paragraph'), value: 0 },
  { label: 'H1', value: 1 },
  { label: 'H2', value: 2 },
  { label: 'H3', value: 3 },
  { label: 'H4', value: 4 },
];

const currentHeading = computed(() => {
  for (let i = 1; i <= 6; i++) {
    if (props.editor.isActive('heading', { level: i })) return i;
  }
  return 0;
});

function setHeading(level: number) {
  if (level === 0) {
    props.editor.chain().focus().setParagraph().run();
  } else {
    props.editor
      .chain()
      .focus()
      .toggleHeading({ level: level as 1 | 2 | 3 | 4 | 5 | 6 })
      .run();
  }
}

// ==================== 颜色 ====================

const presetColors = [
  '#000000', '#434343', '#666666', '#999999', '#B7B7B7', '#D9D9D9', '#FFFFFF',
  '#FF0000', '#FF4D00', '#FF9900', '#FFCC00', '#FFFF00', '#99FF00', '#00FF00',
  '#00FF99', '#00FFFF', '#0099FF', '#0000FF', '#9900FF', '#FF00FF', '#FF0099',
  '#CC0000', '#CC3D00', '#CC7A00', '#CCA300', '#CCCC00', '#7ACC00', '#00CC00',
  '#00CC7A', '#00CCCC', '#007ACC', '#0000CC', '#7A00CC', '#CC00CC', '#CC007A',
];

function setTextColor(color: string) {
  props.editor.chain().focus().setColor(color).run();
}

function unsetTextColor() {
  props.editor.chain().focus().unsetColor().run();
}

function setHighlightColor(color: string) {
  props.editor.chain().focus().toggleHighlight({ color }).run();
}

function unsetHighlight() {
  props.editor.chain().focus().unsetHighlight().run();
}

// ==================== 对齐 ====================

const alignOptions = [
  { key: 'left', icon: 'icon-[lucide--align-left]' },
  { key: 'center', icon: 'icon-[lucide--align-center]' },
  { key: 'right', icon: 'icon-[lucide--align-right]' },
  { key: 'justify', icon: 'icon-[lucide--align-justify]' },
];

function setAlign(align: string) {
  props.editor.chain().focus().setTextAlign(align).run();
}

// ==================== 缩进 ====================

function indent() {
  props.editor.chain().focus().sinkListItem('listItem').run();
}

function outdent() {
  props.editor.chain().focus().liftListItem('listItem').run();
}

// ==================== 任务列表 ====================

function toggleTaskList() {
  props.editor.chain().focus().toggleTaskList().run();
}

// ==================== 图片 ====================

function insertImage() {
  const url = window.prompt($t('tenant.richEditor.toolbar.imagePrompt'));
  if (url) {
    props.editor.chain().focus().setImage({ src: url }).run();
  }
}

// ==================== 代码块 ====================

function insertCodeBlock() {
  props.editor.chain().focus().toggleCodeBlock().run();
}

// ==================== 表格 ====================

function insertTable() {
  props.editor
    .chain()
    .focus()
    .insertTable({ rows: 3, cols: 3, withHeaderRow: true })
    .run();
}

function addTableRowAfter() {
  props.editor.chain().focus().addRowAfter().run();
}
function deleteTableRow() {
  props.editor.chain().focus().deleteRow().run();
}
function addTableColAfter() {
  props.editor.chain().focus().addColumnAfter().run();
}
function deleteTableCol() {
  props.editor.chain().focus().deleteColumn().run();
}
function deleteTable() {
  props.editor.chain().focus().deleteTable().run();
}
function mergeCells() {
  props.editor.chain().focus().mergeCells().run();
}
function splitCell() {
  props.editor.chain().focus().splitCell().run();
}

// ==================== Emoji ====================

function insertEmoji(emoji: string) {
  props.editor.chain().focus().insertContent(emoji).run();
}

// ==================== 全屏 ====================

const isFullscreen = ref(false);

function toggleFullscreen() {
  isFullscreen.value = !isFullscreen.value;
  emit('toggleFullscreen');
}

// ==================== 链接 ====================

function toggleLink() {
  if (props.editor.isActive('link')) {
    props.editor.chain().focus().unsetLink().run();
    return;
  }
  const url = window.prompt($t('tenant.richEditor.toolbar.linkPrompt'));
  if (url) {
    props.editor.chain().focus().setLink({ href: url }).run();
  }
}

function tooltipTitle(btn: ToolbarButton) {
  return btn.shortcut ? `${btn.title} (${btn.shortcut})` : btn.title;
}
</script>

<template>
  <div
    class="editor-toolbar bg-card/80 border-border flex flex-wrap items-center gap-0.5 border-b px-3 py-1.5 backdrop-blur"
  >
    <!-- 历史 -->
    <template v-for="btn in historyButtons" :key="btn.key">
      <Tooltip :title="tooltipTitle(btn)" placement="bottom">
        <button
          class="toolbar-btn"
          :class="{ disabled: btn.isDisabled?.() }"
          :disabled="btn.isDisabled?.()"
          @click="btn.action"
        >
          <span :class="[btn.icon, 'h-4 w-4']" />
        </button>
      </Tooltip>
    </template>

    <Divider type="vertical" class="!mx-1 !h-5" />

    <!-- 标题选择 -->
    <Select
      :value="currentHeading"
      :options="headingOptions"
      size="small"
      style="width: 100px"
      :bordered="false"
      @change="(val: unknown) => setHeading(Number(val))"
    />

    <Divider type="vertical" class="!mx-1 !h-5" />

    <!-- 格式按钮 -->
    <template v-for="btn in formatButtons" :key="btn.key">
      <Tooltip :title="tooltipTitle(btn)" placement="bottom">
        <button
          class="toolbar-btn"
          :class="{ active: btn.isActive?.() }"
          @click="btn.action"
        >
          <span :class="[btn.icon, 'h-4 w-4']" />
        </button>
      </Tooltip>
    </template>

    <!-- 链接 -->
    <Tooltip :title="$t('tenant.richEditor.toolbar.link')" placement="bottom">
      <button
        class="toolbar-btn"
        :class="{ active: editor.isActive('link') }"
        @click="toggleLink"
      >
        <span class="icon-[lucide--link] h-4 w-4" />
      </button>
    </Tooltip>

    <Divider type="vertical" class="!mx-1 !h-5" />

    <!-- 段落按钮 -->
    <template v-for="btn in paragraphButtons" :key="btn.key">
      <Tooltip :title="tooltipTitle(btn)" placement="bottom">
        <button
          class="toolbar-btn"
          :class="{ active: btn.isActive?.() }"
          @click="btn.action"
        >
          <span :class="[btn.icon, 'h-4 w-4']" />
        </button>
      </Tooltip>
    </template>

    <!-- 待办事项 -->
    <Tooltip :title="$t('tenant.richEditor.toolbar.taskList')" placement="bottom">
      <button
        class="toolbar-btn"
        :class="{ active: editor.isActive('taskList') }"
        @click="toggleTaskList"
      >
        <span class="icon-[lucide--list-checks] h-4 w-4" />
      </button>
    </Tooltip>

    <Divider type="vertical" class="!mx-1 !h-5" />

    <!-- 对齐方式 -->
    <Dropdown :trigger="['click']" placement="bottomLeft">
      <Tooltip :title="$t('tenant.richEditor.toolbar.align')" placement="bottom">
        <button class="toolbar-btn">
          <span class="icon-[lucide--align-left] h-4 w-4" />
          <span class="icon-[lucide--chevron-down] ml-0.5 h-3 w-3" />
        </button>
      </Tooltip>
      <template #overlay>
        <div class="bg-card flex gap-1 rounded-lg border p-1.5 shadow-lg">
          <Tooltip v-for="opt in alignOptions" :key="opt.key" :title="opt.key" placement="bottom">
            <button
              class="toolbar-btn"
              :class="{ active: editor.isActive({ textAlign: opt.key }) }"
              @click="setAlign(opt.key)"
            >
              <span :class="[opt.icon, 'h-4 w-4']" />
            </button>
          </Tooltip>
        </div>
      </template>
    </Dropdown>

    <!-- 缩进 -->
    <Tooltip :title="$t('tenant.richEditor.toolbar.indent')" placement="bottom">
      <button class="toolbar-btn" @click="indent">
        <span class="icon-[lucide--indent-increase] h-4 w-4" />
      </button>
    </Tooltip>
    <Tooltip :title="$t('tenant.richEditor.toolbar.outdent')" placement="bottom">
      <button class="toolbar-btn" @click="outdent">
        <span class="icon-[lucide--indent-decrease] h-4 w-4" />
      </button>
    </Tooltip>

    <Divider type="vertical" class="!mx-1 !h-5" />

    <!-- 字体颜色 -->
    <Popover trigger="click" placement="bottomLeft">
      <Tooltip :title="$t('tenant.richEditor.toolbar.textColor')" placement="bottom">
        <button class="toolbar-btn">
          <span class="icon-[lucide--palette] h-4 w-4" />
        </button>
      </Tooltip>
      <template #content>
        <div class="color-picker-panel">
          <div class="mb-2 text-xs text-muted-foreground">{{ $t('tenant.richEditor.toolbar.textColor') }}</div>
          <div class="grid grid-cols-7 gap-1">
            <button
              v-for="c in presetColors"
              :key="'tc-' + c"
              class="color-swatch"
              :style="{ backgroundColor: c }"
              @click="setTextColor(c)"
            />
          </div>
          <button class="mt-2 text-xs text-muted-foreground hover:text-foreground" @click="unsetTextColor">
            {{ $t('tenant.richEditor.toolbar.clearColor') }}
          </button>
        </div>
      </template>
    </Popover>

    <!-- 背景高亮 -->
    <Popover trigger="click" placement="bottomLeft">
      <Tooltip :title="$t('tenant.richEditor.toolbar.highlight')" placement="bottom">
        <button class="toolbar-btn" :class="{ active: editor.isActive('highlight') }">
          <span class="icon-[lucide--highlighter] h-4 w-4" />
        </button>
      </Tooltip>
      <template #content>
        <div class="color-picker-panel">
          <div class="mb-2 text-xs text-muted-foreground">{{ $t('tenant.richEditor.toolbar.highlight') }}</div>
          <div class="grid grid-cols-7 gap-1">
            <button
              v-for="c in presetColors"
              :key="'hl-' + c"
              class="color-swatch"
              :style="{ backgroundColor: c }"
              @click="setHighlightColor(c)"
            />
          </div>
          <button class="mt-2 text-xs text-muted-foreground hover:text-foreground" @click="unsetHighlight">
            {{ $t('tenant.richEditor.toolbar.clearColor') }}
          </button>
        </div>
      </template>
    </Popover>

    <Divider type="vertical" class="!mx-1 !h-5" />

    <!-- 格式刷 -->
    <Tooltip :title="$t('tenant.richEditor.toolbar.formatPainter')" placement="bottom">
      <button
        class="toolbar-btn"
        :class="{ active: isFormatPainterActive }"
        @click="isFormatPainterActive ? applyFormatPainter() : activateFormatPainter()"
      >
        <span class="icon-[lucide--paintbrush] h-4 w-4" />
      </button>
    </Tooltip>

    <!-- 橡皮擦 -->
    <Tooltip :title="$t('tenant.richEditor.toolbar.clearFormat')" placement="bottom">
      <button class="toolbar-btn" @click="clearFormat">
        <span class="icon-[lucide--eraser] h-4 w-4" />
      </button>
    </Tooltip>

    <!-- 图片 -->
    <Tooltip :title="$t('tenant.richEditor.toolbar.image')" placement="bottom">
      <button class="toolbar-btn" @click="insertImage">
        <span class="icon-[lucide--image] h-4 w-4" />
      </button>
    </Tooltip>

    <!-- 代码块 -->
    <Tooltip :title="$t('tenant.richEditor.toolbar.codeBlock')" placement="bottom">
      <button
        class="toolbar-btn"
        :class="{ active: editor.isActive('codeBlock') }"
        @click="insertCodeBlock"
      >
        <span class="icon-[lucide--file-code] h-4 w-4" />
      </button>
    </Tooltip>

    <!-- 表格 -->
    <Dropdown :trigger="['click']" placement="bottomLeft">
      <Tooltip :title="$t('tenant.richEditor.toolbar.table')" placement="bottom">
        <button class="toolbar-btn">
          <span class="icon-[lucide--table] h-4 w-4" />
          <span class="icon-[lucide--chevron-down] ml-0.5 h-3 w-3" />
        </button>
      </Tooltip>
      <template #overlay>
        <div class="bg-card rounded-lg border p-2 shadow-lg" style="min-width: 160px">
          <button class="table-menu-item" @click="insertTable">
            <span class="icon-[lucide--table] h-4 w-4" />
            {{ $t('tenant.richEditor.toolbar.insertTable') }}
          </button>
          <button class="table-menu-item" @click="addTableRowAfter">
            <span class="icon-[lucide--between-horizontal-end] h-4 w-4" />
            {{ $t('tenant.richEditor.toolbar.addRow') }}
          </button>
          <button class="table-menu-item" @click="addTableColAfter">
            <span class="icon-[lucide--between-vertical-end] h-4 w-4" />
            {{ $t('tenant.richEditor.toolbar.addCol') }}
          </button>
          <button class="table-menu-item" @click="deleteTableRow">
            <span class="icon-[lucide--row-spacing] h-4 w-4" />
            {{ $t('tenant.richEditor.toolbar.deleteRow') }}
          </button>
          <button class="table-menu-item" @click="deleteTableCol">
            <span class="icon-[lucide--column-spacing] h-4 w-4" />
            {{ $t('tenant.richEditor.toolbar.deleteCol') }}
          </button>
          <button class="table-menu-item" @click="mergeCells">
            <span class="icon-[lucide--combine] h-4 w-4" />
            {{ $t('tenant.richEditor.toolbar.mergeCells') }}
          </button>
          <button class="table-menu-item" @click="splitCell">
            <span class="icon-[lucide--split] h-4 w-4" />
            {{ $t('tenant.richEditor.toolbar.splitCell') }}
          </button>
          <button class="table-menu-item text-destructive" @click="deleteTable">
            <span class="icon-[lucide--trash-2] h-4 w-4" />
            {{ $t('tenant.richEditor.toolbar.deleteTable') }}
          </button>
        </div>
      </template>
    </Dropdown>

    <Divider type="vertical" class="!mx-1 !h-5" />

    <!-- Emoji -->
    <Popover trigger="click" placement="bottomLeft">
      <Tooltip :title="$t('tenant.richEditor.toolbar.emoji')" placement="bottom">
        <button class="toolbar-btn">
          <span class="icon-[lucide--smile] h-4 w-4" />
        </button>
      </Tooltip>
      <template #content>
        <EmojiPicker @select="insertEmoji" />
      </template>
    </Popover>

    <Divider type="vertical" class="!mx-1 !h-5" />

    <!-- 导出 -->
    <Dropdown :trigger="['click']" placement="bottomLeft">
      <Tooltip :title="$t('tenant.richEditor.toolbar.export')" placement="bottom">
        <button class="toolbar-btn">
          <span class="icon-[lucide--download] h-4 w-4" />
          <span class="icon-[lucide--chevron-down] ml-0.5 h-3 w-3" />
        </button>
      </Tooltip>
      <template #overlay>
        <div class="bg-card rounded-lg border p-2 shadow-lg" style="min-width: 180px">
          <button class="table-menu-item" @click="emit('exportMarkdown')">
            <span class="icon-[lucide--file-text] h-4 w-4" />
            {{ $t('tenant.richEditor.toolbar.exportMarkdown') }}
          </button>
          <button class="table-menu-item" @click="emit('exportHtml')">
            <span class="icon-[lucide--file-code] h-4 w-4" />
            {{ $t('tenant.richEditor.toolbar.exportHTML') }}
          </button>
          <button class="table-menu-item" @click="emit('exportJson')">
            <span class="icon-[lucide--braces] h-4 w-4" />
            {{ $t('tenant.richEditor.toolbar.exportJSON') }}
          </button>
          <button class="table-menu-item" @click="emit('exportPdf')">
            <span class="icon-[lucide--printer] h-4 w-4" />
            {{ $t('tenant.richEditor.toolbar.exportPDF') }}
          </button>
        </div>
      </template>
    </Dropdown>

    <!-- AI 助手（仅当 AI 启用时显示） -->
    <Dropdown v-if="aiEnabled" :trigger="['click']" placement="bottomLeft">
      <Tooltip :title="$t('tenant.richEditor.toolbar.ai')" placement="bottom">
        <button class="toolbar-btn ai-btn">
          <span class="icon-[lucide--sparkles] h-4 w-4" />
          <span class="icon-[lucide--chevron-down] ml-0.5 h-3 w-3" />
        </button>
      </Tooltip>
      <template #overlay>
        <div class="bg-card rounded-lg border p-2 shadow-lg" style="min-width: 180px">
          <button class="table-menu-item" @click="emit('aiAction', 'continue_writing')">
            <span class="icon-[lucide--pen-line] h-4 w-4" />
            {{ $t('tenant.richEditor.toolbar.aiContinue') }}
          </button>
          <button class="table-menu-item" @click="emit('aiAction', 'optimize')">
            <span class="icon-[lucide--wand-sparkles] h-4 w-4" />
            {{ $t('tenant.richEditor.toolbar.aiOptimize') }}
          </button>
          <button class="table-menu-item" @click="emit('aiAction', 'proofread')">
            <span class="icon-[lucide--spell-check] h-4 w-4" />
            {{ $t('tenant.richEditor.toolbar.aiProofread') }}
          </button>
          <button class="table-menu-item" @click="emit('aiAction', 'translate')">
            <span class="icon-[lucide--languages] h-4 w-4" />
            {{ $t('tenant.richEditor.toolbar.aiTranslate') }}
          </button>
          <button class="table-menu-item" @click="emit('aiAction', 'summarize')">
            <span class="icon-[lucide--text-select] h-4 w-4" />
            {{ $t('tenant.richEditor.toolbar.aiSummarize') }}
          </button>
          <button class="table-menu-item" @click="emit('aiAction', 'expand')">
            <span class="icon-[lucide--unfold-vertical] h-4 w-4" />
            {{ $t('tenant.richEditor.toolbar.aiExpand') }}
          </button>
          <button class="table-menu-item" @click="emit('aiAction', 'explain_code')">
            <span class="icon-[lucide--message-circle-question] h-4 w-4" />
            {{ $t('tenant.richEditor.toolbar.aiExplainCode') }}
          </button>
          <button class="table-menu-item" @click="emit('aiAction', 'comment_code')">
            <span class="icon-[lucide--message-square-code] h-4 w-4" />
            {{ $t('tenant.richEditor.toolbar.aiCommentCode') }}
          </button>
        </div>
      </template>
    </Dropdown>

    <Divider type="vertical" class="!mx-1 !h-5" />

    <!-- 全屏 -->
    <Tooltip :title="$t('tenant.richEditor.toolbar.fullscreen')" placement="bottom">
      <button class="toolbar-btn" :class="{ active: isFullscreen }" @click="toggleFullscreen">
        <span :class="[isFullscreen ? 'icon-[lucide--minimize-2]' : 'icon-[lucide--maximize-2]', 'h-4 w-4']" />
      </button>
    </Tooltip>
  </div>
</template>

<style scoped>
.toolbar-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 0.5rem;
  border: none;
  background: transparent;
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  transition: all 150ms ease-out;
}

.toolbar-btn:hover {
  background: hsl(var(--accent));
  color: hsl(var(--foreground));
}

.toolbar-btn.active {
  background: hsl(var(--primary) / 0.1);
  color: hsl(var(--primary));
}

.toolbar-btn.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.toolbar-btn:active:not(.disabled) {
  transform: scale(0.95);
}

.color-picker-panel {
  width: 220px;
}

.color-swatch {
  width: 24px;
  height: 24px;
  border-radius: 4px;
  border: 1px solid hsl(var(--border));
  cursor: pointer;
  transition: transform 150ms ease-out;
}

.color-swatch:hover {
  transform: scale(1.15);
  box-shadow: 0 0 0 2px hsl(var(--primary) / 0.3);
}

.table-menu-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.375rem 0.5rem;
  border: none;
  background: transparent;
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.8125rem;
  color: hsl(var(--foreground));
  transition: background 150ms ease-out;
}

.table-menu-item:hover {
  background: hsl(var(--accent));
}

.ai-btn {
  color: hsl(var(--primary));
}

.ai-btn:hover {
  background: hsl(var(--primary) / 0.1);
}
</style>
