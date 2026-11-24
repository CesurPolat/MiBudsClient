import { afterNextRender, ChangeDetectionStrategy, Component, DestroyRef, ElementRef, inject, input, viewChild } from '@angular/core';

@Component({
  selector: 'app-sound-waves', changeDetection: ChangeDetectionStrategy.OnPush,
  template: '<canvas #surface aria-hidden="true"></canvas>',
  styles: [':host,canvas{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}:host{z-index:-1;overflow:hidden}']
})
export class SoundWaves {
  readonly paused = input(false);
  private readonly canvas = viewChild.required<ElementRef<HTMLCanvasElement>>('surface');
  constructor() {
    const lifetime = inject(DestroyRef);
    afterNextRender(() => {
      const canvas = this.canvas().nativeElement;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      const reduced = matchMedia('(prefers-reduced-motion: reduce)');
      let frame = 0, visible = true, phase = 0, last = 0;
      const draw = () => {
        const w = canvas.width, h = canvas.height;
        ctx.clearRect(0, 0, w, h);
        const light = ctx.createLinearGradient(0,0,w,0);
        light.addColorStop(0,'#5499ff'); light.addColorStop(.37,'#295298');
        light.addColorStop(.68,'#72ceff'); light.addColorStop(1,'#808dff');
        ctx.strokeStyle = light;
        for (let strand = 0; strand < 44; strand++) {
          const s = strand / 43;
          ctx.beginPath();
          ctx.globalAlpha = .13 + .45 * Math.pow(Math.sin(s * Math.PI),8);
          ctx.lineWidth = (strand % 6 === 0 ? 1.3 : .65) * w / 1300;
          for (let x = 0; x <= 180; x++) {
            const t = x / 180;
            const swell = Math.sin(t*8.6 + phase*.52 + .62*s);
            const y = .63 + .085*swell + .063*Math.sin(t*15.6-phase*.7 + s)
                      + (s-.5)*(.045+.13*Math.pow(Math.cos(t*8-phase*.3),2));
            if (x === 0) ctx.moveTo(0,y*h); else ctx.lineTo(t*w,y*h);
          }
          ctx.stroke();
        }
      };
      function stop() { cancelAnimationFrame(frame); frame = 0; last = 0; }
      const tick = (now: number) => {
        if (!visible || document.hidden || reduced.matches) { stop(); return; }
        if (now-last >= 48) {
          if (!this.paused()) { phase += Math.min((now-last)/1000,.05); draw(); }
          last = now;
        }
        frame = requestAnimationFrame(tick);
      };
      const sync = () => {
        stop();
        if (visible && !document.hidden && !reduced.matches) frame = requestAnimationFrame(tick);
        else if (reduced.matches) draw();
      };
      const size = new ResizeObserver(() => {
        canvas.width = Math.max(1,Math.round(canvas.clientWidth * Math.min(devicePixelRatio,1.5)));
        canvas.height = Math.max(1,Math.round(canvas.clientHeight * Math.min(devicePixelRatio,1.5)));
        draw();
      });
      const visibility = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; sync(); });
      size.observe(canvas); visibility.observe(canvas);
      document.addEventListener('visibilitychange',sync); reduced.addEventListener('change',sync);
      lifetime.onDestroy(() => {
        stop(); size.disconnect(); visibility.disconnect();
        document.removeEventListener('visibilitychange',sync); reduced.removeEventListener('change',sync);
      });
    });
  }
}