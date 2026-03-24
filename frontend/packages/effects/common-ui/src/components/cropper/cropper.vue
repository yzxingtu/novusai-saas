<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue';

// 定义组件参数 / defineProps
const props = defineProps<{
  /** 裁剪比例 格式如 '1:1', '16:9', '3:4' 等（非必填） */
  aspectRatio?: string;
  /** 容器高度（默认400） */
  height?: number;
  /** 图片地址 */
  img: string;
  /** 容器宽度（默认500） */
  width?: number;
}>();

const CROPPER_CONSTANTS = {
  MIN_WIDTH: 60 as const,
  MIN_HEIGHT: 60 as const,
  DEFAULT_WIDTH: 500 as const,
  DEFAULT_HEIGHT: 400 as const,
  PADDING_RATIO: 0.1 as const,
  MAX_PADDING: 50 as const,
} as const;

type Point = [number, number]; // [clientX, clientY] / pointer coords
type Dimension = [number, number, number, number]; // [top, right, bottom, left] / inset from edges

// 拖拽点类型 / Resize handle kind
type DragAction =
  | 'bottom'
  | 'bottom-left'
  | 'bottom-right'
  | 'left'
  | 'move'
  | 'right'
  | 'top'
  | 'top-left'
  | 'top-right';

// DOM 引用 / Template refs
const containerRef = ref<HTMLDivElement | null>(null);
const bgImageRef = ref<HTMLImageElement | null>(null);
const maskRef = ref<HTMLDivElement | null>(null);
void maskRef.value; // Reserved / 预留未用 ref
const maskViewRef = ref<HTMLDivElement | null>(null);
const cropperRef = ref<HTMLDivElement | null>(null);
const cropperViewRef = ref<HTMLDivElement | null>(null);
void cropperViewRef.value; // Reserved / 预留未用 ref

// 响应式数据 / Reactive state
const isCropperVisible = ref<boolean>(false);
const validAspectRatio = ref<null | number>(null); // 有效比例值（null表示无固定比例）/ parsed w/h ratio or null
const containerWidth = ref<number>(
  props.width ?? CROPPER_CONSTANTS.DEFAULT_WIDTH,
);
const containerHeight = ref<number>(
  props.height ?? CROPPER_CONSTANTS.DEFAULT_HEIGHT,
);

// 裁剪区域尺寸（top, right, bottom, left）/ Crop box insets [top,right,bottom,left]
const currentDimension = ref<Dimension>([50, 50, 50, 50]);
const initDimension = ref<Dimension>([50, 50, 50, 50]);

// 拖拽状态 / Drag interaction state
const dragging = ref<boolean>(false);
const startPoint = ref<Point>([0, 0]);
const startDimension = ref<Dimension>([0, 0, 0, 0]);
const direction = ref<Dimension>([0, 0, 0, 0]);
const moving = ref<boolean>(false);

/**
 * 计算图片的适配尺寸，保证完整显示且不超过最大宽高限制
 */
const calculateImageFitSize = () => {
  if (!bgImageRef.value) return;

  // 获取图片原始尺寸 / Natural image size
  const imgWidth = bgImageRef.value.naturalWidth;
  const imgHeight = bgImageRef.value.naturalHeight;

  if (imgWidth === 0 || imgHeight === 0) return;

  // 计算缩放比例（使用传入的width/height，默认500/400）/ Fit scale from props or defaults
  const widthRatio =
    (props.width ?? CROPPER_CONSTANTS.DEFAULT_WIDTH) / imgWidth;
  const heightRatio =
    (props.height ?? CROPPER_CONSTANTS.DEFAULT_HEIGHT) / imgHeight;
  const scaleRatio = Math.min(widthRatio, heightRatio, 1); // 不放大图片，只缩小 / shrink only, never upscale

  // 计算适配后的容器尺寸 / Fitted container size
  const fitWidth = Math.floor(imgWidth * scaleRatio);
  const fitHeight = Math.floor(imgHeight * scaleRatio);

  containerWidth.value = fitWidth;
  containerHeight.value = fitHeight;

  // 重置裁剪框初始尺寸（基于新的容器尺寸）/ Reset crop padding for new container
  const padding = Math.min(
    CROPPER_CONSTANTS.MAX_PADDING,
    Math.floor(fitWidth * CROPPER_CONSTANTS.PADDING_RATIO),
    Math.floor(fitHeight * CROPPER_CONSTANTS.PADDING_RATIO),
  );

  initDimension.value = [padding, padding, padding, padding];
  currentDimension.value = [padding, padding, padding, padding];
};

