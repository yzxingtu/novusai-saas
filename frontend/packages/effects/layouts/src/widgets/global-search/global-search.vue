<script setup lang="ts">
import type { MenuRecordRaw } from '@vben/types';

import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue';

import { Search } from '@vben/icons';
import { $t } from '@vben/locales';
import { isWindowsOs } from '@vben/utils';

import SearchPanel from './search-panel.vue';

defineOptions({
  name: 'GlobalSearch',
});

const props = withDefaults(
  defineProps<{ enableShortcutKey?: boolean; menus?: MenuRecordRaw[] }>(),
  {
    enableShortcutKey: true,
    menus: () => [],
  },
);

const keyword = ref('');
const searchInputRef = ref<HTMLInputElement>();
const open = ref(false);

function show() {
  open.value = true;
  keyword.value = '';
}

function hide() {
  open.value = false;
  keyword.value = '';
}

function toggleOpen() {
  open.value ? hide() : show();
}

function handleClose() {
  hide();
}

function handleMaskClick() {
  hide();
}

watch(open, async (isOpen) => {
  if (isOpen) {
    await nextTick();
    searchInputRef.value?.focus();
  }
});

function handleKeydown(event: KeyboardEvent) {
  if (
    event.key?.toLowerCase() === 'k' &&
    (event.metaKey || event.ctrlKey)
  ) {
    event.preventDefault();
    event.stopPropagation();
    if (props.enableShortcutKey) {
      toggleOpen();
    }
    return;
  }
  if (event.key === 'Escape' && open.value) {
    event.preventDefault();
    hide();
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown, { capture: true });
});

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown, { capture: true });
});
</script>

<template>
  <div>
    <Teleport to="body">
      <Transition name="search-bar-mask">
        <div
          v-if="open"
          class="fixed inset-0 z-[1100] bg-black/50"
          @click="handleMaskClick"
        ></div>
      </Transition>

      <Transition name="search-bar">
        <div
          v-if="open"
          class="fixed left-1/2 top-[15%] z-[1101] w-full max-w-[580px] -translate-x-1/2"
        >
          <div
            class="overflow-hidden rounded-2xl border border-border/60 bg-card shadow-2xl"
            @click.stop
          >
            <!-- Input Area -->
            <div
              class="flex items-center gap-3 border-b border-border/40 px-4 py-3"
            >
              <Search class="size-5 shrink-0 text-primary" />
              <input
                ref="searchInputRef"
                v-model="keyword"
                :placeholder="$t('ui.widgets.search.searchNavigate')"
                class="min-w-0 flex-1 border-none bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground/60"
                type="text"
              />
              <kbd
                v-if="enableShortcutKey"
                class="hidden rounded border border-border/60 bg-muted/60 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground sm:inline-block"
              >
                {{ isWindowsOs() ? 'Ctrl' : '⌘' }} K
              </kbd>
            </div>

            <!-- Search Results -->
            <SearchPanel
              :keyword="keyword"
              :menus="menus"
              @close="handleClose"
            />
          </div>
        </div>
      </Transition>
    </Teleport>
    <div
      class="md:bg-accent group flex h-8 cursor-pointer items-center gap-3 rounded-2xl border-none bg-none px-2 py-0.5 outline-none"
      @click="toggleOpen()"
    >
      <Search
        class="text-muted-foreground group-hover:text-foreground size-4 group-hover:opacity-100"
      />
      <span
        class="text-muted-foreground group-hover:text-foreground hidden text-xs duration-300 md:block"
      >
        {{ $t('ui.widgets.search.title') }}
      </span>
      <span
        v-if="enableShortcutKey"
        class="bg-background border-foreground/60 text-muted-foreground group-hover:text-foreground relative hidden rounded-sm rounded-r-xl px-1.5 py-1 text-xs leading-none group-hover:opacity-100 md:block"
      >
        {{ isWindowsOs() ? 'Ctrl' : '⌘' }}
        <kbd>K</kbd>
      </span>
      <span v-else></span>
    </div>
  </div>
</template>

<style scoped>
/* Mask transition */
.search-bar-mask-enter-active {
  transition: opacity 0.2s ease-out;
}

.search-bar-mask-leave-active {
  transition: opacity 0.15s ease-in;
}

.search-bar-mask-enter-from,
.search-bar-mask-leave-to {
  opacity: 0;
}

/* Bar transition */
.search-bar-enter-active {
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.search-bar-leave-active {
  transition: all 0.15s ease-in;
}

.search-bar-enter-from {
  opacity: 0;
  transform: translate(-50%, -20px) scale(0.96);
}

.search-bar-leave-to {
  opacity: 0;
  transform: translate(-50%, -10px) scale(0.98);
}
</style>
