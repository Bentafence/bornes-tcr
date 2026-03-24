import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd

# Configuration
st.set_page_config(page_title="TCR Dashboard", page_icon="🔋", layout="wide")

CAPACITES = {'P2': 8, 'P4': 15, 'P5': 20, 'P6': 49, 'P8': 5, 'P19': 10, 'P18': 9}
HISTO_SAT = {'P2': '06:55', 'P4': '07:18', 'P5': '07:28', 'P6': '07:38', 'P8': '07:51', 'P19': '07:05', 'P18': '07:13'}
DEPART_MIDI = {'P4': '11:50', 'P5': '12:37', 'P6': '11:38', 'P8': '11:34'}
ORDRE = ['P2', 'P4', 'P5', 'P6', 'P8', 'P19', 'P18']

def get_live_data():
    try:
        response = requests.get("http://www.smartevlab.fr/", timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Méthode simple : on prend tous les noms et tous les nombres
        raw_names = [c.get_text(strip=True).replace(" ", "").upper() for c in soup.select(".cardChallengeImg.cardWidth2")]
        raw_counts = [int(c.get_text(strip=True)) for c in soup.select("div[id^=count_parking_]")]
        
        # On crée le dictionnaire
        data = dict(zip(raw_names, raw_counts))
        
        # DEBUG : Si P18 manque, on essaie de le trouver par son ID direct
        if 'P18' not in data:
            p18_val = soup.find("div", id="count_parking_7") # Souvent l'ID du P18
            if p18_val: data['P18'] = int(p18_val.get_text(strip=True))
            
        return data
    except Exception as e:
        return {}

# --- EXECUTION ---
data_live = get_live_data()
now = datetime.now()
is_monday = now.weekday() == 0
is_rainy = st.sidebar.checkbox("Pluie (Guyancourt) 🌧️", value=False)

st.title("🔋 TCR Bornes Predict")

# 1. TABLEAU RÉCAPITULATIF
st.header("🚗 État Actuel & Saturation")

if not data_live:
    st.error("⚠️ Aucune donnée reçue du site. Vérification de la connexion...")
else:
    summary_data = []
    total_dispo = 0
    for p in ORDRE:
        # On cherche P2, P4... ou PARKING2, PARKING4...
        dispo = data_live.get(p, data_live.get(f"PARKING{p[1:]}", 0))
        total_dispo += dispo
        
        h_theo = datetime.strptime(HISTO_SAT[p], "%H:%M")
        recalage = -15 if (now.hour < 8 and dispo == 0) else 0
        h_prev = (h_theo + timedelta(minutes=recalage + (-15 if is_monday else 0))).strftime("%H:%M")
        
        status = "🔴" if dispo == 0 else ("🟠" if dispo < 3 else "🟢")
        summary_data.append({"Parking": p, "Statut": status, "Libre": f"{dispo}/{CAPACITES[p]}", "Saturation": h_prev})
    
    st.table(pd.DataFrame(summary_data))

# 2. GRAPHIQUE
st.header("📈 Courbes de Remplissage")
p_selected = st.selectbox("Détail pour :", ["Global"] + ORDRE)
# (Le reste du code pour le graphique et le midi reste identique à la V6)
# ... [Copie ici la suite du code V6 pour le graphique et le tableau de midi] ...
