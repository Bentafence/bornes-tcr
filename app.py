import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import re
import plotly.graph_objects as go
import plotly.express as px
from PIL import Image
import os

st.set_page_config(page_title="TCR Bornes", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fafafa; }
    .sat-ok   { color: #4caf50; font-weight: 600; }
    .sat-warn { color: #ff9800; font-weight: 600; }
    .sat-late { color: #f44336; font-weight: 600; }
    .sat-na   { color: #888; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    thead th { background-color: #1e2233 !important; color: #90caf9 !important; padding: 8px 10px; text-align: left; }
    tbody td { padding: 7px 10px; border-bottom: 1px solid #1e2233; }
    tbody tr:nth-child(even) { background-color: #13161f; }
    tbody tr:nth-child(odd)  { background-color: #1a1d27; }
    tbody tr:hover { background-color: #1e2a40; }
    .conseil-box { background: #1e2a40; border-left: 4px solid #4a90d9;
                   padding: 12px 16px; border-radius: 4px; margin-bottom: 8px; font-size: 15px; }
    .diff-pos { color: #f44336; font-weight: 600; }
    .diff-neg { color: #4caf50; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

MAPPING_IDS = {'P2':7,'P3':1,'P4':2,'P5':3,'P6':5,'P8':4}
CAPACITES   = {'P2':8,'P3':38,'P4':15,'P5':20,'P6':49,'P8':5,'P18':9,'P19':0}
ORDRE       = ['P2','P3','P4','P5','P6','P8','P18','P19']
KW          = {'P2':'3 kW','P3':'3 kW','P4':'7 kW','P5':'22 kW ⚡','P6':'7 kW','P8':'3 kW','P18':'3 kW','P19':'7 kW'}
HISTO_SAT_H = {'P2':7.75,'P3':None,'P4':7.5,'P5':7.5,'P6':7.58,'P8':7.75,'P18':8.0,'P19':None}

# Position des parkings sur le plan (x%, y%) — coordonnées normalisées sur l'image 1552x1660
POSITIONS = {
    'P2':  (0.77, 0.09),
    'P3':  (0.77, 0.20),
    'P4':  (0.77, 0.32),
    'P5':  (0.77, 0.43),
    'P6':  (0.77, 0.62),
    'P8':  (0.63, 0.80),
    'P18': (0.10, 0.38),
    'P19': (0.21, 0.38),
}

OCC_LUNDI = {
    'P2': {7:22,8:88,9:88,10:88,11:88,12:88,13:95,14:100,15:100,16:100,17:100,18:100,19:100},
    'P3': {7:90,8:97,9:97,10:97,11:97,12:97,13:97,14:97,15:96,16:92,17:74,18:51,19:22},
    'P4': {7:93,8:93,9:96,10:93,11:93,12:93,13:100,14:98,15:83,16:96,17:92,18:56,19:10},
    'P5': {7:100,8:100,9:55,10:34,11:43,12:59,13:69,14:70,15:72,16:80,17:86,18:73,19:14},
    'P6': {7:83,8:100,9:100,10:100,11:99,12:99,13:99,14:100,15:99,16:96,17:85,18:54,19:10},
    'P8': {7:49,8:100,9:100,10:100,11:82,12:93,13:87,14:100,15:100,16:87,17:60,18:36,19:14},
    'P18':{7:100,8:100,9:100,10:100,11:100,12:99,13:100,14:100,15:98,16:91,17:55,18:37,19:14},
    'P19':{h:100 for h in range(7,20)},
    'TOTAL':{7:85,8:98,9:92,10:89,11:89,12:92,13:94,14:95,15:93,16:92,17:81,18:57,19:19},
}

OCC_AUTRES = {
    'P2': {7:100,8:100,9:100,10:100,11:100,12:100,13:100,14:100,15:100,16:100,17:100,18:100,19:100},
    'P3': {7:78,8:97,9:97,10:97,11:95,12:96,13:96,14:98,15:98,16:84,17:62,18:30,19:12},
    'P4': {7:92,8:99,9:99,10:99,11:100,12:98,13:100,14:99,15:97,16:90,17:61,18:29,19:11},
    'P5': {7:77,8:100,9:99,10:99,11:98,12:97,13:100,14:100,15:96,16:88,17:94,18:75,19:38},
    'P6': {7:56,8:100,9:100,10:99,11:100,12:99,13:98,14:99,15:97,16:93,17:71,18:36,19:9},
    'P8': {7:27,8:93,9:100,10:100,11:96,12:93,13:96,14:100,15:100,16:72,17:65,18:26,19:7},
    'P18':{7:90,8:96,9:96,10:96,11:90,12:93,13:95,14:100,15:91,16:91,17:82,18:49,19:11},
    'P19':{h:100 for h in range(7,20)},
    'TOTAL':{7:72,8:99,9:99,10:98,11:98,12:97,13:98,14:99,15:97,16:89,17:73,18:43,19:19},
}

ATTENTE_MIDI = {'P2':120,'P3':28,'P4':50,'P5':46,'P6':24,'P8':92,'P18':71}

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
            if code in ('P18','P19'):
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


def saturation_prevue(p, dispo, now, occ_ref):
    cap = CAPACITES[p]
    if cap == 0 or HISTO_SAT_H.get(p) is None:
        return "—", "sat-na"
    if dispo == 0:
        return "Plein 🔴", "sat-late"
    h_base = HISTO_SAT_H[p]
    h = now.hour
    occ_hist = occ_ref.get(p, {}).get(h, 50) / 100
    occ_reel = (cap - dispo) / cap
    decalage_min = round((occ_reel - occ_hist) * 60)
    h_sat_dt = now.replace(hour=int(h_base), minute=int((h_base % 1)*60), second=0, microsecond=0)
    h_sat_corr = h_sat_dt - timedelta(minutes=decalage_min)
    delta = (h_sat_corr - now).total_seconds() / 60
    label = h_sat_corr.strftime("%H:%M")
    if delta < 0:   return f"{label} ⚠️", "sat-late"
    elif delta < 30: return f"{label} (~{int(delta)} min)", "sat-warn"
    else:            return label, "sat-ok"


def color_parking(dispo, cap):
    if cap == 0: return '#555555'
    if dispo == 0: return '#c0392b'
    pct = dispo / cap
    if pct > 0.3: return '#27ae60'
    return '#e67e22'

# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------

st.sidebar.title("⚙️ Paramètres")
is_monday = st.sidebar.checkbox("Lundi", value=(datetime.now().weekday() == 0))
is_rainy  = st.sidebar.checkbox("Pluie 🌧️ (+10%)")
auto_ref  = st.sidebar.checkbox("Rafraîchissement auto 30s")
if st.sidebar.button("🔄 Actualiser"):
    st.cache_data.clear()
    st.rerun()
if auto_ref:
    import time; time.sleep(30)
    st.cache_data.clear()
    st.rerun()

OCC = OCC_LUNDI if is_monday else OCC_AUTRES

# ---------------------------------------------------------------------------
# DONNÉES
# ---------------------------------------------------------------------------

data_live = fetch_data()
now = datetime.now()

st.title("🔋 TCR Bornes — Tableau de bord")
if not data_live:
    st.error("❌ Site Smartevlab injoignable")
    data_live = {p: 0 for p in ORDRE}
else:
    st.success(f"✅ Temps réel — {now.strftime('%H:%M:%S')}")

# --- CONSEIL EN HAUT ---
best_p = None
best_score = -1
for p in ORDRE:
    cap = CAPACITES[p]
    dispo = data_live.get(p, 0)
    if cap > 0 and dispo > 0:
        kw_val = int(re.findall(r'\d+', KW[p])[0])
        score = dispo * kw_val
        if score > best_score:
            best_score = score
            best_p = p
if best_p:
    d = data_live.get(best_p, 0)
    st.markdown(f'<div class="conseil-box">👉 <b>Meilleure borne maintenant : {best_p}</b> — {d} place(s) libre(s) · {KW[best_p]}</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# TABS
# ---------------------------------------------------------------------------

tab1, tab2, tab3, tab4 = st.tabs(["🚗 État", "📈 Affluence", "🗺️ Carte", "🌡️ Heatmap"])

# ===== TAB 1 : ÉTAT =====
with tab1:
    st.subheader("État des parkings")
    rows_html = []
    for p in ORDRE:
        cap   = CAPACITES[p]
        dispo = data_live.get(p, 0)
        if cap == 0:
            statut = "⚫ En panne"; places = "—"; occ_str = "—"
            sat_html = '<span class="sat-na">—</span>'
        else:
            pct = round((cap - dispo) / cap * 100)
            occ_str = f"{pct}%"
            if dispo > cap * 0.3:   statut = "🟢 Disponible"
            elif dispo > 0:          statut = "🟠 Presque plein"
            else:                    statut = "🔴 Complet"
            places = f"{dispo} / {cap}"
            sat_raw, sat_class = saturation_prevue(p, dispo, now, OCC)
            if is_monday and sat_raw not in ("—","Plein 🔴") and "⚠️" not in sat_raw:
                try:
                    t = datetime.strptime(sat_raw.split(" ")[0], "%H:%M") - timedelta(minutes=15)
                    sat_raw = t.strftime("%H:%M") + " (lundi)"
                except: pass
            sat_html = f'<span class="{sat_class}">{sat_raw}</span>'
        rows_html.append(f'<tr><td><b>{p}</b></td><td>{KW[p]}</td><td>{statut}</td><td>{places}</td><td>{occ_str}</td><td>{sat_html}</td></tr>')

    st.markdown(f"""<table>
      <thead><tr><th>Parking</th><th>Puissance</th><th>Statut</th><th>Dispo / Total</th><th>Occupation</th><th>Saturation prévue</th></tr></thead>
      <tbody>{''.join(rows_html)}</tbody></table><br>""", unsafe_allow_html=True)

    st.subheader("🕒 Recharger le midi (11h–14h)")
    midi_rows = []
    for p in ORDRE:
        cap = CAPACITES[p]; dispo = data_live.get(p, 0)
        if cap == 0: continue
        wait = ATTENTE_MIDI.get(p)
        if wait is None:         conseil, emoji = "—", "⚪"
        elif wait <= 5:          conseil, emoji = "< 5 min", "🟢"
        elif wait < 20:          conseil, emoji = f"~{wait} min", "🟢"
        elif wait < 45:          conseil, emoji = f"~{wait} min", "🟡"
        elif wait < 75:          conseil, emoji = f"~{wait} min", "🟠"
        else:                    conseil, emoji = f"~{wait} min — éviter", "🔴"
        midi_rows.append({"Parking":p,"Puissance":KW[p],"Dispo maintenant":f"{dispo}/{cap}","Attente si plein":f"{emoji} {conseil}"})
    st.table(pd.DataFrame(midi_rows).set_index("Parking"))

# ===== TAB 2 : AFFLUENCE SYTADIN =====
with tab2:
    parkings_dispo = ['Tous les parkings'] + [p for p in ORDRE if CAPACITES[p] > 0 and p != 'P19']
    choix  = st.selectbox("Parking :", parkings_dispo)
    key    = 'TOTAL' if choix == 'Tous les parkings' else choix
    heures = list(range(7, 20))
    h_labels = [f"{h}h" for h in heures]

    moy = [OCC[key].get(h, 0) for h in heures]
    if is_rainy: moy = [min(100, v+10) for v in moy]

    b1 = [round(v*0.75) for v in moy]
    b2 = [max(0, v-round(v*0.75)) for v in moy]
    b3 = [max(0, min(100, round(v*1.12))-v) for v in moy]
    b4 = [max(0, 100-min(100, round(v*1.12))) for v in moy]

    if choix == 'Tous les parkings':
        cap_t  = sum(CAPACITES[p] for p in ORDRE if CAPACITES[p]>0 and p!='P19')
        disp_t = sum(data_live.get(p,0) for p in ORDRE if CAPACITES[p]>0 and p!='P19')
        occ_now = round((cap_t-disp_t)/cap_t*100, 1) if cap_t else 0
    else:
        cap_p = CAPACITES[choix]; disp_p = data_live.get(choix, 0)
        occ_now = round((cap_p-disp_p)/cap_p*100, 1) if cap_p else 0
    reel = [occ_now if h==now.hour else None for h in heures]

    fig = go.Figure()
    for band, color, name in [
        (b1,'rgba(90,158,58,0.80)','Faible occupation'),
        (b2,'rgba(232,208,32,0.80)','Habituel'),
        (b3,'rgba(224,128,32,0.80)','Inhabituel'),
        (b4,'rgba(208,48,32,0.80)','Exceptionnel'),
    ]:
        fig.add_trace(go.Bar(x=h_labels,y=band,name=name,marker_color=color,hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=h_labels,y=moy,name='Moyenne',mode='lines',
        line=dict(color='#4a90d9',width=2.5,dash='dot'),hovertemplate='Moyenne: %{y}%<extra></extra>'))
    fig.add_trace(go.Scatter(x=h_labels,y=reel,name='Maintenant',mode='markers',
        marker=dict(color='white',size=13,symbol='diamond',line=dict(color='#4a90d9',width=2)),
        hovertemplate='Maintenant: %{y}%<extra></extra>'))
    fig.update_layout(barmode='stack',plot_bgcolor='#0e1117',paper_bgcolor='#0e1117',
        font_color='#fafafa',xaxis=dict(title='Heure',gridcolor='#2a2d3a'),
        yaxis=dict(title="Occupation (%)",range=[0,100],gridcolor='#2a2d3a',ticksuffix='%'),
        legend=dict(orientation='h',yanchor='bottom',y=-0.35,bgcolor='rgba(0,0,0,0)'),
        margin=dict(t=10,b=10),height=380,hovermode='x unified')
    st.plotly_chart(fig, use_container_width=True)

    # Différence lundi vs autres
    st.subheader("📊 Lundi vs autres jours")
    heures_list = list(range(7,20))
    diff_vals = [OCC_LUNDI['TOTAL'].get(h,0) - OCC_AUTRES['TOTAL'].get(h,0) for h in heures_list]
    colors_diff = ['#f44336' if d > 0 else '#4caf50' for d in diff_vals]

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=[f"{h}h" for h in heures_list], y=diff_vals,
        marker_color=colors_diff,
        hovertemplate='%{x}: %{y:+.1f}%<extra></extra>',
        name='Écart lundi - autres jours'
    ))
    fig2.add_hline(y=0, line_color='#888', line_width=1)
    fig2.update_layout(
        plot_bgcolor='#0e1117', paper_bgcolor='#0e1117', font_color='#fafafa',
        xaxis=dict(gridcolor='#2a2d3a'),
        yaxis=dict(title="Écart d'occupation (%)", gridcolor='#2a2d3a', ticksuffix='%'),
        height=280, margin=dict(t=10, b=10),
        showlegend=False,
    )
    st.plotly_chart(fig2, use_container_width=True)
    st.caption("🔴 Rouge = lundi plus chargé | 🟢 Vert = lundi moins chargé. Le lundi est plus léger en journée (9h–15h) mais plus chargé tôt le matin et en fin de journée.")

# ===== TAB 3 : CARTE =====
with tab3:
    st.subheader("🗺️ Plan du site — disponibilité en temps réel")

    # Charge l'image du plan
    plan_path = os.path.join(os.path.dirname(__file__), "plan_tcr.png")
    try:
        img = Image.open(plan_path)
        img_w, img_h = img.size

        fig_map = go.Figure()

        # Image de fond
        fig_map.add_layout_image(
            dict(source=img, xref="x", yref="y",
                 x=0, y=img_h, sizex=img_w, sizey=img_h,
                 sizing="stretch", opacity=1, layer="below")
        )

        # Marqueurs par parking
        for p, (px_pct, py_pct) in POSITIONS.items():
            cap   = CAPACITES[p]
            dispo = data_live.get(p, 0)
            color = color_parking(dispo, cap)
            px_coord = px_pct * img_w
            py_coord = (1 - py_pct) * img_h

            if cap == 0:
                label = f"{p}<br>⚫ En panne"
            elif dispo == 0:
                label = f"{p}<br>🔴 Complet"
            else:
                label = f"{p}<br>{dispo}/{cap} libres"

            fig_map.add_trace(go.Scatter(
                x=[px_coord], y=[py_coord],
                mode='markers+text',
                marker=dict(size=28, color=color, opacity=0.9,
                            line=dict(color='white', width=2)),
                text=[f"{dispo}" if cap > 0 else "⚫"],
                textposition='middle center',
                textfont=dict(color='white', size=11, family='Arial Black'),
                hovertext=[label],
                hoverinfo='text',
                showlegend=False,
            ))

        fig_map.update_xaxes(range=[0, img_w], showgrid=False, showticklabels=False, zeroline=False)
        fig_map.update_yaxes(range=[0, img_h], showgrid=False, showticklabels=False, zeroline=False, scaleanchor='x')
        fig_map.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='#0e1117',
            margin=dict(l=0, r=0, t=0, b=0),
            height=600,
        )
        st.plotly_chart(fig_map, use_container_width=True)

    except Exception as e:
        st.error(f"Plan non trouvé — place plan_tcr.png dans le même dossier que app.py ({e})")

    # Légende
    col1, col2, col3 = st.columns(3)
    col1.markdown("🟢 **Disponible** (>30% libre)")
    col2.markdown("🟠 **Presque plein** (<30%)")
    col3.markdown("🔴 **Complet** (0 dispo)")

# ===== TAB 4 : HEATMAP =====
with tab4:
    st.subheader("🌡️ Heatmap d'occupation")
    mode_heatmap = st.radio("Données :", ["Lundi", "Mardi–Jeudi", "Différence lundi vs autres"], horizontal=True)

    parkings_hm = ['P2','P3','P4','P5','P6','P8','P18']
    heures_hm   = list(range(7, 20))

    if mode_heatmap == "Lundi":
        matrix = [[OCC_LUNDI[p].get(h, 0) for h in heures_hm] for p in parkings_hm]
        title  = "Occupation % — Lundi"
        cmin, cmax = 0, 100
        colorscale = [[0,'#27ae60'],[0.5,'#f39c12'],[1,'#c0392b']]
        fmt = ".0f"
    elif mode_heatmap == "Mardi–Jeudi":
        matrix = [[OCC_AUTRES[p].get(h, 0) for h in heures_hm] for p in parkings_hm]
        title  = "Occupation % — Mardi à Jeudi"
        cmin, cmax = 0, 100
        colorscale = [[0,'#27ae60'],[0.5,'#f39c12'],[1,'#c0392b']]
        fmt = ".0f"
    else:
        matrix = [[OCC_LUNDI[p].get(h,0) - OCC_AUTRES[p].get(h,0) for h in heures_hm] for p in parkings_hm]
        title  = "Écart lundi vs autres jours (rouge = lundi plus chargé)"
        cmin, cmax = -30, 30
        colorscale = [[0,'#27ae60'],[0.5,'#1a1d27'],[1,'#c0392b']]
        fmt = "+.0f"

    fig_hm = go.Figure(data=go.Heatmap(
        z=matrix,
        x=[f"{h}h" for h in heures_hm],
        y=parkings_hm,
        colorscale=colorscale,
        zmin=cmin, zmax=cmax,
        text=[[f"{v:{fmt}}%" for v in row] for row in matrix],
        texttemplate="%{text}",
        textfont=dict(size=11, color='white'),
        hoverongaps=False,
        hovertemplate='%{y} à %{x} : %{z:.0f}%<extra></extra>',
        colorbar=dict(ticksuffix='%', tickfont=dict(color='#fafafa'),
                      title=dict(text='Occupation', font=dict(color='#fafafa'))),
    ))
    fig_hm.update_layout(
        plot_bgcolor='#0e1117', paper_bgcolor='#0e1117', font_color='#fafafa',
        xaxis=dict(title='Heure', tickfont=dict(size=12)),
        yaxis=dict(title='Parking', tickfont=dict(size=12)),
        height=380, margin=dict(t=20, b=20),
    )
    st.plotly_chart(fig_hm, use_container_width=True)

    if mode_heatmap == "Différence lundi vs autres":
        st.markdown("""
**Ce qu'on observe :**
- 🔴 **7h** : le lundi, les parkings se remplissent **plus tôt** (+12%) — les gens arrivent plus tôt en début de semaine
- 🟢 **9h–15h** : en milieu de journée, le lundi est **moins chargé** (jusqu'à -10%) — certains télétravaillent le lundi
- 🔴 **17h–18h** : le lundi, les départs sont **plus tardifs** (+8 à +14%) — les réunions de début de semaine durent plus longtemps
- **P5** est la plus atypique : le lundi elle est pleine à 7h mais se libère dès 9h30, contrairement aux autres jours
        """)

    with st.expander("ℹ️ Notes"):
        st.markdown("""
- Basé sur **4 jours ouvrés** (lundi 23 → jeudi 26 mars 2026)
- P19 exclue (borne en panne)
- Les données s'affineront semaine après semaine
        """)