/**
 * 验证并解析比例字符串
 * @returns {number|null} 比例值 (width/height)，解析失败返回null
 */
const parseAndValidateAspectRatio = (): null | number => {
  // 如果未传入比例参数，直接返回null / No aspect ratio prop
  if (!props.aspectRatio) {
    return null;
  }

  // 验证比例格式 / Validate "W:H" string
  const ratioRegex = /^[1-9]\d*:[1-9]\d*$/;
  if (!ratioRegex.test(props.aspectRatio)) {
    console.warn('裁剪比例格式错误，应为 "数字:数字" 格式，如 "16:9"');
    return null;
  }

  // 解析比例 / Parse width and height
  const [width, height] = props.aspectRatio.split(':').map(Number);

  // 验证解析结果有效性 / Ensure positive integers
  if (Number.isNaN(width) || Number.isNaN(height) || !width || !height) {
    console.warn('裁剪比例解析失败，宽高必须为正整数');
    return null;
  }

  return width / height;
};

/**
 * 设置裁剪区域尺寸
 * @param {Dimension} dimension - [top, right, bottom, left]
 */
const setDimension = (dimension: Dimension) => {
  currentDimension.value = [...dimension];
  if (maskViewRef.value) {
    maskViewRef.value.style.clipPath = `inset(${dimension[0]}px ${dimension[1]}px ${dimension[2]}px ${dimension[3]}px)`;
  }
};

/**
 * 调整裁剪区域至指定比例
 */
const adjustCropperToAspectRatio = () => {
  if (!cropperRef.value) return;

  // 验证并解析比例 / Parse aspect ratio
  validAspectRatio.value = parseAndValidateAspectRatio();

  // 如果无有效比例，使用初始尺寸，不强制固定比例 / Free ratio: use initial padding box
  if (validAspectRatio.value === null) {
    setDimension(initDimension.value);
    return;
  }

  // 有有效比例，按比例调整裁剪框 / Fixed ratio: fit box in container
  const ratio = validAspectRatio.value;
  const containerWidthVal = containerWidth.value;
  const containerHeightVal = containerHeight.value;

  // 根据比例计算裁剪框尺寸 / Target box size from ratio
  let newHeight: number, newWidth: number;

  // 先按宽度优先计算 / Prefer width-first fit
  newWidth = containerWidthVal;
  newHeight = newWidth / ratio;

  // 如果高度超出容器，按高度优先计算 / Switch to height-first if overflow
  if (newHeight > containerHeightVal) {
    newHeight = containerHeightVal;
    newWidth = newHeight * ratio;
  }

  // 居中显示 / Center crop box
  const leftRight = (containerWidthVal - newWidth) / 2;
  const topBottom = (containerHeightVal - newHeight) / 2;

  const newDimension: Dimension = [topBottom, leftRight, topBottom, leftRight];

  setDimension(newDimension);
};

/**
 * 创建裁剪器
 */
const createCropper = () => {
  // 计算图片适配尺寸 / Fit image in container
  calculateImageFitSize();

  isCropperVisible.value = true;
  adjustCropperToAspectRatio();
};

/**
 * 处理鼠标按下事件
 * @param {MouseEvent} e - 鼠标事件
 * @param {DragAction} action - 操作类型
 */
