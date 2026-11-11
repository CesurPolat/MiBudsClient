[English](../../README.md) · [Türkçe](README.tr.md) · [Deutsch](README.de.md) · [Español](README.es.md) · **Français** · [Русский](README.ru.md) · [简体中文](README.zh-CN.md)

<div align="center">

<img src="../../assets/icon.png" alt="Icône de MiBudsClient" width="88">

# MiBudsClient

**Vos écouteurs Xiaomi et Redmi, sur votre ordinateur.**

Batterie, faible latence, profils sonores et commandes tactiles au même endroit.<br>
Développé avec Python et Flet pour Windows et Linux.

[**Télécharger**](https://github.com/CesurPolat/MiBudsClient/releases) · [Premiers pas](#premiers-pas) · [Exécuter depuis les sources](#exécuter-depuis-les-sources) · [Signaler un problème](https://github.com/CesurPolat/MiBudsClient/issues)

<img src="../MiBudsClientPreview.png" alt="Aperçu de l’interface MiBudsClient" width="720">

</div>

## Fonctionnalités

| Fonction | Possibilités |
| --- | --- |
| Contrôle du bruit | ANC, transparence et niveaux propres au modèle selon le catalogue. La compatibilité matérielle entre modèles reste à vérifier. |
| Batterie | Niveaux séparés des deux écouteurs et du boîtier, indicateurs de charge et actualisation manuelle. |
| Faible latence | Mode jeu désactivé, activé ou automatique selon l’application active. |
| Profils sonores | Lecture et modification des préréglages EQ proposés par les écouteurs. |
| Commandes tactiles | Actions gauche et droite : appui simple, double, triple ou prolongé. |
| Notifications | Connexion, déconnexion et changements dans le boîtier, avec batterie et image si disponibles. |
| Zone de notification | Fonctionnement en arrière-plan, restauration de la fenêtre et changement du mode de latence. |
| Au quotidien | Connexion automatique, lancement au démarrage, préférences enregistrées et vérification des mises à jour. |
| Langues | 27 variantes régionales pour 24 langues, changement immédiat et disposition de droite à gauche pour l’arabe. |

## Compatibilité

**MiBudsClient est développé pour plusieurs modèles Xiaomi et Redmi.** Sous Windows, il tente de connecter les appareils reconnus du catalogue et active les commandes implémentées selon les fonctions et options du modèle. Aucune liste séparée de modèles approuvés n'est nécessaire.

- **Commandes :** batterie, ANC/transparence, préréglages EQ, gestes tactiles pris en charge et faible latence. Les choix dépendent du modèle ; la batterie dépend des données transmises par l'appareil.
- **Windows :** découverte dynamique du canal RFCOMM ; authentification par commandes sur MIUI SPP (FD2D), authentification brute sur XiaoAI/SPP standard.
- **Linux :** découverte dynamique du canal RFCOMM via les enregistrements SDP de BlueZ et l’UUID exact du service. L’authentification dépend du service. Seuls les Redmi Buds 6 Play conservent le canal 6 de secours si aucun canal de service n’est résolu. La compatibilité dépend du matériel et du firmware.
- **Preuves matérielles :** Redmi Buds 6 Play est l'appareil de référence, avec utilisation documentée de la batterie/faible latence et vérifications EQ/gestes datées ci-dessous. Cela ne valide pas chaque modèle ; ANC/transparence et authentification brute restent à confirmer sur appareil réel.

Noms, identifiants, images et capacités viennent du [catalogue](../../assets/device_catalog.json). Reconnaître un modèle ne garantit pas une session fonctionnelle. Les commandes dépendent du catalogue ; leur réussite dépend de la connexion et des réponses de l'appareil. Firmware et variantes régionales peuvent différer.

L'EQ personnalisé est reporté et masqué, y compris son préréglage. Les autres fonctions du catalogue ne créent pas automatiquement des commandes.

Mode jeu automatique : GNOME 46 sous Wayland est configuré automatiquement ; reconnectez-vous si demandé. KDE Plasma 6 nécessite `kdotool` avec `kwinscript`, Sway `swaymsg` et Hyprland `hyprctl`. Ces trois nouveaux backends restent à vérifier en session réelle. X11 ne nécessite pas d’extension. [Détails](../wayland.md).

Ce README décrit les sources actuelles ; les anciens paquets peuvent ne pas inclure ces changements. Détails techniques : [capacités](../device-capabilities.md), [authentification par commandes](../command-auth.md), [authentification brute](../raw-auth.md) (en anglais).

MiBudsClient est un projet communautaire indépendant, sans affiliation à Xiaomi.

## Premiers pas

1. Associez et connectez les écouteurs dans les paramètres Bluetooth de l’ordinateur.
2. Téléchargez un paquet adapté depuis [Releases](https://github.com/CesurPolat/MiBudsClient/releases) ou [exécutez depuis les sources](#exécuter-depuis-les-sources).
3. Lancez MiBudsClient. Il recherche les appareils connectés du catalogue et tente automatiquement une connexion de contrôle Bluetooth.
4. Consultez la batterie et les commandes disponibles pour votre modèle. **Paramètres** contient les gestes pris en charge, l'EQ, le contrôle du bruit, le démarrage et la langue.

L’association est gérée par le système ; l’application exige une connexion Bluetooth existante. Une seule instance fonctionne à la fois. Relancer l’application affiche la fenêtre existante. Utilisez la commande de fermeture de la zone de notification pour quitter complètement.

Appuyez sur **F12** pour consulter les journaux. Sous Linux, MiBudsClient doit avoir le focus ; sa console intégrée permet de sélectionner, copier ou effacer les journaux. F12 la referme. Windows conserve sa console séparée. Les journaux restent collectés quand la console est fermée.

## Utilisation

### Faible latence

- **Désactivé :** mode standard.
- **Activé :** faible latence manuelle.
- **Automatique :** activation pour les applications en plein écran. **Inclure** active aussi sans plein écran ; **Exclure** ignore l’application.

**Attendre la fermeture de l’application** conserve la faible latence jusqu’à la fin de l’application détectée. Les règles sont enregistrées séparément pour Windows et Linux.

### Égaliseur

Ouvrez **Paramètres → Égaliseur** pour lire le profil actuel et choisir les préréglages du catalogue de votre modèle. Les changements sont confirmés puis vérifiés par relecture.

**L'EQ personnalisé est prévu pour une version ultérieure.** L'éditeur de bandes et le préréglage personnalisé restent masqués même s'ils figurent au catalogue.

Le changement de profil a été vérifié sur Redmi Buds 6 Play le **2026-10-27** ; cela ne valide pas les autres modèles. Historique technique : [notes EQ](../equalizer.md) (en anglais).

### Gestes tactiles

Dans **Paramètres → Gestes**, chargez les actions. Les sélecteurs gauche et droite sont distincts ; les options viennent de l’entrée exacte du modèle. Les changements sont envoyés immédiatement et indiqués comme enregistrés uniquement après relecture. Ils sont stockés dans les écouteurs. La modification des cycles ANC n’est pas incluse.

La lecture et la réécriture des valeurs existantes ont été vérifiées le **2026-10-26**. Attribuer une autre fonction et la déclencher physiquement restent à vérifier manuellement.

### Notifications et langue

Les notifications affichent la batterie disponible. L’insertion et le retrait sont déduits du drapeau de charge ; aucun capteur distinct de boîtier ou de port n’est lu. À la déconnexion, les dernières valeurs connues sont utilisées.

Cliquer sur une notification restaure la fenêtre. Sous Linux, le serveur doit prendre en charge les actions par défaut. Les sons de notification du système sont supprimés. L’application joue ses propres mélodies aux transitions de charge et une fois à la première connexion réussie des écouteurs de chaque session.

Dans **Paramètres → Langue**, choisissez la langue du système ou une langue précise. Le choix est enregistré et s’applique immédiatement à l’interface, à la zone de notification et aux prochaines notifications. Une langue système non prise en charge utilise l’anglais.

Langues : arabe, chinois (simplifié, Taïwan, Hong Kong), néerlandais, anglais, estonien, finnois, français, allemand, hindi, hongrois, indonésien, italien, japonais, coréen, malais, polonais, portugais (Brésil et Portugal), russe, espagnol, suédois, thaï, turc, ukrainien et vietnamien.

## Exécuter depuis les sources

Il faut Python avec `venv` et `pip`, un adaptateur Bluetooth et des écouteurs déjà connectés via le système.

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

Les notifications Linux utilisent un worker D-Bus Gio/GLib indépendant de l’icône de notification ; un serveur de notifications est requis. Si l’hôte de l’icône disparaît, la fenêtre est restaurée. Clics et images dépendent du serveur. [Intégration](../linux-desktop.md).

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Linux nécessite `bluetoothctl` de BlueZ pour la détection, et PyGObject (`gi`) avec AppIndicator3 ou GTK pour la zone de notification. La détection X11 exige `xprop`, `xwininfo` et `xrandr`. Ces dépendances système ne sont pas installées par `requirements.txt`, qui contient uniquement les paquets Python.

La découverte dynamique des services RFCOMM nécessite aussi `sdptool` de BlueZ, parfois fourni dans un paquet séparé.

## Dépannage

| Problème | Vérifications |
| --- | --- |
| Aucun écouteur trouvé | Activez Bluetooth, vérifiez la connexion dans les paramètres système et réessayez. |
| Délai dépassé | Gardez les écouteurs allumés et proches. Désactivez Bluetooth sur l’ordinateur, attendez 10 secondes et réactivez-le. Si nécessaire, placez les deux écouteurs dans le boîtier, fermez-le 5 secondes, ressortez-les et réessayez. |
| Batterie indisponible | Lancez la vérification après connexion. Les données absentes sont considérées comme inconnues. |
| Erreur de geste ou EQ | Fermez puis rouvrez la section pour relire les données. |
| EQ personnalisé absent | Reporté et masqué dans cette version ; les préréglages pris en charge restent disponibles. |
| Automatique inactif sous Linux | Mode jeu automatique : GNOME 46 sous Wayland est configuré automatiquement ; reconnectez-vous si demandé. KDE Plasma 6 nécessite `kdotool` avec `kwinscript`, Sway `swaymsg` et Hyprland `hyprctl`. Ces trois nouveaux backends restent à vérifier en session réelle. X11 ne nécessite pas d’extension. [Détails](../wayland.md). |
| Clic sur une notification Linux sans effet | Vérifiez les actions par défaut du serveur ou ouvrez depuis la zone de notification. |

Pour [signaler un problème](https://github.com/CesurPolat/MiBudsClient/issues), indiquez la version, le système et la session de bureau, le modèle, les étapes de reproduction et les détails d’erreur.

## Développement

`main.py` initialise et relie les composants. `controllers/` contient Bluetooth, état du périphérique, latence et réglages ; `ui/`, l’interface Flet, la zone de notification et les notifications ; `utils/`, les utilitaires de plateforme. Les ressources sont dans `assets/`, les tests dans `tests/` et la documentation dans `docs/`.

Depuis la racine du dépôt, dans l’environnement de développement :

```sh
python -m unittest discover -s tests
```

Lors des essais de protocole, notez le modèle, le firmware, le système, la méthode de connexion et la fonction. Les tests synthétiques ne prouvent pas la compatibilité matérielle ; les rapports sont des preuves, pas une condition d'activation par modèle. Lisez [AGENTS.md](../../AGENTS.md) avant de modifier le périphérique ou le packaging.

Les traductions sont dans `assets/locales/`. Le [guide de localisation](../localization.md) (en anglais) décrit clés, paramètres et ressources Xiaomi. Mettez `docs/readme/` à jour avec le README anglais lorsque les fonctions ou l’installation changent.

### Créer un exécutable

La CLI Flet doit être disponible dans l’environnement actif. Exécutez sur la plateforme cible :

**Windows — PowerShell**

```powershell
flet pack main.py --icon assets\icon.ico --add-data "assets:assets" --name "MiBudsClient"
```

**Linux**

```sh
flet pack main.py --icon assets/icon.ico --add-data "assets:assets" --name "MiBudsClient" --hidden-import optparse
```

Gardez les ressources d’interface dans `assets/` pour les inclure au paquet. Avant publication, vérifiez avec les écouteurs et lancez l’exécutable deux fois : la seconde instance doit activer la fenêtre existante et se fermer silencieusement.

## Licence

MiBudsClient est distribué sous la [Licence publique générale GNU v3.0](../../LICENSE).
