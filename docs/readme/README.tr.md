[English](../../README.md) · **Türkçe** · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md) · [Русский](README.ru.md) · [简体中文](README.zh-CN.md)

<div align="center">

<img src="../../assets/icon.png" alt="MiBudsClient simgesi" width="88">

# MiBudsClient

**Xiaomi ve Redmi kulaklıkların masaüstünde.**

Pil seviyeleri, düşük gecikme, ses profilleri ve dokunmatik kontroller bir arada.<br>
Windows ve Linux için Python ve Flet ile geliştirildi.

[**İndir**](https://github.com/CesurPolat/MiBudsClient/releases) · [Başlangıç](#başlangıç) · [Kaynak koddan çalıştırma](#kaynak-koddan-çalıştırma) · [Sorun bildir](https://github.com/CesurPolat/MiBudsClient/issues)

<img src="../MiBudsClientPreview.png" alt="MiBudsClient arayüzü önizlemesi" width="720">

</div>

## Özellikler

| Özellik | Neler sunar? |
| --- | --- |
| Pil takibi | Sol ve sağ kulaklık ile kutu için ayrı seviyeler, şarj göstergeleri ve elle yenileme. |
| Düşük gecikme | Oyun modunu kapatma, açma veya etkin uygulamaya göre otomatik değiştirme. |
| Ses profilleri | Kulaklıkların sunduğu EQ ön ayarlarını okuma ve değiştirme. |
| Dokunmatik kontroller | Tek, çift, üçlü dokunma ve uzun basma için sol ve sağ atamalarını düzenleme. |
| Bildirimler | Bağlantı, bağlantı kesilmesi ve kutu değişiklikleri; mevcutsa pil bilgisi ve cihaz görseli. |
| Sistem tepsisi | Arka planda çalışma, pencereyi açma ve düşük gecikmeyi tepsiden değiştirme. |
| Günlük kullanım | Otomatik bağlantı denemeleri, başlangıçta çalıştırma, kaydedilen tercihler ve güncelleme denetimi. |
| Dil desteği | 24 dilde 27 yerel ayar, anında dil değiştirme ve Arapça için sağdan sola düzen. |

## Uyumluluk

**Desteklenen cihaz Redmi Buds 6 Play'dir.** Xiaomi/Redmi kataloğunda başka modellerin adları, görselleri ve yetenek bilgileri bulunur. Katalogda yer almak, o modelin kontrol edilebildiği anlamına gelmez.

Windows ve Linux, platforma özgü Bluetooth keşfi kullanır. Linux'ta tepsi ve bildirim davranışı masaüstüne bağlıdır. Otomatik tam ekran algılama X11 araçlarını kullanır ve Wayland'de kullanılamaz. Linux donanım ve arayüz doğrulaması henüz tamamlanmadı.

MiBudsClient, Xiaomi ile bağlantısı olmayan bağımsız bir topluluk projesidir.

## Başlangıç

1. Kulaklıklarını bilgisayarının Bluetooth ayarlarından eşleştir ve bağla.
2. [Sürümler](https://github.com/CesurPolat/MiBudsClient/releases) sayfasından platformuna uygun paketi indir veya [kaynak koddan çalıştır](#kaynak-koddan-çalıştırma).
3. Uygulamayı aç. Bağlı katalog cihazlarını arar ve Bluetooth kontrol bağlantısını otomatik kurmayı dener.
4. Pil kartlarını kontrol et ve düşük gecikme modunu seç. Jestler, EQ, başlangıç ve dil tercihleri için **Ayarlar** bölümünü aç.

Eşleştirmeyi işletim sistemi yapar; uygulama mevcut bir Bluetooth bağlantısı gerektirir. Aynı anda tek örnek çalışır. Tekrar açmak mevcut pencereyi öne getirir. Tamamen kapatmak için tepsideki çıkış komutunu kullan.

## Kullanım

### Düşük gecikme

- **Kapalı:** Standart mod.
- **Açık:** Düşük gecikmeyi elle etkinleştirir.
- **Otomatik:** Tam ekran uygulamalarda etkinleştirir. **Dahil et**, tam ekran olmadan da etkinleştirir; **Hariç tut**, uygulamayı atlar.

**Uygulama kapanana kadar bekle**, eşleşen uygulama kapanana kadar düşük gecikmeyi korur. Windows ve Linux kuralları ayrı kaydedilir.

### Ekolayzır

**Ayarlar → Ekolayzır** bölümünü açarak profili ve ön ayarları oku. Profil değişiklikleri kulaklık onayı ve yeniden okumayla doğrulanır.

Özel düzenleyici yalnızca geçerli bant verisi gelirse görünür. Kaydırıcıyı bırakmak taslağı önizler, kaydetme kalıcılaştırır, sıfırlama düz eğri ister. Hata sonrası veya veriyi yenilemek için bölümü kapatıp aç.

Ön ayar değiştirme **2026-10-27** tarihinde doğrulandı. Test edilen cihaz özel bant verisi döndürmedi; özel EQ önizleme, kaydetme ve sıfırlama donanımda doğrulanmadı. [EQ teknik notları](../equalizer.md) (İngilizce).

### Dokunmatik jestler

**Ayarlar → Jestler** bölümünde atamaları oku. Sol ve sağ seçimleri ayrıdır; seçenekler modelin katalog kaydından gelir. Değişiklik hemen gönderilir ve ancak geri okunup doğrulanırsa kaydedildi olarak gösterilir. Atamalar kulaklıklarda saklanır. ANC döngüsü düzenleme kapsam dışıdır.

Okuma ve mevcut değerleri tekrar yazma **2026-10-26** tarihinde doğrulandı. Farklı bir işlev atayıp hareketi fiziksel olarak deneme hâlâ elle doğrulama gerektirir.

### Bildirimler ve dil

Bildirimler, varsa pil seviyelerini içerir. Kutuya koyma ve çıkarma şarj bayrağından çıkarılır; ayrı bir kutu veya takılma sensörü okunmaz. Bağlantı kesilince son bilinen pil verisi kullanılır.

Bildirime tıklamak pencereyi açar; Linux bildirim sunucusunun varsayılan eylemleri desteklemesi gerekir. Sistem bildirim sesleri bastırılır. Uygulama şarj geçişlerinde kendi melodilerini ve her oturumun ilk başarılı bağlantısında bir kez bağlantı melodisini çalar.

**Ayarlar → Dil** bölümünde sistem dilini veya istediğin dili seç. Tercih kaydedilir; hemen arayüze, tepsiye ve sonraki bildirimlere uygulanır. Desteklenmeyen sistem dilleri İngilizceye döner.

Desteklenen diller: Arapça, Çince (Basitleştirilmiş, Tayvan, Hong Kong), Felemenkçe, İngilizce, Estonca, Fince, Fransızca, Almanca, Hintçe, Macarca, Endonezce, İtalyanca, Japonca, Korece, Malayca, Lehçe, Portekizce (Brezilya ve Portekiz), Rusça, İspanyolca, İsveççe, Tayca, Türkçe, Ukraynaca ve Vietnamca.

## Kaynak koddan çalıştırma

`venv` ve `pip` içeren Python, Bluetooth adaptörü ve sistem üzerinden bağlanmış kulaklıklar gerekir.

```sh
git clone https://github.com/CesurPolat/MiBudsClient.git
cd MiBudsClient
```

**Windows — PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

**Linux**

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Linux'ta keşif için BlueZ'nin `bluetoothctl` aracı; tepsi için PyGObject (`gi`) ile AppIndicator3 veya GTK gerekir. X11 tam ekran algılama ayrıca `xprop`, `xwininfo` ve `xrandr` kullanır. Bunlar sistem bağımlılıklarıdır; `requirements.txt` yalnızca Python paketlerini yükler.

## Sorun giderme

| Sorun | Kontrol edilecekler |
| --- | --- |
| Kulaklık bulunamıyor | Bluetooth'u aç, sistem ayarlarından bağlantıyı doğrula ve yeniden dene. |
| Bağlantı zaman aşımı | Kulaklıkları yakında ve açık tut. Bilgisayarın Bluetooth'unu kapat, 10 saniye bekle ve aç. Gerekirse iki kulaklığı kutuya koyup kapağı 5 saniye kapat; ardından çıkarıp yeniden dene. |
| Pil seviyesi yok | Bağlandıktan sonra pil kontrolünü kullan. Eksik veriler bilinmiyor sayılır. |
| Jest veya EQ hatası | İlgili bölümü kapatıp açarak cihaz verisini yeniden oku. |
| Özel EQ görünmüyor | Geçerli bant verisi gerekir; test edilen cihaz bunu sağlamadı. Ön ayarlar yine kullanılabilir. |
| Linux otomatik modu çalışmıyor | X11 oturumunu ve yukarıdaki araçları kontrol et. Wayland algılama kullanılamaz. |
| Linux bildirimine tıklamak işe yaramıyor | Sunucunun varsayılan eylem desteğini kontrol et; pencereyi tepsiden aç. |

[Sorun bildirirken](https://github.com/CesurPolat/MiBudsClient/issues) uygulama sürümünü, işletim sistemini ve masaüstü oturumunu, modeli, yeniden üretme adımlarını ve hata ayrıntılarını ekle.

## Geliştirme

`main.py` başlangıcı yönetir. `controllers/` Bluetooth, cihaz durumu, düşük gecikme ve ayar işlemlerini; `ui/` Flet arayüzünü, tepsiyi ve bildirimleri; `utils/` platform yardımcılarını içerir. Kaynaklar `assets/`, testler `tests/`, belgeler `docs/` altındadır.

Geliştirme ortamında depo kökünden çalıştır:

```sh
python -m unittest discover -s tests
```

Protokol ve sabit değişiklikleri gerçek Redmi Buds 6 Play ile de test edilmelidir. Sentetik testler cihaz uyumluluğunu kanıtlamaz. Cihaz davranışını veya paketlemeyi değiştirmeden önce [AGENTS.md](../../AGENTS.md) dosyasını oku.

Arayüz çevirileri `assets/locales/` altındadır. Anahtarlar, yer tutucular ve Xiaomi kaynakları için [yerelleştirme rehberine](../localization.md) (İngilizce) bak. `docs/readme/` çevirilerini özellik veya kurulum değişikliklerinde İngilizce README ile birlikte güncelle.

### Çalıştırılabilir dosya oluşturma

Etkin ortamında Flet CLI bulunmalıdır. Hedef platformda çalıştır:

**Windows — PowerShell**

```powershell
flet pack main.py --icon assets\icon.ico --add-data "assets:assets" --name "MiBudsClient"
```

**Linux**

```sh
flet pack main.py --icon assets/icon.ico --add-data "assets:assets" --name "MiBudsClient" --hidden-import optparse
```

Paketlenmeleri için arayüz kaynaklarını `assets/` altında tut. Dağıtımdan önce kulaklıkla doğrula; ikinci kez açıldığında mevcut pencerenin öne geldiğini ve ikinci örneğin sessizce kapandığını kontrol et.

## Lisans

MiBudsClient, [GNU Genel Kamu Lisansı v3.0](../../LICENSE) ile lisanslanmıştır.
