[English](../../README.md) · **Türkçe** · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md) · [Русский](README.ru.md) · [简体中文](README.zh-CN.md)

<div align="center">

<img src="../../assets/icon.png" alt="MiBudsClient simgesi" width="88">

# MiBudsClient

**Xiaomi ve Redmi kulaklıkların masaüstünde.**

Pil seviyelerini takip et; gürültü kontrolünü, EQ ön ayarlarını, dokunmatik hareketleri ve düşük gecikme modunu yönet.<br>
Windows ve Linux için Python ve Flet ile geliştirildi.

[**İndir**](https://github.com/CesurPolat/MiBudsClient/releases) · [Başlangıç](#başlangıç) · [Kaynak koddan çalıştırma](#kaynak-koddan-çalıştırma) · [Sorun bildir](https://github.com/CesurPolat/MiBudsClient/issues)

<img src="../MiBudsClientPreview.png" alt="MiBudsClient arayüzü önizlemesi" width="720">

</div>

## Özellikler

| Özellik | Neler sunar? |
| --- | --- |
| Gürültü kontrolü | ANC, şeffaflık ve modele ait seviye seçenekleri cihaz kataloğuna göre açılır. Modeller genelinde donanım uyumluluğu henüz doğrulanmadı. |
| Pil takibi | Sol ve sağ kulaklık ile kutu için ayrı seviyeler, şarj göstergeleri ve elle yenileme. |
| Düşük gecikme | Oyun modunu kapatma, açma veya etkin uygulamaya göre otomatik değiştirme. |
| Ses profilleri | Kulaklıkların sunduğu EQ ön ayarlarını okuma ve değiştirme. |
| Dokunmatik kontroller | Tek, çift, üçlü dokunma, uzun basma ve kaydırma için sol ve sağ atamalarını düzenleme. |
| Bildirimler | Bağlantı, bağlantı kesilmesi ve kutu değişiklikleri; mevcutsa pil bilgisi ve cihaz görseli. |
| Sistem tepsisi | Arka planda çalışma, pencereyi açma ve düşük gecikmeyi tepsiden değiştirme. |
| Günlük kullanım | Otomatik bağlantı denemeleri, başlangıçta çalıştırma, kaydedilen tercihler ve güncelleme denetimi. |
| Dil desteği | 24 dilde 27 yerel ayar, anında dil değiştirme ve Arapça için sağdan sola düzen. |

## Uyumluluk

**MiBudsClient birden fazla Xiaomi ve Redmi modeli için geliştiriliyor.** Windows'ta tanınan katalog cihazlarına kontrol bağlantısı kurmayı dener; uygulanmış kontrolleri modelin özellik listesine ve seçeneklerine göre açar. Ayrı bir model onay listesine ihtiyaç yoktur.

| Alan | Mevcut kapsam |
| --- | --- |
| Model tanıma | Adlar, VID/PID kimlikleri, görseller ve yetenekler [cihaz kataloğundan](../../assets/device_catalog.json) gelir. Modelin tanınması tek başına çalışan bir protokol oturumunu garanti etmez. |
| Uygulanmış kontroller | Pil, ANC/şeffaflık, EQ ön ayarları, desteklenen dokunma hareketleri ve düşük gecikme. Kontroller ve seçenekler modele; pil verisi cihazın bildirdiği değerlere bağlıdır. |
| Windows bağlantısı | Cihazın Bluetooth servisinden RFCOMM kanalını bulur. MIUI SPP (FD2D) için komutlu, XiaoAI/standart SPP için ham doğrulamayı destekler. |
| Linux bağlantısı | BlueZ SDP kayıtlarından tam servis UUID'sine göre RFCOMM kanalını bulur. Doğrulama servise göre seçilir. Kanal çözülemezse yalnız Redmi Buds 6 Play için kanal 6 yedeği kullanılır. Donanım uyumluluğu cihaz ve firmware'e bağlıdır. |
| Donanım kanıtı | Redmi Buds 6 Play, projenin donanım referansıdır; pil/düşük gecikme kullanımı ve aşağıdaki tarihli EQ/jest kontrolleri kaydedilmiştir. Bu, her modelin her özelliğini doğrulamaz; ANC/şeffaflık ve ham doğrulama için gerçek cihaz denemesi hâlâ gerekir. |

Custom EQ ileri bir sürüme bırakıldı; özel profil dahil gizlidir. Katalogdaki diğer özellikler kendiliğinden uygulama kontrolüne dönüşmez. Özelliklerin görünürlüğünü katalog, işlemin tamamlanmasını bağlantı ve cihaz yanıtları belirler. Firmware ve bölgesel sürümler farklı davranabilir.

Otomatik oyun modu: GNOME 46 Wayland desteği otomatik kurulur; istenirse çıkış/giriş yapın. KDE Plasma 6 için `kwinscript` destekli `kdotool`, Sway için `swaymsg`, Hyprland için `hyprctl` gerekir. Bu üç yeni yol canlı masaüstünde henüz doğrulanmadı. X11 ek eklenti kullanmaz. [Ayrıntılar](../wayland.md).

Bu README güncel kaynak kodu anlatır; eski paketlenmiş sürümler bu değişiklikleri içermeyebilir. Teknik ayrıntılar: [cihaz yetenekleri](../device-capabilities.md), [komutlu doğrulama](../command-auth.md), [ham doğrulama](../raw-auth.md) (İngilizce).

MiBudsClient, Xiaomi ile bağlantısı olmayan bağımsız bir topluluk projesidir.

## Başlangıç

1. Kulaklıklarını bilgisayarının Bluetooth ayarlarından eşleştir ve bağla.
2. [Sürümler](https://github.com/CesurPolat/MiBudsClient/releases) sayfasından platformuna uygun paketi indir veya [kaynak koddan çalıştır](#kaynak-koddan-çalıştırma).
3. Uygulamayı aç. Bağlı katalog cihazlarını arar ve Bluetooth kontrol bağlantısını otomatik kurmayı dener.
4. Bağlanınca pil kartlarını ve modeline sunulan kontrolleri incele. Desteklenen jestler, EQ, gürültü kontrolü, başlangıç ve dil tercihleri için **Ayarlar** bölümünü aç.

Eşleştirmeyi işletim sistemi yapar; uygulama mevcut bir Bluetooth bağlantısı gerektirir. Aynı anda tek örnek çalışır. Tekrar açmak mevcut pencereyi öne getirir. Tamamen kapatmak için tepsideki çıkış komutunu kullan.

Çalışma logları için **F12** tuşuna bas. Linux’ta MiBudsClient odaktayken uygulama içi konsol açılır; logları seçip kopyalayabilir veya temizleyebilirsin. F12 tekrar kapatır. Windows ayrı konsol penceresini kullanmaya devam eder. Konsol kapalıyken log toplama sürer.

## Kullanım

### Düşük gecikme

- **Kapalı:** Standart mod.
- **Açık:** Düşük gecikmeyi elle etkinleştirir.
- **Otomatik:** Tam ekran uygulamalarda etkinleştirir. **Dahil et**, tam ekran olmadan da etkinleştirir; **Hariç tut**, uygulamayı atlar.

**Uygulama kapanana kadar bekle**, eşleşen uygulama kapanana kadar düşük gecikmeyi korur. Windows ve Linux kuralları ayrı kaydedilir.

### Ekolayzır

**Ayarlar → Ekolayzır** bölümünde mevcut profili oku ve modelin katalog kaydındaki ön ayarlardan seçim yap. Profil değişiklikleri kulaklık onayı ve yeniden okumayla doğrulanır.

**Custom EQ sonraki bir sürüm için planlanıyor.** Katalogda bulunsa bile bant düzenleyicisi ve özel profil şu anda gizlidir.

Ön ayar değiştirme Redmi Buds 6 Play üzerinde **2026-10-27** tarihinde doğrulandı; bu, diğer modeller için donanım doğrulaması değildir. Önceki uygulama ve doğrulama ayrıntıları için [EQ teknik notlarına](../equalizer.md) (İngilizce) bak.

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

Linux’ta bildirimler, tray ikonundan bağımsız Gio/GLib D-Bus işçisiyle gönderilir; bir bildirim sunucusu gerekir. İkonu barındıran panel kaybolursa pencere geri gelir. Tıklama ve resim desteği sunucuya bağlıdır. [Masaüstü entegrasyonu](../linux-desktop.md).

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Linux'ta keşif için BlueZ'nin `bluetoothctl` aracı; tepsi için PyGObject (`gi`) ile AppIndicator3 veya GTK gerekir. X11 tam ekran algılama ayrıca `xprop`, `xwininfo` ve `xrandr` kullanır. Bunlar sistem bağımlılıklarıdır; `requirements.txt` yalnızca Python paketlerini yükler.

Dinamik RFCOMM servis keşfi için BlueZ'nin `sdptool` aracı da gerekir; bazı dağıtımlarda ayrı paketlenir.

## Sorun giderme

| Sorun | Kontrol edilecekler |
| --- | --- |
| Kulaklık bulunamıyor | Bluetooth'u aç, sistem ayarlarından bağlantıyı doğrula ve yeniden dene. |
| Bağlantı zaman aşımı | Kulaklıkları yakında ve açık tut. Bilgisayarın Bluetooth'unu kapat, 10 saniye bekle ve aç. Gerekirse iki kulaklığı kutuya koyup kapağı 5 saniye kapat; ardından çıkarıp yeniden dene. |
| Pil seviyesi yok | Bağlandıktan sonra pil kontrolünü kullan. Eksik veriler bilinmiyor sayılır. |
| Jest veya EQ hatası | İlgili bölümü kapatıp açarak cihaz verisini yeniden oku. |
| Özel EQ görünmüyor | Custom EQ bu sürümde ertelendi ve gizlendi. Modelin desteklediği ön ayarlar kullanılabilir. |
| Linux otomatik modu çalışmıyor | Otomatik oyun modu: GNOME 46 Wayland desteği otomatik kurulur; istenirse çıkış/giriş yapın. KDE Plasma 6 için `kwinscript` destekli `kdotool`, Sway için `swaymsg`, Hyprland için `hyprctl` gerekir. Bu üç yeni yol canlı masaüstünde henüz doğrulanmadı. X11 ek eklenti kullanmaz. [Ayrıntılar](../wayland.md). |
| Linux bildirimine tıklamak işe yaramıyor | Sunucunun varsayılan eylem desteğini kontrol et; pencereyi tepsiden aç. |

[Sorun bildirirken](https://github.com/CesurPolat/MiBudsClient/issues) uygulama sürümünü, işletim sistemini ve masaüstü oturumunu, modeli, yeniden üretme adımlarını ve hata ayrıntılarını ekle.

## Geliştirme

`main.py` başlangıcı yönetir. `controllers/` Bluetooth, cihaz durumu, düşük gecikme ve ayar işlemlerini; `ui/` Flet arayüzünü, tepsiyi ve bildirimleri; `utils/` platform yardımcılarını içerir. Kaynaklar `assets/`, testler `tests/`, belgeler `docs/` altındadır.

Geliştirme ortamında depo kökünden çalıştır:

```sh
python -m unittest discover -s tests
```

Protokol değişikliklerini denerken tam modeli, firmware sürümünü, işletim sistemini, bağlantı yöntemini ve denenen özelliği kaydet. Sentetik testler donanım uyumluluğunu kanıtlamaz; donanım raporları kanıttır, model bazında özellik açma şartı değildir. Cihaz davranışını veya paketlemeyi değiştirmeden önce [AGENTS.md](../../AGENTS.md) dosyasını oku.

Arayüz çevirileri `assets/locales/` altındadır. Anahtarlar, yer tutucular ve Xiaomi kaynakları için [yerelleştirme rehberine](../localization.md) (İngilizce) bak. `docs/readme/` çevirilerini özellik veya kurulum değişikliklerinde İngilizce README ile birlikte güncelle.

### Çalıştırılabilir dosya oluşturma

Etkin ortamında Flet CLI bulunmalıdır. Hedef platformda çalıştır:

**Windows — PowerShell**

```powershell
flet pack main.py --icon assets\icon.ico --add-data "assets:assets" --name "MiBudsClient"
```

**Linux**

```sh
python tools/build_linux.py
```

Paketlenmeleri için arayüz kaynaklarını `assets/` altında tut. Dağıtımdan önce kulaklıkla doğrula; ikinci kez açıldığında mevcut pencerenin öne geldiğini ve ikinci örneğin sessizce kapandığını kontrol et.

Linux çalıştırılabilir dosyasından AppImage üretmek için `appimagetool` kurulu olduğunda `bash tools/build_appimage.sh` çalıştır. Yalnız AppDir hazırlama seçeneği ve çıktı yolları için [paketleme rehberine](../linux-desktop.md#appimage-packaging) bak.

## Lisans

MiBudsClient, [GNU Genel Kamu Lisansı v3.0](../../LICENSE) ile lisanslanmıştır.
