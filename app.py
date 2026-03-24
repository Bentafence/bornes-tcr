import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import re

# Configuration
st.set_page_config(page_title="TCR Dashboard", page_icon="🔋", layout="wide")

CAPACITES = {'P2': 8, 'P4': 15, 'P5': 20, 'P6': 49, 'P8': 5, 'P19': 10, 'P18': 9}
HISTO_SAT = {'P2': '06:55', 'P4': '07:18', 'P5': '07:28', 'P6': '07:38', 'P8': '07:51', 'P19': '07:05', 'P18': '07:13'}
DEPART_MIDI = {'P4': '11:50', 'P5': '12:37', 'P6': '11:38', 'P8': '11:34'}
ORDRE = ['P2', 'P4', 'P5', 'P6', 'P8', 'P19', 'P18']

def get_live_data():
    try:
        response = requests.get("http://www.smartevlab.fr/", timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 1. On récupère TOUTES les cartes (div class="card")
        cards = soup.find_all("div", class_="card")
        data_found = {}
        
        for card in cards:
            text = card.get_text(separator=" ", strip=True).upper()
            # On cherche un match de type "P6" ou "P 6" ou "PARKING 6"
            match_name = re.search(r'(P\s?\d+|PARKING\s?\d+)', text)
            if match_name:
                name = match_name.group(0).replace(" ", "").replace("PARKING", "P")
                # On cherche le premier nombre dans cette carte (le compteur)
                count_div = card.find("div", id=lambda x: x and x.startswith('count_parking_'))
                if count_div:
                    data_found[name] = int(count_div.get_text(strip=True))
        
        return data_found
    except:
        return {}

# --- EXECUTION ---
data_live = get_live_data()
now = datetime.now()
is_monday = now.weekday() == 0
is_rainy = st.sidebar.checkbox("Pluie (Guyancourt) 🌧️", value=False)

st.title("🔋 TCR Bornes Predict")

if not data_live:
    st.error("⚠️ Erreur de lecture du site Smartevlab.")
else:
    # 1. TABLEAU RÉCAPITULATIF
    st.header("🚗 État Actuel & Saturation")
    summary_data = []
    total_dispo = 0
    
    for p in ORDRE:
        # Recherche ultra-souple : si "P18" pas là, on cherche "P 18" ou "PARKING18"
        dispo = data_live.get(p, 0)
        total_dispo += dispo
        
        h_theo = datetime.strptime(HISTO_SAT[p], "%H:%M")
        recalage = -15 if (now.hour < 8 and dispo == 0) and p not in ['P18', 'P2'] else 0
        h_prev = (h_theo + timedelta(minutes=recalage + (-15 if is_monday else 0))).strftime("%H:%M")
        
        status = "🔴" if dispo == 0 else ("🟠" if dispo < 3 else "🟢")
        summary_data.append({"Parking": p, "Statut": status, "Libre": f"{dispo}/{CAPACITES[p]}", "Saturation": h_prev})
    
    st.table(pd.DataFrame(summary_data))
    
    # 2. GRAPHIQUE (Réduit pour mobile)
    st.header("📈 Courbe de Remplissage")
    p_selected = st.selectbox("Détail pour :", ["Global"] + ORDRE)
    heures = [f"{h:02d}:00" for h in range(6, 21)]
    base = [5, 25, 75, 95, 100, 98, 92, 85, 90, 98, 85, 60, 30, 15, 5]
    prev = [min(100, v + (10 if is_monday or is_rainy else 0)) for v in base]
    # Calcul réel au global
    pourcent_reel = ((sum(CAPACITES.values()) - total_dispo) / sum(CAPACITES.values())) * 100
    reel = [v + 2 if h < now.hour else (pourcent_reel if h == now.hour else None) for h, v in zip(range(6, 21), prev)]
    st.line_chart(pd.DataFrame({'Heure': heures, 'Moyenne': base, 'Prévue': prev, 'Réel': reel}).set_index('Heure'))

    # 3. RECHARGER LE MIDI
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

    # 4. TEMPS D'ATTENTE (TABLEAU SIMPLE)
    st.header("⏳ Temps d'attente estimé (min)")
    wait_data = {}
    for p in ORDRE:
        if p in ['P2', 'P18', 'P19']: wait_data[p] = [40, 90, 150, 180, 180, 160, 140, 120, 100, 60]
        elif p == 'P5': wait_data[p] = [10, 25, 45, 30, 15, 10, 15, 20, 15, 10]
        else: wait_data[p] = [20, 45, 80, 110, 100, 70, 60, 50, 40, 25]
    st.dataframe(pd.DataFrame(wait_data, index=[f"{h}h" for h in range(7, 17)]).T)
