import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import pandas as pd
import re
from datetime import datetime

# Configuration
st.set_page_config(page_title="TCR - Scanner & Dashboard", layout="wide")

# Paramètres fixes (Source Terrain)
CAPACITES = {'P2': 8, 'P4': 15, 'P5': 20, 'P6': 49, 'P8': 8, 'P19': 10, 'P18': 9}
ORDRE = ['P2', 'P4', 'P5', 'P6', 'P8', 'P19', 'P18']

def get_raw_and_parsed():
    """Récupère le flux brut et tente l'extraction"""
    try:
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
        )
        url = "http://www.smartevlab.fr/"
        res = scraper.get(url, timeout=12)
        
        if res.status_code != 200:
            return None, f"Erreur Serveur: {res.status_code}", None

        soup = BeautifulSoup(res.text, "html.parser")
        raw_text = soup.get_text(separator="\n", strip=True)
        
        # Extraction pour le tableau
        extracted_data = {}
        cards = soup.find_all("div", class_="card")
        for card in cards:
            card_txt = card.get_text(" ", strip=True).upper().replace(" ", "")
            for p in ORDRE:
                if p in card_txt or (p == 'P19' and 'FOSSEAULOUP' in card_txt):
                    count_el = card.find("div", id=re.compile(r'count_parking_'))
                    if count_el:
                        nums = re.findall(r'\d+', count_el.get_text())
                        if nums: extracted_data[p] = int(nums[0])
        
        return raw_text, None, extracted_data

    except Exception as e:
        return None, str(e), None

# --- UI ---
st.title("🔋 TCR : Scanner de Flux & Dashboard")

raw_content, error, live_data = get_raw_and_parsed()

# 1. Diagnostic de flux (La capture d'écran textuelle)
with st.expander("🔍 Voir le scan brut du site (Debug)", expanded=False):
    if error:
        st.error(f"Impossible de scanner le site : {error}")
    elif raw_content:
        st.code(raw_content, language=None)
    else:
        st.warning("Aucun contenu reçu.")

# 2. Reconstruction du Tableau Originel
st.header("🚗 État des bornes (Reconstruit)")

if live_data:
    st.success(f"✅ Données extraites avec succès à {datetime.now().strftime('%H:%M:%S')}")
    
    rows = []
    for p in ORDRE:
        dispo = live_data.get(p, 0)
        status = "🟢" if dispo > 3 else ("🟠" if dispo > 0 else "🔴")
        rows.append({
            "Parking": p,
            "Statut": status,
            "Disponibilité": f"{dispo} / {CAPACITES[p]}",
            "Identifiant Mat (ex)": "Mat-..." # On garde la structure pour tes refs
        })
    
    st.table(pd.DataFrame(rows))
else:
    st.error("❌ Le tableau ne peut pas être construit : Les données de comptage sont absentes du flux brut.")
    st.info("Regarde le 'Scan brut' au-dessus : si tu vois des '--' à la place des chiffres, c'est que le site utilise du JavaScript que Streamlit ne peut pas lire.")

# 3. Matrice d'attente (Toujours utile en repli)
st.divider()
st.subheader("⏳ Prévisions basées sur l'historique")
h_range = [f"{h}h" for h in range(7, 18)]
wait_rows = []
for p in ORDRE:
    profile = [5, 15, 30, 45, 25, 10, 5, 15, 20, 15, 5] if p in ['P4', 'P5', 'P6'] else [15, 45, 90, 120, 180, 180, 150, 100, 60, 40, 20]
    row = {"Parking": p}
    for idx, h in enumerate(h_range): row[h] = profile[idx]
    wait_rows.append(row)

st.dataframe(pd.DataFrame(wait_rows).set_index("Parking").style.background_gradient(cmap='RdYlGn_r', axis=None))
