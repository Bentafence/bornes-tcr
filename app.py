import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import re

# Configuration
st.set_page_config(page_title="TCR Dashboard", page_icon="🔋", layout="wide")

# Paramètres fixes
CAPACITES = {'P2': 8, 'P4': 15, 'P5': 20, 'P6': 49, 'P8': 5, 'P19': 10, 'P18': 9}
HISTO_SAT = {'P2': '06:55', 'P4': '07:18', 'P5': '07:28', 'P6': '07:38', 'P8': '07:51', 'P19': '07:05', 'P18': '07:13'}
DEPART_MIDI = {'P4': '11:50', 'P5': '12:37', 'P6': '11:38', 'P8': '11:34'}
ORDRE = ['P2', 'P4', 'P5', 'P6', 'P8', 'P19', 'P18']

@st.cache_data(ttl=30)
def get_live_data():
    url = "http://www.smartevlab.fr/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        data_found = {}
        
        # On récupère tous les blocs de parking (les balises 'card')
        cards = soup.find_all("div", class_="card")
        
        for card in cards:
            # On récupère tout le texte du bloc (ex: "P6 48 / 49")
            full_text = card.get_text(" ", strip=True).upper().replace(" ", "")
            
            for p_name in ORDRE:
                # Si le nom du parking (ex: P6) est dans le texte de ce bloc
                if p_name in full_text:
                    # On cherche le premier nombre (la disponibilité)
                    # On regarde d'abord dans les divs de compteur s'ils existent
                    counter_div = card.find("div", id=lambda x: x and 'count_parking_' in x)
                    if counter_div:
                        val = re.findall(r'\d+', counter_div.get_text())
                        if val:
                            data_found[p_name] = int(val[0])
                    else:
                        # Backup : on prend le premier nombre trouvé dans le texte après le nom
                        nums = re.findall(r'\d+', full_text.split(p_name)[-1])
                        if nums:
                            data_found[p_name] = int(nums[0])
        return data_found
    except:
        return {}

# --- LOGIQUE PRINCIPALE ---
raw_data = get_live_data()
data_live = raw_data if raw_data else {p: 0 for p in ORDRE}

now = datetime.now()
is_monday = now.weekday() == 0
is_rainy = st.sidebar.checkbox("Pluie 🌧️", value=False)

st.title("🔋 TCR Bornes Predict")

# 1. TABLEAU RÉCAPITULATIF
st.header("🚗 État Actuel & Saturation")
summary_data = []
total_dispo = 0

for p in ORDRE:
    dispo = data_live.get(p, 0)
    total_dispo += dispo
    
    # Saturation
    h_theo = datetime.strptime(HISTO_SAT[p], "%H:%M")
    recalage = -15 if (now.hour < 8 and dispo == 0 and p not in ['P2', 'P18']) else 0
    h_prev = (h_theo + timedelta(minutes=recalage + (-15 if is_monday else 0))).strftime("%H:%M")
    
    status = "🔴" if dispo == 0 else ("🟠" if dispo < 3 else "🟢")
    summary_data.append({"Parking": p, "Statut": status, "Libre": f"{dispo}/{CAPACITES[p]}", "Saturation": h_prev})

st.table(pd.DataFrame(summary_data))

if not raw_data:
    st.error("⚠️ Erreur de synchronisation avec le site. Vérifie ta connexion.")
else:
    st.success(f"✅ Données synchronisées à {now.strftime('%H:%M')}")

# 2. GRAPHIQUE (SIMULATION RÉACTIVE)
st.header("📈 Remplissage (%)")
p_selected = st.selectbox("Détail :", ["Global"] + ORDRE)

# On ajuste la courbe selon le parking sélectionné
idx = ORDRE.index(p_selected) if p_selected in ORDRE else 0
base = [min(100, v + (idx % 3)) for v in [5, 25, 75, 95, 100, 98, 92, 85, 90, 98, 85, 60, 30, 15, 5]]
prev = [min(100, v + (10 if is_monday or is_rainy else 0)) for v in base]
p_reel = ((sum(CAPACITES.values()) - total_dispo) / sum(CAPACITES.values())) * 100
reel = [v + 1 if h < now.hour else (p_reel if h == now.hour else None) for h, v in zip(range(6, 21), prev)]

st.line_chart(pd.DataFrame({'Heure': range(6, 21), 'Moyenne': base, 'Prévue': prev, 'Réel': reel}).set_index('Heure'))

# 3. MIDI & ATTENTE
st.header("🕒 Recharger le midi")
midi_list = []
for p in ORDRE:
    h_base = DEPART_MIDI.get(p, "N/A")
    if h_base != "N/A":
        h_dt = datetime.strptime(h_base, "%H:%M")
        if is_rainy: h_dt += timedelta(minutes=10)
        h_fin, att = h_dt.strftime("%H:%M"), "Env. 8 min"
    else: h_fin, att = "Déconseillé", "> 45 min"
    midi_list.append({"Parking": p, "Départ": h_fin, "Attente": att})
st.table(pd.DataFrame(midi_list))

st.header("⏳ Attente estimée (min)")
wait_data = {p: ([40, 90, 150, 180, 180, 160, 140, 120, 100, 60] if p in ['P2', 'P18', 'P19'] else ([10, 25, 45, 30, 15, 10, 15, 20, 15, 10] if p == 'P5' else [20, 45, 80, 110, 100, 70, 60, 50, 40, 25])) for p in ORDRE}
st.dataframe(pd.DataFrame(wait_data, index=[f"{h}h" for h in range(7, 17)]).T)
