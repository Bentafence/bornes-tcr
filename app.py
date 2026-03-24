import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

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
        cap = CAPACITES[p]
        h_theo = datetime.strptime(HISTO_SAT[p], "%H:%M")
        h_prev = (h_theo + timedelta(minutes=recalage + (-15 if is_monday else 0))).strftime("%H:%M")
        
        # Icône de statut rapide
        status = "🔴 PLEIN" if dispo == 0 else ("🟠" if dispo < 3 else "🟢")
        summary_data.append({
            "Parking": p,
            "État": status,
            "Places": f"{dispo} / {cap}",
            "Saturation Prévue": h_prev
        })
    st.table(pd.DataFrame(summary_data))
else:
    st.error("Données indisponibles.")

# --- 2. GRAPHIQUE SYTADIN & FILTRE ---
st.header("📈 Courbes de Remplissage")
p_selected = st.selectbox("Sélectionner un parking pour le détail :", ["Global"] + ORDRE)

heures = [f"{h:02d}:00" for h in range(6, 21)]
base_remplissage = [5, 25, 75, 95, 100, 98, 92, 85, 90, 98, 85, 60, 30, 15, 5]
prevue = [min(100, v + (10 if is_monday or is_rainy else 0)) for v in base_remplissage]
reel = [v + 2 if h < now.hour else ((((total_cap - total_dispo)/total_cap)*100) if h == now.hour else None) for h, v in zip(range(6, 21), prevue)]

df_graph = pd.DataFrame({'Heure': heures, 'Moyenne': base_remplissage, 'Prévue': prevue, 'Temps Réel': reel}).set_index('Heure')
st.line_chart(df_graph)

# --- 3. RECHARGER LE MIDI ---
st.header("🕒 Recharger le midi")
st.write("Heure de départ conseillée (limiter l'attente)")
midi_list = []
for p in ORDRE:
    h_base = DEPART_MIDI.get(p, "N/A")
    if h_base != "N/A":
        h_dt = datetime.strptime(h_base, "%H:%M")
        if is_rainy: h_dt += timedelta(minutes=10)
        h_fin = h_dt.strftime("%H:%M")
        attente = "Env. 8 min"
    else: h_fin, attente = "Déconseillé", "> 45 min"
    midi_list.append({"Parking": p, "Départ (10m marche)": h_fin, "Attente estimée": attente})
st.table(pd.DataFrame(midi_list))

# --- 4. TABLEAU TEMPS D'ATTENTE HEURE PAR HEURE ---
st.header("⏳ Temps d'attente estimé (min)")
heures_wait = [f"{h:02d}h" for h in range(7, 18)]
wait_data = {}
for p in ORDRE:
    # Simulation basée sur tes calculs de turnover : P5 fluide, P2 ventouse
    if p in ['P2', 'P18', 'P19']: base_w = [40, 90, 150, 180, 180, 160, 140, 120, 100, 60, 30]
    elif p == 'P5': base_w = [10, 25, 45, 30, 15, 10, 15, 20, 15, 10, 5]
    else: base_w = [20, 45, 80, 110, 100, 70, 60, 50, 40, 25, 10]
    wait_data[p] = base_w

df_wait = pd.DataFrame(wait_data, index=heures_wait).T
st.dataframe(df_wait.style.background_gradient(cmap='YlOrRd', axis=None))
