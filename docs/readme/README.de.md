[English](../../README.md) · [Türkçe](README.tr.md) · **Deutsch** · [Español](README.es.md) · [Français](README.fr.md) · [Русский](README.ru.md) · [简体中文](README.zh-CN.md)

<div align="center">

<img src="../../assets/icon.png" alt="MiBudsClient-Symbol" width="88">

# MiBudsClient

**Deine Xiaomi- und Redmi-Ohrhörer auf dem Desktop.**

Akkustände, niedrige Latenz, Klangprofile und Touch-Steuerung an einem Ort.<br>
Mit Python und Flet für Windows und Linux entwickelt.

[**Download**](https://github.com/CesurPolat/MiBudsClient/releases) · [Erste Schritte](#erste-schritte) · [Aus dem Quellcode starten](#aus-dem-quellcode-starten) · [Problem melden](https://github.com/CesurPolat/MiBudsClient/issues)

<img src="../MiBudsClientPreview.png" alt="Vorschau der MiBudsClient-Oberfläche" width="720">

</div>

## Funktionen

| Funktion | Möglichkeiten |
| --- | --- |
| Geräuschkontrolle | ANC, Transparenz und modellspezifische Stufen anhand des Gerätekatalogs. Die Hardwarekompatibilität aller Modelle ist noch nicht bestätigt. |
| Akkuüberwachung | Separate Werte für beide Ohrhörer und das Ladecase, Ladeanzeigen und manuelle Aktualisierung. |
| Niedrige Latenz | Spielmodus aus, ein oder automatisch anhand der aktiven Anwendung. |
| Klangprofile | EQ-Voreinstellungen des Geräts lesen und ändern. |
| Touch-Steuerung | Belegungen für einfaches, doppeltes, dreifaches Tippen und langes Drücken links und rechts bearbeiten. |
| Benachrichtigungen | Verbindungs- und Ladecase-Meldungen mit Akkudaten und Gerätebild, sofern verfügbar. |
| Infobereich | Im Hintergrund arbeiten, das Fenster öffnen und den Latenzmodus wechseln. |
| Komfort | Automatische Verbindungsversuche, Autostart, gespeicherte Einstellungen und Updateprüfung. |
| Sprachen | 27 Gebietsschemata für 24 Sprachen, sofortiger Wechsel und arabisches Rechts-nach-links-Layout. |

## Kompatibilität

**MiBudsClient wird für mehrere Xiaomi- und Redmi-Modelle entwickelt.** Unter Windows versucht die App, erkannte Kataloggeräte zu verbinden, und aktiviert implementierte Funktionen anhand der Funktionsliste und Optionen des Modells. Eine separate Modellfreigabe ist nicht erforderlich.

- **Funktionen:** Akkuanzeige, ANC/Transparenz, EQ-Voreinstellungen, unterstützte Touch-Gesten und niedrige Latenz. Die verfügbaren Optionen hängen vom Modell ab; Akkudaten vom Gerät.
- **Windows:** dynamische RFCOMM-Kanalsuche; Befehlsauthentifizierung über MIUI SPP (FD2D), rohe Authentifizierung über XiaoAI/Standard-SPP.
- **Linux:** dynamische RFCOMM-Kanalsuche über BlueZ-SDP mit exakter Dienst-UUID. Die Authentifizierung richtet sich nach dem Dienst. Nur Redmi Buds 6 Play nutzt Kanal 6 als Fallback, wenn kein Dienstkanal aufgelöst wird. Die Hardwarekompatibilität hängt von Gerät und Firmware ab.
- **Hardwarebelege:** Redmi Buds 6 Play ist das Referenzgerät mit dokumentierter Akku-/Latenznutzung und den unten datierten EQ-/Gestenprüfungen. ANC/Transparenz, rohe Authentifizierung und andere Modelle sind damit nicht auf Hardware bestätigt.

Modellnamen, Identitäten, Bilder und Funktionsdaten stammen aus dem [Gerätekatalog](../../assets/device_catalog.json). Ein erkannter Name garantiert keine funktionierende Protokollverbindung. Implementierte Funktionen werden ohne Modellfreigabeliste angeboten; erfolgreiche Vorgänge erfordern eine Verbindung und passende Geräteantworten. Firmware und regionale Varianten können abweichen.

Benutzerdefinierter EQ ist auf eine spätere Version verschoben und einschließlich des eigenen Profils ausgeblendet. Weitere Katalogfunktionen erzeugen nicht automatisch Bedienelemente.

Unter GNOME Shell 46 mit Wayland wird die Vollbilderkennung automatisch eingerichtet. Bei Aufforderung ab- und wieder anmelden; kein Terminalbefehl erforderlich. X11 benötigt keine Erweiterung. Andere Wayland-Desktops werden noch nicht unterstützt. [Details](../wayland.md).

Diese README beschreibt den aktuellen Quellcode; ältere Pakete können davon abweichen. Technische Hinweise: [Funktionen](../device-capabilities.md), [Befehlsauthentifizierung](../command-auth.md), [rohe Authentifizierung](../raw-auth.md) (Englisch).

MiBudsClient ist ein unabhängiges Community-Projekt ohne Verbindung zu Xiaomi.

## Erste Schritte

1. Kopple und verbinde die Ohrhörer in den Bluetooth-Einstellungen des Computers.
2. Lade ein Paket für deine Plattform unter [Releases](https://github.com/CesurPolat/MiBudsClient/releases) oder [starte aus dem Quellcode](#aus-dem-quellcode-starten).
3. Starte MiBudsClient. Die App sucht verbundene Kataloggeräte und versucht automatisch eine Bluetooth-Steuerverbindung.
4. Prüfe nach dem Verbinden die Akkukarten und verfügbaren Funktionen deines Modells. **Einstellungen** enthält unterstützte Gesten, EQ, Geräuschkontrolle, Autostart und Sprache.

Die Kopplung übernimmt das Betriebssystem; die App benötigt eine bestehende Bluetooth-Verbindung. Es läuft nur eine Instanz. Erneutes Starten bringt das vorhandene Fenster nach vorn. Zum vollständigen Beenden verwende den Beenden-Befehl im Infobereich.

## Bedienung

### Niedrige Latenz

- **Aus:** Standardmodus.
- **Ein:** Niedrige Latenz manuell aktivieren.
- **Automatisch:** Bei Vollbildanwendungen aktivieren. **Einschließen** aktiviert auch ohne Vollbild; **Ausschließen** überspringt die Anwendung.

Mit **Warten, bis die App geschlossen wird** bleibt niedrige Latenz bis zum Ende der erkannten Anwendung aktiv. Regeln werden für Windows und Linux getrennt gespeichert.

### Equalizer

Öffne **Einstellungen → Equalizer**, um das aktuelle Profil zu lesen und die im Modellkatalog angebotenen Voreinstellungen zu wählen. Änderungen werden bestätigt und durch erneutes Lesen überprüft.

**Benutzerdefinierter EQ ist für eine spätere Version geplant.** Bandeditor und eigenes Profil bleiben auch dann ausgeblendet, wenn sie im Katalog stehen.

Der Profilwechsel wurde am **2026-10-27** mit Redmi Buds 6 Play bestätigt; dies bestätigt keine anderen Modelle. Frühere Implementierungs- und Prüfhistorie: [EQ-Hinweise](../equalizer.md) (Englisch).

### Touch-Gesten

Unter **Einstellungen → Gesten** werden Belegungen geladen. Links und rechts sind getrennt; die Optionen stammen aus dem genauen Modellkatalogeintrag. Änderungen werden sofort gesendet und erst nach erfolgreichem Zurücklesen als gespeichert angezeigt. Sie werden auf den Ohrhörern gespeichert. ANC-Zyklen können nicht bearbeitet werden.

Lesen und Zurückschreiben unveränderter Werte wurden am **2026-10-26** bestätigt. Das Zuweisen einer anderen Funktion und ihr tatsächliches Auslösen müssen noch manuell geprüft werden.

### Benachrichtigungen und Sprache

Meldungen enthalten verfügbare Akkudaten. Einlegen und Herausnehmen werden aus dem Ladezustandsbit abgeleitet; ein separater Case- oder Tragesensor wird nicht gelesen. Beim Trennen erscheinen die zuletzt bekannten Werte.

Ein Klick auf eine Meldung öffnet das Fenster. Unter Linux muss der Benachrichtigungsserver Standardaktionen unterstützen. Systemklänge für Meldungen werden unterdrückt. Die App spielt eigene Melodien bei Ladeübergängen sowie einmal bei der ersten erfolgreichen Ohrhörerverbindung jeder Sitzung.

Unter **Einstellungen → Sprache** kannst du die Systemsprache oder eine Sprache wählen. Die gespeicherte Wahl gilt sofort für Oberfläche, Infobereich und zukünftige Meldungen. Nicht unterstützte Systemsprachen fallen auf Englisch zurück.

Verfügbar: Arabisch, Chinesisch (vereinfacht, Taiwan, Hongkong), Niederländisch, Englisch, Estnisch, Finnisch, Französisch, Deutsch, Hindi, Ungarisch, Indonesisch, Italienisch, Japanisch, Koreanisch, Malaiisch, Polnisch, Portugiesisch (Brasilien und Portugal), Russisch, Spanisch, Schwedisch, Thai, Türkisch, Ukrainisch und Vietnamesisch.

## Aus dem Quellcode starten

Benötigt werden Python mit `venv` und `pip`, ein Bluetooth-Adapter und über das Betriebssystem verbundene Ohrhörer.

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

Linux benötigt BlueZs `bluetoothctl` zur Erkennung sowie PyGObject (`gi`) mit AppIndicator3 oder GTK für den Infobereich. Die X11-Vollbilderkennung benötigt `xprop`, `xwininfo` und `xrandr`. Diese Systemabhängigkeiten werden nicht durch `requirements.txt` installiert; die Datei enthält nur Python-Pakete.

Die dynamische RFCOMM-Dienstsuche benötigt außerdem BlueZs `sdptool`, das manche Distributionen separat paketieren.

## Fehlerbehebung

| Problem | Prüfen |
| --- | --- |
| Keine Ohrhörer gefunden | Bluetooth einschalten, Verbindung in den Systemeinstellungen prüfen und erneut versuchen. |
| Zeitüberschreitung | Ohrhörer eingeschaltet in der Nähe halten. Computer-Bluetooth ausschalten, 10 Sekunden warten und einschalten. Nötigenfalls beide Ohrhörer ins Case legen, den Deckel 5 Sekunden schließen, dann herausnehmen und erneut versuchen. |
| Akkudaten fehlen | Nach dem Verbinden die Akkuprüfung verwenden. Fehlende Werte gelten als unbekannt. |
| Gesten- oder EQ-Fehler | Den Abschnitt schließen und erneut öffnen, um Gerätedaten zu laden. |
| Benutzerdefinierter EQ fehlt | In dieser Version verschoben und ausgeblendet; unterstützte Voreinstellungen bleiben verfügbar. |
| Automatik unter Linux ohne Wirkung | Unter GNOME Shell 46 mit Wayland wird die Vollbilderkennung automatisch eingerichtet. Bei Aufforderung ab- und wieder anmelden; kein Terminalbefehl erforderlich. X11 benötigt keine Erweiterung. Andere Wayland-Desktops werden noch nicht unterstützt. [Details](../wayland.md). |
| Klick auf Linux-Meldung ohne Wirkung | Standardaktionen prüfen oder das Fenster über den Infobereich öffnen. |

Gib bei einer [Fehlermeldung](https://github.com/CesurPolat/MiBudsClient/issues) App-Version, Betriebssystem und Desktopsitzung, Modell, Schritte zur Reproduktion und Fehlerdetails an.

## Entwicklung

`main.py` verbindet die Anwendungsteile. `controllers/` enthält Bluetooth, Gerätestatus, Latenz- und Einstellungslogik; `ui/` die Flet-Oberfläche, den Infobereich und Meldungen; `utils/` Plattformhelfer. Ressourcen liegen in `assets/`, Tests in `tests/` und Dokumente in `docs/`.

Tests in der Entwicklungsumgebung vom Repository-Stamm aus starten:

```sh
python -m unittest discover -s tests
```

Dokumentiere bei Protokollprüfungen Modell, Firmware, Betriebssystem, Verbindungsmethode und geprüfte Funktion. Synthetische Tests belegen keine Hardwarekompatibilität; Hardwareberichte sind Belege, keine Freigabebedingung je Modell. Lies vor Änderungen [AGENTS.md](../../AGENTS.md).

Übersetzungen liegen in `assets/locales/`. Der [Lokalisierungsleitfaden](../localization.md) (Englisch) erklärt Schlüssel, Platzhalter und Xiaomi-Quellen. Aktualisiere `docs/readme/` bei Funktions- oder Installationsänderungen zusammen mit der englischen README.

### Ausführbare Datei erstellen

Die Flet CLI muss in der aktiven Umgebung verfügbar sein. Auf der Zielplattform ausführen:

**Windows — PowerShell**

```powershell
flet pack main.py --icon assets\icon.ico --add-data "assets:assets" --name "MiBudsClient"
```

**Linux**

```sh
flet pack main.py --icon assets/icon.ico --add-data "assets:assets" --name "MiBudsClient" --hidden-import optparse
```

Alle UI-Ressourcen müssen zum Bündeln unter `assets/` bleiben. Vor Veröffentlichung mit den Ohrhörern prüfen und zweimal starten: Der zweite Start soll das vorhandene Fenster fokussieren und lautlos enden.

## Lizenz

MiBudsClient steht unter der [GNU General Public License v3.0](../../LICENSE).
