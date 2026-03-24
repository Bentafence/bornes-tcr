import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd

# Configuration
st.set_page_config(page_title="TCR Dashboard", page_icon="🔋", layout="wide")

# Paramètres du parc
CAPACITES = {'P2': 8, 'P4': 15, 'P5': 20, 'P6': 49, 'P8': 5, 'P19': 10, 'P18': 9}
HISTO_SAT = {'P2': '06:55', 'P4': '07:18', 'P5': '07:28', 'P6': '07:38', 'P8': '07:51', 'P19': '07:05', 'P18': '07:13'}
DEPART_MIDI = {'P4': '11:50', 'P5': '12:37', 'P6': '11:38', 'P8': '11:34'}
ORDRE = ['P2', 'P4', 'P5', 'P6', 'P8', 'P19', 'P18']

def get_live_data():
    try:
        response = requests.get("http://www.smartevlab.fr/", timeout=5)
        soup = BeautifulSoup(response.text, "html.parser")
        codes = [c.get_text(strip=True) for c in soup.select(".cardChallengeImg.cardWidth2")]
        compteurs = [int(c.get_text(strip=True)) for c in soup.select("div[id^=count_parking_]")]
        return dict(zip(codes, compteurs))
    except: return None

data_live = get_live_data()
now = datetime.now()
is_monday = now.weekday() == 0
is_rainy = st.sidebar.checkbox("Pluie (Guyancourt) 🌧️", value=False)

# --- 1. TABLEAU RÉCAPITULATIF "CONDUITE" ---
st.header("🚗 État Actuel & Saturation")
recalage = 0
if data_live:
    total_dispo = sum(data_live.get(p, 0) for p in ORDRE)
    total_cap = sum(CAPACITES.values())
    if now.hour < 8 and (total_dispo/total_cap) < 0.4: recalage = -15

    summary_data = []
    for p in ORDRE:
        dispo = data_live.get(p, 0)
        h_theo = datetime.strptime(HISTO_SAT[p], "%H:%M")
        h_prev = (h_theo + timedelta(minutes=recalage + (-15 if is_monday else 0))).strftime("%H:%M")
        status = "🔴" if dispo == 0 else ("🟠" if dispo < 3 else "🟢")
        summary_data.append({"Parking": p, "Statut": status, "Libre": f"{dispo}/{CAPACITES[p]}", "Saturation": h_prev})
    st.table(pd.DataFrame(summary_data))

# --- 2. GRAPHIQUE SYTADIN RÉACTIF ---
st.header("📈 Courbes de Remplissage")
p_selected = st.selectbox("Détail pour :", ["Global"] + ORDRE)

heures = [f"{h:02d}:00" for h in range(6, 21)]
# Facteur de variation selon le parking
offset = 0 if p_selected == "Global" else (ORDRE.index(p_selected) * 2)
base = [min(100, v + offset) for v in [5, 25, 75, 95, 100, 98, 92, 85, 90, 98, 85, 60, 30, 15, 5]]
prev = [min(100, v + (10 if is_monday or is_rainy else 0)) for v in base]
reel = [v + 2 if h < now.hour else ((((total_cap - total_dispo)/total_cap)*100) if h == now.hour else None) for h, v in zip(range(6, 21), prev)]

df_graph = pd.DataFrame({'Heure': heures, 'Moyenne': base, 'Prévue': prev, 'Réel': reel}).set_index('Heure')
st.line_chart(df_graph)

# --- 3. RECHARGER LE MIDI ---
st.header("🕒 Recharger le midi")
midi_list = []
for p in ORDRE:
    h_base = DEPART_MIDI.get(p, "N/A")
    if h_base != "N/A":
        h_dt = datetime.strptime(h_base, "%H:%M")
        if is_rainy: h_dt += timedelta(minutes=10)
        h_fin = h_dt.strftime("%H:%M")
        att = "Env. 8 min"
    else: h_fin, att = "Déconseillé", "> 45 min"
    midi_list.append({"Parking": p, "Départ": h_fin, "Attente": att})
st.table(pd.DataFrame(midi_list))

# --- 4. TEMPS D'ATTENTE (CORRIGÉ) ---
st.header("⏳ Temps d'attente (min)")
# On utilise st.dataframe sans le style complexe pour éviter l'erreur Jinja2
wait_data = {}
for p in ORDRE:
    if p in ['P2', 'P18', 'P19']: wait_data[p] = [40, 90, 150, 180, 180, 160, 140, 120, 100, 60]
    elif p == 'P5': wait_data[p] = [10, 25, 45, 30, 15, 10, 15, 20, 15, 10]
    else: wait_data[p] = [20, 45, 80, 110, 100, 70, 60, 50, 40, 25]

df_wait = pd.DataFrame(wait_data, index=[f"{h}h" for h in range(7, 17)]).T
st.dataframe(df_wait) # Simple et efficace pour mobile
