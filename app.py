import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import re

# Désactivation totale des alertes de sécurité
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="TCR Bornes Predict", layout="wide")

CAPACITES = {'P2': 8, 'P4': 15, 'P5': 20, 'P6': 49, 'P8': 5, 'P19': 10, 'P18': 9}
ORDRE = ['P2', 'P4', 'P5', 'P6', 'P8', 'P19', 'P18']
HISTO_SAT = {'P2':'06:55','P4':'07:18','P5':'07:28','P6':'07:38','P8':'07:51','P19':'07:05','P18':'07:13'}

@st.cache_data(ttl=30)
def fetch_data():
    # Utilisation du HTTP simple pour contourner le SSL foireux
    url = "http://www.smartevlab.fr/"
    try:
        # Timeout court pour ne pas bloquer l'appli
        res = requests.get(url, timeout=8, verify=False, headers={'User-Agent': 'Mozilla/5.0'})
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            results = {}
            cards = soup.find_all("div", class_="card")
            for card in cards:
                txt = card.get_text(" ", strip=True).upper().replace(" ", "")
                for p in ORDRE:
                    if p in txt:
                        c_el = card.find("div", id=re.compile(r'count_parking_'))
                        if c_el:
                            n = re.findall(r'\d+', c_el.get_text())
                            if n: results[p] = int(n[0])
            if results: return results
    except:
        pass
    return None

# --- LOGIQUE ---
raw_live = fetch_data()
now = datetime.now()
is_monday = now.weekday() == 0

# Système de secours si le site est bloqué
if not raw_live:
    st.error("🔌 Site source inaccessible (SSL/Timeout). Passage en mode 'Estimation historique'.")
    # On simule des données crédibles : le matin c'est plein, le midi ça se libère un peu
    hour = now.hour
    if hour < 7: data_live = {p: CAPACITES[p] for p in ORDRE}
    elif hour < 12: data_live = {p: 0 for p in ORDRE}
    elif hour < 14: data_live = {'P2':0, 'P4':2, 'P5':5, 'P6':12, 'P8':1, 'P19':0, 'P18':1}
    else: data_live = {p: 0 for p in ORDRE}
else:
    data_live = raw_live
    st.success(f"✅ Live OK ({now.strftime('%H:%M')})")

# --- UI TABLEAU ---
st.header("🚗 État & Saturation")
summary = []
for p in ORDRE:
    dispo = data_live.get(p, 0)
    h_theo = datetime.strptime(HISTO_SAT[p], "%H:%M")
    h_sat = (h_theo + timedelta(minutes=-15 if is_monday else 0)).strftime("%H:%M")
    status = "🟢" if dispo > 2 else ("🟠" if dispo > 0 else "🔴")
    summary.append({"Parking": p, "Statut": status, "Places": f"{dispo}/{CAPACITES[p]}", "Saturation": h_sat})

st.table(pd.DataFrame(summary))

# --- GRAPHIQUE ---
st.header("📈 Remplissage (%)")
base_curves = [5, 25, 75, 95, 100, 98, 92, 85, 90, 98, 85, 60, 30]
total_libres = sum(data_live.values())
p_reel = ((sum(CAPACITES.values()) - total_libres) / sum(CAPACITES.values())) * 100
reel_curve = [v if h < now.hour else (p_reel if h == now.hour else None) for h, v in zip(range(6, 19), base_curves)]
st.line_chart(pd.DataFrame({'Moyenne': base_curves, 'Réel': reel_curve}, index=[f"{h}h" for h in range(6, 19)]))

# --- ATTENTE ---
st.header("⏳ Temps d'attente (min)")
wait_data = {p: [40, 90, 150, 180, 180, 160, 140, 120, 100, 60] for p in ORDRE}
# On affiche un tableau condensé pour la conduite
st.dataframe(pd.DataFrame(wait_data, index=[f"{h}h" for h in range(7, 17)]).T)
