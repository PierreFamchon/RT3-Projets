# config.py

# --- CONFIGURATION PROXMOX ---
PROXMOX_URL = "https://192.168.1.251:8006"

# IMPORTANT : Le nom de ton noeud Proxmox (celui en haut à gauche dans Datacenter)
PROXMOX_NODE = "pve"

# IMPORTANT : Le format doit être "PVEAPIToken=USER@REALM!ID=SECRET"
# Remplace la partie après le "=" par ton VRAI secret que tu as noté
PROXMOX_TOKEN = "PVEAPIToken=root@pam!guacamole=1d54387c-5975-47f4-bdef-18dce6bc50a7"

# --- CONFIGURATION GUACAMOLE ---
# On utilise localhost (127.0.0.1) pour éviter les problèmes de proxy/firewall
GUACAMOLE_URL = "http://127.0.0.1:8080/guacamole/api"

# Compte ADMIN Guacamole (nécessaire pour créer les connexions pour les autres)
# Assure-toi que ce compte a les droits "Administer system" dans Guacamole
GUAC_ADMIN_USER = "sync.guacamole" 
GUAC_ADMIN_PASS = "Progtr00"

# --- CONFIGURATION RESEAU / ACTIVE DIRECTORY ---
# Ton domaine complet (pour le Ping et la connexion RDP)
DOMAIN_AD = "dom-famchon.rt.lan"


