/**
 * DOM Semantic Scanner
 * DOM 语义快照扫描器
 *
 * Provides a fallback page context for pages that have not called registerPageContext().
 * Scans the DOM for key semantic elements (headings, tables, forms, buttons, tabs)
 * and returns a lightweight snapshot the AI can use to understand the page.
 *
 * Security: never extracts input values (only labels/headings/visible descriptive text).
 * Performance: capped at ~50ms scan budget; output capped at ~3KB JSON.
 * 安全：不采集输入框值，仅标签/标题/可见描述性文本。
 * 性能：扫描约 50ms 预算，序列化输出约 3KB 上限。
 */

// --- Snapshot shape & byte budget / 快照结构与字节预算 ---

export interface DomSnapshot {
  action_buttons: string[];
  breadcrumb: string[];
  detail_fields: Array<{ label: string; value: string }>;
  forms: Array<{ labels: string[]; title?: string }>;
  overlays: Array<{
    summary?: string;
    title: string;
    type: 'drawer' | 'modal';
  }>;
  page_title: string;
  stat_cards: Array<{ label: string; value: string }>;
  tables: Array<{ columns: string[]; row_count: number }>;
  tabs: Array<{ active: boolean; label: string }>;
  text_blocks: string[];
}

const MAX_OUTPUT_BYTES = 3072;
const MAX_BUTTONS = 15;
const MAX_COLUMNS = 15;
const MAX_DETAIL_FIELDS = 12;
const MAX_LABELS_PER_FORM = 20;
const MAX_OVERLAYS = 3;
const MAX_STAT_CARDS = 6;
const MAX_TABS = 12;
const MAX_TEXT_BLOCKS = 6;
const MAX_TEXT_LENGTH = 180;
const encoder = new TextEncoder();

// --- Text & collection helpers / 文本与采集辅助 ---

function normalizeText(text: string, maxLength = 80): string {
  return text.replaceAll(/\s+/g, ' ').trim().slice(0, maxLength);
}

function textOf(el: Element | null, maxLength = 80): string {
  return normalizeText(el?.textContent || '', maxLength);
}

function serializedBytes(value: unknown): number {
  return encoder.encode(JSON.stringify(value)).length;
}

function pushUnique(target: string[], value: string, maxItems: number): void {
  if (!value || target.length >= maxItems || target.includes(value)) {
    return;
  }
  target.push(value);
}

function addDetailField(
  target: Array<{ label: string; value: string }>,
  label: string,
  value: string,
): void {
  if (!label || !value || target.length >= MAX_DETAIL_FIELDS) {
    return;
  }
  if (target.some((item) => item.label === label && item.value === value)) {
    return;
  }
  target.push({ label, value });
}

function collectTextSummary(
  root: Element,
  selectors: string[],
  maxItems: number,
): string[] {
  const values: string[] = [];
  selectors.forEach((selector) => {
    root.querySelectorAll(selector).forEach((node) => {
      if (values.length >= maxItems) return;
      const text = textOf(node, MAX_TEXT_LENGTH);
      if (text.length < 16) return;
      pushUnique(values, text, maxItems);
    });
  });
  return values;
}

// --- Shrink snapshot JSON to MAX_OUTPUT_BYTES / 将快照压到 MAX_OUTPUT_BYTES 以下 ---

