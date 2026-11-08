# Değerlendirme için UI notları

## 9 Kasım 2026 — Geri alınan son rötuşlar

Durum: Kullanıcının isteğiyle geri alındı; ileride değerlendirmek için kaydedildi.

- Ayarlar butonunun ikonuna 32 × 32 px, 10 px köşe yarıçaplı bir kutu eklendi. Kutunun arka planı `COLOR_HOME_CONTROL`, 1 px çerçevesi `COLOR_HOME_BORDER` idi. İkon 18 px, ikon ile yazı arası 8 px idi. Geri navigasyonunda aynı kutunun içindeki ikon ok simgesine dönüşüyordu. Uygulama yeri: `ui/components/app_layout.py`.
- Kart ve seçim kutularının daha belirgin görünmesi için `ui/constants.py` içindeki `COLOR_HOME_BORDER`, `#252D36` yerine `#35414E`; `COLOR_HOME_CONTROL`, `#1B2127` yerine `#242C35` yapıldı. Ortak renkler olduğu için Ayarlar bölümünü de etkiliyordu.

Geri alma sonrasında buton tekrar standart ikon ve yazı kullanıyor; renkler `#252D36` ve `#1B2127` değerlerine döndü. Önceki tasarım düzenlemeleri korundu. Bu rötuşlar için test veya build çalıştırılmadı.
