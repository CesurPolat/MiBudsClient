import { NgOptimizedImage } from '@angular/common';
import { ChangeDetectionStrategy, Component } from '@angular/core';
import { Features } from './features';
import { Hero } from './hero';

@Component({
  selector: 'app-root',
  imports: [Hero, Features, NgOptimizedImage],
  templateUrl: './app.html',
  styleUrl: './app.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class App {
  protected readonly repo = 'https://github.com/CesurPolat/MiBudsClient';

  protected readonly questions = [
    { q: 'Kulaklığım MiBudsClient ile çalışır mı?', a: 'Redmi Buds 6 Play, projenin donanım üzerinde test ettiği referans model. Diğer Xiaomi ve Redmi modellerinde bağlantı ve kullanılabilen kontroller, kulaklığın modeline ve yazılımına göre değişir.' },
    { q: 'İlk bağlantıyı nasıl kurarım?', a: 'Önce kulaklığını bilgisayarının Bluetooth ayarlarından eşleştir ve bağla. Ardından MiBudsClient’ı aç. Uygulama tanıdığı bağlı kulaklıkları arar ve bağlantı kurulduğunda kullanılabilir ayarları gösterir.' },
    { q: 'MiBudsClient ücretsiz mi?', a: 'Evet. MiBudsClient, GPL-3.0 lisansıyla geliştirilen ücretsiz ve açık kaynaklı bir topluluk projesidir. Kaynak kodunu ve sürüm geçmişini GitHub’da inceleyebilirsin.' }
  ];
}
