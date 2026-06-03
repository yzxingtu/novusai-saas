export type AnnouncementFieldType = 'checkbox' | 'consent' | 'radio' | 'text';
export type AnnouncementPriority = 'high' | 'low' | 'normal' | 'urgent';
export type AnnouncementDeliveryStatus =
  | 'pending'
  | 'read'
  | 'submitted'
  | string;
export type AnnouncementStatus = 'draft' | 'published';

export interface AnnouncementFormOption {
  label: string;
  value: string;
}

export interface AnnouncementFormField {
  key: string;
  type: AnnouncementFieldType;
  label: string;
  required: boolean;
  placeholder?: string;
  options?: AnnouncementFormOption[];
  must_be_true?: boolean;
}

export type AnnouncementAnswers = Record<string, boolean | string | string[]>;

export interface AnnouncementInfoRaw {
  id: number;
  tenant_id: number;
  scope: string;
  title: string;
  content?: null | string;
  status: AnnouncementStatus | string;
  priority: AnnouncementPriority | string;
  require_response: boolean;
  form_schema?: AnnouncementFormField[] | null;
  published_at?: null | string;
  recipient_count: number;
  response_count: number;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface AnnouncementInfo {
  id: number;
  tenantId: number;
  scope: string;
  title: string;
  content?: null | string;
  status: AnnouncementStatus | string;
  priority: AnnouncementPriority | string;
  requireResponse: boolean;
  formSchema: AnnouncementFormField[];
  publishedAt?: null | string;
  recipientCount: number;
  responseCount: number;
  sortOrder: number;
  createdAt: string;
  updatedAt: string;
}

export interface AnnouncementPayload {
  title: string;
  content?: null | string;
  priority: AnnouncementPriority;
  require_response: boolean;
  form_schema: AnnouncementFormField[];
  sort_order?: number;
}

export type AnnouncementUpdatePayload = Partial<AnnouncementPayload>;

export interface AnnouncementListResponse {
  items: AnnouncementInfo[];
  page: number;
  page_size: number;
  total: number;
}

export interface AnnouncementDeliveryRaw {
  id: number;
  tenant_id: number;
  announcement_id: number;
  recipient_type: string;
  recipient_id: number;
  status: string;
  notification_id?: null | number;
  submitted_at?: null | string;
  answers?: null | Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AnnouncementDelivery {
  id: number;
  tenantId: number;
  announcementId: number;
  recipientType: string;
  recipientId: number;
  status: string;
  notificationId?: null | number;
  submittedAt?: null | string;
  answers?: null | Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export interface PendingAnnouncementRaw extends AnnouncementInfoRaw {
  delivery_id: number;
}

export interface CurrentAnnouncementRaw extends AnnouncementInfoRaw {
  answers?: null | Record<string, unknown>;
  delivery_id: number;
  delivery_status: AnnouncementDeliveryStatus;
  notification_id?: null | number;
  submitted_at?: null | string;
}

export interface CurrentAnnouncement extends AnnouncementInfo {
  answers?: null | Record<string, unknown>;
  deliveryId: number;
  deliveryStatus: AnnouncementDeliveryStatus;
  notificationId?: null | number;
  submittedAt?: null | string;
}

export type PendingAnnouncement = CurrentAnnouncement;
export type AnnouncementModalItem = CurrentAnnouncement;

export interface AnnouncementSubmitResultRaw {
  id: number;
  announcement_id: number;
  delivery_id: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface AnnouncementSubmitResult {
  id: number;
  announcementId: number;
  deliveryId: number;
  status: string;
  createdAt: string;
  updatedAt: string;
}

export interface AnnouncementManagementApi {
  create: (payload: AnnouncementPayload) => Promise<AnnouncementInfo>;
  delete: (id: number) => Promise<void>;
  get: (id: number) => Promise<AnnouncementInfo>;
  getMine?: (id: number) => Promise<CurrentAnnouncement>;
  getResponses: (id: number) => Promise<AnnouncementDelivery[]>;
  list: (params?: Record<string, unknown>) => Promise<AnnouncementListResponse>;
  publish: (id: number) => Promise<AnnouncementInfo>;
  update: (
    id: number,
    payload: AnnouncementUpdatePayload,
  ) => Promise<AnnouncementInfo>;
}

export function transformAnnouncement(
  raw: AnnouncementInfoRaw,
): AnnouncementInfo {
  return {
    id: raw.id,
    tenantId: raw.tenant_id,
    scope: raw.scope,
    title: raw.title,
    content: raw.content,
    status: raw.status,
    priority: raw.priority,
    requireResponse: raw.require_response,
    formSchema: raw.form_schema ?? [],
    publishedAt: raw.published_at,
    recipientCount: raw.recipient_count,
    responseCount: raw.response_count,
    sortOrder: raw.sort_order,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

export function createAnnouncementFormField(
  type: AnnouncementFieldType,
  index: number,
): AnnouncementFormField {
  const key = `${type}_${index + 1}`;
  const field: AnnouncementFormField = {
    key,
    label: '',
    required: true,
    type,
  };

  if (type === 'consent') {
    field.must_be_true = true;
  }

  if (type === 'radio' || type === 'checkbox') {
    field.options = [
      { label: '', value: 'option_1' },
      { label: '', value: 'option_2' },
    ];
  }

  return field;
}

export function createDefaultAnnouncementAnswers(
  schema: AnnouncementFormField[],
): AnnouncementAnswers {
  const answers: AnnouncementAnswers = {};
  for (const field of schema) {
    if (field.type === 'checkbox') {
      answers[field.key] = [];
    } else if (field.type === 'consent') {
      answers[field.key] = false;
    } else {
      answers[field.key] = '';
    }
  }
  return answers;
}

export function normalizeAnnouncementAnswers(
  schema: AnnouncementFormField[],
  rawAnswers?: null | Record<string, unknown>,
): AnnouncementAnswers {
  const answers = createDefaultAnnouncementAnswers(schema);
  if (!rawAnswers) {
    return answers;
  }

  for (const field of schema) {
    const value = rawAnswers[field.key];
    if (field.type === 'consent') {
      if (typeof value === 'boolean') {
        answers[field.key] = value;
      }
      continue;
    }

    if (field.type === 'text' || field.type === 'radio') {
      if (typeof value === 'string') {
        answers[field.key] = value;
      }
      continue;
    }

    if (field.type === 'checkbox' && Array.isArray(value)) {
      answers[field.key] = value.filter(
        (item): item is string => typeof item === 'string',
      );
    }
  }

  return answers;
}

export function validateAnnouncementAnswers(
  schema: AnnouncementFormField[],
  answers: Record<string, unknown>,
): string[] {
  const errors: string[] = [];

  for (const field of schema) {
    const value = answers[field.key];
    const required = Boolean(field.required);

    if (field.type === 'consent') {
      if (value === undefined || value === null) {
        if (required || field.must_be_true)
          errors.push(`${field.key}.required`);
        continue;
      }
      if (typeof value !== 'boolean') {
        errors.push(`${field.key}.boolean`);
        continue;
      }
      if (field.must_be_true && value !== true) {
        errors.push(`${field.key}.must_be_true`);
      }
      continue;
    }

    if (field.type === 'text') {
      if (
        (typeof value !== 'string' || value.trim().length === 0) &&
        required
      ) {
        errors.push(`${field.key}.required`);
      }
      continue;
    }

    const optionValues = new Set(
      (field.options ?? []).map((option) => option.value),
    );

    if (field.type === 'radio') {
      if (typeof value !== 'string' || value.length === 0) {
        if (required) errors.push(`${field.key}.required`);
        continue;
      }
      if (!optionValues.has(value)) {
        errors.push(`${field.key}.invalid_option`);
      }
      continue;
    }

    if (field.type === 'checkbox') {
      if (!Array.isArray(value)) {
        if (required) errors.push(`${field.key}.required`);
        continue;
      }
      if (required && value.length === 0) {
        errors.push(`${field.key}.required`);
      }
      if (
        value.some(
          (item) => typeof item !== 'string' || !optionValues.has(item),
        )
      ) {
        errors.push(`${field.key}.invalid_option`);
      }
    }
  }

  const validKeys = new Set(schema.map((field) => field.key));
  for (const key of Object.keys(answers)) {
    if (!validKeys.has(key)) {
      errors.push(`${key}.unknown`);
    }
  }

  return errors;
}

export function transformDelivery(
  raw: AnnouncementDeliveryRaw,
): AnnouncementDelivery {
  return {
    id: raw.id,
    tenantId: raw.tenant_id,
    announcementId: raw.announcement_id,
    recipientType: raw.recipient_type,
    recipientId: raw.recipient_id,
    status: raw.status,
    notificationId: raw.notification_id,
    submittedAt: raw.submitted_at,
    answers: raw.answers,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

export function transformPendingAnnouncement(
  raw: PendingAnnouncementRaw,
): PendingAnnouncement {
  return {
    ...transformAnnouncement(raw),
    answers: null,
    deliveryId: raw.delivery_id,
    deliveryStatus: 'pending',
    notificationId: null,
    submittedAt: null,
  };
}

export function transformCurrentAnnouncement(
  raw: CurrentAnnouncementRaw,
): CurrentAnnouncement {
  return {
    ...transformAnnouncement(raw),
    answers: raw.answers,
    deliveryId: raw.delivery_id,
    deliveryStatus: raw.delivery_status,
    notificationId: raw.notification_id,
    submittedAt: raw.submitted_at,
  };
}

export function transformSubmitResult(
  raw: AnnouncementSubmitResultRaw,
): AnnouncementSubmitResult {
  return {
    id: raw.id,
    announcementId: raw.announcement_id,
    deliveryId: raw.delivery_id,
    status: raw.status,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}
