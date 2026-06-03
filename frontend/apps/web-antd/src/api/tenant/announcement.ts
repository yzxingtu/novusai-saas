import type {
  AnnouncementDelivery,
  AnnouncementDeliveryRaw,
  AnnouncementInfo,
  AnnouncementInfoRaw,
  AnnouncementListResponse,
  AnnouncementPayload,
  AnnouncementSubmitResult,
  AnnouncementSubmitResultRaw,
  AnnouncementUpdatePayload,
  CurrentAnnouncement,
  CurrentAnnouncementRaw,
  PendingAnnouncement,
  PendingAnnouncementRaw,
} from '#/types/announcement';
import type { ApiRequestOptions } from '#/utils/request';

import {
  transformAnnouncement,
  transformCurrentAnnouncement,
  transformDelivery,
  transformPendingAnnouncement,
  transformSubmitResult,
} from '#/types/announcement';
import { requestClient } from '#/utils/request';

const API_PREFIX = '/tenant/announcements';

export async function getAnnouncementListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<AnnouncementListResponse> {
  const response = await requestClient.get<{
    items: AnnouncementInfoRaw[];
    page: number;
    page_size: number;
    total: number;
  }>(API_PREFIX, { params, ...options });

  return {
    items: response.items.map((item) => transformAnnouncement(item)),
    page: response.page,
    page_size: response.page_size,
    total: response.total,
  };
}

export async function getAnnouncementDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AnnouncementInfo> {
  const raw = await requestClient.get<AnnouncementInfoRaw>(
    `${API_PREFIX}/${id}`,
    options,
  );
  return transformAnnouncement(raw);
}

export async function getMyAnnouncementApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<CurrentAnnouncement> {
  const raw = await requestClient.get<CurrentAnnouncementRaw>(
    `${API_PREFIX}/${id}/mine`,
    options,
  );
  return transformCurrentAnnouncement(raw);
}

export async function createAnnouncementApi(
  data: AnnouncementPayload,
  options?: ApiRequestOptions,
): Promise<AnnouncementInfo> {
  const raw = await requestClient.post<AnnouncementInfoRaw>(
    API_PREFIX,
    data,
    options,
  );
  return transformAnnouncement(raw);
}

export async function updateAnnouncementApi(
  id: number,
  data: AnnouncementUpdatePayload,
  options?: ApiRequestOptions,
): Promise<AnnouncementInfo> {
  const raw = await requestClient.put<AnnouncementInfoRaw>(
    `${API_PREFIX}/${id}`,
    data,
    options,
  );
  return transformAnnouncement(raw);
}

export async function deleteAnnouncementApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/${id}`, options);
}

export async function publishAnnouncementApi(
  id: number,
): Promise<AnnouncementInfo> {
  const raw = await requestClient.post<AnnouncementInfoRaw>(
    `${API_PREFIX}/${id}/publish`,
  );
  return transformAnnouncement(raw);
}

export async function getAnnouncementResponsesApi(
  id: number,
): Promise<AnnouncementDelivery[]> {
  const rows = await requestClient.get<AnnouncementDeliveryRaw[]>(
    `${API_PREFIX}/${id}/responses`,
  );
  return rows.map((row) => transformDelivery(row));
}

export async function getPendingAnnouncementsApi(): Promise<
  PendingAnnouncement[]
> {
  const rows = await requestClient.get<PendingAnnouncementRaw[]>(
    `${API_PREFIX}/pending`,
  );
  return rows.map((row) => transformPendingAnnouncement(row));
}

export async function submitAnnouncementResponseApi(
  id: number,
  answers: Record<string, unknown>,
): Promise<AnnouncementSubmitResult> {
  const raw = await requestClient.post<AnnouncementSubmitResultRaw>(
    `${API_PREFIX}/${id}/response`,
    { answers },
  );
  return transformSubmitResult(raw);
}

export async function markAnnouncementReadApi(
  id: number,
): Promise<AnnouncementSubmitResult> {
  const raw = await requestClient.post<AnnouncementSubmitResultRaw>(
    `${API_PREFIX}/${id}/read`,
  );
  return transformSubmitResult(raw);
}

export const tenantAnnouncementApi = {
  create: createAnnouncementApi,
  delete: deleteAnnouncementApi,
  get: getAnnouncementDetailApi,
  getMine: getMyAnnouncementApi,
  getResponses: getAnnouncementResponsesApi,
  list: getAnnouncementListApi,
  publish: publishAnnouncementApi,
  update: updateAnnouncementApi,
};
