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
  protected readonly motionEnabled = signal(false);

  constructor() {
    afterNextRender(() => {
      gsap.registerPlugin(ScrollTrigger);
      const media = gsap.matchMedia();
      media.add('(prefers-reduced-motion: no-preference)', () => {
        this.motionEnabled.set(true);
        const stage = this.stage().nativeElement;
        const playhead = { progress: 0 };
        gsap.to(playhead, {
          progress: 1, ease: 'none',
          onUpdate: () => this.viewer().seek(playhead.progress),
          scrollTrigger: {
            trigger: stage, pin: stage, scrub: .32, invalidateOnRefresh: true,
            start: () => 'top ' + Math.min(0, window.innerHeight - stage.offsetHeight) + 'px',
            end: () => '+=' + Math.max(550, window.innerHeight * .95)
          }
        });
        return () => {
          this.motionEnabled.set(false);
          this.viewer().seek(.48);
        };
      });
      if (!this.motionEnabled()) this.viewer().seek(.48);
      this.lifetime.onDestroy(() => media.revert());
    });
  }
}