const handleMouseDown = (e: MouseEvent, action: DragAction) => {
  dragging.value = true;
  startPoint.value = [e.clientX, e.clientY];
  startDimension.value = [...currentDimension.value];
  direction.value = [0, 0, 0, 0];
  moving.value = false;

  // 处理移动 / Pan crop box
  if (action === 'move') {
    direction.value[0] = 1;
    direction.value[2] = -1;
    direction.value[3] = 1;
    direction.value[1] = -1;
    moving.value = true;
    return;
  }

  // 处理拖拽方向 / Map handle to resize direction
  switch (action) {
    case 'bottom': {
      direction.value[2] = -1;
      break;
    }
    case 'bottom-left': {
      direction.value[2] = -1;
      direction.value[3] = 1;
      break;
    }
    case 'bottom-right': {
      direction.value[2] = -1;
      direction.value[1] = -1;
      break;
    }
    case 'left': {
      direction.value[3] = 1;
      break;
    }
    case 'right': {
      direction.value[1] = -1;
      break;
    }
    case 'top': {
      direction.value[0] = 1;
      break;
    }
    case 'top-left': {
      direction.value[0] = 1;
      direction.value[3] = 1;
      break;
    }
    case 'top-right': {
      direction.value[0] = 1;
      direction.value[1] = -1;
      break;
    }
  }
};

/**
 * 处理鼠标移动事件
 * @param {MouseEvent} e - 鼠标事件
 */
const handleMouseMove = (e: MouseEvent) => {
  if (!dragging.value || !cropperRef.value) return;

  const { clientX, clientY } = e;
  const diffX = clientX - startPoint.value[0];
  const diffY = clientY - startPoint.value[1];

  // 处理移动裁剪框 / Drag-move handler
  if (moving.value) {
    handleMoveCropBox(diffX, diffY);
    return;
  }

  // 无有效比例 / Free aspect resize path
  if (validAspectRatio.value === null) {
    handleFreeAspectResize(diffX, diffY);
  } else {
    handleFixedAspectResize(diffX, diffY);
  }
};

const handleMoveCropBox = (diffX: number, diffY: number) => {
  const newDimension = [...startDimension.value] as Dimension;

  // 计算临时偏移后的位置 / Proposed top-left after drag delta
  const tempTop = startDimension.value[0] + diffY;
  const tempLeft = startDimension.value[3] + diffX;

  // 计算裁剪框的固定尺寸 / Fixed inner width/height while moving
  const cropWidth =
    containerWidth.value - startDimension.value[3] - startDimension.value[1];
  const cropHeight =
    containerHeight.value - startDimension.value[0] - startDimension.value[2];

  // 边界限制：确保裁剪框完全在容器内，且尺寸不变 / Clamp move inside container, same size
  // 顶部边界：top >= 0，且 bottom = 容器高度 - top - 裁剪高度 >= 0 / Top edge clamp
  newDimension[0] = Math.max(
    0,
    Math.min(tempTop, containerHeight.value - cropHeight),
  );
  // 底部边界：bottom = 容器高度 - top - 裁剪高度（由top推导，无需额外计算）/ Bottom from top + height
  newDimension[2] = containerHeight.value - newDimension[0] - cropHeight;
  // 左侧边界：left >= 0，且 right = 容器宽度 - left - 裁剪宽度 >= 0 / Left edge clamp
  newDimension[3] = Math.max(
    0,
    Math.min(tempLeft, containerWidth.value - cropWidth),
  );
  // 右侧边界：right = 容器宽度 - left - 裁剪宽度（由left推导，无需额外计算）/ Right from left + width
  newDimension[1] = containerWidth.value - newDimension[3] - cropWidth;

  // 强制保证尺寸不变（兜底）/ Correct rounding drift
  const finalWidth = containerWidth.value - newDimension[3] - newDimension[1];
  const finalHeight = containerHeight.value - newDimension[0] - newDimension[2];

  if (finalWidth !== cropWidth) {
    newDimension[1] = containerWidth.value - newDimension[3] - cropWidth;
  }

  if (finalHeight !== cropHeight) {
    newDimension[2] = containerHeight.value - newDimension[0] - cropHeight;
  }

  // 更新裁剪区域（仅位置变化，尺寸/比例完全不变）/ Apply translated box
  setDimension(newDimension);
};

