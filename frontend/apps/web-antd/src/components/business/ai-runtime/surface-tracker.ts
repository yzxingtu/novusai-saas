import type {
  UIOverlaySurfaceInput,
  UIPageSurfaceInput,
  UISurface,
  UISurfaceDelta,
  UISurfaceSyncInput,
} from './types';

interface SurfaceDraftBase {
  key: string;
  metadata?: Record<string, unknown>;
  parentId?: string;
  title: string;
}

interface PageSurfaceDraft extends SurfaceDraftBase {
  kind: 'page';
  pageKey: string;
  routePath?: string;
}

interface OverlaySurfaceDraft extends SurfaceDraftBase {
  kind: UIOverlaySurfaceInput['kind'];
}

type SurfaceDraft = OverlaySurfaceDraft | PageSurfaceDraft;

function cloneSurface(surface: UISurface): UISurface {
  return {
    ...surface,
    ...(surface.metadata ? { metadata: { ...surface.metadata } } : {}),
    ...(surface.extensions ? { extensions: { ...surface.extensions } } : {}),
  };
}

function shallowEqualRecord(
  left?: Record<string, unknown>,
  right?: Record<string, unknown>,
): boolean {
  const leftKeys = Object.keys(left ?? {});
  const rightKeys = Object.keys(right ?? {});
  if (leftKeys.length !== rightKeys.length) {
    return false;
  }
  return leftKeys.every((key) => Object.is(left?.[key], right?.[key]));
}

function toPageDraft(input: UIPageSurfaceInput): PageSurfaceDraft {
  return {
    key: input.key,
    kind: 'page',
    metadata: input.metadata,
    pageKey: input.pageKey,
    routePath: input.routePath,
    title: input.title,
  };
}

function toOverlayDraft(
  input: UIOverlaySurfaceInput,
  parentId?: string,
): OverlaySurfaceDraft {
  return {
    key: input.key,
    kind: input.kind,
    metadata: input.metadata,
    parentId,
    title: input.title,
  };
}

export class UISurfaceTracker {
  private sequence = 0;

  private readonly stackKeys: string[] = [];

  private readonly surfacesByKey = new Map<string, UISurface>();

  closeSurfaceById(surfaceId: string): UISurface[] {
    const key = this.findKeyById(surfaceId);
    if (!key) {
      return [];
    }

    const toRemoveKeys = this.collectRemovableKeys(surfaceId, key);
    const removed: UISurface[] = [];

    toRemoveKeys.forEach((removableKey) => {
      const surface = this.surfacesByKey.get(removableKey);
      if (!surface) {
        return;
      }
      removed.push(cloneSurface(surface));
      this.surfacesByKey.delete(removableKey);
    });

    this.rewriteStack(
      this.stackKeys.filter((stackKey) => !toRemoveKeys.has(stackKey)),
    );
    return removed;
  }

  getActiveSurface(): null | UISurface {
    const lastKey = this.stackKeys.at(-1);
    if (!lastKey) {
      return null;
    }
    const surface = this.surfacesByKey.get(lastKey);
    return surface ? cloneSurface(surface) : null;
  }

  getStack(): UISurface[] {
    return this.stackKeys
      .map((key) => this.surfacesByKey.get(key))
      .filter((surface): surface is UISurface => surface !== undefined)
      .map((surface) => cloneSurface(surface));
  }

  openOverlay(input: UIOverlaySurfaceInput): UISurface {
    const parentId = input.parentKey
      ? this.surfacesByKey.get(input.parentKey)?.id
      : undefined;
    const draft = toOverlayDraft(input, parentId);
    const { surface } = this.ensureSurface(draft, Date.now());
    const nextStack = this.stackKeys.filter((key) => key !== input.key);
    nextStack.push(input.key);
    this.rewriteStack(nextStack);
    return cloneSurface(surface);
  }

