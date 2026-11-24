import {afterNextRender, ChangeDetectionStrategy, Component, DestroyRef, ElementRef, inject} from '@angular/core';
import {gsap} from 'gsap';
import {BudsViewer} from './buds-viewer';
@Component({selector:'app-hero', imports:[BudsViewer], templateUrl:'./hero.html', styleUrl:'./hero.css', changeDetection:ChangeDetectionStrategy.OnPush})
export class Hero {
  constructor() {
    const root = inject(ElementRef<HTMLElement>);
    const lifetime = inject(DestroyRef);
    afterNextRender(() => {
      const motion = gsap.matchMedia();
      motion.add('(prefers-reduced-motion: no-preference)', () => {
        gsap.from(root.nativeElement.querySelectorAll('.intro > *'), {y: 15, duration: .65, stagger: .055, ease: 'power3.out', clearProps: 'transform'});
      });
      lifetime.onDestroy(() => motion.revert());
    });
  }
}