const handleFreeAspectResize = (diffX: number, diffY: number) => {
  const cropperWidth = containerWidth.value;
  const cropperHeight = containerHeight.value;
  const currentDimensionNew: Dimension = [0, 0, 0, 0];

  // 计算新的尺寸，确保不小于最小值 / Resize with min size guard
  currentDimensionNew[0] = Math.min(
    Math.max(startDimension.value[0] + direction.value[0] * diffY, 0),
    cropperHeight - CROPPER_CONSTANTS.MIN_HEIGHT,
  );

  currentDimensionNew[1] = Math.min(
    Math.max(startDimension.value[1] + direction.value[1] * diffX, 0),
    cropperWidth - CROPPER_CONSTANTS.MIN_WIDTH,
  );

  currentDimensionNew[2] = Math.min(
    Math.max(startDimension.value[2] + direction.value[2] * diffY, 0),
    cropperHeight - CROPPER_CONSTANTS.MIN_HEIGHT,
  );

  currentDimensionNew[3] = Math.min(
    Math.max(startDimension.value[3] + direction.value[3] * diffX, 0),
    cropperWidth - CROPPER_CONSTANTS.MIN_WIDTH,
  );

  // 确保裁剪区域宽度和高度不小于最小值 / Enforce MIN_WIDTH / MIN_HEIGHT
  const newWidth =
    cropperWidth - currentDimensionNew[3] - currentDimensionNew[1];
  const newHeight =
    cropperHeight - currentDimensionNew[0] - currentDimensionNew[2];

  if (newWidth < CROPPER_CONSTANTS.MIN_WIDTH) {
    if (direction.value[3] === 1) {
      currentDimensionNew[3] =
        cropperWidth - currentDimensionNew[1] - CROPPER_CONSTANTS.MIN_WIDTH;
    } else {
      currentDimensionNew[1] =
        cropperWidth - currentDimensionNew[3] - CROPPER_CONSTANTS.MIN_WIDTH;
    }
  }

  if (newHeight < CROPPER_CONSTANTS.MIN_HEIGHT) {
    if (direction.value[0] === 1) {
      currentDimensionNew[0] =
        cropperHeight - currentDimensionNew[2] - CROPPER_CONSTANTS.MIN_HEIGHT;
    } else {
      currentDimensionNew[2] =
        cropperHeight - currentDimensionNew[0] - CROPPER_CONSTANTS.MIN_HEIGHT;
    }
  }

  setDimension(currentDimensionNew);
};

