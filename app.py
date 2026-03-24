import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime

st.set_page_config(page_title="TCR - Analyseur de Flux", layout="wide")

st.title("🔍 Analyseur de Réponse Smartevlab")
st.write("Ce script affiche ce que le site 'dit' réellement, sans filtre.")

url = "http://www.smartevlab.fr/"

if st.button("Lancer le scan maintenant"):
    try:
        # On utilise cloudscraper pour essayer de passer les protections standards
        scraper = cloudscraper.create_scraper()
        res = scraper.get(url, timeout=15)
        
        st.subheader(f"Statut de la réponse : {res.status_code}")
        
        if res.status_code == 200:
            st.success("✅ Connexion établie. Voici le contenu brut détecté :")
            
            # Affichage du texte pur extrait de la page
            soup = BeautifulSoup(res.text, "html.parser")
            raw_text = soup.get_text(separator="\n", strip=True)
            
            st.text_area("Texte brut reçu du site :", raw_text, height=400)
            
            # Analyse des balises spécifiques aux parkings
            st.subheader("Structure des compteurs (HTML)")
            elements = soup.find_all(id=lambda x: x and 'count_parking' in x)
            if elements:
                for el in elements:
                    st.code(str(el))
            else:
                st.warning("⚠️ Aucune balise de compteur ('count_parking') n'a été trouvée dans le code source.")
        
        else:
            st.error(f"❌ Le site a répondu avec une erreur {res.status_code}")
            st.write("Détails de l'erreur :")
            st.code(res.text[:500]) # Affiche le début du message d'erreur (ex: Cloudflare blocking)

    except Exception as e:
        st.error(f"🚨 Erreur de connexion critique : {str(e)}")
        st.info("Cela confirme que l'hébergeur (Streamlit) est bloqué au niveau du réseau.")

st.divider()
st.caption(f"Scan généré le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}")
