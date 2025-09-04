
import streamlit as st
import pandas as pd
import re, json
from pathlib import Path
from normal_utils import load_normals, pick_age_column, get_normal_value
import uuid

st.set_page_config(page_title="CMR Report Builder", layout="wide")

def split_cols(ln: str):
    ln = ln.replace("\t", " ").strip()
    return [c.strip() for c in re.split(r"\s{2,}", ln) if c.strip()]

def is_sep(ln: str) -> bool:
    s = ln.strip()
    return (set(s) <= set("-")) and len(s) >= 5

def parse_sections(text: str):
    sections = {}
    current = None
    for ln in text.splitlines():
        s = ln.strip()
        if s in {"LV","RV","Atria","T1","T2"}:
            current = s
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(ln.rstrip("\n"))
    return sections

def parse_generic_table(lines):
    tables = []
    i=0
    while i < len(lines):
        if is_sep(lines[i]):
            j = i+1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                header = split_cols(lines[j])
                if len(header) >= 2 and (any("Value" in h for h in header) or "Volume" in header):
                    header_full = ["Metric"] + header
                    k = j+1
                    if k < len(lines) and is_sep(lines[k]):
                        k += 1
                    rows = []
                    while k < len(lines):
                        if is_sep(lines[k]):
                            break
                        if not lines[k].strip():
                            k += 1
                            continue
                        parts = split_cols(lines[k])
                        if len(parts) >= 2:
                            parts += [""] * (len(header_full)-len(parts))
                            rows.append(parts[:len(header_full)])
                        else:
                            break
                        k += 1
                    if rows:
                        df = pd.DataFrame(rows, columns=header_full)
                        tables.append(df)
                        i = k
                        continue
        i += 1
    return tables

def parse_t1_global(lines):
    i=0
    while i < len(lines):
        if lines[i].strip().startswith("Global"):
            j = i+1
            while j < len(lines) and is_sep(lines[j]): j += 1
            if j < len(lines):
                header = split_cols(lines[j])
                k = j+1
                if k < len(lines) and is_sep(lines[k]): k += 1
                rows = []
                while k < len(lines) and lines[k].strip():
                    parts = split_cols(lines[k])
                    parts += [""] * (len(header)-len(parts))
                    rows.append(parts[:len(header)])
                    k += 1
                if rows:
                    return pd.DataFrame(rows, columns=header)
        i += 1
    return None

def parse_t2_global(lines):
    i=0
    while i < len(lines):
        if lines[i].strip().startswith("Global"):
            j = i+1
            while j < len(lines) and is_sep(lines[j]): j += 1
            if j < len(lines):
                header = split_cols(lines[j])
                k = j+1
                if k < len(lines) and is_sep(lines[k]): k += 1
                rows = []
                while k < len(lines) and lines[k].strip():
                    parts = split_cols(lines[k])
                    parts += [""] * (len(header)-len(parts))
                    rows.append(parts[:len(header)])
                    k += 1
                if rows:
                    return pd.DataFrame(rows, columns=header)
        i += 1
    return None

def extract_patient_values(text: str):
    secs = parse_sections(text)
    out = {}

    lv_tables = parse_generic_table(secs.get("LV", []))
    lv_df = lv_tables[0] if lv_tables else None
    if lv_df is not None:
        def row(name): 
            m = lv_df["Metric"].str.strip().str.lower() == name.lower()
            return lv_df[m].iloc[0] if m.any() else None
        r = row("LV EDV")
        if r is not None:
            out["LVedv"] = r.get("Value","")
            out["LVedvbsa"] = r.get("Value / BSA","")
        r = row("LV EDM")
        if r is not None:
            out["LVmass"] = r.get("Value","")
            out["LVmassbsa"] = r.get("Value / BSA","")
        r = row("LV EF")
        if r is not None:
            out["LVEF"] = r.get("Value","").replace("%","").strip()
    else:
        lv_df = None

    rv_tables = parse_generic_table(secs.get("RV", []))
    rv_df = rv_tables[0] if rv_tables else None
    if rv_df is not None:
        def rowr(name): 
            m = rv_df["Metric"].str.strip().str.lower() == name.lower()
            return rv_df[m].iloc[0] if m.any() else None
        r = rowr("RV EDV")
        if r is not None:
            out["RVedv"] = r.get("Value","")
            out["RVedvbsa"] = r.get("Value / BSA","")
        r = rowr("RV EF")
        if r is not None:
            out["RVEF"] = r.get("Value","").replace("%","").strip()

    at = parse_generic_table(secs.get("Atria", []))
    if at:
        df = at[0]
        def rowa(name):
            m = df["Metric"].str.strip().str.lower() == name.lower()
            return df[m].iloc[0] if m.any() else None
        r = rowa("LA Maximum")
        if r is not None:
            out["LA"] = r.get("Volume","")
            out["LAbsa"] = r.get("Value / BSA","")
        r = rowa("RA Maximum")
        if r is not None:
            out["RA"] = r.get("Volume","")
            out["RAbsa"] = r.get("Value / BSA","")

    t1g = parse_t1_global(secs.get("T1", []))
    if isinstance(t1g, pd.DataFrame) and "Name" in list(t1g.columns):
        mask = t1g["Name"].str.strip().str.lower().isin(["myo","myocardium"])
        if mask.any():
            row = t1g[mask].iloc[0]
            out["T1_native"] = str(row.get("Native T1 (ms)","")).split()[0].replace(",","")
            out["ECV"] = str(row.get("ECV Value (%)","")).split()[0]

    t2g = parse_t2_global(secs.get("T2", []))
    if isinstance(t2g, pd.DataFrame) and "Name" in list(t2g.columns):
        mask = t2g["Name"].str.strip().str.lower().isin(["myo","myocardium"])
        if mask.any():
            row = t2g[mask].iloc[0]
            import re
            val = str(row.iloc[1])
            nums = re.findall(r"\d+(?:[.,]\d+)?", val)
            if nums:
                out["T2"] = nums[0]

    return out, lv_df, rv_df

