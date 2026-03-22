import { _api } from '@iconify/vue';

type IconifyQuery =
  | {
      icons: string[];
      prefix: string;
      provider: string;
      type: 'icons';
    }
  | {
      provider?: string;
      type: 'custom';
      uri: string;
    };

type IconifyQueryDone = (status: 'abort' | 'next' | 'success', data: unknown) => void;

const warnedQueries = new Set<string>();

let onlineIconifyRequestsDisabled = false;

function getQueryKey(query: IconifyQuery): string {
  if (query.type === 'custom') {
    return `custom:${query.provider ?? ''}:${query.uri}`;
  }

  return `icons:${query.provider}:${query.prefix}:${query.icons.join(',')}`;
}

function warnBlockedQuery(query: IconifyQuery): void {
  const key = getQueryKey(query);
  if (warnedQueries.has(key)) {
    return;
  }

  warnedQueries.add(key);
  console.warn(`[Iconify] Blocked online icon request: ${key}`);
}

function normalizeIcons(icons: string[]): string[] {
  return [...new Set(icons.map((icon) => icon.trim()).filter(Boolean))];
}

function disableOnlineIconifyRequests(): void {
  if (onlineIconifyRequestsDisabled) {
    return;
  }

  _api.setAPIModule('', {
    prepare(provider, prefix, icons) {
      const normalizedIcons = normalizeIcons(icons);
      if (normalizedIcons.length === 0) {
        return [];
      }

      return [
        {
          icons: normalizedIcons,
          prefix,
          provider,
          type: 'icons',
        },
      ];
    },
    send(_host: string, query: IconifyQuery, done: IconifyQueryDone) {
      warnBlockedQuery(query);
      done('abort', query);
    },
  });

  onlineIconifyRequestsDisabled = true;
}

export { disableOnlineIconifyRequests };
