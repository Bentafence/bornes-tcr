import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import re

# Configuration ultra-compacte pour mobile
st.set_page_config(page_title="TCR Dashboard", layout="wide")

# Paramètres fixes (Ton expertise terrain)
CAPACITES = {'P2': 8, 'P4': 15, 'P5': 20, 'P6': 49, 'P8': 5, 'P19': 10, 'P18': 9}
ORDRE = ['P2', 'P4', 'P5', 'P6', 'P8', 'P19', 'P18']
HISTO_SAT = {'P2':'06:55','P4':'07:18','P5':'07:28','P6':'07:38','P8':'07:51','P19':'07:05','P18':'07:13'}

@st.cache_data(ttl=15)
def get_live_data():
    try:
        scraper = cloudscraper.create_scraper()
        res = scraper.get("http://www.smartevlab.fr/", timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        data = {}
        # Mapping IDs Claude
        mapping = {'P2':1,'P4':3,'P5':4,'P6':5,'P8':6,'P18':11,'P19':12}
        for p, idx in mapping.items():
            el = soup.find("div", id=f"count_parking_{idx}")
            if el:
                val = re.search(r'\d+', el.get_text())
                if val: data[p] = int(val.group())
        return data
    except:
        return None

# --- LOGIQUE ---
live_data = get_live_data()
now = datetime.now()
is_monday = now.weekday() == 0

# --- 1. ÉTAT ACTUEL (Tableau Conduite) ---
st.header("🚗 État Actuel & Saturation")
if not live_data:
    st.error("⚠️ Direct indisponible (Mode Estimation)")
    live_data = {p: 0 for p in ORDRE} # Secours
else:
    st.success(f"✅ Live OK ({now.strftime('%H:%M')})")

summary = []
total_libres = 0
for p in ORDRE:
    dispo = live_data.get(p, 0)
    total_libres += dispo
    h_sat = (datetime.strptime(HISTO_SAT[p], "%H:%M") + timedelta(minutes=-15 if is_monday else 0)).strftime("%H:%M")
    status = "🔴" if dispo == 0 else ("🟠" if dispo < 3 else "🟢")
    summary.append({"Parking": p, "État": status, "Libre": f"{dispo}/{CAPACITES[p]}", "Saturation": h_sat})

st.table(pd.DataFrame(summary))

# --- 2. GRAPHIQUE AVEC MENU SÉLECTION ---
st.header("📈 Courbes de Remplissage")
p_selected = st.selectbox("Sélectionner un parking particulier :", ["Site Global"] + ORDRE)

# On simule la courbe Sytadin (Moyenne historique)
h_axis = [f"{h}h" for h in range(6, 19)]
base_curves = [5, 25, 75, 95, 100, 100, 95, 80, 85, 98, 90, 60, 30]

# Calcul du point réel (en %)
p_reel_total = ((sum(CAPACITES.values()) - total_libres) / sum(CAPACITES.values())) * 100
reel_curve = [v if h < now.hour else (p_reel_total if h == now.hour else None) for h, v in zip(range(6, 19), base_curves)]

st.line_chart(pd.DataFrame({'Historique': base_curves, 'Temps Réel': reel_curve}, index=h_axis))

# --- 3. TABLEAU TEMPS D'ATTENTE (Heure par heure) ---
st.header("⏳ Temps d'attente estimé (min)")
# Matrice simplifiée selon le type de parking
wait_rows = []
for p in ORDRE:
    # Profil 'lent' (P2, P18, P19) vs 'dynamique' (P5, P6)
    wait_profile = [10, 40, 80, 120, 180, 180, 150, 100, 60, 40, 15] if p in ['P2','P18','P19'] else [5, 15, 30, 45, 30, 15, 10, 20, 25, 15, 5]
    row = {"Parking": p}
    for i, h in enumerate(range(7, 18)):
        row[f"{h}h"] = wait_profile[i]
    wait_rows.append(row)

st.dataframe(pd.DataFrame(wait_rows).set_index("Parking"))

st.info("💡 Astuce : Entre 12h15 et 12h45, le P6 a le turnover le plus élevé.")
