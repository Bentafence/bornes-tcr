import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="TCR - Guide de Survie Recharge", layout="wide")

# DONNÉES TERRAIN (TES CAPTURES)
DATA = {
    'P6':  {'cap': 49, 'sat': '07:38', 'ids': 'Mat-009167 à 009215', 'type': '22kW'},
    'P4':  {'cap': 15, 'sat': '07:18', 'ids': 'Mat-009122 à 009136', 'type': '7kW/22kW'},
    'P19': {'cap': 10, 'sat': '07:05', 'ids': 'Mat-008145 à 008154', 'type': '7kW'},
    'P18': {'cap': 9,  'sat': '07:13', 'ids': 'Mat-008136 à 008144', 'type': '7kW'},
    'P5':  {'cap': 20, 'sat': '07:28', 'ids': 'Mat-008xxx',           'type': '7kW'},
    'P2':  {'cap': 8,  'sat': '06:55', 'ids': 'Mat-009045 à 009052', 'type': '22kW'},
    'P8':  {'cap': 8,  'sat': '07:51', 'ids': 'Mat-009159 à 009166', 'type': '22kW'}
}

st.title("🔋 TCR - Guide de Survie Recharge")
st.warning("⚠️ Accès Smartevlab bloqué par Renault. Utilisation du mode Expert.")

# --- 1. LE CONSEILLER TEMPS RÉEL ---
now = datetime.now().time()
st.header("🎯 Quelle est la meilleure option maintenant ?")

if now < datetime.strptime("07:00", "%H:%M").time():
    st.success("🟢 Tout est vide. Priorité au P2 ou P19 (confort).")
elif now < datetime.strptime("07:30", "%H:%M").time():
    st.warning("🟠 Ça se remplit vite. Vise le P6 ou le P5 immédiatement.")
elif now < datetime.strptime("11:45", "%H:%M").time():
    st.error("🔴 Tout est plein. Attends la vague de midi (11h45 - 12h15) pour le P6.")
else:
    st.info("🔵 Turnover en cours au P6 et P4. Tente ta chance !")

# --- 2. LA CARTE DES RÉFÉRENCES ---
st.header("📋 Correspondance Freshmile")
df_data = []
for k, v in DATA.items():
    df_data.append({"Parking": k, "Série Mat-": v['ids'], "Places": v['cap'], "Plein à": v['sat']})

st.table(pd.DataFrame(df_data))

# --- 3. MATRICE D'ATTENTE ---
st.header("⏳ Temps d'attente estimé (min)")
h_range = [f"{h}h" for h in range(7, 18)]
wait_rows = []
for p in ['P2', 'P4', 'P5', 'P6', 'P8', 'P19', 'P18']:
    profile = [5, 15, 30, 45, 25, 10, 5, 15, 20, 15, 5] if p in ['P4', 'P5', 'P6'] else [15, 45, 90, 120, 180, 180, 150, 100, 60, 40, 20]
    row = {"Parking": p}
    for idx, h in enumerate(h_range): row[h] = profile[idx]
    wait_rows.append(row)

st.dataframe(pd.DataFrame(wait_rows).set_index("Parking").style.background_gradient(cmap='RdYlGn_r', axis=None))
