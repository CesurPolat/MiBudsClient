import { NgOptimizedImage } from '@angular/common';
import { ChangeDetectionStrategy, Component, signal } from '@angular/core';

@Component({
  selector: 'app-features', imports: [NgOptimizedImage], templateUrl: './features.html',
  styleUrls: ['./features.css', './feature-motion.css'], changeDetection: ChangeDetectionStrategy.OnPush
})
export class Features {
  protected readonly mode = signal(0);
  protected readonly levels = [14,22,32,25,15,25,33,43,34,26,16,22,31,40,48,38,29,19,14,22,30,23,16,12];
}