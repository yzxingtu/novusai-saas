const MAX_FORM_FIELDS = 20;
const DEFAULT_PAGE_CONTEXT_MAX_BYTES_FALLBACK = 8192;
const PAGE_CONTEXT_SOFT_RESERVE_BYTES = 1024;

export function collectVisualState(
  modals: Array<{ type: string }> = [],
): Record<string, unknown> {
  return {
    url: window.location.pathname,
    viewport: { w: window.innerWidth, h: window.innerHeight },
    scroll_y: Math.round(window.scrollY),
    has_modal: modals.some((m) => m.type === 'modal'),
    has_drawer: modals.some((m) => m.type === 'drawer'),
    ...(modals.length > 0 ? { open_overlays: modals } : {}),
  };
}

export function getPageContextHardLimitBytes(configuredValue?: number): number {
  return configuredValue || DEFAULT_PAGE_CONTEXT_MAX_BYTES_FALLBACK;
}

export function getPageContextSoftLimitBytes(hardLimitBytes: number): number {
  return Math.max(hardLimitBytes - PAGE_CONTEXT_SOFT_RESERVE_BYTES, 1024);
}

export function getSerializedPageDataBytes(
  pageData: Record<string, unknown>,
): number {
  return new TextEncoder().encode(JSON.stringify(pageData)).length;
}

export function truncateTextByBytes(text: string, maxBytes: number): string {
  const encoder = new TextEncoder();
  const encoded = encoder.encode(text);
  if (encoded.length <= maxBytes) return text;
  return new TextDecoder().decode(encoded.slice(0, maxBytes));
}

export function truncateFormFields(
  pageData: Record<string, unknown>,
): Record<string, unknown> {
  const ff = pageData.form_fields;
  if (!ff || typeof ff !== 'object') return pageData;
  const entries = Object.entries(ff as Record<string, unknown>);
  if (entries.length <= MAX_FORM_FIELDS) return pageData;
  const truncated = Object.fromEntries(entries.slice(0, MAX_FORM_FIELDS));
  (truncated as Record<string, unknown>)._truncated =
    `Showing ${MAX_FORM_FIELDS} of ${entries.length} fields`;
  return { ...pageData, form_fields: truncated };
}

export function compactAvailableOperations(
  operations: unknown[],
  options: {
    includeDescriptions: boolean;
    includeParams: boolean;
    maxOps: number;
    maxParamsPerOp: number;
  },
): unknown[] {
  const operationPriority: Record<string, number> = {
    create_record: 0,
    edit_record: 1,
    fill_form: 2,
    submit_form: 3,
    get_form_state: 4,
    validate_form: 5,
    delete_record: 6,
    search: 7,
    read_visible_rows: 8,
    capture_screenshot: 9,
    read_current_view: 10,
    read_current_sections: 11,
  };
  const normalizedOperations = operations.filter(Boolean);
  const writableOperations = normalizedOperations.filter(
    (operation) =>
      typeof operation === 'object' &&
      operation !== null &&
      (operation as Record<string, unknown>).readonly === false,
  );
  const readonlyOperations = normalizedOperations.filter(
    (operation) =>
      !(
        typeof operation === 'object' &&
        operation !== null &&
        (operation as Record<string, unknown>).readonly === false
      ),
  );
  const prioritizedOperations = [...writableOperations, ...readonlyOperations]
    .map((operation, index) => ({
      index,
      operation,
      priority:
        typeof operation === 'object' && operation !== null
          ? (operationPriority[
              String((operation as Record<string, unknown>).name || '')
            ] ?? 1000)
          : 1000,
    }))
    .toSorted((left, right) =>
      left.priority === right.priority
        ? left.index - right.index
        : left.priority - right.priority,
    )
    .map((item) => item.operation);

  return prioritizedOperations.slice(0, options.maxOps).map((operation) => {
    if (!operation || typeof operation !== 'object') {
      return operation;
    }

    const source = operation as Record<string, unknown>;
    const operationName = String(source.name || '');
    const compact: Record<string, unknown> = {
      name: operationName,
      label: source.label,
      readonly: source.readonly,
    };

    if (options.includeDescriptions && typeof source.description === 'string') {
      compact.description = source.description;
    }

    if (
      options.includeParams &&
      source.params &&
      typeof source.params === 'object'
    ) {
      const preferredParamCount =
        operationName === 'create_record' ||
        operationName === 'edit_record' ||
        operationName === 'fill_form'
          ? Math.max(options.maxParamsPerOp, 6)
          : options.maxParamsPerOp;
      const paramEntries = Object.entries(
        source.params as Record<string, unknown>,
      ).slice(0, preferredParamCount);
      compact.params = Object.fromEntries(
        paramEntries.map(([paramName, rawSchema]) => {
          if (!rawSchema || typeof rawSchema !== 'object') {
            return [paramName, rawSchema];
          }
          const schema = rawSchema as Record<string, unknown>;
          return [
            paramName,
            {
              type: schema.type,
              required: schema.required,
              ...(Array.isArray(schema.enum) && schema.enum.length > 0
                ? { enum: schema.enum.slice(0, 5) }
                : {}),
            },
          ];
        }),
      );
    }

    return compact;
  });
}

