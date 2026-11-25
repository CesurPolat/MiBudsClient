import { afterNextRender, ChangeDetectionStrategy, Component, DestroyRef, inject, input, signal, viewChild } from '@angular/core';
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
  readonly opening = input.required<HTMLElement>();
  readonly frame = input.required<HTMLElement>();
  private readonly viewer = viewChild.required(BudsViewer);
  private readonly lifetime = inject(DestroyRef);
  protected readonly motionEnabled = signal(false);

  constructor() {
    afterNextRender(() => {
      gsap.registerPlugin(ScrollTrigger);
      const media = gsap.matchMedia();
      media.add('(prefers-reduced-motion: no-preference)', () => {
        this.motionEnabled.set(true);
        const track = this.opening();
        const frame = this.frame();
        track.classList.add('unboxing');
        const alignFrame = () => {
          track.style.setProperty('--sticky-top', Math.min(0, window.innerHeight - frame.offsetHeight) + 'px');
        };
        alignFrame();
        const playhead = { progress: 0 };
        gsap.to(playhead, {
          progress: 1, ease: 'none',
          onUpdate: () => this.viewer().seek(playhead.progress),
          scrollTrigger: {
            trigger: track, start: 'top top', end: 'bottom bottom',
            scrub: true, invalidateOnRefresh: true, onRefreshInit: alignFrame
          }
        });
        return () => {
          track.classList.remove('unboxing');
          track.style.removeProperty('--sticky-top');
          this.motionEnabled.set(false);
          this.viewer().seek(.48);
        };
      });
      if (!this.motionEnabled()) this.viewer().seek(.48);
      this.lifetime.onDestroy(() => media.revert());
    });
  }
}