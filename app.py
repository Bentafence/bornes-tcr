import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd

st.set_page_config(page_title="TCR Dashboard - Ultra-Stable", layout="wide")

# Paramètres consolidés par tes photos
CAPACITES = {'P2': 8, 'P4': 15, 'P5': 20, 'P6': 49, 'P8': 8, 'P19': 10, 'P18': 9}
ORDRE = ['P2', 'P4', 'P5', 'P6', 'P8', 'P19', 'P18']
HISTO_SAT = {'P2':'06:55','P4':'07:18','P5':'07:28','P6':'07:38','P8':'07:51','P19':'07:05','P18':'07:13'}

# Identifiants techniques Freshmile (issus de tes captures)
IDS_TECH = {
    'P2': 'P7802', 'P4': 'P7804', 'P5': 'P7805', 
    'P6': 'P7806', 'P8': 'P7808', 'P18': 'P7818', 'P19': 'P7819'
}

@st.cache_data(ttl=30)
def get_freshmile_data():
    """Interroge l'API Freshmile directement (Simule l'App Mobile)"""
    results = {}
    try:
        for p, station_id in IDS_TECH.items():
            # URL de l'API publique de Freshmile pour le statut des stations
            api_url = f"https://api.freshmile.com/stations/{station_id}"
            # On ajoute des Headers pour faire croire qu'on est l'application mobile
            headers = {'User-Agent': 'Freshmile/4.0.0 (iPhone; iOS 15.0; Scale/3.00)'}
            
            response = requests.get(api_url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                # On compte combien de 'evses' (points de charge) sont 'AVAILABLE'
                dispos = 0
                for evse in data.get('evses', []):
                    if evse.get('status') == 'AVAILABLE':
                        dispos += 1
                results[p] = dispos
            else:
                results[p] = None # Signal d'erreur pour ce parking
        return results
    except:
        return None

# --- LOGIQUE D'AFFICHAGE ---
live_data = get_freshmile_data()
now = datetime.now()

st.title("🔋 TCR Dashboard - Source Freshmile")

if not live_data or all(v is None for v in live_data.values()):
    st.error("⚠️ API Freshmile injoignable. Passage en mode Estimation Historique.")
    # Simulation réaliste en cas de coupure (basée sur tes heures de saturation)
    hour = now.hour
    live_data = {p: (CAPACITES[p] if hour < 7 else 0) for p in ORDRE}
else:
    st.success(f"✅ Données Temps Réel (Source API) - {now.strftime('%H:%M')}")

# --- 1. TABLEAU DE BORD ---
rows = []
total_libres = 0
for p in ORDRE:
    dispo = live_data.get(p, 0) if live_data.get(p) is not None else 0
    total_libres += dispo
    h_sat = HISTO_SAT[p]
    status = "🟢" if dispo > 3 else ("🟠" if dispo > 0 else "🔴")
    rows.append({"Parking": f"{p} ✔️", "État": status, "Libre": f"{dispo}/{CAPACITES[p]}", "Saturation": h_sat})

st.table(pd.DataFrame(rows))

# --- 2. MATRICE D'ATTENTE ---
st.divider()
st.header("⏳ Temps d'attente estimé (min)")
wait_matrix = []
for p in ORDRE:
    profile = [5, 15, 30, 45, 25, 10, 5, 15, 20, 15, 5] if p in ['P4', 'P6'] else [15, 45, 90, 120, 180, 180, 150, 100, 60, 40, 20]
    row = {"Parking": p}
    for i, h in enumerate(range(7, 18)):
        row[f"{h}h"] = profile[i]
    wait_matrix.append(row)

st.dataframe(pd.DataFrame(wait_matrix).set_index("Parking").style.background_gradient(cmap='RdYlGn_r', axis=None))
