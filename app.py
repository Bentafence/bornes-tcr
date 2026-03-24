import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import re

# Configuration de la page
st.set_page_config(page_title="TCR Bornes Predict", page_icon="🔋", layout="wide")

# --- PARAMÈTRES ET CONSTANTES ---
CAPACITES = {'P2': 8, 'P4': 15, 'P5': 20, 'P6': 49, 'P8': 5, 'P19': 10, 'P18': 9}
HISTO_SAT = {'P2': '06:55', 'P4': '07:18', 'P5': '07:28', 'P6': '07:38', 'P8': '07:51', 'P19': '07:05', 'P18': '07:13'}
DEPART_MIDI = {'P4': '11:50', 'P5': '12:37', 'P6': '11:38', 'P8': '11:34'}
ORDRE = ['P2', 'P4', 'P5', 'P6', 'P8', 'P19', 'P18']

# --- FONCTION DE RÉCUPÉRATION (SCAN TEXTUEL) ---
@st.cache_data(ttl=15)
def get_live_data():
    url = "http://www.smartevlab.fr/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        data_found = {}
        
        # On récupère tous les blocs "card" du site
        cards = soup.find_all("div", class_="card")
        
        for card in cards:
            # On nettoie le texte pour la recherche
            text = card.get_text(" ", strip=True).upper().replace(" ", "")
            
            for p in ORDRE:
                if p in text or f"PARKING{p[1:]}" in text:
                    # On a identifié le bloc du parking, on cherche le chiffre de dispo
                    # On cible le div spécifique du compteur pour éviter de prendre le numéro du parking
                    counter_div = card.find("div", id=lambda x: x and x.startswith('count_parking_'))
                    if counter_div:
                        val_txt = counter_div.get_text(strip=True)
                        nums = re.findall(r'\d+', val_txt)
                        if nums:
                            data_found[p] = int(nums[0])
        return data_found
    except:
        return None

# --- LOGIQUE D'AFFICHAGE ---
data_live = get_live_data()
now = datetime.now()
is_monday = now.weekday() == 0
is_rainy = st.sidebar.checkbox("Pluie (Guyancourt) 🌧️", value=False)

st.title("🔋 TCR Bornes Predict")

# 1. TABLEAU RÉCAPITULATIF "CONDUITE"
st.header("🚗 État Actuel & Saturation")
if not data_live:
    st.warning("⚠️ Connexion difficile au site. Affichage des dernières prévisions.")
    data_live = {} # Évite les erreurs de calcul

summary_data = []
total_dispo = 0

for p in ORDRE:
    dispo = data_live.get(p, 0)
    total_dispo += dispo
    
    # Calcul saturation avec recalage
    h_theo = datetime.strptime(HISTO_SAT[p], "%H:%M")
    # Recalage si déjà plein avant l'heure (sauf P18/P2 souvent pleins)
    recalage = -15 if (now.hour < 8 and dispo == 0 and p not in ['P2', 'P18']) else 0
    h_prev = (h_theo + timedelta(minutes=recalage + (-15 if is_monday else 0))).strftime("%H:%M")
    
    status = "🔴" if dispo == 0 else ("🟠" if dispo < 3 else "🟢")
    summary_data.append({
        "Parking": p,
        "Statut": status,
        "Libre": f"{dispo} / {CAPACITES[p]}",
        "Saturation": h_prev
    })

st.table(pd.DataFrame(summary_data))
st.write(f"**Total Site : {total_dispo} places libres.**")

# 2. GRAPHIQUE DE REMPLISSAGE
st.header("📈 Courbes de Remplissage (%)")
p_selected = st.selectbox("Détail pour :", ["Global"] + ORDRE)

heures = [f"{h:02d}:00" for h in range(6, 21)]
base_remplissage = [5, 25, 75, 95, 100, 98, 92, 85, 90, 98, 85, 60, 30, 15, 5]
prevue = [min(100, v + (10 if is_monday or is_rainy else 0)) for v in base_remplissage]
pourcent_reel = ((sum(CAPACITES.values()) - total_dispo) / sum(CAPACITES.values())) * 100
reel = [v + 2 if h < now.hour else (pourcent_reel if h == now.hour else None) for h, v in zip(range(6, 21), prevue)]

df_graph = pd.DataFrame({'Heure': heures, 'Moyenne': base_remplissage, 'Prévue': prevue, 'Réel': reel}).set_index('Heure')
st.line_chart(df_graph)

# 3. RECHARGER LE MIDI
st.header("🕒 Recharger le midi")
st.write("Heure de départ conseillée (10 min marche incluse)")
midi_list = []
for p in ORDRE:
    h_base = DEPART_MIDI.get(p, "N/A")
    if h_base != "N/A":
        h_dt = datetime.strptime(h_base, "%H:%M")
        if is_rainy: h_dt += timedelta(minutes=10)
        h_fin = h_dt.strftime("%H:%M")
        attente = "Env. 8 min"
    else:
        h_fin, attente = "Déconseillé", "> 45 min"
    midi_list.append({"Parking": p, "Départ": h_fin, "Attente": attente})

st.table(pd.DataFrame(midi_list))

# 4. TEMPS D'ATTENTE HEURE PAR HEURE
st.header("⏳ Temps d'attente estimé (min)")
heures_wait = [f"{h}h" for h in range(7, 17)]
wait_data = {}
for p in ORDRE:
    if p in ['P2', 'P18', 'P19']: wait_data[p] = [40, 90, 150, 180, 180, 160, 140, 120, 100, 60]
    elif p == 'P5': wait_data[p] = [10, 25, 45, 30, 15, 10, 15, 20, 15, 10]
    else: wait_data[p] = [20, 45, 80, 110, 100, 70, 60, 50, 40, 25]

st.dataframe(pd.DataFrame(wait_data, index=heures_wait).T)
