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

@st.cache_data(ttl=30)
def get_live_data():
    # Tentative 1 : Direct
    # Tentative 2 : Via Proxy si la 1 échoue
    urls = [
        "http://www.smartevlab.fr/",
        "https://api.allorigins.win/get?url=" + requests.utils.quote("http://www.smartevlab.fr/")
    ]
    
    for url in urls:
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
            response = requests.get(url, headers=headers, timeout=12)
            
            # Si on passe par AllOrigins, le HTML est dans le champ 'contents'
            if "allorigins" in url:
                html = response.json().get('contents', '')
            else:
                html = response.text
                
            soup = BeautifulSoup(html, "html.parser")
            data_found = {}
            
            # Analyse des cartes
            cards = soup.find_all("div", class_="card")
            for card in cards:
                txt = card.get_text(" ", strip=True).upper().replace(" ", "")
                for p in ORDRE:
                    if p in txt:
                        # On cherche l'ID de compteur count_parking_X
                        c_div = card.find("div", id=lambda x: x and 'count_parking_' in x)
                        if c_div:
                            n = re.findall(r'\d+', c_div.get_text())
                            if n: data_found[p] = int(n[0])
            
            if data_found: return data_found
        except:
            continue
    return None

# --- AFFICHAGE ---
live_raw = get_live_data()
data_live = live_raw if live_raw else {p: 0 for p in ORDRE}
now = datetime.now()
is_monday = now.weekday() == 0
is_rainy = st.sidebar.checkbox("Pluie 🌧️", value=False)

st.title("🔋 TCR Bornes Predict")

if not live_raw:
    st.error("⚠️ Site Smartevlab inaccessible (Même via Proxy). Vérifie si le site fonctionne sur ton navigateur.")
else:
    st.success(f"✅ Connecté à {now.strftime('%H:%M')}")

# Tableau "Conduite"
summary = []
total_dispo = 0
for p in ORDRE:
    dispo = data_live.get(p, 0)
    total_dispo += dispo
    h_theo = datetime.strptime(HISTO_SAT[p], "%H:%M")
    recalage = -15 if (now.hour < 8 and dispo == 0 and p not in ['P2', 'P18']) else 0
    h_prev = (h_theo + timedelta(minutes=recalage + (-15 if is_monday else 0))).strftime("%H:%M")
    status = "🔴" if dispo == 0 else ("🟠" if dispo < 3 else "🟢")
    summary.append({"Parking": p, "Statut": status, "Libre": f"{dispo}/{CAPACITES[p]}", "Saturation": h_prev})

st.table(pd.DataFrame(summary))

# Graphique
st.header("📈 Remplissage (%)")
heures = [f"{h:02d}:00" for h in range(6, 21)]
base = [5, 25, 75, 95, 100, 98, 92, 85, 90, 98, 85, 60, 30, 15, 5]
prev = [min(100, v + (10 if is_monday or is_rainy else 0)) for v in base]
p_reel = ((sum(CAPACITES.values()) - total_dispo) / sum(CAPACITES.values())) * 100 if live_raw else None
reel = [v + 1 if h < now.hour else (p_reel if (h == now.hour and live_raw) else None) for h, v in zip(range(6, 21), prev)]
st.line_chart(pd.DataFrame({'Heure': heures, 'Moyenne': base, 'Prévue': prev, 'Réel': reel}).set_index('Heure'))

# Midi
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

# Attente
st.header("⏳ Attente estimée (min)")
wait_data = {p: ([40, 90, 150, 180, 180, 160, 140, 120, 100, 60] if p in ['P2', 'P18', 'P19'] else ([10, 25, 45, 30, 15, 10, 15, 20, 15, 10] if p == 'P5' else [20, 45, 80, 110, 100, 70, 60, 50, 40, 25])) for p in ORDRE}
st.dataframe(pd.DataFrame(wait_data, index=[f"{h}h" for h in range(7, 17)]).T)
