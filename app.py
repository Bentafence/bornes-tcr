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

@st.cache_data(ttl=20)
def get_live_data():
    url = "http://www.smartevlab.fr/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=12)
        soup = BeautifulSoup(response.text, "html.parser")
        data_found = {}
        
        # Extraction par ID direct (la plus fiable si l'ID est bon)
        # IDs observés : P2=1, P4=3, P5=4, P6=5, P8=6, P18=11, P19=12
        for p_name, p_id_num in [('P2',1),('P4',3),('P5',4),('P6',5),('P8',6),('P18',11),('P19',12)]:
            el = soup.find("div", id=f"count_parking_{p_id_num}")
            if el:
                nums = re.findall(r'\d+', el.get_text())
                if nums: data_found[p_name] = int(nums[0])
        
        # Si on n'a rien trouvé, on tente la recherche par texte (Plan B)
        if not data_found:
            for card in soup.find_all("div", class_="card"):
                txt = card.get_text(" ", strip=True).upper().replace(" ", "")
                for p in ORDRE:
                    if p in txt:
                        c_div = card.find("div", id=lambda x: x and x.startswith('count_parking_'))
                        if c_div:
                            n = re.findall(r'\d+', c_div.get_text())
                            if n: data_found[p] = int(n[0])
        return data_found
    except:
        return {} # On renvoie un dico vide au lieu de None pour éviter le crash

# --- EXECUTION ---
live_raw = get_live_data()
# Sécurité : si live_raw est vide, on crée un dico avec des 0 pour éviter l'AttributeError
data_live = live_raw if live_raw else {p: 0 for p in ORDRE}

now = datetime.now()
is_monday = now.weekday() == 0
is_rainy = st.sidebar.checkbox("Pluie 🌧️", value=False)

st.title("🔋 TCR Bornes Predict")

# 1. TABLEAU RÉCAPITULATIF
st.header("🚗 État Actuel & Saturation")
summary_data = []
total_dispo = 0

for p in ORDRE:
    dispo = data_live.get(p, 0) # Sécurisé par le dico par défaut
    total_dispo += dispo
    h_theo = datetime.strptime(HISTO_SAT[p], "%H:%M")
    recalage = -15 if (now.hour < 8 and dispo == 0 and p not in ['P2', 'P18']) else 0
    h_prev = (h_theo + timedelta(minutes=recalage + (-15 if is_monday else 0))).strftime("%H:%M")
    status = "🔴" if dispo == 0 else ("🟠" if dispo < 3 else "🟢")
    summary_data.append({"Parking": p, "Statut": status, "Libre": f"{dispo}/{CAPACITES[p]}", "Saturation": h_prev})

st.table(pd.DataFrame(summary_data))

if not live_raw:
    st.error("⚠️ Connexion Smartevlab échouée. Chiffres en direct indisponibles.")
else:
    st.success(f"✅ Données à jour ({now.strftime('%H:%M')})")

# 2. GRAPHIQUE
st.header("📈 Remplissage (%)")
p_selected = st.selectbox("Détail :", ["Global"] + ORDRE)
heures = [f"{h:02d}:00" for h in range(6, 21)]
base = [5, 25, 75, 95, 100, 98, 92, 85, 90, 98, 85, 60, 30, 15, 5]
prev = [min(100, v + (10 if is_monday or is_rainy else 0)) for v in base]
p_reel = ((sum(CAPACITES.values()) - total_dispo) / sum(CAPACITES.values())) * 100
reel = [v + 2 if h < now.hour else (p_reel if h == now.hour else None) for h, v in zip(range(6, 21), prev)]
st.line_chart(pd.DataFrame({'Heure': heures, 'Moyenne': base, 'Prévue': prev, 'Réel': reel}).set_index('Heure'))

# 3. RECHARGER LE MIDI
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

# 4. TEMPS D'ATTENTE
st.header("⏳ Attente estimée (min)")
wait_data = {p: ([40, 90, 150, 180, 180, 160, 140, 120, 100, 60] if p in ['P2', 'P18', 'P19'] else ([10, 25, 45, 30, 15, 10, 15, 20, 15, 10] if p == 'P5' else [20, 45, 80, 110, 100, 70, 60, 50, 40, 25])) for p in ORDRE}
st.dataframe(pd.DataFrame(wait_data, index=[f"{h}h" for h in range(7, 17)]).T)