DATA_DIR = str(Path(__file__).parent.resolve())
NORMALS = load_normals(DATA_DIR)

def N(sex: str, age: int, key: str) -> str:
    return get_normal_value(NORMALS, sex, age, key)

def _col_widths(rows):
    w = [0]*max(len(r) for r in rows)
    for r in rows:
        for i, c in enumerate(r):
            w[i] = max(w[i], len(str(c)))
    return w

def _format_ascii_table(title: str, df: pd.DataFrame, keep_cols=("Metric","Value","Value / BSA")) -> str:
    if df is None or df.empty:
        return f"--- {title} ---\n(nessun dato)\n"
    cols = [c for c in keep_cols if c in df.columns]
    if not cols:
        return f"--- {title} ---\n(nessun dato)\n"
    header = ["Metric"] + [c for c in cols if c != "Metric"]
    rows = [header]
    for _, row in df.iterrows():
        rows.append([str(row.get(h, "")).strip() for h in header])
    widths = _col_widths(rows)
    def fmt(r):
        return "  ".join(str(c).ljust(widths[i]) for i, c in enumerate(r))
    sep = "-" * max(20, sum(widths) + 2*(len(widths)-1))
    out = [f"{sep}\n{title}\n{sep}"]
    out.append(fmt(header))
    out.append(sep)
    for r in rows[1:]:
        out.append(fmt(r))
    out.append(sep)
    return "\n".join(out) + "\n"

