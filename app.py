import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import re
import urllib3

# Désactive les avertissements de sécurité dans la console
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Config
st.set_page_config(page_title="TCR Dashboard", layout="wide")

CAPACITES = {'P2': 8, 'P4': 15, 'P5': 20, 'P6': 49, 'P8': 5, 'P19': 10, 'P18': 9}
ORDRE = ['P2', 'P4', 'P5', 'P6', 'P8', 'P19', 'P18']
HISTO_SAT = {'P2':'06:55','P4':'07:18','P5':'07:28','P6':'07:38','P8':'07:51','P19':'07:05','P18':'07:13'}

@st.cache_data(ttl=20)
def fetch_live_data():
    url = "http://www.smartevlab.fr/"
    try:
        # verify=False permet d'ignorer l'erreur de certificat SSL
        res = requests.get(url, timeout=15, verify=False, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(res.text, "html.parser")
        
        final_results = {}
        cards = soup.find_all("div", class_="card")
        
        for card in cards:
            text = card.get_text(" ", strip=True).upper().replace(" ", "")
            for p_name in ORDRE:
                if p_name in text:
                    count_el = card.find("div", id=re.compile(r'count_parking_'))
                    if count_el:
                        val = re.findall(r'\d+', count_el.get_text())
                        if val: final_results[p_name] = int(val[0])
        return final_results
    except Exception as e:
        print(f"Erreur : {e}")
        return None

# --- UI ---
st.title("🔋 TCR Bornes Predict")
if st.button('🔄 Forcer la mise à jour'):
    st.cache_data.clear()

live_data = fetch_live_data()
now = datetime.now()
is_monday = now.weekday() == 0
is_rainy = st.sidebar.checkbox("Pluie 🌧️")

# 1. ÉTAT ACTUEL
st.header("🚗 État & Saturation")
if not live_data:
    st.error("⚠️ Le site source a un problème de sécurité (SSL). Tentative de lecture sécurisée en cours...")
    live_data = {p: 0 for p in ORDRE}
else:
    st.success(f"✅ Données en direct ({now.strftime('%H:%M')})")

rows = []
total_libres = 0
for p in ORDRE:
    dispo = live_data.get(p, 0)
    total_libres += dispo
    h_theo = datetime.strptime(HISTO_SAT[p], "%H:%M")
    recalage = -15 if (is_monday) else 0
    h_sat = (h_theo + timedelta(minutes=recalage)).strftime("%H:%M")
    status = "🟢" if dispo > 2 else ("🟠" if dispo > 0 else "🔴")
    rows.append({"Parking": p, "Statut": status, "Places": f"{dispo}/{CAPACITES[p]}", "Saturation": h_sat})

st.table(pd.DataFrame(rows))
st.write(f"**Disponibilité totale : {total_libres} bornes.**")

# (Garder le reste du code pour le graphique et le midi identique à la V18)
