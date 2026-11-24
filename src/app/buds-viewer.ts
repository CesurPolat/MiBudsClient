import { NgOptimizedImage } from '@angular/common';
import { afterNextRender, ChangeDetectionStrategy, Component, DestroyRef, ElementRef, inject, signal, viewChild } from '@angular/core';
import { gsap } from 'gsap';
import { createRenderer, presets } from './buds-renderer';

@Component({
  selector: 'app-buds-viewer',
  imports: [NgOptimizedImage],
  templateUrl: './buds-viewer.html',
  styleUrl: './buds-viewer.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class BudsViewer {
  private readonly canvas = viewChild.required<ElementRef<HTMLCanvasElement>>('surface');
  private readonly lifetime = inject(DestroyRef);
  private readonly pose = { ...presets[0] };
  private renderer?: Awaited<ReturnType<typeof createRenderer>>;
  private drag?: { id: number; x: number; yaw: number };
  protected readonly ready = signal(false);
  protected readonly active = signal(0);
  protected readonly labels = ['Açık kutu', 'Kapalı kutu', 'Kulaklık'];
  protected readonly posters = ['media/acik.webp', 'media/kapali.webp', 'media/kulaklik.webp'];
  protected readonly captions = ['Şarj kutusu', 'Menteşeli kapak', 'Silikon uç'];
  constructor() {
    afterNextRender(async () => {
      const canvas = this.canvas().nativeElement;
      const abort = new AbortController();
      const resize = new ResizeObserver(() => this.paint());
      let disposed = false;
      this.lifetime.onDestroy(() => {
        disposed = true;
        abort.abort();
        resize.disconnect();
        gsap.killTweensOf(this.pose);
        this.renderer?.destroy();
      });
      canvas.addEventListener('webglcontextlost', () => { this.ready.set(false); }, {signal: abort.signal});
      try {
        const renderer = await createRenderer(canvas, abort.signal);
        if (disposed) { renderer.destroy(); return; }
        this.renderer = renderer;
        resize.observe(canvas);
        this.paint();
        this.ready.set(true);
      } catch { /* Each view also has a still render for devices without WebGL. */ }
    });
  }
  private paint() { this.renderer?.draw(this.pose); }
  select(index: number) {
    this.active.set(index);
    gsap.killTweensOf(this.pose);
    if (!this.ready() || matchMedia('(prefers-reduced-motion: reduce)').matches) {
      Object.assign(this.pose,presets[index]);
      this.paint();
      return;
    }
    gsap.to(this.pose,{...presets[index], duration: .85, ease: 'power2.inOut', onUpdate: () => this.paint()});
  }
  start(event: PointerEvent) {
    if (!this.ready() || !event.isPrimary || event.button !== 0) return;
    gsap.killTweensOf(this.pose);
    this.drag = { id: event.pointerId, x: event.clientX, yaw: this.pose.yaw };
    this.canvas().nativeElement.setPointerCapture(event.pointerId);
  }
  move(event: PointerEvent) {
    if (this.drag?.id !== event.pointerId) return;
    this.pose.yaw = this.drag.yaw - (event.clientX-this.drag.x)*.009;
    this.paint();
  }
  end() { this.drag = undefined; }
  turn(event: KeyboardEvent) {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    gsap.killTweensOf(this.pose);
    this.pose.yaw += event.key === 'ArrowRight' ? .14 : -.14;
    this.paint();
  }
}