def build_report_text(sex: str, age: int, field3t: bool, pvals: dict, lv_df: pd.DataFrame, rv_df: pd.DataFrame, include_tables: bool) -> str:
    scanner = "3T (Philips 7700)" if field3t else "1,5T"
    t1_norm = "1130–1300 ms" if field3t else "<1045 ms"

    def pv(key, default=""):
        return pvals.get(key, default)

    base = f"""ANAMNESI

TECNICA D’ESAME
Esame eseguito su scanner {scanner}.
Esame eseguito con sequenze morfologiche (STIR), sequenze cine multiplanari, mapping T1 e T2, studio di perfusione miocardica in condizioni di riposo e studio di late gadolinium enhancement (LGE). Durante l’esame è stato iniettato mezzo di contrasto paramagnetico (gadobutrolo) per via endovenosa.

REFERTO
VENTRICOLO SINISTRO dimensionalmente nei limiti di norma (volume telediastolico: {pv('LVedv')}, v.n. {N(sex, age, 'LVedv')} mL*; volume telediastolico indicizzato: {pv('LVedvbsa')}, v.n. {N(sex, age, 'LVedvbsa')} mL/m^2*), di normale morfologia.
Massa miocardica nei limiti ({pv('LVmass')}, v.n. {N(sex, age, 'LVmass')} g*; massa indicizzata {pv('LVmassbsa')}, v.n. {N(sex, age, 'LVmassbsa')} g/m^2*), con normali spessori parietali (spessore telediastolico massimo in corrispondenza del setto interventricolare inferiore basale: mm).
Normale cinesi globale e segmentaria, con frazione d’eiezione conservata (FE {pv('LVEF')} %, v.n.  {N(sex, age, 'LVEF')}%*).
Non aree di edema focale nelle sequenze STIR.
Nei limiti i tempi di rilassamento T1 nativo (media globale: {pv('T1_native')}, v.n. {t1_norm}) e T2 (media globale: {pv('T2')}; v.n. 50 ms; valori borderline 53 ms) e la frazione di volume extracellulare (ECV) (media globale: {pv('ECV')}%, v.n. 27%).
Non significative cicatrici miocardiche nelle sequenze di LGE.
Non evidenti difetti funzionali delle valvole mitralica e aortica.

VENTRICOLO DESTRO dimensionalmente nei limiti di norma (volume telediastolico: {pv('RVedv')}, v.n. {N(sex, age, 'RVedv')} mL*; volume telediastolico indicizzato: {pv('RVedvbsa')}, v.n. {N(sex, age, 'RVedvbsa')} mL/m^2*).
Nei limiti spessore e intensità di segnale della parete libera, che presenta normale contrattilità con conservata frazione di eiezione (FE {pv('RVEF')}, v.n. {N(sex, age, 'RVEF')}%*).

Atri non dilatati.
Atrio sinistro: volume telesistolico {pv('LA')} (v.n. {N(sex, age, 'LA')} mL); volume telesistolico indicizzato {pv('LAbsa')} (v.n. {N(sex, age, 'LAbsa')} mL/m^2*).
Atrio destro: volume telesistolico {pv('RA')} mL (v.n. {N(sex, age, 'RA')} mL); volume telesistolico indicizzato {pv('RAbsa')} (v.n. {N(sex, age, 'RAbsa')} mL/m^2*).

Non versamento pericardico.
Non ispessimento dei foglietti pericardici.


CONCLUSIONI
Reperti cardio-RM nei limiti di norma.


*valori di riferimento: Raisi-Estabragh, Z, Szabo, L, McCracken, C. et al. Cardiovascular Magnetic Resonance Reference Ranges from the Healthy Hearts Consortium. J Am Coll Cardiol Img. 2024 Jul, 17 (7) 746–762.

TABELLA PARAMETRI VOLUMETRICO-FUNZIONALI VENTRICOLO SINISTRO E VENTRICOLO DESTRO:
"""
    if include_tables:
        lv_txt = _format_ascii_table("--- LV ---", lv_df, keep_cols=("Metric","Value","Value / BSA"))
        rv_txt = _format_ascii_table("--- RV ---", rv_df, keep_cols=("Metric","Value","Value / BSA"))
        base = base + "\n" + lv_txt + "\n" + rv_txt
    return base

st.title("CMR Report Builder v4.2")

col1, col2, col3, col4 = st.columns([1,1,1,1])
with col1:
    sex = st.selectbox("Sesso", ["M", "F"], index=0, help="M = maschio, F = femmina")
with col2:
    age = st.number_input("Età", min_value=0, max_value=110, value=18, step=1)
with col3:
    field3t = st.checkbox("Scanner 3T (Philips 7700)", value=False, help="Se non spuntato → 1,5T")
with col4:
    include_tables = st.checkbox("Includi tabella LV/RV a fine referto", value=True)

uploaded = st.file_uploader("Carica file TXT", type=["txt"])
text_input = st.text_area("...oppure incolla qui il testo", height=260)

if uploaded or text_input.strip():
    if uploaded:
        text = uploaded.read().decode("utf-8", errors="ignore")
    else:
        text = text_input

    pvals, lv_df, rv_df = extract_patient_values(text)
    report_text = build_report_text(sex, int(age), field3t, pvals, lv_df, rv_df, include_tables)
    report_text_unicode = report_text.replace("^2", "²")

    st.subheader("Referto")
    st.text(report_text_unicode)

    st.write("")
    st.caption("Copia rapida del referto:")
    txt_id = "report_" + str(uuid.uuid4()).replace("-", "")
    from streamlit.components.v1 import html
    html(f"""
        <div>
            <button id="btn_{txt_id}" style="padding:8px 12px; font-weight:600;">Copia il referto</button>
            <pre id="{txt_id}" style="position:absolute; left:-9999px; white-space:pre-wrap;">{report_text_unicode}</pre>
        </div>
        <script>
            const btn = document.getElementById("btn_{txt_id}");
            const pre = document.getElementById("{txt_id}");
            btn.addEventListener("click", async () => {{
            try {{
                await navigator.clipboard.writeText(pre.innerText);
                btn.innerText = "Copiato!";
                setTimeout(()=>btn.innerText="Copia il referto", 1500);
            }} catch (e) {{
                const range = document.createRange();
                range.selectNode(pre);
                const sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
                document.execCommand("copy");
                sel.removeAllRanges();
                btn.innerText = "Copiato!";
                setTimeout(()=>btn.innerText="Copia il referto", 1500);
            }}
         }});
        </script>
    """, height=60)


    with st.expander("Valori paziente estratti (debug)"):
        st.json(pvals, expanded=False)
else:
    st.info("Carica o incolla un testo per generare il referto.")
