import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import re

# Config
st.set_page_config(page_title="TCR Dashboard", layout="wide")

# Data Statique
CAPACITES = {'P2': 8, 'P4': 15, 'P5': 20, 'P6': 49, 'P8': 5, 'P19': 10, 'P18': 9}
ORDRE = ['P2', 'P4', 'P5', 'P6', 'P8', 'P19', 'P18']
HISTO_SAT = {'P2':'06:55','P4':'07:18','P5':'07:28','P6':'07:38','P8':'07:51','P19':'07:05','P18':'07:13'}

def fetch_data():
    # On essaie 3 sources différentes
    urls = [
        "http://www.smartevlab.fr/",
        "https://api.allorigins.win/get?url=" + requests.utils.quote("http://www.smartevlab.fr/"),
        "https://thingproxy.freeboard.io/fetch/http://www.smartevlab.fr/"
    ]
    
    for url in urls:
        try:
            res = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            if res.status_code == 200:
                # Si proxy AllOrigins, on extrait le JSON
                content = res.json()['contents'] if "allorigins" in url else res.text
                soup = BeautifulSoup(content, "html.parser")
                
                # Extraction ultra-directe par les IDs de Claude
                results = {}
                mapping = {'P2':1,'P4':3,'P5':4,'P6':5,'P8':6,'P18':11,'P19':12}
                for p, idx in mapping.items():
                    el = soup.find("div", id=f"count_parking_{idx}")
                    if el:
                        val = re.findall(r'\d+', el.get_text())
                        results[p] = int(val[0]) if val else 0
                
                if results: return results
        except:
            continue
    return None

# --- UI ---
st.title("🔋 TCR Bornes Predict")
if st.button('🔄 Forcer la mise à jour'):
    st.cache_data.clear()

data_live = fetch_data()
now = datetime.now()
is_monday = now.weekday() == 0
is_rainy = st.sidebar.checkbox("Pluie 🌧️")

# 1. TABLEAU PRINCIPAL
st.header("🚗 État & Saturation")
if not data_live:
    st.error("❌ Site Smartevlab injoignable. Vérifiez votre connexion ou le site source.")
    data_live = {p: 0 for p in ORDRE}
else:
    st.success(f"✅ Mis à jour à {now.strftime('%H:%M:%S')}")

rows = []
for p in ORDRE:
    dispo = data_live.get(p, 0)
    h_theo = datetime.strptime(HISTO_SAT[p], "%H:%M")
    recalage = -15 if (is_monday) else 0
    h_sat = (h_theo + timedelta(minutes=recalage)).strftime("%H:%M")
    
    status = "🟢" if dispo > 2 else ("🟠" if dispo > 0 else "🔴")
    rows.append({"Parking": p, "Statut": status, "Places": f"{dispo}/{CAPACITES[p]}", "Saturation": h_sat})

st.table(pd.DataFrame(rows))

# 2. GRAPHIQUE
st.header("📈 Remplissage global")
base = [5, 25, 75, 95, 100, 98, 92, 85, 90, 98, 85, 60, 30]
# Calcul du point réel si data dispo
total_dispo = sum(data_live.values())
p_reel = ((sum(CAPACITES.values()) - total_dispo) / sum(CAPACITES.values())) * 100
reel = [v if h < now.hour else (p_reel if h == now.hour else None) for h, v in zip(range(6, 19), base)]
st.line_chart(pd.DataFrame({'Moyenne': base, 'Réel': reel}, index=[f"{h}h" for h in range(6, 19)]))

# 3. MIDI
st.header("🕒 Recharger le midi")
st.write("Départ conseillé pour <10min d'attente :")
midi = {"P4":"11:50","P5":"12:37","P6":"11:38","P8":"11:34"}
st.table(pd.DataFrame([{"Parking":k, "Départ":v} for k,v in midi.items()]))
