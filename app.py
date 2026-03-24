import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# Configuration de la page
st.set_page_config(page_title="TCR Bornes Tactique", page_icon="🔋")

st.title("🔋 TCR Bornes Tactique")
st.write("Optimisation des recharges - Guyancourt")

# --- 1. PANNEAU DE PRÉVISIONS ---
st.header("📍 Prévisions du jour")
col1, col2 = st.columns(2)

# Logique de calcul (Lundi / Pluie)
is_monday = datetime.now().weekday() == 0
is_rainy = st.sidebar.checkbox("Il pleut à Guyancourt 🌧️", value=False)

with col1:
    st.info("🕒 Saturation (2 places)")
    st.write(f"P6: **{'07:23' if is_monday else '07:38'}**")
    st.write(f"P5: **{'07:13' if is_monday else '07:28'}**")

with col2:
    st.warning("🚶 Départ Midi (<10m attente)")
    retard = 10 if is_rainy else 0
    st.write(f"P6: **{(datetime.strptime('11:38', '%H:%M') + timedelta(minutes=retard)).strftime('%H:%M')}**")
    st.write(f"P5: **{(datetime.strptime('12:37', '%H:%M') + timedelta(minutes=retard)).strftime('%H:%M')}**")

# --- 2. SCAN EN DIRECT ---
st.header("📊 État des Bornes en Direct")

if st.button('Actualiser les données'):
    try:
        response = requests.get("http://www.smartevlab.fr/", timeout=5)
        soup = BeautifulSoup(response.text, "html.parser")
        codes = [c.get_text(strip=True) for c in soup.select(".cardChallengeImg.cardWidth2")]
        compteurs = [int(c.get_text(strip=True)) for c in soup.select("div[id^=count_parking_]")]
        data = dict(zip(codes, compteurs))
        
        # Affichage dynamique
        target_parkings = ['P18', 'P2', 'P4', 'P5', 'P6', 'P8']
        for p in target_parkings:
            val = data.get(p, 0)
            # Barre de progression de couleur
            color = "green" if val > 2 else ("orange" if val > 0 else "red")
            st.write(f"**{p}** : {val} places libres")
            st.progress(min(val * 10, 100)) # Simple jauge visuelle
            
    except Exception as e:
        st.error(f"Erreur de connexion au site : {e}")

st.sidebar.write("---")
st.sidebar.write("💡 *Astuce : Le P5 est le plus fluide entre 11h et 13h.*")
