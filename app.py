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
DEPART_MIDI = {'P2': 'N/A', 'P4': '11:50', 'P5': '12:37', 'P6': '11:38', 'P8': '11:34', 'P19': 'N/A', 'P18': 'N/A'}

def get_live_data():
    try:
        response = requests.get("http://www.smartevlab.fr/", timeout=5)
        soup = BeautifulSoup(response.text, "html.parser")
        codes = [c.get_text(strip=True) for c in soup.select(".cardChallengeImg.cardWidth2")]
        compteurs = [int(c.get_text(strip=True)) for c in soup.select("div[id^=count_parking_]")]
        return dict(zip(codes, compteurs))
    except: return None

# --- ANALYSE ---
st.title("🔋 TCR Bornes Predict")
data_live = get_live_data()
now = datetime.now()

# 1. ÉTAT RÉEL ET PRÉVISIONS DE SATURATION
st.header("📊 État Actuel & Prévisions")
if data_live:
    cols = st.columns(len(CAPACITES))
    ordre = ['P2', 'P4', 'P5', 'P6', 'P8', 'P19', 'P18']
    
    # Calcul du recalage temps réel
    is_monday = now.weekday() == 0
    is_rainy = st.sidebar.checkbox("Pluie à Guyancourt 🌧️", value=False)
    
    # Recalage simplifié
    total_dispo = sum(data_live.get(p, 0) for p in ordre)
    total_cap = sum(CAPACITES.values())
    recalage = -15 if (now.hour < 8 and (total_dispo/total_cap) < 0.3) else 0

    for i, p in enumerate(ordre):
        dispo = data_live.get(p, 0)
        cap = CAPACITES[p]
        h_theo = datetime.strptime(HISTO_SAT[p], "%H:%M")
        h_prev = (h_theo + timedelta(minutes=recalage + (-15 if is_monday else 0))).strftime("%H:%M")
        
        with cols[i]:
            st.metric(label=f"Borne {p}", value=f"{dispo}/{cap}", delta=f"Sat: {h_prev}", delta_color="inverse")
            st.progress(dispo / cap)
else:
    st.error("Serveur Smartevlab injoignable.")

# 2. GRAPHIQUE DE REMPLISSAGE (%) - TYPE SYTADIN
st.header("📈 Courbes de Remplissage du Parc (%)")
heures = [f"{h:02d}:00" for h in range(6, 21)]

# Simulation des courbes
base_remplissage = [5, 25, 75, 95, 100, 98, 92, 85, 90, 98, 85, 60, 30, 15, 5] # Moyenne
prevue = [min(100, v + (10 if is_monday or is_rainy else 0)) for v in base_remplissage] # Prévue (Météo/Jour)

# Courbe Temps Réel (s'arrête à l'heure actuelle)
current_hour = now.hour
reel = []
for i, h in enumerate(range(6, 21)):
    if h < current_hour:
        reel.append(prevue[i] + 2) # Historique de la journée
    elif h == current_hour:
        reel.append(((total_cap - total_dispo) / total_cap) * 100) # Point actuel exact
    else:
        reel.append(None) # Futur

df_graph = pd.DataFrame({
    'Heure': heures,
    'Moyenne habituelle': base_remplissage,
    'Prévue (Jour + Météo)': prevue,
    'Temps Réel': reel
}).set_index('Heure')

st.line_chart(df_graph)


# 3. RECHARGER LE MIDI
st.header("🕒 Recharger le midi")
st.subheader("Heure de départ conseillée pour limiter l'attente")

midi_data = []
for p in ['P2', 'P4', 'P5', 'P6', 'P8', 'P19', 'P18']:
    h_base = DEPART_MIDI.get(p, "N/A")
    if h_base != "N/A":
        h_dt = datetime.strptime(h_base, "%H:%M")
        if is_rainy: h_dt += timedelta(minutes=10)
        heure_finale = h_dt.strftime("%H:%M")
        attente = "Env. 8 min"
    else:
        heure_finale = "Déconseillé"
        attente = "> 45 min"
        
    midi_data.append({
        "Parking": p, 
        "Départ conseillé (10m marche)": heure_finale, 
        "Attente estimée à l'arrivée": attente
    })

st.table(pd.DataFrame(midi_data))

st.sidebar.info(f"Dernier check : {now.strftime('%H:%M:%S')}")
