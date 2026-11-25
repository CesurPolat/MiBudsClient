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
  private readonly section = viewChild.required<ElementRef<HTMLElement>>('gallery');
  private readonly lifetime = inject(DestroyRef);
  private manual = false;

  constructor() {
    afterNextRender(() => {
      const section = this.section().nativeElement;
      const reduced = matchMedia('(prefers-reduced-motion: reduce)');
      let timer: number | undefined;
      let visible = false;
      const schedule = () => {
        clearInterval(timer);
        if (!visible || document.hidden || reduced.matches || this.manual) return;
        timer = window.setInterval(() => {
          if (!this.manual && !section.matches(':hover, :focus-within')) this.advance(1);
        }, 4200);
      };
      const observer = new IntersectionObserver(([entry]) => {
        visible = entry.isIntersecting;
        schedule();
      }, { threshold: .25 });
      observer.observe(section);
      document.addEventListener('visibilitychange', schedule);
      reduced.addEventListener('change', schedule);
      this.lifetime.onDestroy(() => {
        clearInterval(timer);
        observer.disconnect();
        document.removeEventListener('visibilitychange', schedule);
        reduced.removeEventListener('change', schedule);
      });
    });
  }

  stopAutoplay() { this.manual = true; }

  move(direction: number) {
    this.stopAutoplay();
    this.advance(direction);
  }

  private advance(direction: number) {
    const rail = this.rail().nativeElement;
    const stops = Array.from(rail.children, item => (item as HTMLElement).offsetLeft);
    const last = rail.scrollWidth - rail.clientWidth;
    const next = direction > 0
      ? (rail.scrollLeft >= last - 2 ? 0 : stops.find(x => x > rail.scrollLeft + 2) ?? last)
      : (rail.scrollLeft <= 2 ? last : stops.reverse().find(x => x < rail.scrollLeft - 2) ?? 0);
    rail.scrollTo({
      left: Math.min(next, last),
      behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'
    });
  }
}