function compactFormFieldsForBudget(
  formFields: Record<string, unknown>,
  options: {
    includeConstraints: boolean;
    includeOptions: boolean;
    maxFields: number;
  },
): Record<string, unknown> {
  const entries = Object.entries(formFields).filter(
    ([fieldName]) => fieldName !== '_truncated',
  );
  const compact = Object.fromEntries(
    entries.slice(0, options.maxFields).map(([fieldName, rawDescriptor]) => {
      if (!rawDescriptor || typeof rawDescriptor !== 'object') {
        return [fieldName, rawDescriptor];
      }
      const descriptor = rawDescriptor as Record<string, unknown>;
      const nextDescriptor: Record<string, unknown> = {
        type: descriptor.type,
        component: descriptor.component,
        description: descriptor.description,
      };
      if (descriptor.required) {
        nextDescriptor.required = descriptor.required;
      }
      if (descriptor.optionsSource) {
        nextDescriptor.optionsSource = descriptor.optionsSource;
      }
      if (options.includeConstraints && descriptor.constraints) {
        nextDescriptor.constraints = descriptor.constraints;
      }
      if (
        options.includeOptions &&
        Array.isArray(descriptor.options) &&
        descriptor.options.length > 0
      ) {
        nextDescriptor.options = descriptor.options.slice(0, 4);
      }
      return [fieldName, nextDescriptor];
    }),
  );
  if (entries.length > options.maxFields) {
    compact._truncated = `Showing ${options.maxFields} of ${entries.length} fields`;
  }
  return compact;
}

function compactSemanticSnapshot(
  pageData: Record<string, unknown>,
  options: {
    maxDetailFields: number;
    maxOverlays: number;
    maxStatCards: number;
    maxTextBlocks: number;
    overlaySummaryChars: number;
    textMaxChars: number;
  },
): Record<string, unknown> {
  let changed = false;
  const nextPageData: Record<string, unknown> = { ...pageData };

  const textBlocks = pageData.text_blocks;
  if (Array.isArray(textBlocks)) {
    nextPageData.text_blocks = textBlocks
      .slice(0, options.maxTextBlocks)
      .map((item) =>
        typeof item === 'string' ? item.slice(0, options.textMaxChars) : item,
      );
    changed = true;
  }

  const detailFields = pageData.detail_fields;
  if (Array.isArray(detailFields)) {
    nextPageData.detail_fields = detailFields
      .slice(0, options.maxDetailFields)
      .map((item) => {
        if (!item || typeof item !== 'object') {
          return item;
        }
        const field = item as Record<string, unknown>;
        return {
          label:
            typeof field.label === 'string' ? field.label.slice(0, 32) : '',
          value:
            typeof field.value === 'string'
              ? field.value.slice(0, options.textMaxChars)
              : '',
        };
      });
    changed = true;
  }

  const statCards = pageData.stat_cards;
  if (Array.isArray(statCards)) {
    nextPageData.stat_cards = statCards
      .slice(0, options.maxStatCards)
      .map((item) => {
        if (!item || typeof item !== 'object') {
          return item;
        }
        const card = item as Record<string, unknown>;
        return {
          label: typeof card.label === 'string' ? card.label.slice(0, 28) : '',
          value: typeof card.value === 'string' ? card.value.slice(0, 48) : '',
        };
      });
    changed = true;
  }

  const overlays = pageData.overlays;
  if (Array.isArray(overlays)) {
    nextPageData.overlays = overlays
      .slice(0, options.maxOverlays)
      .map((item) => {
        if (!item || typeof item !== 'object') {
          return item;
        }
        const overlay = item as Record<string, unknown>;
        return {
          type: overlay.type,
          title:
            typeof overlay.title === 'string' ? overlay.title.slice(0, 48) : '',
          ...(options.overlaySummaryChars > 0 &&
          typeof overlay.summary === 'string'
            ? { summary: overlay.summary.slice(0, options.overlaySummaryChars) }
            : {}),
        };
      });
    changed = true;
  }

  return changed ? nextPageData : pageData;
}

