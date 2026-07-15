DOMAIN = "smartx_face"

CONF_SERVICE_HOST = "service_host"
CONF_SERVICE_PORT = "service_port"

CONF_AUTO_OPEN_DOOR = "auto_open_door"

# Choix de la source caméra pour la reconnaissance faciale
CONF_CAMERA_SOURCE = "camera_source"
CAMERA_SOURCE_VTO = "vto"          # la caméra du VTO sert à la fois à la reconnaissance et à la porte
CAMERA_SOURCE_SEPARATE = "separate"  # une caméra IP séparée fait la reconnaissance, le VTO ne gère que la porte

# Caméra séparée (utilisée seulement si CAMERA_SOURCE_SEPARATE)
CONF_CAM_IP = "cam_ip"
CONF_CAM_USERNAME = "cam_username"
CONF_CAM_PASSWORD = "cam_password"
CONF_CAM_CHANNEL = "cam_channel"
CONF_CAM_SUBTYPE = "cam_subtype"

# VTO Dahua : toujours nécessaire pour l'ouverture de porte.
# Si CAMERA_SOURCE_VTO, sert aussi de flux caméra (channel/subtype utilisés).
# Si CAMERA_SOURCE_SEPARATE, channel/subtype ne sont pas demandés (inutiles).
CONF_VTO_IP = "vto_ip"
CONF_VTO_USERNAME = "vto_username"
CONF_VTO_PASSWORD = "vto_password"
CONF_VTO_CHANNEL = "vto_channel"
CONF_VTO_SUBTYPE = "vto_subtype"

# Interphone (appel SIP bidirectionnel PC/HA <-> VTO).
# Nécessite une entrée "VTS" créée manuellement sur le VTO (Système -> Ajouter).
CONF_ENABLE_TALK = "enable_talk"
CONF_TALK_LOCAL_IP = "talk_local_ip"       # IP de la machine hébergeant le container face-service
CONF_TALK_EXTENSION = "talk_extension"     # numéro VTS créé sur le VTO (ex: 9904)
CONF_TALK_PASSWORD = "talk_password"       # mot de passe défini pour cette entrée VTS
CONF_TALK_VTO_EXTENSION = "talk_vto_extension"  # numéro SIP du VTO à appeler (8001 par défaut)

DEFAULT_SERVICE_PORT = 5001
