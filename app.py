import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import re

# Configuration
st.set_page_config(page_title="TCR Bornes Predict", page_icon="🔋", layout="wide")

CAPACITES = {'P2': 8, 'P4': 15, 'P5': 20, 'P6': 49, 'P8': 5, 'P19': 10, 'P18': 9}
HISTO_SAT = {'P2': '06:55', 'P4': '07:18', 'P5': '07:28', 'P6': '07:38', 'P8': '07:51', 'P19': '07:05', 'P18': '07:13'}
DEPART_MIDI = {'P4': '11:50', 'P5': '12:37', 'P6': '11:38', 'P8': '11:34'}
ORDRE = ['P2', 'P4', 'P5', 'P6', 'P8', 'P19', 'P18']

# On cible les IDs de Claude mais avec une extraction de nombres par Regex
MAP_IDS = {
    'P2': 'count_parking_1', 'P4': 'count_parking_3', 'P5': 'count_parking_4',
    'P6': 'count_parking_5', 'P8': 'count_parking_6', 'P18': 'count_parking_11', 'P19': 'count_parking_12'
}

@st.cache_data(ttl=20)
def get_live_data():
    url = "http://www.smartevlab.fr/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        data_found = {}
        
        for p_name, p_id in MAP_IDS.items():
            element = soup.find("div", id=p_id)
            if element:
                # REGEX : On extrait uniquement les chiffres du texte (ignore les espaces, %, etc.)
                raw_text = element.get_text(strip=True)
                numbers = re.findall(r'\d+', raw_text)
                data_found[p_name] = int(numbers[0]) if numbers else 0
            else:
                data_found[p_name] = 0
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

if data_live:
    for p in ORDRE:
        dispo = data_live.get(p, 0)
        total_dispo += dispo
        h_theo = datetime.strptime(HISTO_SAT[p], "%H:%M")
        recalage = -15 if (now.hour < 8 and dispo == 0) and p not in ['P18', 'P2'] else 0
        h_prev = (h_theo + timedelta(minutes=recalage + (-15 if is_monday else 0))).strftime("%H:%M")
        status = "🔴" if dispo == 0 else ("🟠" if dispo < 3 else "🟢")
        summary_data.append({"Parking": p, "Statut": status, "Libre": f"{dispo}/{CAPACITES[p]}", "Saturation": h_prev})
    
    st.table(pd.DataFrame(summary_data))
    st.success(f"✅ Live : {total_dispo} places totales ({now.strftime('%H:%M')})")
else:
    st.error("Serveur Smartevlab injoignable.")

# [Le reste du code pour le graphique et le midi reste identique]
# ...