export function guardPageDataSize(
  pageData: Record<string, unknown>,
  maxPageDataBytes: number,
): Record<string, unknown> {
  let data = { ...pageData };
  let size = getSerializedPageDataBytes(data);
  if (size <= maxPageDataBytes) return data;

  const ls = data.list_summary as Record<string, unknown> | undefined;
  if (
    ls?.sample_rows &&
    Array.isArray(ls.sample_rows) &&
    ls.sample_rows.length > 0
  ) {
    data = {
      ...data,
      list_summary: {
        ...ls,
        sample_rows: (ls.sample_rows as unknown[]).slice(0, 2),
      },
    };
    size = getSerializedPageDataBytes(data);
    if (size <= maxPageDataBytes) return data;
    data = { ...data, list_summary: { ...ls, sample_rows: [] } };
    size = getSerializedPageDataBytes(data);
    if (size <= maxPageDataBytes) return data;
  }

  if (
    Array.isArray(data.text_blocks) ||
    Array.isArray(data.detail_fields) ||
    Array.isArray(data.stat_cards) ||
    Array.isArray(data.overlays)
  ) {
    const semanticVariants = [
      compactSemanticSnapshot(data, {
        maxDetailFields: 8,
        maxOverlays: 2,
        maxStatCards: 4,
        maxTextBlocks: 4,
        overlaySummaryChars: 96,
        textMaxChars: 120,
      }),
      compactSemanticSnapshot(data, {
        maxDetailFields: 4,
        maxOverlays: 1,
        maxStatCards: 2,
        maxTextBlocks: 2,
        overlaySummaryChars: 0,
        textMaxChars: 80,
      }),
    ];

    for (const compactSemanticData of semanticVariants) {
      data = compactSemanticData;
      size = getSerializedPageDataBytes(data);
      if (size <= maxPageDataBytes) return data;
    }
  }

  const aops = data.available_operations;
  if (Array.isArray(aops) && aops.length > 0) {
    const operationVariants = [
      compactAvailableOperations(aops, {
        includeDescriptions: true,
        includeParams: true,
        maxOps: 12,
        maxParamsPerOp: 4,
      }),
      compactAvailableOperations(aops, {
        includeDescriptions: true,
        includeParams: false,
        maxOps: 10,
        maxParamsPerOp: 0,
      }),
      compactAvailableOperations(aops, {
        includeDescriptions: false,
        includeParams: false,
        maxOps: 8,
        maxParamsPerOp: 0,
      }),
    ];

    for (const compactOperations of operationVariants) {
      data = {
        ...data,
        available_operations: compactOperations,
      };
      size = getSerializedPageDataBytes(data);
      if (size <= maxPageDataBytes) return data;
    }

    const { available_operations: _ao, ...rest } = data;
    data = rest;
    size = getSerializedPageDataBytes(data);
    if (size <= maxPageDataBytes) return data;
  }

  const body = data.document_body_text;
  if (typeof body === 'string' && body.length > 0) {
    for (const maxBodyBytes of [2400, 1600, 800]) {
      data = {
        ...data,
        document_body_text: truncateTextByBytes(body, maxBodyBytes),
      };
      size = getSerializedPageDataBytes(data);
      if (size <= maxPageDataBytes) return data;
    }
    data = { ...data, document_body_text: truncateTextByBytes(body, 400) };
    size = getSerializedPageDataBytes(data);
    if (size <= maxPageDataBytes) return data;
  }

  const formFields = data.form_fields;
  if (formFields && typeof formFields === 'object') {
    const compactVariants = [
      compactFormFieldsForBudget(formFields as Record<string, unknown>, {
        includeConstraints: true,
        includeOptions: true,
        maxFields: 16,
      }),
      compactFormFieldsForBudget(formFields as Record<string, unknown>, {
        includeConstraints: true,
        includeOptions: false,
        maxFields: 12,
      }),
      compactFormFieldsForBudget(formFields as Record<string, unknown>, {
        includeConstraints: false,
        includeOptions: false,
        maxFields: 8,
      }),
      compactFormFieldsForBudget(formFields as Record<string, unknown>, {
        includeConstraints: false,
        includeOptions: false,
        maxFields: 4,
      }),
    ];

    for (const compactFields of compactVariants) {
      data = { ...data, form_fields: compactFields };
      size = getSerializedPageDataBytes(data);
      if (size <= maxPageDataBytes) return data;
    }

    const { form_fields: _ff, ...rest } = data;
    data = rest;
  }

  return data;
}
