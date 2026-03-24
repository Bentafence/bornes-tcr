import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import re

# Configuration
st.set_page_config(page_title="TCR RealTime", layout="wide")

CAPACITES = {'P2': 8, 'P4': 15, 'P5': 20, 'P6': 49, 'P8': 5, 'P19': 10, 'P18': 9}
ORDRE = ['P2', 'P4', 'P5', 'P6', 'P8', 'P19', 'P18']
HISTO_SAT = {'P2':'06:55','P4':'07:18','P5':'07:28','P6':'07:38','P8':'07:51','P19':'07:05','P18':'07:13'}

# --- MOTEUR DE RÉCUPÉRATION ROBUSTE ---
@st.cache_data(ttl=15)
def get_live_data():
    try:
        # cloudscraper imite un navigateur pour éviter le blocage IP
        scraper = cloudscraper.create_scraper()
        response = scraper.get("http://www.smartevlab.fr/", timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        data_found = {}
        # On scanne les cartes par ID fixe (méthode la plus rapide)
        mapping = {'P2':1,'P4':3,'P5':4,'P6':5,'P8':6,'P18':11,'P19':12}
        
        for p_name, p_id in mapping.items():
            element = soup.find("div", id=f"count_parking_{p_id}")
            if element:
                # Extraction propre du chiffre uniquement
                val = re.search(r'\d+', element.get_text())
                if val:
                    data_found[p_name] = int(val.group())
        
        return data_found
    except Exception as e:
        return None

# --- LOGIQUE D'AFFICHAGE ---
live_data = get_live_data()
now = datetime.now()
is_monday = now.weekday() == 0

st.title("🔌 TCR Live - Temps Réel")

# 1. TABLEAU DE BORD (Priorité Conduite)
if not live_data:
    st.error("❌ Échec de synchronisation. Tentative de reconnexion automatique...")
    if st.button("Réessayer maintenant"):
        st.cache_data.clear()
        st.rerun()
    live_data = {p: 0 for p in ORDRE} # Évite le crash
else:
    st.success(f"✅ Données Live Synchronisées - {now.strftime('%H:%M:%S')}")

# Tableau compact
summary = []
total_libres = 0
for p in ORDRE:
    dispo = live_data.get(p, 0)
    total_libres += dispo
    h_sat = (datetime.strptime(HISTO_SAT[p], "%H:%M") + timedelta(minutes=-15 if is_monday else 0)).strftime("%H:%M")
    status = "🟢" if dispo > 3 else ("🟠" if dispo > 0 else "🔴")
    summary.append({"Parking": p, "État": status, "Dispo": f"{dispo}/{CAPACITES[p]}", "Saturation": h_sat})

st.table(pd.DataFrame(summary))

# 2. MENU SÉLECTION & GRAPHIQUE PRÉDICTIF
st.header("📈 Graphique de remplissage")
target_p = st.selectbox("Sélectionner un parking :", ["Site Global"] + ORDRE)

# Simulation des courbes
h_axis = [f"{h}h" for h in range(6, 20)]
base_data = [5, 25, 75, 98, 100, 100, 95, 70, 80, 95, 80, 50, 20, 5]
p_reel = ((sum(CAPACITES.values()) - total_libres) / sum(CAPACITES.values())) * 100
reel_curve = [v if h < now.hour else (p_reel if h == now.hour else None) for h, v in zip(range(6, 20), base_data)]

st.line_chart(pd.DataFrame({"Historique": base_data, "Réel": reel_curve}, index=h_axis))

# 3. TABLEAU TEMPS D'ATTENTE (HEURE PAR HEURE)
st.header("⏳ Temps d'attente estimé (min)")
# Création dynamique du tableau d'attente
wait_profiles = {
    "P2/P18/P19": [0, 45, 90, 120, 180, 180, 150, 120, 90, 60, 30],
    "P5/P6/P4": [0, 15, 30, 45, 30, 20, 15, 20, 30, 20, 5]
}

wait_rows = []
for p in ORDRE:
    profile = wait_profiles["P2/P18/P19"] if p in ['P2','P18','P19'] else wait_profiles["P5/P6/P4"]
    row = {"Parking": p}
    for i, h in enumerate(range(7, 18)):
        row[f"{h}h"] = profile[i]
    wait_rows.append(row)

st.dataframe(pd.DataFrame(wait_rows).set_index("Parking"))
