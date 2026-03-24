import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import re

# Configuration
st.set_page_config(page_title="TCR Dashboard Pro", layout="wide")

# Paramètres du parc
CAPACITES = {'P2': 8, 'P4': 15, 'P5': 20, 'P6': 49, 'P8': 8, 'P19': 10, 'P18': 9}
ORDRE = ['P2', 'P4', 'P5', 'P6', 'P8', 'P19', 'P18']
HISTO_SAT = {'P2':'06:55','P4':'07:18','P5':'07:28','P6':'07:38','P8':'07:51','P19':'07:05','P18':'07:13'}

@st.cache_data(ttl=20)
def get_live_data():
    try:
        scraper = cloudscraper.create_scraper()
        res = scraper.get("http://www.smartevlab.fr/", timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        data = {}
        
        cards = soup.find_all("div", class_="card")
        for card in cards:
            text = card.get_text(" ", strip=True).upper().replace(" ", "")
            for p in ORDRE:
                # Détection hybride (Nom ou Fosse au loup)
                if p in text or (p == 'P19' and 'FOSSEAULOUP' in text):
                    count_el = card.find("div", id=re.compile(r'count_parking_'))
                    if count_el:
                        val = re.findall(r'\d+', count_el.get_text())
                        if val: data[p] = int(val[0])
        return data
    except:
        return None

# --- LOGIQUE ---
live_data = get_live_data()
now = datetime.now()
is_monday = now.weekday() == 0

st.title("🔋 TCR Dashboard - Live & Predict")

# --- 1. TABLEAU DE BORD ---
st.header("🚗 État des bornes")
if not live_data:
    st.error("🔌 Source Smartevlab injoignable. Mode Estimation.")
    live_data = {p: 0 for p in ORDRE}
else:
    st.success(f"✅ Synchronisation OK ({now.strftime('%H:%M')})")

summary_rows = []
total_libres = 0
for p in ORDRE:
    dispo = live_data.get(p, 0)
    total_libres += dispo
    h_sat = (datetime.strptime(HISTO_SAT[p], "%H:%M") + timedelta(minutes=-15 if is_monday else 0)).strftime("%H:%M")
    
    # Statut visuel
    status = "🟢" if dispo > 3 else ("🟠" if dispo > 0 else "🔴")
    
    # Label avec badge de vérification Freshmile
    if p in ['P2', 'P4', 'P8', 'P18', 'P19']:
        label = f"{p} ✔️"
    else:
        # P5 et P6 n'ont pas encore leurs IDs Freshmile
        label = f"{p} 🔍" if dispo > 0 else f"{p} ⚠️"
        
    summary_rows.append({"Parking": label, "Statut": status, "Places": f"{dispo}/{CAPACITES[p]}", "Saturation": h_sat})

st.table(pd.DataFrame(summary_rows))

# --- 2. ANALYSE ET SÉLECTION ---
st.divider()
st.subheader("📈 Courbe de Remplissage")
p_select = st.selectbox("Sélectionner un parking pour le graphique :", ["Vue Globale"] + ORDRE)

h_axis = [f"{h}h" for h in range(6, 20)]
hist_vals = [5, 25, 75, 95, 100, 100, 95, 80, 85, 98, 90, 60, 20, 5]
p_occ_reel = ((sum(CAPACITES.values()) - total_libres) / sum(CAPACITES.values())) * 100
reel_vals = [v if h < now.hour else (p_occ_reel if h == now.hour else None) for h, v in zip(range(6, 20), hist_vals)]

st.line_chart(pd.DataFrame({'Historique': hist_vals, 'Réel': reel_vals}, index=h_axis))

# --- 3. MATRICE D'ATTENTE (HEURE PAR HEURE) ---
st.divider()
st.header("⏳ Temps d'attente estimé (min)")
wait_matrix = []
for p in ORDRE:
    # Profil P4, P5, P6 (Turnover plus élevé) vs P2, P18, P19 (Sédentaires)
    if p in ['P4', 'P5', 'P6']:
        profile = [5, 15, 30, 45, 30, 15, 10, 20, 25, 15, 5]
    else:
        profile = [15, 45, 90, 120, 180, 180, 150, 100, 60, 40, 20]
    
    row = {"Parking": p}
    for i, h in enumerate(range(7, 18)):
        row[f"{h}h"] = profile[i]
    wait_matrix.append(row)

st.dataframe(pd.DataFrame(wait_matrix).set_index("Parking").style.background_gradient(cmap='RdYlGn_r', axis=None))
