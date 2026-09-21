<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { isFrozen, rectFromPoints, type BatchPage, type BatchRegion, type Rect } from '@/lib/batchDrafts';

const props = defineProps<{ page: BatchPage; source: string; selected: string; disabled: boolean }>();
const emit = defineEmits<{ select: [id: string]; create: [rect: Rect]; change: [id: string, rect: Rect] }>();
type CanvasMode = 'draw' | 'pan';
const MODE_STORAGE_KEY = 'mikanquiz-batch-crop-mode';
const viewport = ref<HTMLDivElement>();
const svg = ref<SVGSVGElement>();
const scale = ref(1);
function readMode(): CanvasMode {
  try {
    const saved = localStorage.getItem(MODE_STORAGE_KEY);
    return saved === 'draw' || saved === 'pan' ? saved : 'pan';
  } catch {
    return 'pan';
  }
}
const mode = ref<CanvasMode>(readMode());
const space = ref(false);
const drawing = ref<Rect>();
const moving = ref<{ id: string; rect: Rect }>();
let drag: { kind: 'draw' | 'move' | 'resize' | 'pan'; start: { x: number; y: number }; region?: BatchRegion; corner?: string; left: number; top: number } | undefined;
const corners = ['nw', 'ne', 'sw', 'se'];
const selectedRegion = computed(() => props.page.regions.find((region) => region.id === props.selected));
watch(mode, (value) => {
  try { localStorage.setItem(MODE_STORAGE_KEY, value); } catch { /* local storage may be unavailable */ }
});
function displayed(region: BatchRegion): Rect { return moving.value?.id === region.id ? moving.value.rect : region; }
function point(event: PointerEvent) {
  const box = svg.value!.getBoundingClientRect();
  return { x: (event.clientX - box.left) / scale.value, y: (event.clientY - box.top) / scale.value };
}
function start(event: PointerEvent) {
  if (props.disabled || event.button !== 0) return;
  svg.value?.focus({ preventScroll: true });
  const target = event.target as SVGElement;
  const id = target.dataset.region;
  const region = props.page.regions.find((item) => item.id === id);
  if (region) emit('select', region.id);
  // Region editing should remain available after drawing switches back to pan.
  // Holding Space is the explicit way to pan across an existing region.
  const editRegion = !space.value && !!region && !isFrozen(region);
  const pan = space.value || (mode.value === 'pan' && !editRegion);
  if (!pan && region && isFrozen(region)) return;
  svg.value!.setPointerCapture(event.pointerId);
  drag = { kind: pan ? 'pan' : target.dataset.corner ? 'resize' : region ? 'move' : 'draw',
    start: pan ? { x: event.clientX, y: event.clientY } : point(event),
    region: region ? { ...region } : undefined, corner: target.dataset.corner,
    left: viewport.value!.scrollLeft, top: viewport.value!.scrollTop };
  event.preventDefault();
}
function move(event: PointerEvent) {
  if (!drag) return;
  if (drag.kind === 'pan') {
    viewport.value!.scrollLeft = drag.left - (event.clientX - drag.start.x);
    viewport.value!.scrollTop = drag.top - (event.clientY - drag.start.y);
    return;
  }
  const end = point(event);
  if (drag.kind === 'draw') drawing.value = rectFromPoints(drag.start, end, props.page.width, props.page.height);
  else if (drag.region) {
    const original = drag.region;
    let rect: Rect;
    if (drag.kind === 'move') {
      rect = { x: Math.round(Math.max(0, Math.min(props.page.width - original.width, original.x + end.x - drag.start.x))),
        y: Math.round(Math.max(0, Math.min(props.page.height - original.height, original.y + end.y - drag.start.y))),
        width: original.width, height: original.height };
    } else {
      const anchor = { x: original.x + (drag.corner!.includes('w') ? original.width : 0),
        y: original.y + (drag.corner!.includes('n') ? original.height : 0) };
      rect = rectFromPoints(anchor, end, props.page.width, props.page.height);
    }
    moving.value = { id: original.id, rect };
  }
}
function finish() {
  if (drawing.value && drawing.value.width >= 4 && drawing.value.height >= 4) {
    mode.value = 'pan';
    emit('create', drawing.value);
  }
  if (moving.value && moving.value.rect.width >= 1 && moving.value.rect.height >= 1) emit('change', moving.value.id, moving.value.rect);
  cancel();
}
function cancel() { drag = undefined; drawing.value = undefined; moving.value = undefined; }
function fit(kind: 'width' | 'page' = 'width') {
  if (!viewport.value) return;
  scale.value = Math.min(1, (viewport.value.clientWidth - 32) / props.page.width,
    kind === 'page' ? (viewport.value.clientHeight - 32) / props.page.height : Infinity);
}
function zoom(factor: number) { scale.value = Math.max(0.05, Math.min(4, scale.value * factor)); }
function keydown(event: KeyboardEvent) {
  if (event.key === 'Escape') { cancel(); return; }
  if (event.code === 'Space') { event.preventDefault(); space.value = true; return; }
  const region = selectedRegion.value;
  if (!region || isFrozen(region) || props.disabled) return;
  const delta = ({ ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] } as Record<string, number[]>)[event.key];
  if (!delta) return;
  event.preventDefault();
  const step = event.shiftKey ? 10 : 1;
  emit('change', region.id, { x: Math.max(0, Math.min(props.page.width - region.width, region.x + delta[0] * step)),
    y: Math.max(0, Math.min(props.page.height - region.height, region.y + delta[1] * step)), width: region.width, height: region.height });
}
function releaseSpace() { space.value = false; }
function focusCanvas() { svg.value?.focus({ preventScroll: true }); }
defineExpose({ focusCanvas });
watch(() => props.page.id, async () => { cancel(); await nextTick(); fit(); viewport.value?.scrollTo(0, 0); });
onMounted(() => { fit(); window.addEventListener('keyup', releaseSpace); window.addEventListener('blur', releaseSpace); });
onBeforeUnmount(() => { window.removeEventListener('keyup', releaseSpace); window.removeEventListener('blur', releaseSpace); });
</script>

