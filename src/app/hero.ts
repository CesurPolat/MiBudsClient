import { afterNextRender, ChangeDetectionStrategy, Component, DestroyRef, ElementRef, inject, signal, viewChild } from '@angular/core';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { BudsViewer } from './buds-viewer';
import { SoundWaves } from './sound-waves';

@Component({
  selector: 'app-hero', imports: [BudsViewer, SoundWaves],
  templateUrl: './hero.html', styleUrl: './hero.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class Hero {
  private readonly stage = viewChild.required<ElementRef<HTMLElement>>('stage');
  private readonly viewer = viewChild.required(BudsViewer);
  private readonly lifetime = inject(DestroyRef);
  private scroll?: ScrollTrigger;
  protected readonly motionEnabled = signal(false);
  protected readonly paused = signal(false);

  constructor() {
    afterNextRender(() => {
      gsap.registerPlugin(ScrollTrigger);
      const media = gsap.matchMedia();
      media.add('(prefers-reduced-motion: no-preference)', () => {
        this.motionEnabled.set(true);
        const stage = this.stage().nativeElement;
        const playhead = { progress: 0 };
        const tween = gsap.to(playhead, {
          progress: 1, ease: 'none',
          onUpdate: () => this.viewer().seek(playhead.progress),
          scrollTrigger: {
            trigger: stage, pin: stage, scrub: .32, invalidateOnRefresh: true,
            start: () => 'top ' + Math.min(0, window.innerHeight - stage.offsetHeight) + 'px',
            end: () => '+=' + Math.max(550, window.innerHeight * .95)
          }
        });
        this.scroll = tween.scrollTrigger;
        return () => {
          this.scroll = undefined;
          this.motionEnabled.set(false);
          this.viewer().seek(.48);
        };
      });
      if (!this.scroll) this.viewer().seek(.48);
      this.lifetime.onDestroy(() => media.revert());
    });
  }

  choose(progress: number) {
    if (!this.scroll) { this.viewer().seek(progress); return; }
    window.scrollTo({ top: this.scroll.start + progress * (this.scroll.end - this.scroll.start), behavior: 'instant' });
    ScrollTrigger.update();
  }
}