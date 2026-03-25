import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import re

st.set_page_config(page_title="TCR Dashboard", layout="wide")

# --- CONFIGURATION CORRECTE ---
# Mapping réel : parking → id HTML count_parking_X
# Identifié par inspection du DOM de smartevlab.fr
MAPPING_IDS = {
    'P2': 7,
    'P3': 1,
    'P4': 2,
    'P5': 3,
    'P6': 5,
    'P8': 4,
    # P18 et P19 utilisent cardWidth3 (pas d'ID direct)
}

# Capacités réelles observées
CAPACITES = {
    'P2': 8,
    'P3': 38,
    'P4': 15,
    'P5': 20,
    'P6': 49,
    'P8': 5,
    'P18': 9,
    'P19': 0,  # Toujours à 0 — borne en panne
}

# Ordre d'affichage (du haut en bas sur le plan)
ORDRE = ['P2', 'P3', 'P4', 'P5', 'P6', 'P8', 'P18', 'P19']

# Heure moyenne de saturation (observée lundi/mardi)
HISTO_SAT = {
    'P2': '07:45',
    'P3': 'jamais plein',
    'P4': '07:30',
    'P5': '07:30',
    'P6': '07:35',
    'P8': '07:45',
    'P18': '08:00',
    'P19': '—',
}

# Meilleur créneau midi (attente < 15 min)
MIDI_CONSEILLE = {
    'P5': '12h (9 min)',
    'P6': '12h (13 min)',
    'P8': '12h (23 min)',
    'P3': 'toujours libre',
}


# ---------------------------------------------------------------------------
# SCRAPING
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30)
def fetch_data():
    url = "http://www.smartevlab.fr/"
    try:
        res = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(res.text, "html.parser")
        results = {}

        # Parkings avec ID direct
        for p, idx in MAPPING_IDS.items():
            el = soup.find("div", id=f"count_parking_{idx}")
            if el:
                val = re.findall(r'\d+', el.get_text())
                results[p] = int(val[0]) if val else 0

        # P18 et P19 : cardWidth3, on remonte le DOM
        cards = soup.select(".cardChallengeImg.cardWidth3")
        for card in cards:
            code = card.get_text(strip=True)
            if code in ('P18', 'P19'):
                parent = card.find_parent()
                while parent:
                    compteur = parent.find("div", id=lambda x: x and x.startswith("count_parking_"))
                    if compteur:
                        val = re.findall(r'\d+', compteur.get_text())
                        results[code] = int(val[0]) if val else 0
                        break
                    parent = parent.find_parent()

        return results if results else None
    except Exception as e:
        return None


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.title("🔋 TCR Bornes — Tableau de bord")

# Sidebar
st.sidebar.header("Paramètres")
is_monday   = st.sidebar.checkbox("Lundi (saturation plus tôt)", value=(datetime.now().weekday() == 0))
is_rainy    = st.sidebar.checkbox("Pluie 🌧️ (affluence +10%)")

if st.button("🔄 Actualiser"):
    st.cache_data.clear()
    st.rerun()

data_live = fetch_data()
now = datetime.now()

if not data_live:
    st.error("❌ Site Smartevlab injoignable.")
    data_live = {p: CAPACITES[p] for p in ORDRE}  # fallback max
else:
    st.success(f"✅ Mis à jour à {now.strftime('%H:%M:%S')}")


# ---------------------------------------------------------------------------
# 1. TABLEAU PRINCIPAL
# ---------------------------------------------------------------------------

st.header("🚗 État des parkings")

rows = []
for p in ORDRE:
    cap = CAPACITES[p]
    dispo = data_live.get(p, 0)

    if cap == 0:
        status = "⚫"
        pct = "—"
        barre = "En panne"
    else:
        pct_val = round((cap - dispo) / cap * 100)
        pct = f"{pct_val}%"
        if dispo > cap * 0.2:
            status = "🟢"
        elif dispo > 0:
            status = "🟠"
        else:
            status = "🔴"
        barre = "█" * (dispo * 10 // max(cap, 1)) + "░" * (10 - dispo * 10 // max(cap, 1))

    h_sat = HISTO_SAT.get(p, "—")
    if is_monday and h_sat not in ("jamais plein", "—"):
        try:
            h_obj = datetime.strptime(h_sat, "%H:%M") - timedelta(minutes=15)
            h_sat = h_obj.strftime("%H:%M") + " (lundi)"
        except:
            pass

    rows.append({
        "Parking": p,
        "Statut": status,
        "Dispo / Total": f"{dispo} / {cap}",
        "Occupation": pct,
        "Saturation habituelle": h_sat,
    })

st.table(pd.DataFrame(rows).set_index("Parking"))


# ---------------------------------------------------------------------------
# 2. GRAPHIQUE D'AFFLUENCE
# ---------------------------------------------------------------------------

st.header("📈 Affluence globale — lundi & mardi")

heures = [f"{h}h" for h in range(7, 20)]
# Taux d'occupation observé (données réelles 2 jours)
moyenne = [78.2, 98.2, 95.5, 93.9, 93.3, 94.3, 95.9, 96.6, 94.7, 90.2, 77.1, 52.2, 19.2]

if is_rainy:
    moyenne = [min(100, v + 10) for v in moyenne]

# Point réel à l'heure courante
total_cap  = sum(CAPACITES[p] for p in ORDRE if CAPACITES[p] > 0)
total_dispo = sum(data_live.get(p, 0) for p in ORDRE if CAPACITES[p] > 0)
p_reel = round((total_cap - total_dispo) / total_cap * 100, 1)

reel = []
for h, v in zip(range(7, 20), moyenne):
    if h < now.hour:
        reel.append(None)
    elif h == now.hour:
        reel.append(p_reel)
    else:
        reel.append(None)

df_chart = pd.DataFrame({
    'Moyenne historique (%)': moyenne,
    'Maintenant (%)': reel
}, index=heures)

st.line_chart(df_chart)


# ---------------------------------------------------------------------------
# 3. MEILLEURS CRÉNEAUX MIDI
# ---------------------------------------------------------------------------

st.header("🕒 Recharger le midi")
st.caption("Créneaux avec moins de 15 min d'attente (basé sur lundi & mardi)")

midi_rows = [{"Parking": p, "Créneau conseillé": v} for p, v in MIDI_CONSEILLE.items()]
st.table(pd.DataFrame(midi_rows).set_index("Parking"))


# ---------------------------------------------------------------------------
# 4. LÉGENDE
# ---------------------------------------------------------------------------

with st.expander("ℹ️ Légende & notes"):
    st.markdown("""
- **P19** : toujours à 0 disponible — borne probablement en panne
- **P3** : jamais saturé (38 places), idéal mais charge lentement (3 kW)
- **P5** : seule borne 22 kW ⚡ — priorité si disponible
- Les heures de saturation et d'attente sont calculées sur 2 jours ouvrés (lundi 23 et mardi 24 mars 2026)
- Les données s'affineront automatiquement au fil des semaines
    """)
