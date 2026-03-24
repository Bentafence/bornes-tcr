import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import re

# Config
st.set_page_config(page_title="TCR Dashboard", layout="wide")

# Paramètres du parc
CAPACITES = {'P2': 8, 'P4': 15, 'P5': 20, 'P6': 49, 'P8': 5, 'P19': 10, 'P18': 9}
ORDRE = ['P2', 'P4', 'P5', 'P6', 'P8', 'P19', 'P18']
HISTO_SAT = {'P2':'06:55','P4':'07:18','P5':'07:28','P6':'07:38','P8':'07:51','P19':'07:05','P18':'07:13'}

@st.cache_data(ttl=30)
def fetch_live_data():
    # Utilisation d'un proxy pour éviter le blocage Streamlit
    proxy_url = "https://api.allorigins.win/get?url=" + requests.utils.quote("http://www.smartevlab.fr/")
    try:
        res = requests.get(proxy_url, timeout=15)
        content = res.json()['contents']
        soup = BeautifulSoup(content, "html.parser")
        
        final_results = {}
        # On attrape TOUS les blocs de parking
        cards = soup.find_all("div", class_="card")
        
        for card in cards:
            text = card.get_text(" ", strip=True).upper().replace(" ", "")
            # On identifie le parking par son nom dans le texte
            for p_name in ORDRE:
                if p_name in text:
                    # On a le bon bloc, on cherche le chiffre dedans
                    # On cible l'élément qui contient "count_parking"
                    count_el = card.find("div", id=re.compile(r'count_parking_'))
                    if count_el:
                        val = re.findall(r'\d+', count_el.get_text())
                        if val:
                            final_results[p_name] = int(val[0])
        return final_results
    except:
        return None

# --- UI ---
st.title("🔋 TCR Bornes Predict")
if st.button('🔄 Forcer la mise à jour'):
    st.cache_data.clear()

live_data = fetch_live_data()
now = datetime.now()
is_monday = now.weekday() == 0
is_rainy = st.sidebar.checkbox("Pluie 🌧️")

# 1. ÉTAT ACTUEL & SATURATION
st.header("🚗 État & Saturation")
if not live_data:
    st.warning("⚠️ Synchronisation en cours ou site source ralenti. Affichage des prévisions...")
    # On initialise avec des 0 pour que le tableau s'affiche quand même
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

# 2. GRAPHIQUE
st.header("📈 Remplissage global (%)")
base_curves = [5, 25, 75, 95, 100, 98, 92, 85, 90, 98, 85, 60, 30]
# Calcul du point réel en %
p_reel = ((sum(CAPACITES.values()) - total_libres) / sum(CAPACITES.values())) * 100
reel_curve = [v if h < now.hour else (p_reel if h == now.hour else None) for h, v in zip(range(6, 19), base_curves)]

st.line_chart(pd.DataFrame({'Moyenne': base_curves, 'Réel': reel_curve}, index=[f"{h}h" for h in range(6, 19)]))

# 3. MIDI
st.header("🕒 Recharger le midi")
midi_plan = {"P4":"11:50","P5":"12:37","P6":"11:38","P8":"11:34"}
rows_midi = []
for p, h in midi_plan.items():
    h_dt = datetime.strptime(h, "%H:%M")
    if is_rainy: h_dt += timedelta(minutes=10)
    rows_midi.append({"Parking": p, "Départ conseillé": h_dt.strftime("%H:%M")})
st.table(pd.DataFrame(rows_midi))
