import { NgOptimizedImage } from '@angular/common';
import { ChangeDetectionStrategy, Component } from '@angular/core';
import { Features } from './features';
import { DeviceGallery } from './device-gallery';
import { Hero } from './hero';

@Component({
  selector: 'app-root', imports: [Hero, Features, DeviceGallery, NgOptimizedImage],
  templateUrl: './app.html', styleUrl: './app.css', changeDetection: ChangeDetectionStrategy.OnPush
})
export class App {
  protected readonly repo = 'https://github.com/CesurPolat/MiBudsClient';
  protected readonly questions = [
    { q: 'Will my earbuds work with MiBudsClient?', a: 'Redmi Buds 6 Play is the hardware reference for the project. On other Xiaomi and Redmi models, available controls and connection support depend on the model and firmware. ANC and transparency are model-specific and still need hardware verification across devices.' },
    { q: 'How do I connect for the first time?', a: 'Pair and connect your earbuds in your computer’s Bluetooth settings, then launch MiBudsClient. It looks for connected, recognized devices and shows the controls available for your model.' },
    { q: 'Can I change my touch controls?', a: 'Open Settings and choose Gestures to view the left and right assignments. The available actions and gestures depend on your earbuds.' },
    { q: 'Is MiBudsClient free?', a: 'Yes. MiBudsClient is an independent, open-source community project licensed under GPL-3.0. You can explore the source code and release history on GitHub.' }
  ];
}