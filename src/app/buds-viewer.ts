import { NgOptimizedImage } from '@angular/common';
import { afterNextRender, ChangeDetectionStrategy, Component, DestroyRef, ElementRef, inject, output, signal, viewChild } from '@angular/core';
import { gsap } from 'gsap';
import { createRenderer, presets } from './buds-renderer';

@Component({
  selector: 'app-buds-viewer', imports: [NgOptimizedImage],
  templateUrl: './buds-viewer.html', styleUrl: './buds-viewer.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class BudsViewer {
  readonly viewRequested = output<number>();
  private readonly canvas = viewChild.required<ElementRef<HTMLCanvasElement>>('surface');
  private readonly lifetime = inject(DestroyRef);
  private readonly pose = { ...presets[0] };
  private readonly sequence = gsap.timeline({ paused: true })
    .to(this.pose, { ...presets[1], duration: .48, ease: 'sine.inOut' })
    .to(this.pose, { ...presets[2], duration: .52, ease: 'sine.inOut' });
  private renderer?: Awaited<ReturnType<typeof createRenderer>>;
  private drag?: { id: number; x: number; offset: number };
  private orbitOffset = 0;
  protected readonly ready = signal(false);
  protected readonly active = signal(0);
  protected readonly views = [
    { label: 'Case', at: 0, poster: 'media/kapali.webp', alt: 'Closed charging case on a dark stone plinth' },
    { label: 'Open', at: .48, poster: 'media/acik.webp', alt: 'Open charging case with both earbuds seated' },
    { label: 'Earbuds', at: 1, poster: 'media/lifted.webp', alt: 'The left and right earbuds lifted out of the case' }
  ];

  constructor() {
    this.lifetime.onDestroy(() => { this.sequence.kill(); });
    afterNextRender(async () => {
      const canvas = this.canvas().nativeElement;
      const abort = new AbortController();
      const resize = new ResizeObserver(() => this.paint());
      this.lifetime.onDestroy(() => {
        abort.abort(); resize.disconnect(); this.renderer?.destroy();
      });
      canvas.addEventListener('webglcontextlost', () => { this.ready.set(false); }, {signal: abort.signal});
      try {
        this.renderer = await createRenderer(canvas, abort.signal);
        if (abort.signal.aborted) { this.renderer.destroy(); return; }
        resize.observe(canvas);
        this.paint();
        this.ready.set(true);
      } catch { /* The three photographed model poses remain available. */ }
    });
  }

  seek(progress: number) {
    this.sequence.progress(progress);
    this.active.set(progress < .24 ? 0 : progress < .74 ? 1 : 2);
    this.paint();
  }
  private paint() {
    this.renderer?.draw({ ...this.pose, yaw: this.pose.yaw + this.orbitOffset });
  }
  start(event: PointerEvent) {
    if (!this.ready() || !event.isPrimary || event.button !== 0) return;
    this.drag = { id: event.pointerId, x: event.clientX, offset: this.orbitOffset };
    this.canvas().nativeElement.setPointerCapture(event.pointerId);
  }
  move(event: PointerEvent) {
    if (this.drag?.id !== event.pointerId) return;
    this.orbitOffset = this.drag.offset - (event.clientX-this.drag.x)*.009;
    this.paint();
  }
  end() { this.drag = undefined; }
  turn(event: KeyboardEvent) {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    this.orbitOffset += event.key === 'ArrowRight' ? .14 : -.14;
    this.paint();
  }
}