<template>
  <section class="crop-canvas">
    <div class="canvas-tools" aria-label="画布工具">
      <div class="toolbar-leading"><slot name="toolbar-leading" /></div>
      <div class="toolbar-controls">
        <button :aria-pressed="mode === 'draw'" @click="mode = 'draw'">框选</button><button :aria-pressed="mode === 'pan'" @click="mode = 'pan'">移动</button>
        <span class="tool-divider"></span><button aria-label="缩小" @click="zoom(0.8)">−</button><button @click="scale = 1">{{ Math.round(scale * 100) }}%</button><button aria-label="放大" @click="zoom(1.25)">＋</button>
        <button @click="fit('width')">适合宽度</button><button @click="fit('page')">整页</button>
      </div><div class="toolbar-trailing"><slot name="toolbar-trailing" /></div>
    </div>
    <div ref="viewport" class="canvas-viewport" :class="{ panning: mode === 'pan' || space }">
      <svg ref="svg" tabindex="0" role="group" aria-label="漫画框选画布，拖动框选；选中区域后方向键微调，空格拖动，Esc 取消"
        :width="page.width * scale" :height="page.height * scale" :viewBox="`0 0 ${page.width} ${page.height}`"
        @pointerdown="start" @pointermove="move" @pointerup="finish" @pointercancel="cancel" @lostpointercapture="cancel" @keydown="keydown" @blur="releaseSpace">
        <image :href="source" :width="page.width" :height="page.height" />
        <g v-for="(region, index) in page.regions" :key="region.id" :class="['region', { selected: selected === region.id, complete: region.status === 'ready' || region.status === 'saved' }]">
          <rect v-bind="displayed(region)" :data-region="region.id" vector-effect="non-scaling-stroke" />
          <text :x="displayed(region).x + 4 / scale" :y="displayed(region).y + 19 / scale" :font-size="15 / scale" pointer-events="none">{{ index + 1 }}{{ region.status === 'saved' ? ' 已入库' : region.status === 'ready' ? ' ✓' : '' }}</text>
          <template v-if="selected === region.id && !isFrozen(region) && !disabled">
            <rect v-for="corner in corners" :key="corner" class="handle" :data-region="region.id" :data-corner="corner"
              :x="displayed(region).x + (corner.includes('e') ? displayed(region).width : 0) - 5 / scale"
              :y="displayed(region).y + (corner.includes('s') ? displayed(region).height : 0) - 5 / scale"
              :width="10 / scale" :height="10 / scale" vector-effect="non-scaling-stroke" />
          </template>
        </g>
        <rect v-if="drawing" v-bind="drawing" class="new-region" vector-effect="non-scaling-stroke" />
      </svg>
    </div>
  </section>
</template>

<style scoped>
.crop-canvas{display:flex;flex:1;min-height:0;flex-direction:column}.canvas-tools{display:flex;align-items:center;gap:5px;flex-wrap:wrap;padding:10px 14px;border-bottom:1px solid var(--color-border);background:var(--color-surface)}button{min-height:34px;border:1px solid var(--color-border);border-radius:7px;background:var(--color-surface);color:var(--color-text);padding:4px 10px;font:inherit;font-size:12px;cursor:pointer}button[aria-pressed=true]{background:var(--color-surface-accent);border-color:var(--color-action);color:var(--color-action)}.tool-divider{width:8px}.canvas-viewport{flex:1;min-height:150px;overflow:auto;padding:16px;background:#e8e7e4;overscroll-behavior:contain}.canvas-viewport svg{display:block;max-width:none;touch-action:none;cursor:crosshair;box-shadow:0 2px 12px #0002}.panning svg{cursor:grab}.region rect{fill:rgba(169,79,31,.06);stroke:var(--color-action);stroke-width:1.5;cursor:move}.region.complete rect{stroke:var(--color-success,#39864a)}.region.selected rect{stroke-width:3;fill:rgba(169,79,31,.12)}.region text{fill:#fff;stroke:#713211;stroke-width:3px;paint-order:stroke;stroke-linejoin:round}.region .handle{fill:#fff;stroke:var(--color-action);cursor:nwse-resize}.new-region{fill:rgba(169,79,31,.12);stroke:var(--color-action);stroke-width:2;stroke-dasharray:6 3;pointer-events:none}.canvas-hint{margin:0;padding:7px 14px;background:var(--color-surface);color:var(--color-text-muted);font-size:11px}button:focus-visible,svg:focus-visible{outline:2px solid var(--color-action);outline-offset:2px}
.canvas-viewport{min-height:clamp(500px,calc(100dvh - 250px),1000px)}
.canvas-tools{gap:4px;padding:6px 10px}.canvas-tools button{min-height:30px;padding:3px 9px}.tool-divider{width:5px}
.canvas-tools{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr)}.toolbar-leading{grid-column:1;min-width:0}.toolbar-controls{display:flex;align-items:center;justify-content:center;gap:4px;flex-wrap:wrap}.toolbar-trailing{grid-column:3;justify-self:end}
@media(max-width:760px){.canvas-viewport{min-height:clamp(280px,calc(100dvh - 160px),640px)}}
</style>
