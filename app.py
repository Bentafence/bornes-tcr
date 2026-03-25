import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import re
import plotly.graph_objects as go

st.set_page_config(page_title="TCR Bornes", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fafafa; }
    .sat-ok   { color: #4caf50; font-weight: 600; }
    .sat-warn { color: #ff9800; font-weight: 600; }
    .sat-late { color: #f44336; font-weight: 600; }
    .sat-na   { color: #888; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    thead th { background-color: #1e2233 !important; color: #90caf9 !important;
               padding: 8px 10px; text-align: left; }
    tbody td { padding: 7px 10px; border-bottom: 1px solid #1e2233; }
    tbody tr:nth-child(even) { background-color: #13161f; }
    tbody tr:nth-child(odd)  { background-color: #1a1d27; }
    tbody tr:hover { background-color: #1e2a40; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

MAPPING_IDS = {'P2': 7, 'P3': 1, 'P4': 2, 'P5': 3, 'P6': 5, 'P8': 4}
CAPACITES   = {'P2': 8, 'P3': 38, 'P4': 15, 'P5': 20, 'P6': 49, 'P8': 5, 'P18': 9, 'P19': 0}
ORDRE       = ['P2', 'P3', 'P4', 'P5', 'P6', 'P8', 'P18', 'P19']
KW          = {'P2':'3 kW','P3':'3 kW','P4':'7 kW','P5':'22 kW ⚡','P6':'7 kW','P8':'3 kW','P18':'3 kW','P19':'7 kW'}

# Heure de saturation habituelle (décimale)
HISTO_SAT_H = {'P2':7.75,'P3':None,'P4':7.5,'P5':7.5,'P6':7.58,'P8':7.75,'P18':8.0,'P19':None}

# Occupation % par heure (lundi & mardi observés)
OCC = {
    'P2':   {7:53, 8:92, 9:92, 10:92, 11:92, 12:92, 13:97, 14:100,15:100,16:100,17:100,18:100,19:100},
    'P3':   {7:87, 8:97, 9:97, 10:97, 11:97, 12:97, 13:97, 14:97, 15:96, 16:87, 17:67, 18:45, 19:22},
    'P4':   {7:93, 8:96, 9:97, 10:96, 11:96, 12:94, 13:100,14:99, 15:87, 16:95, 17:80, 18:47, 19:10},
    'P5':   {7:90, 8:100,9:70, 10:56, 11:62, 12:71, 13:79, 14:80, 15:79, 16:82, 17:89, 18:75, 19:14},
    'P6':   {7:73, 8:100,9:100,10:100,11:99, 12:99, 13:99, 14:99, 15:98, 16:95, 17:81, 18:50, 19:10},
    'P8':   {7:31, 8:93, 9:100,10:100,11:86, 12:89, 13:88, 14:100,15:100,16:86, 17:72, 18:43, 19:14},
    'P18':  {7:96, 8:100,9:100,10:100,11:97, 12:99, 13:100,14:100,15:98, 16:92, 17:67, 18:44, 19:14},
    'P19':  {h:100 for h in range(7,20)},
    'TOTAL':{7:78, 8:98, 9:96, 10:94, 11:93, 12:94, 13:96, 14:97, 15:95, 16:90, 17:77, 18:52, 19:19},
}

# Attente midi (11h–14h) en minutes si parking plein
ATTENTE_MIDI = {'P2':0,'P3':0,'P4':59,'P5':39,'P6':20,'P8':78,'P18':83}


# ---------------------------------------------------------------------------
# SCRAPING
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30)
def fetch_data():
    try:
        res = requests.get("http://www.smartevlab.fr/", timeout=10,
                           headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(res.text, "html.parser")
        results = {}
        for p, idx in MAPPING_IDS.items():
            el = soup.find("div", id=f"count_parking_{idx}")
            if el:
                val = re.findall(r'\d+', el.get_text())
                results[p] = int(val[0]) if val else 0
        for card in soup.select(".cardChallengeImg.cardWidth3"):
            code = card.get_text(strip=True)
            if code in ('P18', 'P19'):
                parent = card.find_parent()
                while parent:
                    cpt = parent.find("div", id=lambda x: x and x.startswith("count_parking_"))
                    if cpt:
                        val = re.findall(r'\d+', cpt.get_text())
                        results[code] = int(val[0]) if val else 0
                        break
                    parent = parent.find_parent()
        return results if results else None
    except:
        return None


def saturation_prevue(p, dispo, now):
    cap = CAPACITES[p]
    if cap == 0 or HISTO_SAT_H.get(p) is None:
        return "—", "sat-na"
    if dispo == 0:
        return "Plein 🔴", "sat-late"
    h_base = HISTO_SAT_H[p]
    h = now.hour
    occ_hist = OCC.get(p, {}).get(h, 50) / 100
    occ_reel = (cap - dispo) / cap
    ecart = occ_reel - occ_hist
    decalage_min = round(ecart * 60)
    h_sat_dt = now.replace(hour=int(h_base), minute=int((h_base % 1) * 60), second=0, microsecond=0)
    h_sat_corr = h_sat_dt - timedelta(minutes=decalage_min)
    delta = (h_sat_corr - now).total_seconds() / 60
    label = h_sat_corr.strftime("%H:%M")
    if delta < 0:
        return f"{label} ⚠️", "sat-late"
    elif delta < 30:
        return f"{label} (~{int(delta)} min)", "sat-warn"
    else:
        return label, "sat-ok"


# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------

st.sidebar.title("⚙️ Paramètres")
is_monday = st.sidebar.checkbox("Lundi (saturation 15min plus tôt)", value=(datetime.now().weekday() == 0))
is_rainy  = st.sidebar.checkbox("Pluie 🌧️ (+10% affluence)")
auto_ref  = st.sidebar.checkbox("Rafraîchissement auto 30s")

if st.sidebar.button("🔄 Actualiser"):
    st.cache_data.clear()
    st.rerun()

if auto_ref:
    import time; time.sleep(30)
    st.cache_data.clear()
    st.rerun()

# ---------------------------------------------------------------------------
# DONNÉES
# ---------------------------------------------------------------------------

data_live = fetch_data()
now = datetime.now()

st.title("🔋 TCR Bornes — Tableau de bord")
col_status, col_time = st.columns([3, 1])
with col_status:
    if not data_live:
        st.error("❌ Site Smartevlab injoignable — données indisponibles")
        data_live = {p: 0 for p in ORDRE}
    else:
        st.success(f"✅ Temps réel — {now.strftime('%H:%M:%S')}")

# ---------------------------------------------------------------------------
# 1. ÉTAT DES PARKINGS
# ---------------------------------------------------------------------------

st.header("🚗 État des parkings")

rows_html = []
for p in ORDRE:
    cap  = CAPACITES[p]
    dispo = data_live.get(p, 0)

    if cap == 0:
        statut = "⚫ En panne"
        places = "—"
        occ_str = "—"
        sat_html = '<span class="sat-na">—</span>'
    else:
        pct = round((cap - dispo) / cap * 100)
        occ_str = f"{pct}%"
        if dispo > cap * 0.3:   statut = "🟢 Disponible"
        elif dispo > 0:          statut = "🟠 Presque plein"
        else:                    statut = "🔴 Complet"
        places = f"{dispo} / {cap}"
        sat_raw, sat_class = saturation_prevue(p, dispo, now)
        if is_monday and sat_raw not in ("—", "Plein 🔴") and "⚠️" not in sat_raw:
            try:
                t = datetime.strptime(sat_raw.split(" ")[0], "%H:%M") - timedelta(minutes=15)
                sat_raw = t.strftime("%H:%M") + " (lundi)"
            except:
                pass
        sat_html = f'<span class="{sat_class}">{sat_raw}</span>'

    rows_html.append(f"""
    <tr>
      <td><b>{p}</b></td>
      <td>{KW[p]}</td>
      <td>{statut}</td>
      <td>{places}</td>
      <td>{occ_str}</td>
      <td>{sat_html}</td>
    </tr>""")

table_html = f"""
<table>
  <thead><tr>
    <th>Parking</th><th>Puissance</th><th>Statut</th>
    <th>Dispo / Total</th><th>Occupation</th><th>Saturation prévue</th>
  </tr></thead>
  <tbody>{''.join(rows_html)}</tbody>
</table>"""
st.markdown(table_html, unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 2. GRAPHIQUE SYTADIN
# ---------------------------------------------------------------------------

st.header("📈 Affluence — style Sytadin")

parkings_dispo = ['Tous les parkings'] + [p for p in ORDRE if CAPACITES[p] > 0 and p != 'P19']
choix = st.selectbox("Parking :", parkings_dispo)
key = 'TOTAL' if choix == 'Tous les parkings' else choix

heures   = list(range(7, 20))
h_labels = [f"{h}h" for h in heures]
moy      = [OCC[key].get(h, 0) for h in heures]
if is_rainy:
    moy = [min(100, v + 10) for v in moy]

# Bandes
b1 = [round(v * 0.75) for v in moy]
b2 = [max(0, v - round(v * 0.75)) for v in moy]
b3 = [max(0, min(100, round(v * 1.15)) - v) for v in moy]
b4 = [max(0, 100 - min(100, round(v * 1.15))) for v in moy]

# Point temps réel
if choix == 'Tous les parkings':
    cap_t  = sum(CAPACITES[p] for p in ORDRE if CAPACITES[p] > 0 and p != 'P19')
    disp_t = sum(data_live.get(p, 0) for p in ORDRE if CAPACITES[p] > 0 and p != 'P19')
    occ_now = round((cap_t - disp_t) / cap_t * 100, 1) if cap_t else 0
else:
    cap_p  = CAPACITES[choix]
    disp_p = data_live.get(choix, 0)
    occ_now = round((cap_p - disp_p) / cap_p * 100, 1) if cap_p else 0

reel = [occ_now if h == now.hour else None for h in heures]

fig = go.Figure()

for band, color, name in [
    (b1, 'rgba(90,158,58,0.80)',  'Faible occupation'),
    (b2, 'rgba(232,208,32,0.80)', 'Habituel'),
    (b3, 'rgba(224,128,32,0.80)', 'Inhabituel'),
    (b4, 'rgba(208,48,32,0.80)',  'Exceptionnel'),
]:
    fig.add_trace(go.Bar(x=h_labels, y=band, name=name,
                         marker_color=color, hoverinfo='skip'))

fig.add_trace(go.Scatter(
    x=h_labels, y=moy, name='Moyenne historique',
    mode='lines', line=dict(color='#4a90d9', width=2.5, dash='dot'),
    hovertemplate='Moyenne : %{y}%<extra></extra>',
))

fig.add_trace(go.Scatter(
    x=h_labels, y=reel, name='Maintenant',
    mode='markers',
    marker=dict(color='white', size=13, symbol='diamond',
                line=dict(color='#4a90d9', width=2)),
    hovertemplate='Maintenant : %{y}%<extra></extra>',
))

fig.update_layout(
    barmode='stack',
    plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
    font_color='#fafafa',
    xaxis=dict(title='Heure', gridcolor='#2a2d3a', tickfont=dict(size=12)),
    yaxis=dict(title="Taux d'occupation (%)", range=[0,100],
               gridcolor='#2a2d3a', ticksuffix='%'),
    legend=dict(orientation='h', yanchor='bottom', y=-0.35,
                bgcolor='rgba(0,0,0,0)', font=dict(size=11)),
    margin=dict(t=10, b=10), height=400,
    hovermode='x unified',
)
st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# 3. RECHARGER LE MIDI
# ---------------------------------------------------------------------------

st.header("🕒 Recharger le midi (11h–14h)")
st.caption("Temps d'attente moyen si vous arrivez sur un parking complet entre 11h et 14h")

midi_rows = []
for p in ORDRE:
    cap   = CAPACITES[p]
    dispo = data_live.get(p, 0)
    if cap == 0:
        continue
    wait = ATTENTE_MIDI.get(p, None)
    if wait is None:
        conseil, emoji = "—", "⚪"
    elif wait <= 5:
        conseil, emoji = "< 5 min", "🟢"
    elif wait < 20:
        conseil, emoji = f"~{wait} min", "🟡"
    elif wait < 60:
        conseil, emoji = f"~{wait} min", "🟠"
    else:
        conseil, emoji = f"~{wait} min — éviter", "🔴"

    midi_rows.append({
        "Parking": p,
        "Puissance": KW[p],
        "Dispo maintenant": f"{dispo} / {cap}",
        "Attente si plein": f"{emoji} {conseil}",
    })

st.table(pd.DataFrame(midi_rows).set_index("Parking"))


# ---------------------------------------------------------------------------
# 4. LÉGENDE
# ---------------------------------------------------------------------------

with st.expander("ℹ️ Légende & notes"):
    st.markdown("""
- **P19** : toujours à 0 — borne en panne (exclue des calculs)
- **P5** : seule borne **22 kW ⚡** — priorité si disponible
- **Saturation prévue** : heure habituelle ajustée selon l'écart occupation actuelle / moyenne historique
- 🟢 dans les temps &nbsp;|&nbsp; 🟠 saturation imminente (&lt;30 min) &nbsp;|&nbsp; 🔴 déjà saturé
- Basé sur **2 jours ouvrés** (lundi 23 & mardi 24 mars 2026) — s'affine avec le temps
    """)
