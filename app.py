import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd

# Configuration
st.set_page_config(page_title="TCR Bornes Predict", page_icon="🔋", layout="wide")

# Paramètres du parc
CAPACITES = {'P2': 8, 'P4': 15, 'P5': 20, 'P6': 49, 'P8': 5, 'P19': 10, 'P18': 9}
HISTO_SAT = {'P2': '06:55', 'P4': '07:18', 'P5': '07:28', 'P6': '07:38', 'P8': '07:51', 'P19': '07:05', 'P18': '07:13'}
DEPART_MIDI = {'P4': '11:50', 'P5': '12:37', 'P6': '11:38', 'P8': '11:34'}
ORDRE = ['P2', 'P4', 'P5', 'P6', 'P8', 'P19', 'P18']

# Mapping Précis des IDs (Basé sur l'analyse de Claude)
# Si un ID change, il suffira de modifier ce dictionnaire
MAP_IDS = {
    'P2': 'count_parking_1',
    'P4': 'count_parking_3',
    'P5': 'count_parking_4',
    'P6': 'count_parking_5',
    'P8': 'count_parking_6',
    'P19': 'count_parking_12', # Hypothèse logique suite au 11
    'P18': 'count_parking_11'  # Confirmé par ton image !
}

@st.cache_data(ttl=30)
def get_live_data():
    url = "http://www.smartevlab.fr/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        data_found = {}
        
        for p_name, p_id in MAP_IDS.items():
            element = soup.find("div", id=p_id)
            if element:
                data_found[p_name] = int(element.get_text(strip=True))
            else:
                data_found[p_name] = 0 # Par défaut si ID non trouvé
        return data_found
    except:
        return None

# --- EXECUTION ---
data_live = get_live_data()
now = datetime.now()
is_monday = now.weekday() == 0
is_rainy = st.sidebar.checkbox("Pluie (Guyancourt) 🌧️", value=False)

st.title("🔋 TCR Bornes Predict")

# 1. TABLEAU RÉCAPITULATIF
st.header("🚗 État Actuel & Saturation")
summary_data = []
total_dispo = 0

for p in ORDRE:
    dispo = data_live.get(p, 0) if data_live else 0
    total_dispo += dispo
    h_theo = datetime.strptime(HISTO_SAT[p], "%H:%M")
    recalage = -15 if (now.hour < 8 and dispo == 0) and p not in ['P18', 'P2'] else 0
    h_prev = (h_theo + timedelta(minutes=recalage + (-15 if is_monday else 0))).strftime("%H:%M")
    status = "🔴" if dispo == 0 else ("🟠" if dispo < 3 else "🟢")
    summary_data.append({"Parking": p, "Statut": status, "Libre": f"{dispo}/{CAPACITES[p]}", "Saturation": h_prev})

st.table(pd.DataFrame(summary_data))

if data_live:
    st.success(f"✅ Live : {total_dispo} places libres au total ({now.strftime('%H:%M')})")
else:
    st.warning("⚠️ Serveur injoignable - Mode prévisions uniquement.")

# --- 2. GRAPHIQUE ---
st.header("📈 Courbe de Remplissage")
p_selected = st.selectbox("Détail pour :", ["Global"] + ORDRE)
heures = [f"{h:02d}:00" for h in range(6, 21)]
base = [5, 25, 75, 95, 100, 98, 92, 85, 90, 98, 85, 60, 30, 15, 5]
prev = [min(100, v + (10 if is_monday or is_rainy else 0)) for v in base]
p_reel = ((sum(CAPACITES.values()) - total_dispo) / sum(CAPACITES.values())) * 100
reel = [v + 2 if h < now.hour else (p_reel if h == now.hour else None) for h, v in zip(range(6, 21), prev)]
st.line_chart(pd.DataFrame({'Heure': heures, 'Moyenne': base, 'Prévue': prev, 'Réel': reel}).set_index('Heure'))

# --- 3. MIDI & ATTENTE ---
st.header("🕒 Recharger le midi")
midi_list = [{"Parking": p, "Départ": (datetime.strptime(DEPART_MIDI[p], "%H:%M") + timedelta(minutes=(10 if is_rainy else 0))).strftime("%H:%M") if p in DEPART_MIDI else "Déconseillé"} for p in ORDRE]
st.table(pd.DataFrame(midi_list))

st.header("⏳ Temps d'attente estimé (min)")
wait_data = {p: ([40, 90, 150, 180, 180, 160, 140, 120, 100, 60] if p in ['P2', 'P18', 'P19'] else ([10, 25, 45, 30, 15, 10, 15, 20, 15, 10] if p == 'P5' else [20, 45, 80, 110, 100, 70, 60, 50, 40, 25])) for p in ORDRE}
st.dataframe(pd.DataFrame(wait_data, index=[f"{h}h" for h in range(7, 17)]).T)
