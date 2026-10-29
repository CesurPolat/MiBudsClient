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
| Batterie | Niveaux séparés des deux écouteurs et du boîtier, indicateurs de charge et actualisation manuelle. |
| Faible latence | Mode jeu désactivé, activé ou automatique selon l’application active. |
| Profils sonores | Lecture et modification des préréglages EQ proposés par les écouteurs. |
| Commandes tactiles | Actions gauche et droite : appui simple, double, triple ou prolongé. |
| Notifications | Connexion, déconnexion et changements dans le boîtier, avec batterie et image si disponibles. |
| Zone de notification | Fonctionnement en arrière-plan, restauration de la fenêtre et changement du mode de latence. |
| Au quotidien | Connexion automatique, lancement au démarrage, préférences enregistrées et vérification des mises à jour. |
| Langues | 27 variantes régionales pour 24 langues, changement immédiat et disposition de droite à gauche pour l’arabe. |

## Compatibilité

**Le modèle pris en charge est Redmi Buds 6 Play.** Le catalogue Xiaomi/Redmi contient des noms, images et capacités d’autres produits. Une entrée au catalogue ne garantit pas leur contrôle.

Windows et Linux utilisent une détection Bluetooth propre à chaque plateforme. Sous Linux, la zone de notification et les notifications dépendent du bureau. La détection automatique du plein écran utilise X11 et n’est pas disponible sous Wayland. La validation matérielle et de l’interface sous Linux reste à effectuer.

MiBudsClient est un projet communautaire indépendant, sans affiliation à Xiaomi.

## Premiers pas

1. Associez et connectez les écouteurs dans les paramètres Bluetooth de l’ordinateur.
2. Téléchargez un paquet adapté depuis [Releases](https://github.com/CesurPolat/MiBudsClient/releases) ou [exécutez depuis les sources](#exécuter-depuis-les-sources).
3. Lancez MiBudsClient. Il recherche les appareils connectés du catalogue et tente automatiquement une connexion de contrôle Bluetooth.
4. Consultez la batterie et choisissez le mode de latence. Ouvrez **Paramètres** pour les gestes, l’EQ, le démarrage et la langue.

L’association est gérée par le système ; l’application exige une connexion Bluetooth existante. Une seule instance fonctionne à la fois. Relancer l’application affiche la fenêtre existante. Utilisez la commande de fermeture de la zone de notification pour quitter complètement.

## Utilisation

### Faible latence

- **Désactivé :** mode standard.
- **Activé :** faible latence manuelle.
- **Automatique :** activation pour les applications en plein écran. **Inclure** active aussi sans plein écran ; **Exclure** ignore l’application.

**Attendre la fermeture de l’application** conserve la faible latence jusqu’à la fin de l’application détectée. Les règles sont enregistrées séparément pour Windows et Linux.

### Égaliseur

Ouvrez **Paramètres → Égaliseur** pour lire le profil et les préréglages. Les changements nécessitent un accusé de réception du périphérique puis une relecture de vérification.

L’éditeur personnalisé apparaît uniquement avec des données de bandes valides. Relâcher un curseur envoie un aperçu ; enregistrer mémorise la courbe et réinitialiser demande une courbe plate. Fermez puis rouvrez la section après une erreur ou pour relire les réglages.

Le changement de profil a été vérifié sur Redmi Buds 6 Play le **2026-10-27**. L’appareil testé n’a fourni aucune bande personnalisée : aperçu, enregistrement et réinitialisation personnalisés ne sont donc pas validés sur matériel. [Notes techniques EQ](../equalizer.md) (en anglais).

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

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Linux nécessite `bluetoothctl` de BlueZ pour la détection, et PyGObject (`gi`) avec AppIndicator3 ou GTK pour la zone de notification. La détection X11 exige `xprop`, `xwininfo` et `xrandr`. Ces dépendances système ne sont pas installées par `requirements.txt`, qui contient uniquement les paquets Python.

## Dépannage

| Problème | Vérifications |
| --- | --- |
| Aucun écouteur trouvé | Activez Bluetooth, vérifiez la connexion dans les paramètres système et réessayez. |
| Délai dépassé | Gardez les écouteurs allumés et proches. Désactivez Bluetooth sur l’ordinateur, attendez 10 secondes et réactivez-le. Si nécessaire, placez les deux écouteurs dans le boîtier, fermez-le 5 secondes, ressortez-les et réessayez. |
| Batterie indisponible | Lancez la vérification après connexion. Les données absentes sont considérées comme inconnues. |
| Erreur de geste ou EQ | Fermez puis rouvrez la section pour relire les données. |
| EQ personnalisé absent | Des bandes valides sont nécessaires ; l’appareil testé n’en a pas fourni. Les préréglages peuvent rester disponibles. |
| Automatique inactif sous Linux | Vérifiez X11 et les outils indiqués. La détection Wayland est indisponible. |
| Clic sur une notification Linux sans effet | Vérifiez les actions par défaut du serveur ou ouvrez depuis la zone de notification. |

Pour [signaler un problème](https://github.com/CesurPolat/MiBudsClient/issues), indiquez la version, le système et la session de bureau, le modèle, les étapes de reproduction et les détails d’erreur.

## Développement

`main.py` initialise et relie les composants. `controllers/` contient Bluetooth, état du périphérique, latence et réglages ; `ui/`, l’interface Flet, la zone de notification et les notifications ; `utils/`, les utilitaires de plateforme. Les ressources sont dans `assets/`, les tests dans `tests/` et la documentation dans `docs/`.

Depuis la racine du dépôt, dans l’environnement de développement :

```sh
python -m unittest discover -s tests
```

Les changements de protocole et de constantes exigent aussi des tests avec de vrais Redmi Buds 6 Play. Les tests synthétiques ne prouvent pas la compatibilité. Lisez [AGENTS.md](../../AGENTS.md) avant de modifier le comportement du périphérique ou le packaging.

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
