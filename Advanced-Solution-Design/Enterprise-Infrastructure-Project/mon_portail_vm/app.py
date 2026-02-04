from flask import Flask, render_template, request, redirect, session, url_for
import requests
import config  # On importe le fichier config.py
import json
import time
import urllib3

# Désactive les avertissements SSL (car Proxmox a un certificat auto-signé)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
app.secret_key = "SECRET_KEY_SUPER_SECURISEE"  # Nécessaire pour les sessions

# --- CONFIGURATION PROXY (FIX CRITIQUE) ---
# Empêche Python d'utiliser le proxy système pour les appels locaux
NO_PROXY = {
    "http": None,
    "https": None,
}

# --- FONCTIONS API ---

def get_guacamole_token(username, password):
    """Authentifie l'utilisateur sur Guacamole et récupère son token"""
    url = f"{config.GUACAMOLE_URL}/tokens"
    data = {"username": username, "password": password}
    
    print(f"\n--- [DEBUG] AUTHENTIFICATION ({username}) ---")
    try:
        resp = requests.post(url, data=data, proxies=NO_PROXY)
        if resp.status_code == 200:
            token = resp.json().get("authToken")
            print("Auth Réussie.")
            return token
        else:
            print(f"Echec Auth: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"CRASH AUTH: {e}")
    return None

def get_admin_guac_token():
    """Récupère le token de l'administrateur technique"""
    return get_guacamole_token(config.GUAC_ADMIN_USER, config.GUAC_ADMIN_PASS)

def proxmox_get_vms(username_prefix):
    """Liste les VMs Proxmox de l'utilisateur"""
    url = f"{config.PROXMOX_URL}/api2/json/nodes/{config.PROXMOX_NODE}/qemu"
    headers = {"Authorization": config.PROXMOX_TOKEN}
    
    try:
        resp = requests.get(url, headers=headers, verify=False, proxies=NO_PROXY)
        if resp.status_code == 200:
            data = resp.json().get('data', [])
            # Filtre : On garde les VMs qui commencent par "user-"
            return [vm for vm in data if vm.get('name', '').startswith(username_prefix)]
    except Exception as e:
        print(f"Erreur Listing Proxmox: {e}")
    return []

def create_guacamole_connection(vm_name, vm_address, rdp_user, rdp_pass):
    """Crée la connexion dans Guacamole via l'API Admin"""
    admin_token = get_admin_guac_token()
    if not admin_token:
        print("Impossible d'avoir le token Admin Guac")
        return False

    url = f"{config.GUACAMOLE_URL}/session/data/mysql/connections?token={admin_token}"
    
    # Configuration RDP
    payload = {
        "name": vm_name, # Nom affiché dans Guacamole
        "protocol": "rdp",
        "parameters": {
            "hostname": vm_address, # Ici on mettra le Nom de Domaine (FQDN)
            "username": rdp_user,   # ${GUAC_USERNAME} pour utiliser le user connecté
            "password": rdp_pass,   # ${GUAC_PASSWORD} pour utiliser le pass connecté
            "security": "any",
            "ignore-cert": "true",
            "resize-method": "display-update" # Meilleure gestion d'écran
        }
    }
    
    try:
        resp = requests.post(url, json=payload, proxies=NO_PROXY)
        if resp.status_code == 200:
            print(f"Connexion Guacamole créée pour {vm_name} -> {vm_address}")
            return True
        else:
            print(f"Erreur Création Guac: {resp.text}")
    except Exception as e:
        print(f"Crash Création Guac: {e}")
    return False

def create_vm_logic(user_prefix, template_id, vm_name_suffix):
    """Logique : Clone -> Start -> DNS -> Guacamole"""
    
    # 1. Calculer le prochain ID libre
    url_list = f"{config.PROXMOX_URL}/api2/json/nodes/{config.PROXMOX_NODE}/qemu"
    headers = {"Authorization": config.PROXMOX_TOKEN}
    
    try:
        vms = requests.get(url_list, headers=headers, verify=False, proxies=NO_PROXY).json()['data']
        ids = [int(vm['vmid']) for vm in vms if str(vm.get('vmid')).isdigit()]
        new_id = max(ids) + 1 if ids else 150
    except:
        new_id = 150
    
    full_name = f"{user_prefix}-{vm_name_suffix}"
    print(f"Création VM {new_id} : {full_name}")
    
    # 2. Cloner le Template
    url_clone = f"{config.PROXMOX_URL}/api2/json/nodes/{config.PROXMOX_NODE}/qemu/{template_id}/clone"
    payload = {"newid": new_id, "name": full_name}
    requests.post(url_clone, headers=headers, data=payload, verify=False, proxies=NO_PROXY)
    
    # 3. Démarrer la VM
    time.sleep(2)
    url_start = f"{config.PROXMOX_URL}/api2/json/nodes/{config.PROXMOX_NODE}/qemu/{new_id}/status/start"
    requests.post(url_start, headers=headers, verify=False, proxies=NO_PROXY)
    
    print("VM démarrée via Proxmox.")
    
    # 4. Construction du Nom de Domaine (FQDN)
    # Grâce à ton DNS bien configuré, on n'a plus besoin d'attendre l'IP !
    vm_fqdn = f"{full_name}.{config.DOMAIN_AD}"
    print(f"Liaison Guacamole vers : {vm_fqdn}")
    
    # 5. Création de la connexion Guacamole
    # On utilise des variables magiques pour que l'utilisateur n'ait pas à retaper son mot de passe
    create_guacamole_connection(full_name, vm_fqdn, "${GUAC_USERNAME}", "${GUAC_PASSWORD}")

    return new_id

# --- ROUTES WEB ---

@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        
        token = get_guacamole_token(user, pwd)
        if token:
            session['user'] = user
            session['token'] = token
            return redirect(url_for('dashboard'))
        else:
            error = "Identifiants invalides."
            
    return render_template('login.html', error=error)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session: return redirect(url_for('login'))
    
    my_vms = proxmox_get_vms(session['user'])
    return render_template('dashboard.html', vms=my_vms, user=session['user'])

@app.route('/create_vm', methods=['POST'])
def create_vm():
    if 'user' not in session: return redirect(url_for('login'))
    
    vm_suffix = request.form['vm_name']
    template_id = request.form['template_id']
    
    create_vm_logic(session['user'], template_id, vm_suffix)
    
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)