function trimSnapshotToBudget(snapshot: DomSnapshot): DomSnapshot {
  const trimmed: DomSnapshot = {
    action_buttons: [...snapshot.action_buttons],
    breadcrumb: [...snapshot.breadcrumb],
    detail_fields: [...snapshot.detail_fields],
    forms: snapshot.forms.map((form) => ({
      ...(form.title ? { title: form.title } : {}),
      labels: [...form.labels],
    })),
    overlays: snapshot.overlays.map((overlay) => ({ ...overlay })),
    page_title: snapshot.page_title,
    stat_cards: [...snapshot.stat_cards],
    tables: snapshot.tables.map((table) => ({
      columns: [...table.columns],
      row_count: table.row_count,
    })),
    tabs: [...snapshot.tabs],
    text_blocks: [...snapshot.text_blocks],
  };

  if (serializedBytes(trimmed) <= MAX_OUTPUT_BYTES) {
    return trimmed;
  }

  trimmed.text_blocks = trimmed.text_blocks
    .slice(0, 4)
    .map((item) => item.slice(0, 120));
  trimmed.detail_fields = trimmed.detail_fields.slice(0, 8).map((item) => ({
    label: item.label.slice(0, 32),
    value: item.value.slice(0, 72),
  }));
  trimmed.stat_cards = trimmed.stat_cards.slice(0, 4).map((item) => ({
    label: item.label.slice(0, 28),
    value: item.value.slice(0, 48),
  }));
  trimmed.overlays = trimmed.overlays.slice(0, 2).map((item) => ({
    ...item,
    ...(item.summary ? { summary: item.summary.slice(0, 96) } : {}),
  }));
  trimmed.action_buttons = trimmed.action_buttons.slice(0, 10);
  trimmed.forms = trimmed.forms.slice(0, 2).map((form) => ({
    ...(form.title ? { title: form.title.slice(0, 40) } : {}),
    labels: form.labels.slice(0, 10),
  }));
  trimmed.tables = trimmed.tables.slice(0, 2).map((table) => ({
    columns: table.columns.slice(0, 8),
    row_count: table.row_count,
  }));

  if (serializedBytes(trimmed) <= MAX_OUTPUT_BYTES) {
    return trimmed;
  }

  trimmed.text_blocks = trimmed.text_blocks.slice(0, 2);
  trimmed.detail_fields = trimmed.detail_fields.slice(0, 4);
  trimmed.stat_cards = trimmed.stat_cards.slice(0, 2);
  trimmed.overlays = trimmed.overlays.map((item) => ({
    title: item.title,
    type: item.type,
  }));
  trimmed.action_buttons = trimmed.action_buttons.slice(0, 6);
  trimmed.breadcrumb = trimmed.breadcrumb.slice(-2);
  trimmed.tabs = trimmed.tabs.slice(0, 6);

  return trimmed;
}

// --- Main entry: ordered DOM passes (tables, forms, …) / 主入口：按序扫描表格、表单等 ---

/**
 * Scan the current page DOM and return a semantic snapshot / 扫描当前页 DOM 并返回语义快照
 * Returns null if no meaningful content is found.
 */
