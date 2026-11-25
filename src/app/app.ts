import { NgOptimizedImage } from '@angular/common';
import { afterNextRender, ChangeDetectionStrategy, Component, DestroyRef, ElementRef, inject } from '@angular/core';
import { Features } from './features';
import { DeviceGallery } from './device-gallery';
import { Hero } from './hero';

@Component({
  selector: 'app-root', imports: [Hero, Features, DeviceGallery, NgOptimizedImage],
  templateUrl: './app.html', styleUrls: ['./app.css', './opening-support.css'], changeDetection: ChangeDetectionStrategy.OnPush
})
export class App {
  protected readonly repo = 'https://github.com/CesurPolat/MiBudsClient';
  constructor() {
    const host: HTMLElement = inject(ElementRef).nativeElement;
    const lifetime = inject(DestroyRef);
    afterNextRender(() => {
      // The Angular base URL identifies the asset directory. Keep fragment links
      // on this document as well when the preview or shared URL has a query.
      if (location.search || location.pathname !== new URL(document.baseURI).pathname) {
        for (const anchor of host.querySelectorAll<HTMLAnchorElement>('a[href^="#"]')) {
          anchor.href = location.pathname + location.search + anchor.hash;
        }
      }
      const observer = new IntersectionObserver(entries => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          entry.target.classList.add('in-view');
          observer.unobserve(entry.target);
        }
      }, { threshold: .12 });
      host.querySelectorAll('[data-reveal]').forEach(node => observer.observe(node));
      lifetime.onDestroy(() => observer.disconnect());
    });
  }

  protected readonly questions = [
    { q: 'Will my earbuds work with MiBudsClient?', a: 'Redmi Buds 6 Play is the hardware reference for the project. On other Xiaomi and Redmi models, available controls and connection support depend on the model and firmware. ANC and transparency are model-specific and still need hardware verification across devices.' },
    { q: 'How do I connect for the first time?', a: 'Pair and connect your earbuds in your computer’s Bluetooth settings, then launch MiBudsClient. It looks for connected, recognized devices and shows the controls available for your model.' },
    { q: 'Can I change my touch controls?', a: 'Open Settings and choose Gestures to view the left and right assignments. The available actions and gestures depend on your earbuds.' },
    { q: 'Is MiBudsClient free?', a: 'Yes. MiBudsClient is an independent, open-source community project licensed under GPL-3.0. You can explore the source code and release history on GitHub.' }
  ];
}