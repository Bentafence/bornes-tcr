import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import re
import plotly.graph_objects as go
from PIL import Image
import os

st.set_page_config(page_title="TCR Bornes", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fafafa; }
    .sat-ok   { color: #4caf50; font-weight: 600; }
    .sat-warn { color: #ff9800; font-weight: 600; }
    .sat-late { color: #f44336; font-weight: 600; }
    .sat-na   { color: #777; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    thead th { background-color: #1e2233 !important; color: #90caf9 !important; padding: 8px 10px; text-align: left; }
    tbody td { padding: 7px 10px; border-bottom: 1px solid #1e2233; }
    tbody tr:nth-child(even) { background-color: #13161f; }
    tbody tr:nth-child(odd)  { background-color: #1a1d27; }
    tbody tr:hover { background-color: #1e2a40; }
    .conseil-box { background: #1e2a40; border-left: 4px solid #4a90d9;
                   padding: 12px 16px; border-radius: 4px; margin-bottom: 10px; font-size: 15px; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
MAPPING_IDS = {'P2':7,'P3':1,'P4':2,'P5':3,'P6':5,'P8':4}
CAPACITES   = {'P2':8,'P3':38,'P4':15,'P5':20,'P6':49,'P8':5,'P18':9,'P19':0}
ORDRE       = ['P2','P3','P4','P5','P6','P8','P18','P19']
KW          = {'P2':'3 kW','P3':'3 kW','P4':'7 kW','P5':'22 kW ⚡','P6':'7 kW','P8':'3 kW','P18':'3 kW','P19':'7 kW'}

POSITIONS = {
    'P2':(0.77,0.09),'P3':(0.77,0.20),'P4':(0.77,0.32),'P5':(0.77,0.43),
    'P6':(0.77,0.62),'P8':(0.63,0.80),'P18':(0.10,0.38),'P19':(0.21,0.38),
}

# Heure de saturation par parking et par jour (décimale) — 7 jours ouvrés
# Format: {parking: {jour: heure_decimale}}
SAT_PAR_JOUR = {
    'P2':  {'Monday':7.02,'Tuesday':7.02,'Wednesday':7.02,'Thursday':7.02,'Friday':7.02},
    'P3':  {'Monday':7.78,'Tuesday':8.10,'Wednesday':None,'Thursday':None,'Friday':8.02},
    'P4':  {'Monday':8.06,'Tuesday':7.31,'Wednesday':7.43,'Thursday':7.27,'Friday':8.10},
    'P5':  {'Monday':7.68,'Tuesday':7.78,'Wednesday':7.68,'Thursday':7.43,'Friday':7.35},
    'P6':  {'Monday':7.77,'Tuesday':7.81,'Wednesday':7.85,'Thursday':7.85,'Friday':None},
    'P8':  {'Monday':7.85,'Tuesday':8.70,'Wednesday':8.10,'Thursday':7.93,'Friday':8.28},
    'P18': {'Monday':7.13,'Tuesday':7.18,'Wednesday':7.18,'Thursday':None,'Friday':7.02},
    'P19': {'Monday':None,'Tuesday':None,'Wednesday':None,'Thursday':None,'Friday':None},
}

# Occupation % par heure, par parking, par jour — données consolidées 7 jours ouvrés
OCC = {
    'Monday': {
        'P2': {7:67,8:94,9:94,10:94,11:94,12:94,13:97,14:100,15:100,16:100,17:100,18:100,19:100},
        'P3': {7:85,8:99,9:99,10:99,11:99,12:98,13:98,14:98,15:97,16:94,17:72,18:43,19:22},
        'P4': {7:97,8:96,9:97,10:97,11:96,12:95,13:99,14:99,15:86,16:95,17:88,18:57,19:11},
        'P5': {7:90,8:100,9:77,10:65,11:70,12:79,13:84,14:84,15:86,16:89,17:90,18:75,19:23},
        'P6': {7:68,8:100,9:100,10:100,11:99,12:100,13:99,14:100,15:99,16:97,17:85,18:47,19:12},
        'P8': {7:50,8:100,9:100,10:100,11:91,12:97,13:93,14:100,15:88,16:72,17:63,18:50,19:20},
        'P18':{7:100,8:100,9:100,10:99,11:100,12:99,13:100,14:99,15:99,16:85,17:60,18:50,19:25},
        'TOTAL':{7:80,8:99,9:96,10:94,11:94,12:95,13:96,14:97,15:95,16:94,17:81,18:54,19:22},
    },
    'Tuesday': {
        'P2': {7:100,8:100,9:100,10:100,11:100,12:100,13:100,14:100,15:100,16:100,17:100,18:100,19:100},
        'P3': {7:79,8:99,9:99,10:98,11:96,12:97,13:98,14:99,15:97,16:83,17:62,18:39,19:18},
        'P4': {7:93,8:99,9:100,10:100,11:100,12:98,13:99,14:100,15:95,16:93,17:70,18:27,19:6},
        'P5': {7:81,8:100,9:100,10:99,11:97,12:93,13:97,14:97,15:95,16:89,17:94,18:64,19:23},
        'P6': {7:56,8:100,9:100,10:100,11:100,12:99,13:99,14:98,15:97,16:95,17:74,18:37,19:12},
        'P8': {7:6,8:77,9:90,10:90,11:88,12:80,13:84,14:90,15:90,16:76,17:71,18:41,19:26},
        'P18':{7:91,8:100,9:100,10:100,11:95,12:97,13:100,14:100,15:94,16:90,17:91,18:53,19:12},
        'TOTAL':{7:72,8:99,9:99,10:99,11:98,12:97,13:98,14:98,15:96,16:90,17:75,18:45,19:20},
    },
    'Wednesday': {
        'P2': {7:100,8:100,9:100,10:100,11:100,12:100,13:100,14:100,15:100,16:100,17:100,18:100,19:100},
        'P3': {7:66,8:96,9:97,10:96,11:94,12:95,13:96,14:100,15:99,16:90,17:70,18:30,19:11},
        'P4': {7:88,8:100,9:97,10:96,11:100,12:99,13:99,14:98,15:97,16:88,17:67,18:34,19:11},
        'P5': {7:78,8:100,9:98,10:95,11:98,12:97,13:100,14:100,15:97,16:90,17:92,18:74,19:40},
        'P6': {7:54,8:100,9:100,10:98,11:100,12:100,13:97,14:100,15:97,16:93,17:68,18:35,19:7},
        'P8': {7:35,8:98,9:100,10:100,11:100,12:100,13:100,14:100,15:100,16:60,17:33,18:2,19:0},
        'P18':{7:94,8:99,9:100,10:100,11:94,12:95,13:93,14:100,15:87,16:89,17:73,18:45,19:9},
        'TOTAL':{7:69,8:99,9:99,10:97,11:98,12:98,13:98,14:100,15:97,16:90,17:73,18:42,19:18},
    },
    'Thursday': {
        'P2': {7:100,8:100,9:100,10:100,11:100,12:100,13:100,14:100,15:100,16:100,17:100,18:100,19:100},
        'P3': {7:84,8:97,9:97,10:97,11:97,12:97,13:96,14:97,15:97,16:86,17:64,18:36,19:26},
        'P4': {7:95,8:98,9:100,10:100,11:99,12:98,13:100,14:99,15:92,16:92,17:72,18:37,19:20},
        'P5': {7:80,8:100,9:98,10:100,11:97,12:98,13:98,14:90,15:88,16:85,17:91,18:74,19:35},
        'P6': {7:54,8:100,9:100,10:100,11:99,12:99,13:100,14:99,15:98,16:94,17:76,18:42,19:8},
        'P8': {7:43,8:100,9:100,10:100,11:93,12:98,13:100,14:100,15:100,16:77,17:65,18:29,19:20},
        'P18':{7:87,8:89,9:89,10:89,11:85,12:88,13:86,14:100,15:91,16:91,17:82,18:45,19:22},
        'TOTAL':{7:74,8:98,9:98,10:99,11:97,12:98,13:98,14:98,15:95,16:89,17:76,18:48,19:24},
    },
    'Friday': {
        'P2': {7:100,8:100,9:100,10:100,11:100,12:100,13:100,14:100,15:100,16:100,17:100,18:100,19:100},
        'P3': {7:50,8:100,9:100,10:98,11:95,12:97,13:97,14:96,15:96,16:84,17:65,18:37,19:17},
        'P4': {7:73,8:99,9:100,10:100,11:100,12:96,13:99,14:91,15:85,16:85,17:83,18:44,19:10},
        'P5': {7:88,8:100,9:99,10:99,11:97,12:96,13:99,14:98,15:98,16:94,17:74,18:52,19:23},
        'P6': {7:45,8:98,9:98,10:98,11:98,12:97,13:99,14:99,15:91,16:77,17:59,18:34,19:11},
        'P8': {7:10,8:90,9:100,10:100,11:100,12:100,13:100,14:100,15:100,16:87,17:52,18:31,19:20},
        'P18':{7:98,8:100,9:100,10:100,11:100,12:100,13:98,14:100,15:75,16:49,17:32,18:3,19:0},
        'TOTAL':{7:60,8:99,9:99,10:99,11:98,12:97,13:99,14:98,15:92,16:82,17:65,18:40,19:19},
    },
}

# Attente midi mise à jour (7 jours ouvrés)
ATTENTE_MIDI = {'P2':120,'P3':37,'P4':44,'P5':36,'P6':24,'P8':96,'P18':60}

# Branchements par jour de semaine
SESSIONS = {'Monday':202,'Tuesday':186,'Wednesday':185,'Thursday':160,'Friday':169}

def get_jour_fr(jour_en):
    m = {'Monday':'Lundi','Tuesday':'Mardi','Wednesday':'Mercredi',
         'Thursday':'Jeudi','Friday':'Vendredi','Saturday':'Samedi','Sunday':'Dimanche'}
    return m.get(jour_en, jour_en)

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
    jour_en = now.strftime('%A')
    if cap == 0: return "—", "sat-na"
    if dispo == 0: return "Plein 🔴", "sat-late"
    h_base = SAT_PAR_JOUR.get(p, {}).get(jour_en)
    if h_base is None: return "Rarement plein", "sat-ok"
    h = now.hour
    occ_hist = occ_ref.get(p, {}).get(h, 50) / 100
    occ_reel = (cap - dispo) / cap
    decalage_min = round((occ_reel - occ_hist) * 60)
    h_sat_dt = now.replace(hour=int(h_base), minute=int((h_base % 1)*60), second=0, microsecond=0)
    h_sat_corr = h_sat_dt - timedelta(minutes=decalage_min)
    delta = (h_sat_corr - now).total_seconds() / 60
    label = h_sat_corr.strftime("%H:%M")
    if delta < 0:    return f"{label} ⚠️", "sat-late"
    elif delta < 30: return f"{label} (~{int(delta)} min)", "sat-warn"
    else:            return label, "sat-ok"


def color_parking(dispo, cap):
    if cap == 0: return '#555'
    if dispo == 0: return '#c0392b'
    if dispo / cap > 0.3: return '#27ae60'
    return '#e67e22'

# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
st.sidebar.title("⚙️ Paramètres")
now = datetime.now()
jour_auto = now.strftime('%A')
jour_options = ['Monday','Tuesday','Wednesday','Thursday','Friday']
jour_labels  = ['Lundi','Mardi','Mercredi','Jeudi','Vendredi']
idx_auto = jour_options.index(jour_auto) if jour_auto in jour_options else 0
jour_sel_idx = st.sidebar.selectbox("Jour de la semaine", range(len(jour_options)),
    format_func=lambda i: jour_labels[i], index=idx_auto)
jour_sel = jour_options[jour_sel_idx]
is_rainy = st.sidebar.checkbox("Pluie 🌧️ (+10%)")
auto_ref = st.sidebar.checkbox("Rafraîchissement auto 30s")
if st.sidebar.button("🔄 Actualiser"):
    st.cache_data.clear()
    st.rerun()
if auto_ref:
    import time; time.sleep(30)
    st.cache_data.clear()
    st.rerun()

occ_ref = {p: OCC[jour_sel].get(p, {}) for p in ORDRE}

# ---------------------------------------------------------------------------
# DONNÉES
# ---------------------------------------------------------------------------
data_live = fetch_data()
st.title("🔋 TCR Bornes — Tableau de bord")
col1, col2 = st.columns([3,1])
with col1:
    if not data_live:
        st.error("❌ Site Smartevlab injoignable")
        data_live = {p: 0 for p in ORDRE}
    else:
        st.success(f"✅ Temps réel — {now.strftime('%H:%M:%S')} · {get_jour_fr(jour_sel)}")
with col2:
    sessions_j = SESSIONS.get(jour_sel, 180)
    st.metric("Sessions habituelles", f"~{sessions_j}/jour")

# Conseil
best_p, best_score = None, -1
for p in ORDRE:
    cap = CAPACITES[p]; dispo = data_live.get(p, 0)
    if cap > 0 and dispo > 0:
        kw_val = int(re.findall(r'\d+', KW[p])[0])
        score = dispo * kw_val
        if score > best_score:
            best_score = score; best_p = p
if best_p:
    d = data_live.get(best_p, 0)
    st.markdown(f'<div class="conseil-box">👉 <b>Meilleure borne maintenant : {best_p}</b> — {d} place(s) libre(s) · {KW[best_p]}</div>',
                unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# TABS
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🚗 État & Saturation", "📈 Affluence", "🗺️ Carte", "🌡️ Heatmap", "📊 Comparaison jours"])

# ===== TAB 1 =====
with tab1:
    st.subheader("État des parkings")
    rows_html = []
    for p in ORDRE:
        cap = CAPACITES[p]; dispo = data_live.get(p, 0)
        if cap == 0:
            statut="⚫ En panne"; places="—"; occ_str="—"
            sat_html='<span class="sat-na">—</span>'
        else:
            pct = round((cap-dispo)/cap*100)
            occ_str = f"{pct}%"
            statut = "🟢 Disponible" if dispo > cap*0.3 else ("🟠 Presque plein" if dispo > 0 else "🔴 Complet")
            places = f"{dispo} / {cap}"
            sat_raw, sat_class = saturation_prevue(p, dispo, now, occ_ref[p] if isinstance(occ_ref, dict) else {})
            sat_html = f'<span class="{sat_class}">{sat_raw}</span>'
        rows_html.append(f'<tr><td><b>{p}</b></td><td>{KW[p]}</td><td>{statut}</td><td>{places}</td><td>{occ_str}</td><td>{sat_html}</td></tr>')

    st.markdown(f"""<table>
      <thead><tr><th>Parking</th><th>Puissance</th><th>Statut</th><th>Dispo/Total</th><th>Occupation</th><th>Saturation prévue</th></tr></thead>
      <tbody>{''.join(rows_html)}</tbody></table><br>""", unsafe_allow_html=True)

    # Tableau saturation par jour
    st.subheader("⏱️ Heure de saturation par parking et jour")
    jours_fr = {'Monday':'Lundi','Tuesday':'Mardi','Wednesday':'Mercredi','Thursday':'Jeudi','Friday':'Vendredi'}
    sat_rows = []
    for p in [p for p in ORDRE if CAPACITES[p] > 0 and p != 'P19']:
        row = {'Parking': p, 'Puissance': KW[p]}
        for j_en, j_fr in jours_fr.items():
            h = SAT_PAR_JOUR.get(p, {}).get(j_en)
            if h is None:
                row[j_fr] = "Rarement plein"
            else:
                hh = int(h); mm = int((h % 1) * 60)
                row[j_fr] = f"{hh:02d}h{mm:02d}" if mm else f"{hh:02d}h00"
        sat_rows.append(row)
    st.dataframe(pd.DataFrame(sat_rows).set_index('Parking'),
                 use_container_width=True,
                 column_config={j: st.column_config.TextColumn(j, width="small") for j in jours_fr.values()})

    # Midi
    st.subheader("🕒 Recharger le midi (11h–14h)")
    st.caption(f"Attente si parking plein — données {len(SESSIONS)} jours ouvrés")
    midi_rows = []
    for p in ORDRE:
        cap = CAPACITES[p]; dispo = data_live.get(p, 0)
        if cap == 0: continue
        wait = ATTENTE_MIDI.get(p)
        if wait is None:    conseil, emoji = "—", "⚪"
        elif wait <= 5:     conseil, emoji = "< 5 min", "🟢"
        elif wait < 20:     conseil, emoji = f"~{wait} min", "🟢"
        elif wait < 45:     conseil, emoji = f"~{wait} min", "🟡"
        elif wait < 75:     conseil, emoji = f"~{wait} min", "🟠"
        else:               conseil, emoji = f"~{wait} min — éviter", "🔴"
        midi_rows.append({"Parking":p,"Puissance":KW[p],"Dispo maintenant":f"{dispo}/{cap}","Attente si plein":f"{emoji} {conseil}"})
    st.table(pd.DataFrame(midi_rows).set_index("Parking"))

# ===== TAB 2 : SYTADIN =====
with tab2:
    parkings_dispo = ['Tous les parkings'] + [p for p in ORDRE if CAPACITES[p] > 0 and p != 'P19']
    choix = st.selectbox("Parking :", parkings_dispo)
    key   = 'TOTAL' if choix == 'Tous les parkings' else choix
    heures = list(range(7, 20)); h_labels = [f"{h}h" for h in heures]
    moy = [OCC[jour_sel].get(key, {}).get(h, 0) for h in heures]
    if is_rainy: moy = [min(100, v+10) for v in moy]
    b1=[round(v*0.75) for v in moy]
    b2=[max(0,v-round(v*0.75)) for v in moy]
    b3=[max(0,min(100,round(v*1.12))-v) for v in moy]
    b4=[max(0,100-min(100,round(v*1.12))) for v in moy]
    if choix == 'Tous les parkings':
        cap_t = sum(CAPACITES[p] for p in ORDRE if CAPACITES[p]>0 and p!='P19')
        disp_t = sum(data_live.get(p,0) for p in ORDRE if CAPACITES[p]>0 and p!='P19')
        occ_now = round((cap_t-disp_t)/cap_t*100,1) if cap_t else 0
    else:
        cap_p = CAPACITES[choix]; disp_p = data_live.get(choix,0)
        occ_now = round((cap_p-disp_p)/cap_p*100,1) if cap_p else 0
    reel = [occ_now if h==now.hour else None for h in heures]
    fig = go.Figure()
    for band, color, name in [(b1,'rgba(90,158,58,0.80)','Faible'),(b2,'rgba(232,208,32,0.80)','Habituel'),
                               (b3,'rgba(224,128,32,0.80)','Inhabituel'),(b4,'rgba(208,48,32,0.80)','Exceptionnel')]:
        fig.add_trace(go.Bar(x=h_labels,y=band,name=name,marker_color=color,hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=h_labels,y=moy,name='Moyenne',mode='lines',
        line=dict(color='#4a90d9',width=2.5,dash='dot'),hovertemplate='Moyenne: %{y}%<extra></extra>'))
    fig.add_trace(go.Scatter(x=h_labels,y=reel,name='Maintenant',mode='markers',
        marker=dict(color='white',size=13,symbol='diamond',line=dict(color='#4a90d9',width=2)),
        hovertemplate='Maintenant: %{y}%<extra></extra>'))
    fig.update_layout(barmode='stack',plot_bgcolor='#0e1117',paper_bgcolor='#0e1117',font_color='#fafafa',
        xaxis=dict(title='Heure',gridcolor='#2a2d3a'),
        yaxis=dict(title="Occupation (%)",range=[0,100],gridcolor='#2a2d3a',ticksuffix='%'),
        legend=dict(orientation='h',yanchor='bottom',y=-0.35,bgcolor='rgba(0,0,0,0)'),
        margin=dict(t=10,b=10),height=380,hovermode='x unified')
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Données basées sur 7 jours ouvrés (23 mars → 31 mars 2026) · Affiché : {get_jour_fr(jour_sel)}")

# ===== TAB 3 : CARTE =====
with tab3:
    st.subheader("🗺️ Plan du site — disponibilité en temps réel")
    plan_path = os.path.join(os.path.dirname(__file__), "plan_tcr.png")
    try:
        img = Image.open(plan_path)
        img_w, img_h = img.size
        fig_map = go.Figure()
        fig_map.add_layout_image(dict(source=img,xref="x",yref="y",x=0,y=img_h,
            sizex=img_w,sizey=img_h,sizing="stretch",opacity=1,layer="below"))
        for p, (px_pct, py_pct) in POSITIONS.items():
            cap = CAPACITES[p]; dispo = data_live.get(p,0)
            color = color_parking(dispo, cap)
            px_c = px_pct*img_w; py_c = (1-py_pct)*img_h
            label = f"{p}<br>⚫ En panne" if cap==0 else (f"{p}<br>🔴 Complet" if dispo==0 else f"{p}<br>{dispo}/{cap} libres")
            fig_map.add_trace(go.Scatter(x=[px_c],y=[py_c],mode='markers+text',
                marker=dict(size=28,color=color,opacity=0.9,line=dict(color='white',width=2)),
                text=[f"{dispo}" if cap>0 else "⚫"],textposition='middle center',
                textfont=dict(color='white',size=11,family='Arial Black'),
                hovertext=[label],hoverinfo='text',showlegend=False))
        fig_map.update_xaxes(range=[0,img_w],showgrid=False,showticklabels=False,zeroline=False)
        fig_map.update_yaxes(range=[0,img_h],showgrid=False,showticklabels=False,zeroline=False,scaleanchor='x')
        fig_map.update_layout(plot_bgcolor='rgba(0,0,0,0)',paper_bgcolor='#0e1117',
            margin=dict(l=0,r=0,t=0,b=0),height=600)
        st.plotly_chart(fig_map, use_container_width=True)
    except Exception as e:
        st.warning(f"Place plan_tcr.png dans le même dossier que app.py ({e})")
    c1,c2,c3=st.columns(3)
    c1.markdown("🟢 **Disponible** (>30%)"); c2.markdown("🟠 **Presque plein** (<30%)"); c3.markdown("🔴 **Complet**")

# ===== TAB 4 : HEATMAP =====
with tab4:
    st.subheader("🌡️ Heatmap d'occupation")
    mode_hm = st.radio("Données :", ['Lundi','Mardi','Mercredi','Jeudi','Vendredi'], horizontal=True)
    j_map = {'Lundi':'Monday','Mardi':'Tuesday','Mercredi':'Wednesday','Jeudi':'Thursday','Vendredi':'Friday'}
    j_key = j_map[mode_hm]
    parkings_hm = ['P2','P3','P4','P5','P6','P8','P18']
    heures_hm = list(range(7,20))
    matrix = [[OCC[j_key].get(p,{}).get(h,0) for h in heures_hm] for p in parkings_hm]
    fig_hm = go.Figure(data=go.Heatmap(
        z=matrix, x=[f"{h}h" for h in heures_hm], y=parkings_hm,
        colorscale=[[0,'#27ae60'],[0.5,'#f39c12'],[1,'#c0392b']],
        zmin=0, zmax=100,
        text=[[f"{v:.0f}%" for v in row] for row in matrix],
        texttemplate="%{text}", textfont=dict(size=11,color='white'),
        hovertemplate='%{y} à %{x} : %{z:.0f}%<extra></extra>',
        colorbar=dict(ticksuffix='%',tickfont=dict(color='#fafafa'),
                      title=dict(text='Occupation',font=dict(color='#fafafa'))),
    ))
    fig_hm.update_layout(plot_bgcolor='#0e1117',paper_bgcolor='#0e1117',font_color='#fafafa',
        xaxis=dict(title='Heure',tickfont=dict(size=12)),
        yaxis=dict(title='Parking',tickfont=dict(size=12)),
        height=380,margin=dict(t=20,b=20))
    st.plotly_chart(fig_hm, use_container_width=True)

# ===== TAB 5 : COMPARAISON JOURS =====
with tab5:
    st.subheader("📊 Comparaison des jours de la semaine")
    heures = list(range(7,20)); h_labels = [f"{h}h" for h in heures]
    colors_j = {'Monday':'#4a90d9','Tuesday':'#27ae60','Wednesday':'#f39c12',
                 'Thursday':'#e74c3c','Friday':'#9b59b6'}
    fig_comp = go.Figure()
    for j_en, j_fr in {'Monday':'Lundi','Tuesday':'Mardi','Wednesday':'Mercredi',
                        'Thursday':'Jeudi','Friday':'Vendredi'}.items():
        vals = [OCC[j_en]['TOTAL'].get(h,0) for h in heures]
        fig_comp.add_trace(go.Scatter(x=h_labels,y=vals,name=j_fr,mode='lines',
            line=dict(color=colors_j[j_en],width=2.5 if j_en==jour_sel else 1.5,
                      dash='solid' if j_en==jour_sel else 'dot'),
            hovertemplate=f'{j_fr}: %{{y}}%<extra></extra>'))
    fig_comp.update_layout(plot_bgcolor='#0e1117',paper_bgcolor='#0e1117',font_color='#fafafa',
        xaxis=dict(title='Heure',gridcolor='#2a2d3a'),
        yaxis=dict(title="Occupation (%)",range=[0,100],gridcolor='#2a2d3a',ticksuffix='%'),
        legend=dict(orientation='h',yanchor='bottom',y=-0.25,bgcolor='rgba(0,0,0,0)'),
        height=350,margin=dict(t=10,b=10),hovermode='x unified')
    st.plotly_chart(fig_comp, use_container_width=True)

    # Sessions par jour
    col1,col2,col3,col4,col5 = st.columns(5)
    for col,(j_en,j_fr) in zip([col1,col2,col3,col4,col5],
                                 {'Monday':'Lundi','Tuesday':'Mardi','Wednesday':'Mercredi',
                                  'Thursday':'Jeudi','Friday':'Vendredi'}.items()):
        col.metric(j_fr, f"{SESSIONS[j_en]}", "branchements/jour")

    st.caption("Le jour sélectionné dans la sidebar apparaît en trait plein sur le graphique.")

with st.expander("ℹ️ Notes"):
    st.markdown("""
- **P19** : toujours à 0 — borne en panne
- **P5** : seule borne **22 kW ⚡** — priorité si disponible
- **Données** : 7 jours ouvrés (lundi 23 mars → mardi 31 mars 2026, 2 lundis et 2 mardis)
- **Saturation prévue** : heure habituelle ajustée selon l'occupation actuelle vs moyenne historique
    """)