export function scanDomSemantics(): DomSnapshot | null {
  const start = performance.now();

  // 1. Page title — breadcrumb last item or header title / 页面标题
  let pageTitle = '';
  const breadcrumbItems = document.querySelectorAll(
    '.ant-breadcrumb-link, .vben-breadcrumb .breadcrumb-label',
  );
  const breadcrumb: string[] = [];
  breadcrumbItems.forEach((el) => {
    const text = textOf(el);
    if (text) breadcrumb.push(text);
  });
  if (breadcrumb.length > 0) {
    pageTitle = breadcrumb.at(-1) ?? '';
  }
  if (!pageTitle) {
    pageTitle =
      textOf(document.querySelector('.vben-page-header-title')) ||
      textOf(document.querySelector('h1')) ||
      textOf(document.querySelector('.ant-page-header-heading-title')) ||
      '';
  }

  // 2. Tables / 表格
  const tables: DomSnapshot['tables'] = [];
  const tableEls = document.querySelectorAll(
    '.ant-table, .vxe-table, [class*="vxe-grid"]',
  );
  tableEls.forEach((tableEl) => {
    if (performance.now() - start > 40) return;

    const columns: string[] = [];
    const headerCells = tableEl.querySelectorAll(
      '.ant-table-thead th, .vxe-header--column .vxe-cell--title',
    );
    headerCells.forEach((th) => {
      pushUnique(columns, textOf(th), MAX_COLUMNS);
    });

    const rows = tableEl.querySelectorAll(
      '.ant-table-tbody tr, .vxe-body--row',
    );

    if (columns.length > 0) {
      tables.push({ columns, row_count: rows.length });
    }
  });

  // 3. Forms (labels only, no values) / 表单仅采集标签不含值
  const forms: DomSnapshot['forms'] = [];
  const formEls = document.querySelectorAll('form, .ant-form');
  formEls.forEach((formEl) => {
    if (performance.now() - start > 40) return;

    const labels: string[] = [];
    formEl.querySelectorAll('.ant-form-item-label label').forEach((lbl) => {
      pushUnique(labels, textOf(lbl), MAX_LABELS_PER_FORM);
    });
    if (labels.length > 0) {
      const title =
        textOf(
          formEl.querySelector(
            '.ant-card-head-title, .ant-drawer-title, .ant-modal-title, h2, h3',
          ),
          48,
        ) || undefined;
      forms.push(title ? { labels, title } : { labels });
    }
  });

  // 4. Action buttons / 操作按钮
  const actionButtons: string[] = [];
  const buttons = document.querySelectorAll(
    'button:not([disabled]):not(.ant-modal button):not(.ant-drawer button)',
  );
  buttons.forEach((btn) => {
    const text = textOf(btn, 30);
    if (text && text.length > 1 && text.length < 30) {
      pushUnique(actionButtons, text, MAX_BUTTONS);
    }
  });

  // 5. Tabs / 页签
  const tabs: DomSnapshot['tabs'] = [];
  document.querySelectorAll('.ant-tabs-tab').forEach((tabEl) => {
    const label = textOf(tabEl, 40);
    if (label && tabs.length < MAX_TABS) {
      tabs.push({
        label,
        active: tabEl.classList.contains('ant-tabs-tab-active'),
      });
    }
  });

  // 6. Statistic cards / 统计卡片
  const statCards: DomSnapshot['stat_cards'] = [];
  document.querySelectorAll('.ant-statistic').forEach((statEl) => {
    const label = textOf(statEl.querySelector('.ant-statistic-title'), 40);
    const value = textOf(statEl.querySelector('.ant-statistic-content'), 48);
    if (!label || !value || statCards.length >= MAX_STAT_CARDS) {
      return;
    }
    if (
      !statCards.some((item) => item.label === label && item.value === value)
    ) {
      statCards.push({ label, value });
    }
  });

  // 7. Detail fields / 详情字段
  const detailFields: DomSnapshot['detail_fields'] = [];
  document.querySelectorAll('.ant-descriptions-item').forEach((item) => {
    if (detailFields.length >= MAX_DETAIL_FIELDS) return;
    const label = textOf(
      item.querySelector('.ant-descriptions-item-label'),
      36,
    );
    const value = textOf(
      item.querySelector('.ant-descriptions-item-content'),
      96,
    );
    addDetailField(detailFields, label, value);
  });

  // 8. Text blocks / 正文摘要
  const textBlocks = collectTextSummary(
    document.body,
    [
      '.vben-page-header-description',
      '.ant-page-header-heading-sub-title',
      '.ant-result-subtitle',
      '.ant-list-item-meta-description',
      '.ant-empty-description',
      '.ant-card-body p',
      '.ant-card-body .ant-typography',
      '.ant-descriptions-item-content',
      '.markdown-body p',
      '.prose p',
      'main p',
      'article p',
    ],
    MAX_TEXT_BLOCKS,
  );

  // 9. Active overlays / 当前弹层
  const overlays: DomSnapshot['overlays'] = [];
  document.querySelectorAll('.ant-modal, .ant-drawer-content').forEach((el) => {
    if (overlays.length >= MAX_OVERLAYS) return;
    const isDrawer = el.classList.contains('ant-drawer-content');
    const title = textOf(
      el.querySelector(isDrawer ? '.ant-drawer-title' : '.ant-modal-title'),
      48,
    );
    const summary = collectTextSummary(
      el,
      [
        isDrawer ? '.ant-drawer-body p' : '.ant-modal-body p',
        isDrawer
          ? '.ant-drawer-body .ant-typography'
          : '.ant-modal-body .ant-typography',
        isDrawer ? '.ant-drawer-body' : '.ant-modal-body',
      ],
      2,
    ).join(' ');
    if (!title && !summary) return;
    overlays.push({
      title: title || (isDrawer ? 'Drawer' : 'Modal'),
      type: isDrawer ? 'drawer' : 'modal',
      ...(summary ? { summary } : {}),
    });
  });

  // Empty check — return null if nothing meaningful found / 无有效内容则返回 null
  if (
    !pageTitle &&
    breadcrumb.length === 0 &&
    tables.length === 0 &&
    forms.length === 0 &&
    actionButtons.length === 0 &&
    tabs.length === 0 &&
    statCards.length === 0 &&
    detailFields.length === 0 &&
    textBlocks.length === 0 &&
    overlays.length === 0
  ) {
    return null;
  }

  return trimSnapshotToBudget({
    action_buttons: actionButtons,
    breadcrumb,
    detail_fields: detailFields,
    forms,
    overlays,
    page_title: pageTitle,
    stat_cards: statCards,
    tables,
    tabs,
    text_blocks: textBlocks,
  });
}
