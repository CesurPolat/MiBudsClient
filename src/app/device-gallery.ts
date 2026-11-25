import { NgOptimizedImage } from '@angular/common';
import { afterNextRender, ChangeDetectionStrategy, Component, DestroyRef, ElementRef, inject, viewChild } from '@angular/core';
import { devices } from './devices';

@Component({
  selector: 'app-device-gallery',
  imports: [NgOptimizedImage],
  templateUrl: './device-gallery.html',
  styleUrl: './device-gallery.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class DeviceGallery {
  protected readonly devices = devices;
  private readonly rail = viewChild.required<ElementRef<HTMLElement>>('rail');
  private readonly lifetime = inject(DestroyRef);
  private reduced?: MediaQueryList;
  private visible = false;
  private touching = false;
  private timer?: number;

  constructor() {
    afterNextRender(() => {
      this.reduced = matchMedia('(prefers-reduced-motion: reduce)');
      const rail = this.rail().nativeElement;
      const observer = new IntersectionObserver(([entry]) => {
        this.visible = entry.intersectionRatio >= .25;
        this.schedule();
      }, { threshold: [0, .25] });
      observer.observe(rail);
      const events = new AbortController();
      const options = { signal: events.signal };
      const sync = () => this.schedule();
      document.addEventListener('visibilitychange', sync, options);
      this.reduced.addEventListener('change', sync, options);
      rail.addEventListener('pointerdown', () => {
        this.touching = true;
        this.schedule();
      }, options);
      const release = () => {
        if (!this.touching) return;
        this.touching = false;
        this.schedule(8000);
      };
      window.addEventListener('pointerup', release, options);
      window.addEventListener('pointercancel', release, options);
      window.addEventListener('blur', release, options);
      this.lifetime.onDestroy(() => {
        clearTimeout(this.timer);
        observer.disconnect();
        events.abort();
      });
    });
  }

  protected restAfterInput() { this.schedule(8000); }

  protected move(direction: number) {
    this.advance(direction);
    this.restAfterInput();
  }

  private schedule(delay = 4000) {
    clearTimeout(this.timer);
    if (!this.visible || this.touching || this.reduced?.matches || document.hidden) return;
    this.timer = window.setTimeout(() => {
      this.advance(1);
      this.schedule();
    }, delay);
  }

  private advance(direction: number) {
    const rail = this.rail().nativeElement;
    const stops = Array.from(rail.children, item => (item as HTMLElement).offsetLeft);
    const last = rail.scrollWidth - rail.clientWidth;
    const wrapping = direction > 0 ? rail.scrollLeft >= last - 2 : rail.scrollLeft <= 2;
    const next = direction > 0
      ? (wrapping ? 0 : stops.find(x => x > rail.scrollLeft + 2) ?? last)
      : (wrapping ? last : stops.reverse().find(x => x < rail.scrollLeft - 2) ?? 0);
    rail.scrollTo({
      left: Math.min(next, last),
      behavior: wrapping || this.reduced?.matches ? 'instant' : 'smooth'
    });
  }
}