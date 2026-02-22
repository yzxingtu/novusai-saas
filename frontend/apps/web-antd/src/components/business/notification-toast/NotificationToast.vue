<script lang="ts" setup>
/**
 * 通知 Toast 弹窗容器
 *
 * 在页面右下角显示实时推送的通知弹窗。
 * 支持多条堆叠、自动消失、点击跳转、不同优先级样式。
 */
import { useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import { useNotificationToast } from '#/composables/use-notification-toast';

const router = useRouter();
const { toasts, removeToast } = useNotificationToast();

function getCategoryIcon(category: string): string {
  switch (category) {
    case 'system': return 'lucide:monitor';
    case 'ai': return 'lucide:sparkles';
    case 'task': return 'lucide:list-checks';
    case 'biz': return 'lucide:briefcase';
    case 'audit': return 'lucide:shield';
    default: return 'lucide:bell';
  }
}

function getPriorityClass(priority: string): string {
  switch (priority) {
    case 'urgent': return 'border-destructive/60 bg-destructive/5';
    case 'high': return 'border-warning/60 bg-warning/5';
    default: return 'border-border bg-background';
  }
}

function handleClick(toast: { id: number; link?: string | null }) {
  if (toast.link) {
    if (toast.link.startsWith('http://') || toast.link.startsWith('https://')) {
      window.open(toast.link, '_blank');
    } else {
      router.push(toast.link);
    }
  }
  removeToast(toast.id);
}
</script>

<template>
  <Teleport to="body">
    <div role="status" aria-live="polite" class="fixed right-4 bottom-4 z-[9999] flex flex-col-reverse gap-3">
      <TransitionGroup
        name="toast"
        tag="div"
        class="flex flex-col-reverse gap-3"
      >
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="w-[360px] max-w-[calc(100vw-2rem)] cursor-pointer rounded-xl border p-4 shadow-lg backdrop-blur-sm transition-all hover:shadow-xl"
          :class="[
            getPriorityClass(toast.priority),
            toast.priority === 'urgent' ? 'animate-shake' : '',
          ]"
          @click="handleClick(toast)"
        >
          <div class="flex items-start gap-3">
            <!-- 分类图标 -->
            <div
              class="flex size-9 flex-shrink-0 items-center justify-center rounded-lg"
              :class="{
                'bg-primary/10 text-primary': toast.priority === 'normal' || toast.priority === 'low',
                'bg-warning/10 text-warning': toast.priority === 'high',
                'bg-destructive/10 text-destructive': toast.priority === 'urgent',
              }"
            >
              <IconifyIcon :icon="getCategoryIcon(toast.category)" class="size-5" />
            </div>

            <!-- 内容 -->
            <div class="min-w-0 flex-1">
              <div class="text-foreground text-sm font-medium leading-tight">
                {{ toast.title }}
              </div>
              <div
                v-if="toast.body"
                class="text-muted-foreground mt-1 line-clamp-2 text-xs leading-relaxed"
              >
                {{ toast.body }}
              </div>
            </div>

            <!-- 关闭按钮 -->
            <button
              :aria-label="$t('common.close')"
              class="text-muted-foreground hover:text-foreground flex-shrink-0 transition-colors"
              @click.stop="removeToast(toast.id)"
            >
              <IconifyIcon icon="lucide:x" class="size-4" />
            </button>
          </div>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-enter-active {
  transition: all 0.3s ease-out;
}

.toast-leave-active {
  transition: all 0.2s ease-in;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(100px);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(100px);
}

.toast-move {
  transition: transform 0.3s ease;
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  10%, 30%, 50%, 70%, 90% { transform: translateX(-2px); }
  20%, 40%, 60%, 80% { transform: translateX(2px); }
}

.animate-shake {
  animation: shake 0.5s ease-in-out;
}
</style>
