import { NgOptimizedImage } from '@angular/common';
import { afterNextRender, ChangeDetectionStrategy, Component, DestroyRef, ElementRef, inject, signal, viewChild } from '@angular/core';
import { gsap } from 'gsap';
import { createRenderer, presets } from './buds-renderer';

@Component({
  selector: 'app-buds-viewer', imports: [NgOptimizedImage],
  templateUrl: './buds-viewer.html', styleUrl: './buds-viewer.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class BudsViewer {
  private readonly canvas = viewChild.required<ElementRef<HTMLCanvasElement>>('surface');
  private readonly lifetime = inject(DestroyRef);
  private readonly pose = { ...presets[0] };
  private readonly sequence = gsap.timeline({ paused: true })
    .to(this.pose, { ...presets[1], duration: .48, ease: 'sine.inOut' })
    .to(this.pose, { ...presets[2], duration: .52, ease: 'sine.inOut' });
  private renderer?: Awaited<ReturnType<typeof createRenderer>>;
  protected readonly ready = signal(false);
  protected readonly active = signal(0);
  protected readonly views = [
    { poster: 'media/kapali.webp', alt: 'Closed charging case on a dark stone plinth' },
    { poster: 'media/acik.webp', alt: 'Open charging case with both earbuds seated' },
    { poster: 'media/lifted.webp', alt: 'The left and right earbuds lifted out of the case' }
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
    this.renderer?.draw(this.pose);
  }
}