  sync(input: UISurfaceSyncInput): UISurfaceDelta {
    const now = Date.now();
    const added: UISurface[] = [];
    const updated: UISurface[] = [];
    const desiredOrder: string[] = [];

    const pageDraft = toPageDraft(input.page);
    const pageResult = this.ensureSurface(pageDraft, now);
    if (pageResult.created) {
      added.push(cloneSurface(pageResult.surface));
    } else if (pageResult.updated) {
      updated.push(cloneSurface(pageResult.surface));
    }
    desiredOrder.push(input.page.key);

    input.overlays.forEach((overlay) => {
      const parentId = overlay.parentKey
        ? this.surfacesByKey.get(overlay.parentKey)?.id
        : undefined;
      const overlayDraft = toOverlayDraft(overlay, parentId);
      const result = this.ensureSurface(overlayDraft, now);
      if (result.created) {
        added.push(cloneSurface(result.surface));
      } else if (result.updated) {
        updated.push(cloneSurface(result.surface));
      }
      desiredOrder.push(overlay.key);
    });

    const desiredKeys = new Set(desiredOrder);
    const removed: UISurface[] = [];
    [...this.surfacesByKey.keys()].forEach((existingKey) => {
      if (desiredKeys.has(existingKey)) {
        return;
      }
      const surface = this.surfacesByKey.get(existingKey);
      if (!surface) {
        return;
      }
      removed.push(cloneSurface(surface));
      this.surfacesByKey.delete(existingKey);
    });

    this.rewriteStack(
      desiredOrder.filter((key) => this.surfacesByKey.has(key)),
    );

    return {
      added,
      changed: added.length > 0 || removed.length > 0 || updated.length > 0,
      removed,
      updated,
    };
  }

  private collectRemovableKeys(surfaceId: string, key: string): Set<string> {
    const removableKeys = new Set<string>([key]);
    let changed = true;

    while (changed) {
      changed = false;
      this.surfacesByKey.forEach((surface, surfaceKey) => {
        if (removableKeys.has(surfaceKey)) {
          return;
        }
        if (surface.parentId !== surfaceId) {
          if (!surface.parentId) {
            return;
          }
          const parent = [...this.surfacesByKey.values()].find(
            (item) => item.id === surface.parentId,
          );
          if (!parent || !removableKeys.has(parent.key)) {
            return;
          }
        }
        removableKeys.add(surfaceKey);
        changed = true;
      });
    }

    return removableKeys;
  }

  private createSurfaceId(kind: UISurface['kind']): string {
    this.sequence += 1;
    return `surface:${kind}:${this.sequence}`;
  }

  private ensureSurface(
    draft: SurfaceDraft,
    now: number,
  ): { created: boolean; surface: UISurface; updated: boolean } {
    const existing = this.surfacesByKey.get(draft.key);
    if (!existing) {
      const created: UISurface = {
        id: this.createSurfaceId(draft.kind),
        key: draft.key,
        kind: draft.kind,
        metadata: draft.metadata,
        openedAt: now,
        parentId: draft.parentId,
        title: draft.title,
        updatedAt: now,
        ...(draft.kind === 'page'
          ? {
              pageKey: draft.pageKey,
              routePath: draft.routePath,
            }
          : {}),
      };
      this.surfacesByKey.set(draft.key, created);
      return {
        created: true,
        surface: created,
        updated: false,
      };
    }

    const changed =
      existing.title !== draft.title ||
      existing.parentId !== draft.parentId ||
      (draft.kind === 'page' &&
        (existing.pageKey !== draft.pageKey ||
          existing.routePath !== draft.routePath)) ||
      !shallowEqualRecord(existing.metadata, draft.metadata);

    if (changed) {
      existing.title = draft.title;
      existing.parentId = draft.parentId;
      existing.metadata = draft.metadata;
      if (draft.kind === 'page') {
        existing.pageKey = draft.pageKey;
        existing.routePath = draft.routePath;
      }
      existing.updatedAt = now;
    }

    return {
      created: false,
      surface: existing,
      updated: changed,
    };
  }

  private findKeyById(surfaceId: string): null | string {
    const match = [...this.surfacesByKey.entries()].find(
      ([, surface]) => surface.id === surfaceId,
    );
    return match?.[0] ?? null;
  }

  private rewriteStack(nextStack: string[]): void {
    this.stackKeys.splice(0, this.stackKeys.length, ...nextStack);
  }
}