const handleFixedAspectResize = (diffX: number, diffY: number) => {
  if (validAspectRatio.value === null) return;
  const cropperWidth = containerWidth.value;
  const cropperHeight = containerHeight.value;
  // 有有效比例 - 固定比例裁剪 / Fixed-aspect resize
  const ratio = validAspectRatio.value;
  const currentWidth =
    cropperWidth - startDimension.value[3] - startDimension.value[1];
  const currentHeight =
    cropperHeight - startDimension.value[0] - startDimension.value[2];

  let newHeight: number, newWidth: number;
  let widthChange = 0;
  let heightChange = 0;

  // 计算宽度/高度变化量 / Delta from drag direction
  if (direction.value[3] === 1) widthChange = -diffX;
  else if (direction.value[1] === -1) widthChange = diffX;

  if (direction.value[0] === 1) heightChange = -diffY;
  else if (direction.value[2] === -1) heightChange = diffY;

  const isCornerDrag =
    (direction.value[3] === 1 || direction.value[1] === -1) &&
    (direction.value[0] === 1 || direction.value[2] === -1);

  // 计算新尺寸 / New width & height keeping ratio
  if (isCornerDrag) {
    if (Math.abs(widthChange) > Math.abs(heightChange)) {
      newWidth = Math.max(
        CROPPER_CONSTANTS.MIN_WIDTH,
        currentWidth + widthChange,
      );
      newHeight = newWidth / ratio;
    } else {
      newHeight = Math.max(
        CROPPER_CONSTANTS.MIN_HEIGHT,
        currentHeight + heightChange,
      );
      newWidth = newHeight * ratio;
    }
  } else {
    if (direction.value[3] === 1 || direction.value[1] === -1) {
      newWidth = Math.max(
        CROPPER_CONSTANTS.MIN_WIDTH,
        currentWidth + widthChange,
      );
      newHeight = newWidth / ratio;
    } else {
      newHeight = Math.max(
        CROPPER_CONSTANTS.MIN_HEIGHT,
        currentHeight + heightChange,
      );
      newWidth = newHeight * ratio;
    }
  }

  // 限制最大尺寸 / Clamp to container
  const maxWidth = cropperWidth;
  const maxHeight = cropperHeight;

  if (newWidth > maxWidth) {
    newWidth = maxWidth;
    newHeight = newWidth / ratio;
  }

  if (newHeight > maxHeight) {
    newHeight = maxHeight;
    newWidth = newHeight * ratio;
  }

  // 计算新的位置 / Recompute insets after resize
  let newLeft = startDimension.value[3];
  let newTop = startDimension.value[0];
  let newRight = startDimension.value[1];
  let newBottom = startDimension.value[2];

  // 根据拖拽方向调整位置 / Anchor box by handle side
  if (direction.value[3] === 1) {
    newLeft = cropperWidth - newWidth - startDimension.value[1];
  } else if (direction.value[1] === -1) {
    newRight = cropperWidth - newWidth - startDimension.value[3];
  } else if (!isCornerDrag) {
    // 居中调整 / Center on edge drag
    const currentHorizontalCenter = startDimension.value[3] + currentWidth / 2;
    newLeft = Math.max(
      0,
      Math.min(cropperWidth - newWidth, currentHorizontalCenter - newWidth / 2),
    );
    newRight = cropperWidth - newWidth - newLeft;
  }

  if (direction.value[0] === 1) {
    newTop = cropperHeight - newHeight - startDimension.value[2];
  } else if (direction.value[2] === -1) {
    newBottom = cropperHeight - newHeight - startDimension.value[0];
  } else if (!isCornerDrag) {
    // 居中调整 / Center vertically on edge drag
    const currentVerticalCenter = startDimension.value[0] + currentHeight / 2;
    newTop = Math.max(
      0,
      Math.min(
        cropperHeight - newHeight,
        currentVerticalCenter - newHeight / 2,
      ),
    );
    newBottom = cropperHeight - newHeight - newTop;
  }

  // 边界检查 / Non-negative insets
  newLeft = Math.max(0, newLeft);
  newTop = Math.max(0, newTop);
  newRight = Math.max(0, newRight);
  newBottom = Math.max(0, newBottom);

  const newDimension: Dimension = [newTop, newRight, newBottom, newLeft];
  setDimension(newDimension);
};

/**
 * 处理鼠标抬起事件
 */
const handleMouseUp = () => {
  dragging.value = false;
  moving.value = false;
  direction.value = [0, 0, 0, 0];
};

/**
 * 处理图片加载完成
 */
const handleImageLoad = () => {
  createCropper();
};

/**
 * 裁剪图片
 * @param {'image/jpeg' | 'image/png'} format - 输出图片格式
 * @param {number} quality - 压缩质量（0-1）
 * @param {number} targetWidth - 目标宽度（可选，不传则为原始裁剪宽度）
 * @param {number} targetHeight - 目标高度（可选，不传则为原始裁剪高度）
 */
