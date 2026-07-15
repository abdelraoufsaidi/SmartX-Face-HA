# SMARTX Face Recognition — intégration Home Assistant

Intégration Home Assistant pour le contrôle d'accès par reconnaissance faciale
SMARTX, connectée à une caméra Dahua VTO (intercom vidéo) : ouverture de porte
et présence par personne, avec panel d'enrôlement intégré.

## ⚠️ Prérequis

Cette intégration ne fait **que piloter** un service séparé qui exécute la
reconnaissance faciale (RTSP + InsightFace). Ce service doit tourner à part
(container Docker recommandé) et être accessible sur le réseau.

Voir : [SmartX-Face-Service](https://github.com/abdelraoufsaidi/SmartX-Face-Service)

## Installation

### Via HACS (recommandé)

1. HACS → menu (⋮) → **Dépôts personnalisés**
2. Ajoute l'URL de ce repo, catégorie **Intégration**
3. Recherche "SMARTX Face Recognition" dans HACS → Installer
4. Redémarre Home Assistant

### Installation manuelle

```bash
cd /config/custom_components
git clone https://github.com/abdelraoufsaidi/SmartX-Face-HA.git temp
mv temp/custom_components/smartx_face .
rm -rf temp
```

Redémarre Home Assistant.

## Configuration

**Paramètres → Appareils et services → Ajouter une intégration → SMARTX Face Recognition**

1. **Étape 1** : adresse et port du container SmartX-Face-Service (par défaut port `5001`)
2. **Étape 2** : identifiants du VTO Dahua (IP, utilisateur, mot de passe, channel, subtype)
   — le VTO fournit à la fois le flux caméra et la commande d'ouverture de porte.

## Ce que ça ajoute dans Home Assistant

- **Panel latéral "SMARTX Enrôlement"** : interface web (flux caméra live +
  boutons Démarrer/Capturer/Terminer) pour enrôler de nouveaux visages sans
  toucher au code.
- **`button.smartx_ouvrir_la_porte`** : déclenche l'ouverture de porte via le VTO.
- **Capteurs de présence par personne** (`binary_sensor.presence_<nom>`) —
  publiés automatiquement en MQTT Discovery par le service, groupés sous
  l'appareil "SMARTX Face Recognition".

## Exemple d'automatisation

```yaml
automation:
  - alias: "Ouvrir la porte si Nabil est reconnu"
    trigger:
      - platform: state
        entity_id: binary_sensor.presence_nabil
        to: "on"
    action:
      - service: button.press
        target:
          entity_id: button.smartx_ouvrir_la_porte
```

## Licence

MIT
