import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Configuration
st.set_page_config(page_title="TCR Bornes Predict", page_icon="🔋", layout="wide")

# Données Historiques Moyennes (Guyancourt)
HISTO_SAT = {
    'P2': '06:55', 'P18': '07:13', 'P4': '07:18', 
    'P5': '07:28', 'P6': '07:38', 'P8': '07:51', 'P19': '07:05'
}
CAPACITES = {'P2': 8, 'P18': 9, 'P4': 15, 'P5': 20, 'P6': 49, 'P8': 5, 'P19': 10}
DEPART_MIDI = {'P4': '11:50', 'P5': '12:37', 'P6': '11:38', 'P8': '11:34'}

def get_live_data():
    try:
        response = requests.get("http://www.smartevlab.fr/", timeout=5)
        soup = BeautifulSoup(response.text, "html.parser")
        codes = [c.get_text(strip=True) for c in soup.select(".cardChallengeImg.cardWidth2")]
        compteurs = [int(c.get_text(strip=True)) for c in soup.select("div[id^=count_parking_]")]
        return dict(zip(codes, compteurs))
    except: return None

# --- LOGIQUE DE RECALAGE TEMPS RÉEL ---
def calculer_recalage(data_live):
    if not data_live: return 0
    # On compare le remplissage actuel global vs une estimation théorique à cette heure
    # Si bcp de places sont déjà prises, on renvoie un malus en minutes
    remplissage_actuel = sum(CAPACITES[p] - data_live.get(p, 0) for p in CAPACITES if p in data_live)
    # Simple simulation : si remplissage > 70% avant 7h15 -> avance de 15 min
    now = datetime.now()
    if now.hour == 7 and now.minute < 30 and remplissage_actuel > 50:
        return -15 
    return 0

# --- INTERFACE ---
st.title("🔋 TCR Bornes Predict")
data_live = get_live_data()
recalage = calculer_recalage(data_live)

# 1. TABLEAU DE SATURATION
st.header("⚡ Prévisions de Saturation")
if recalage != 0:
    st.warning(f"⚠️ Données recalées : Saturation prévue {abs(recalage)} min plus tôt que d'habitude.")
else:
    st.success("✅ Rythme de remplissage normal constaté.")

sat_data = []
for p in ['P2', 'P19', 'P4', 'P5', 'P6', 'P8', 'P18']:
    h_theo = datetime.strptime(HISTO_SAT.get(p, "08:00"), "%H:%M")
    h_recalée = (h_theo + timedelta(minutes=recalage)).strftime("%H:%M")
    sat_data.append({"Parking": p, "Heure Saturation": h_recalée, "Capacité": CAPACITES.get(p, 0)})

st.table(pd.DataFrame(sat_data))

# 2. GRAPHIQUE TYPE SYTADIN (Simulation)
st.header("📈 Courbe d'Affluence (Type Sytadin)")
# Simulation d'une courbe en cloche pour la journée
heures = [f"{h:02d}:00" for h in range(6, 20)]
index_now = datetime.now().hour - 6
y_moyenne = [10, 30, 80, 100, 100, 95, 90, 85, 95, 100, 80, 50, 20, 10]
y_reel = [val + (5 if index_now > i else 0) for i, val in enumerate(y_moyenne)] # Simu décalage

chart_data = pd.DataFrame({
    'Heure': heures,
    'Moyenne habituelle': y_moyenne,
    'Aujourd\'hui (Estimé)': y_reel
}).set_index('Heure')

st.line_chart(chart_data)

# 3. DÉPART MIDI
st.header("🚶 Stratégie de Midi")
st.write("Heure de départ conseillée (10 min de marche incluse) :")
cols_midi = st.columns(len(DEPART_MIDI))
for i, (p, h) in enumerate(DEPART_MIDI.items()):
    cols_midi[i].metric(p, h, help="Arrivée prévue avec <10min d'attente")

# 4. ÉTAT DES BORNES EN DIRECT
st.header("📊 État des Bornes")
if data_live:
    # Ordre spécifique demandé
    ordre = ['P2', 'P19', 'P4', 'P5', 'P6', 'P8', 'P18']
    total_dispo = 0
    total_places = sum(CAPACITES.values())
    
    for p in ordre:
        dispo = data_live.get(p, 0)
        total_dispo += dispo
        cap = CAPACITES.get(p, 1)
        st.write(f"**{p}** : {dispo} / {cap} libres")
        st.progress(min(dispo / cap, 1.0))
    
    st.subheader(f"Total Site : {total_dispo} places libres sur {total_places}")
else:
    st.error("Impossible de joindre le serveur des bornes.")