const getCropImage = async (
  format: 'image/jpeg' | 'image/png' = 'image/jpeg',
  quality: number = 0.92,
  targetWidth?: number,
  targetHeight?: number,
): Promise<string | undefined> => {
  if (!props.img || !bgImageRef.value || !containerRef.value) return;

  // 创建临时图片对象获取原始尺寸 / Decode image to natural size
  const tempImg = new Image();
  // Only set crossOrigin for cross-origin URLs that need CORS / 跨域时设置 anonymous
  if (props.img.startsWith('http://') || props.img.startsWith('https://')) {
    try {
      const url = new URL(props.img);
      if (url.origin !== location.origin) {
        tempImg.crossOrigin = 'anonymous';
      }
    } catch {
      // Invalid URL, proceed without crossOrigin / 非法 URL 则不加 crossOrigin
    }
  }

  // 等待临时图片加载完成 / Wait for temp image decode
  await new Promise<void>((resolve, reject) => {
    const timeout = setTimeout(() => {
      tempImg.removeEventListener('load', handleLoad);
      tempImg.removeEventListener('error', handleError);
      reject(new Error('图片加载超时'));
    }, 10_000);
    const handleLoad = () => {
      clearTimeout(timeout);
      tempImg.removeEventListener('load', handleLoad);
      tempImg.removeEventListener('error', handleError);
      resolve();
    };

    const handleError = (err: ErrorEvent) => {
      clearTimeout(timeout);
      tempImg.removeEventListener('load', handleLoad);
      tempImg.removeEventListener('error', handleError);
      reject(new Error(`图片加载失败: ${err.message}`));
    };

    tempImg.addEventListener('load', handleLoad);
    tempImg.addEventListener('error', handleError);

    tempImg.src = props.img;
  });

  const containerRect = containerRef.value.getBoundingClientRect();
  const imgRect = bgImageRef.value.getBoundingClientRect();

  // 1. 计算图片在容器内的渲染参数 / Rendered image geometry in container
  const containerWidth = containerRect.width;
  const containerHeight = containerRect.height;
  const renderedImgWidth = imgRect.width;
  const renderedImgHeight = imgRect.height;
  const imgOffsetX = (containerWidth - renderedImgWidth) / 2;
  const imgOffsetY = (containerHeight - renderedImgHeight) / 2;

  // 2. 计算裁剪框在容器内的实际坐标 / Crop box size in CSS px
  const [cropTop, cropRight, cropBottom, cropLeft] = currentDimension.value;
  const cropBoxWidth = containerWidth - cropLeft - cropRight;
  const cropBoxHeight = containerHeight - cropTop - cropBottom;

  // 3. 将裁剪框坐标转换为图片上的坐标（考虑图片偏移）/ Map to image-local coords
  const cropOnImgX = cropLeft - imgOffsetX;
  const cropOnImgY = cropTop - imgOffsetY;

  // 4. 计算渲染图片到原始图片的缩放比例（关键：保留原始像素）/ CSS px to source px
  const scaleX = tempImg.width / renderedImgWidth;
  const scaleY = tempImg.height / renderedImgHeight;

  // 5. 映射到原始图片的裁剪区域（精确到原始像素）/ Integer rect in bitmap
  const originalCropX = Math.max(0, Math.floor(cropOnImgX * scaleX));
  const originalCropY = Math.max(0, Math.floor(cropOnImgY * scaleY));
  const originalCropWidth = Math.min(
    Math.floor(cropBoxWidth * scaleX),
    tempImg.width - originalCropX,
  );
  const originalCropHeight = Math.min(
    Math.floor(cropBoxHeight * scaleY),
    tempImg.height - originalCropY,
  );

  // 6. 处理高清屏适配（关键：解决Retina屏模糊）/ devicePixelRatio for sharp export
  const dpr = window.devicePixelRatio || 1;

  // 最终画布尺寸（优先使用原始裁剪尺寸，或目标尺寸）/ Output size (optional upscale)
  const finalWidth = targetWidth || originalCropWidth;
  const finalHeight = targetHeight || originalCropHeight;

  // 创建画布（乘以设备像素比，保证高清）/ Canvas backing store × DPR
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  // 画布物理尺寸（适配高清屏）/ Backing store dimensions
  canvas.width = finalWidth * dpr;
  canvas.height = finalHeight * dpr;

  // 画布显示尺寸（视觉尺寸）/ CSS layout size
  canvas.style.width = `${finalWidth}px`;
  canvas.style.height = `${finalHeight}px`;

  // 缩放上下文（适配DPR）/ Scale 2D context for logical px
  ctx.scale(dpr, dpr);

  // 7. 绘制裁剪后的图片（使用原始像素绘制，保证清晰度）/ drawImage from source rect
  ctx.drawImage(
    tempImg,
    originalCropX, // 原始图片裁剪起始X（精确像素）/ src X
    originalCropY, // 原始图片裁剪起始Y（精确像素）/ src Y
    originalCropWidth, // 原始图片裁剪宽度（精确像素）/ src W
    originalCropHeight, // 原始图片裁剪高度（精确像素）/ src H
    0, // 画布绘制起始X / dest X
    0, // 画布绘制起始Y / dest Y
    finalWidth, // 画布绘制宽度（目标尺寸）/ dest W
    finalHeight, // 画布绘制高度（目标尺寸）/ dest H
  );

  // 8. 导出图片（指定质量，平衡清晰度和体积）/ data URL with quality
  return canvas.toDataURL(format, quality);
};

