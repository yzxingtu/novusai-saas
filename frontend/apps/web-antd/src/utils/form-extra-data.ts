export interface FormExtraDataOptions {
  baseDefaults?: Record<string, unknown>;
  defaults?: Record<string, unknown>;
  overrides?: Record<string, unknown>;
  resource?: string;
}

function mergeOptionalRecords(
  ...records: Array<Record<string, unknown> | undefined>
): Record<string, unknown> | undefined {
  const merged: Record<string, unknown> = {};
  for (const record of records) {
    if (!record) continue;
    Object.assign(merged, record);
  }
  return Object.keys(merged).length > 0 ? merged : undefined;
}

export function buildFormExtraData(
  options: FormExtraDataOptions = {},
): Record<string, unknown> {
  const defaults = mergeOptionalRecords(options.baseDefaults, options.defaults);

  return {
    ...(options.resource ? { _resource: options.resource } : {}),
    ...(defaults ? { _defaults: defaults } : {}),
    ...(options.overrides ? { _overrides: options.overrides } : {}),
  };
}