// 监听比例变化，重新调整裁剪框 / Re-fit when aspectRatio changes
watch(() => props.aspectRatio, adjustCropperToAspectRatio);

// 监听width/height变化，重新计算尺寸 / Re-fit when container size props change
watch([() => props.width, () => props.height], () => {
  calculateImageFitSize();
  adjustCropperToAspectRatio();
});

// 组件挂载时注册全局事件 / Global mouse listeners while mounted
onMounted(() => {
  document.addEventListener('mousemove', handleMouseMove);
  document.addEventListener('mouseup', handleMouseUp);

  // 如果图片已经加载完成，手动触发创建裁剪器 / Init if image already decoded
  if (
    bgImageRef.value &&
    bgImageRef.value.complete &&
    bgImageRef.value.naturalWidth > 0
  ) {
    createCropper();
  }
});

// 组件卸载时清理 / Remove global listeners
onUnmounted(() => {
  document.removeEventListener('mousemove', handleMouseMove);
  document.removeEventListener('mouseup', handleMouseUp);
});

defineExpose({ getCropImage });
</script>

<template>
  <div
    :style="{
      width: `${width || CROPPER_CONSTANTS.DEFAULT_WIDTH}px`,
      height: `${height || CROPPER_CONSTANTS.DEFAULT_HEIGHT}px`,
    }"
    class="cropper-action-wrapper"
  >
    <div
      ref="containerRef"
      class="cropper-container"
      :style="{
        width: `${containerWidth}px`,
        height: `${containerHeight}px`,
      }"
    >
      <!-- 原图展示 - 自适应尺寸 -->
      <img
        ref="bgImageRef"
        class="cropper-image"
        :src="img"
        @load="handleImageLoad"
        :style="{
          maxWidth: '100%',
          maxHeight: '100%',
          objectFit: 'contain',
        }"
        alt="裁剪原图"
      />

      <!-- 遮罩层 -->
      <div
        ref="maskRef"
        class="cropper-mask"
        :style="{
          display: isCropperVisible ? 'block' : 'none',
          width: '100%',
          height: '100%',
        }"
      >
        <div
          ref="maskViewRef"
          class="cropper-mask-view"
          :style="{
            backgroundImage: `url(${img})`,
            backgroundSize: 'contain',
            backgroundPosition: 'center',
            backgroundRepeat: 'no-repeat',
            clipPath: `inset(${currentDimension[0]}px ${currentDimension[1]}px ${currentDimension[2]}px ${currentDimension[3]}px)`,
            width: '100%',
            height: '100%',
          }"
        ></div>
      </div>

      <!-- 裁剪框 -->
      <div
        ref="cropperRef"
        class="cropper-box"
        :style="{
          display: isCropperVisible ? 'block' : 'none',
          width: '100%',
          height: '100%',
        }"
      >
        <div
          ref="cropperViewRef"
          class="cropper-view"
          :style="{
            inset: `${currentDimension[0]}px ${currentDimension[1]}px ${currentDimension[2]}px ${currentDimension[3]}px`,
          }"
        >
          <!-- 裁剪框辅助线-->
          <span class="cropper-dashed-h"></span>
          <span class="cropper-dashed-v"></span>

          <!-- 裁剪框拖拽区域 -->
          <span
            class="cropper-move-area"
            @mousedown="handleMouseDown($event, 'move')"
          ></span>

          <!-- 边框线 -->
          <span class="cropper-line-e"></span>
          <span class="cropper-line-n"></span>
          <span class="cropper-line-w"></span>
          <span class="cropper-line-s"></span>

          <!-- 边角拖拽点 -->
          <span
            class="cropper-point cropper-point-ne"
            @mousedown="handleMouseDown($event, 'top-right')"
          >
            <span class="cropper-point-inner"></span>
          </span>
          <span
            class="cropper-point cropper-point-nw"
            @mousedown="handleMouseDown($event, 'top-left')"
          >
            <span class="cropper-point-inner"></span>
          </span>
          <span
            class="cropper-point cropper-point-sw"
            @mousedown="handleMouseDown($event, 'bottom-left')"
          >
            <span class="cropper-point-inner"></span>
          </span>
          <span
            class="cropper-point cropper-point-se"
            @mousedown="handleMouseDown($event, 'bottom-right')"
          >
            <span class="cropper-point-inner"></span>
          </span>

          <!-- 边中点拖拽点 -->
          <span
            class="cropper-point cropper-point-e"
            @mousedown="handleMouseDown($event, 'right')"
          >
            <span class="cropper-point-inner"></span>
          </span>
          <span
            class="cropper-point cropper-point-n"
            @mousedown="handleMouseDown($event, 'top')"
          >
            <span class="cropper-point-inner"></span>
          </span>
          <span
            class="cropper-point cropper-point-w"
            @mousedown="handleMouseDown($event, 'left')"
          >
            <span class="cropper-point-inner"></span>
          </span>
          <span
            class="cropper-point cropper-point-s"
            @mousedown="handleMouseDown($event, 'bottom')"
          >
            <span class="cropper-point-inner"></span>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cropper-action-wrapper {
  @apply box-border flex items-center justify-center;

  background-color: transparent;

  /* 马赛克背景 */
  background-image:
    linear-gradient(45deg, #ccc 25%, transparent 25%),
    linear-gradient(-45deg, #ccc 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #ccc 75%),
    linear-gradient(-45deg, transparent 75%, #ccc 75%);
  background-position:
    0 0,
    0 10px,
    10px -10px,
    -10px 0;
  background-size: 20px 20px;
}

.cropper-container {
  @apply relative;
}

.cropper-image {
  @apply block;
}

/* 遮罩层 */
.cropper-mask {
  @apply absolute left-0 top-0 bg-black/50;
}

.cropper-mask-view {
  @apply absolute left-0 top-0;
}

/* 裁剪框 */
.cropper-box {
  @apply absolute left-0 top-0 z-10;
}

.cropper-view {
  @apply absolute bottom-0 left-0 right-0 top-0 select-none outline outline-1 outline-blue-500;
}

/* 裁剪框辅助线 */
.cropper-dashed-h {
  @apply absolute left-0 top-1/3 block h-1/3 w-full border-b border-t border-dashed border-gray-200/50;
}

.cropper-dashed-v {
  @apply absolute left-1/3 top-0 block h-full w-1/3 border-l border-r border-dashed border-gray-200/50;
}

/* 裁剪框拖拽区域 */
.cropper-move-area {
  @apply absolute left-0 top-0 block h-full w-full cursor-move bg-white/10;
}

/* 边框拖拽线 */
.cropper-line-e,
.cropper-line-n,
.cropper-line-w,
.cropper-line-s {
  @apply absolute block bg-blue-500/10;
}

.cropper-line-e {
  @apply right-[-3px] top-0 h-full w-1;
}

.cropper-line-n {
  @apply left-0 top-[-3px] h-1 w-full;
}

.cropper-line-w {
  @apply left-[-3px] top-0 h-full w-1;
}

.cropper-line-s {
  @apply bottom-[-3px] left-0 h-1 w-full;
}

/* 拖拽点 */
.cropper-point {
  @apply absolute flex h-2 w-2 items-center justify-center bg-blue-500;
}

.cropper-point-inner {
  @apply block h-1.5 w-1.5 bg-white;
}

/* 边角拖拽点位置和光标 */
.cropper-point-ne {
  @apply right-[-5px] top-[-5px] cursor-ne-resize;
}

.cropper-point-nw {
  @apply left-[-5px] top-[-5px] cursor-nw-resize;
}

.cropper-point-sw {
  @apply bottom-[-5px] left-[-5px] cursor-sw-resize;
}

.cropper-point-se {
  @apply bottom-[-5px] right-[-5px] cursor-se-resize;
}

/* 边中点拖拽点位置和光标 */
.cropper-point-e {
  @apply right-[-5px] top-1/2 -mt-1 cursor-e-resize;
}

.cropper-point-n {
  @apply left-1/2 top-[-5px] -ml-1 cursor-n-resize;
}

.cropper-point-w {
  @apply left-[-5px] top-1/2 -mt-1 cursor-w-resize;
}

.cropper-point-s {
  @apply bottom-[-5px] left-1/2 -ml-1 cursor-s-resize;
}
</style>
