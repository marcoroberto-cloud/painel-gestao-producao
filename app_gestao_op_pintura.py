from datetime import datetime, timedelta, timezone
import io
import json
import os
import re
import shutil
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="FCM Metálicos: Gestão Integrada",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    * {
        user-select: text !important;
        -webkit-user-select: text !important;
        -moz-user-select: text !important;
        -ms-user-select: text !important;
    }
    .block-container {
        padding-top: 3.5rem !important;
        padding-bottom: 1rem !important;
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
        max-width: 100% !important;
    }
    
    .sticky-top-panel {
        position: sticky;
        top: 2.8rem;
        z-index: 999;
        background-color: #161b22;
        padding: 10px 14px;
        border: 1px solid #30363d;
        border-radius: 10px;
        margin-bottom: 14px;
        box-shadow: 0 4px 14px rgba(0,0,0,0.6);
    }
    
    [data-testid="stMetricValue"] {
        font-size: 1.15rem !important;
        font-weight: 700 !important;
        color: #58a6ff !important;
        line-height: 1.1 !important;
    }
    [data-testid="stMetricLabel"] { font-size: 0.75rem !important; line-height: 1.1 !important; color: #c9d1d9 !important; }
    [data-testid="stMetricDelta"] { font-size: 0.70rem !important; }
    
    div[data-baseweb="select"] * { font-size: 0.78rem !important; line-height: 1.25 !important; }
    div[data-baseweb="tag"] { 
        background-color: #1f6feb !important; 
        color: #ffffff !important;
        border-radius: 4px !important;
        padding: 2px 8px !important; 
        margin: 1px !important;
    }
    div[data-baseweb="tag"] span { font-size: 0.74rem !important; color: #ffffff !important; }
    
    .stTabs [data-baseweb="tab-list"] { gap: 6px; overflow-x: auto; }
    .stTabs [data-baseweb="tab"] { height: 38px; font-weight: 600; font-size: 0.80rem; padding: 0 10px; white-space: nowrap; border-radius: 6px; }
    
    .card-mobile-clean {
        background-color: #1c2128;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 12px 14px;
        margin-bottom: 10px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.3);
    }
    .card-mobile-clean b { color: #f0f6fc; }
    
    .badge-status {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-bottom: 6px;
    }
    .badge-ok { background-color: rgba(46, 160, 67, 0.2); color: #3fb950; border: 1px solid #2ea043; }
    .badge-warn { background-color: rgba(210, 153, 34, 0.2); color: #d29922; border: 1px solid #d29922; }
    .badge-alert { background-color: rgba(248, 81, 73, 0.2); color: #ff7b72; border: 1px solid #f85149; }

    [data-testid="stDataFrame"] {
        width: 100% !important;
        min-height: 500px !important;
    }
    [data-testid="stDataFrame"] > div {
        width: 100% !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

STORAGE_DIR = "dados_compartilhados"
BACKUPS_DIR = os.path.join(STORAGE_DIR, "historico_backups")
os.makedirs(STORAGE_DIR, exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)
META_FILE = os.path.join(STORAGE_DIR, "metadata.json")

caminho_op_pqt = os.path.join(STORAGE_DIR, "base_op.parquet")
caminho_rom_pqt = os.path.join(STORAGE_DIR, "base_romaneio.parquet")
caminho_comp_pqt = os.path.join(STORAGE_DIR, "base_compras.parquet")
caminho_sc_pqt = os.path.join(STORAGE_DIR, "base_sc.parquet")

FUSO_BRASILIA = timezone(timedelta(hours=-3))

def carregar_meta():
    if os.path.exists(META_FILE):
        try:
            with open(META_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def salvar_meta(meta):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def criar_backup_historico(data_str):
    stamp = datetime.now(FUSO_BRASILIA).strftime("%Y%m%d_%H%M%S")
    pasta_destino = os.path.join(BACKUPS_DIR, stamp)
    os.makedirs(pasta_destino, exist_ok=True)

    for fname in [
        "base_op.parquet",
        "base_romaneio.parquet",
        "base_compras.parquet",
        "base_sc.parquet",
    ]:
        p_orig = os.path.join(STORAGE_DIR, fname)
        if os.path.exists(p_orig):
            shutil.copy2(p_orig, os.path.join(pasta_destino, fname))

    with open(os.path.join(pasta_destino, "info.json"), "w", encoding="utf-8") as f:
        json.dump({"timestamp": stamp, "data_formatada": data_str}, f)

    todas_pastas = sorted(os.listdir(BACKUPS_DIR), reverse=True)
    if len(todas_pastas) > 5:
        for p_remover in todas_pastas[5:]:
            shutil.rmtree(os.path.join(BACKUPS_DIR, p_remover), ignore_errors=True)

def listar_historicos_disponiveis():
    backups = []
    if os.path.exists(BACKUPS_DIR):
        for pasta in sorted(os.listdir(BACKUPS_DIR), reverse=True):
            p_info = os.path.join(BACKUPS_DIR, pasta, "info.json")
            if os.path.exists(p_info):
                try:
                    with open(p_info, "r", encoding="utf-8") as f:
                        info = json.load(f)
                        backups.append((pasta, info.get("data_formatada", pasta)))
                except Exception:
                    pass
    return backups

def restaurar_backup(pasta_id):
    pasta_origem = os.path.join(BACKUPS_DIR, pasta_id)
    if os.path.exists(pasta_origem):
        for fname in [
            "base_op.parquet",
            "base_romaneio.parquet",
            "base_compras.parquet",
            "base_sc.parquet",
        ]:
            p_bkp = os.path.join(pasta_origem, fname)
            p_dest = os.path.join(STORAGE_DIR, fname)
            if os.path.exists(p_bkp):
                shutil.copy2(p_bkp, p_dest)
            elif os.path.exists(p_dest):
                os.remove(p_dest)
        p_info = os.path.join(pasta_origem, "info.json")
        if os.path.exists(p_info):
            with open(p_info, "r", encoding="utf-8") as f:
                info = json.load(f)
                meta = carregar_meta()
                meta["ultima_atualizacao"] = (
                    f"Restaurado de: {info.get('data_formatada')}"
                )
                salvar_meta(meta)

def normalizar_texto(t):
    if pd.isna(t) or t is None:
        return ""
    
    s = str(t)
    # Remove artefatos de quebra de linha do Excel (ex: _x000D_)
    s = re.sub(r"(?i)_x[0-9a-f]{4}_", " ", s)
    s = (
        s.replace("\xa0", " ")
        .replace("\u00a0", " ")
        .replace("\r", " ")
        .replace("\n", " ")
    )
    s = re.sub(r"[\x00-\x1f\x7f-\x9f\ufeff]", "", s)
    return re.sub(r"\s+", " ", s).strip().upper()

def limpar_cod(c):
    if pd.isna(c) or c is None:
        return ""
    s = str(c).replace("\xa0", " ").replace("\u00a0", " ")
    s = re.sub(r"[\x00-\x1f\x7f-\x9f\ufeff]", "", s)
    return s.strip().upper()

def converter_num(v):
    if pd.isna(v) or v is None:
        return 0.0
    try:
        s = str(v).replace("\xa0", "").replace(" ", "").replace(",", ".")
        return float(s)
    except Exception:
        return 0.0

def formatar_data_br(val):
    if (
        pd.isna(val)
        or val is None
        or str(val).strip() in ["-", "", "nan", "NaT", "None"]
    ):
        return "-"
    s = str(val).strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    m_br = re.match(r"^(\d{2})/(\d{2})/(\d{4})", s)
    if m_br:
        return s[:10]
    return s

def padronizar_fornecedor_romaneio(val):
    if pd.isna(val) or not str(val).strip() or str(val).strip() == "-":
        return "-"
    t = normalizar_texto(val)
    if re.match(r"^\d{2}\.[A-Z0-9]+\.", t):
        return "-"
    if "0002805" in t or "MEGACOLORS PRIME" in t or "PRIME" in t:
        return "MEGACOLORS PRIME"
    elif "0002695" in t or "MEGACOLORS" in t or "MEGA COLORS" in t:
        return "MEGACOLORS"
    elif "000092" in t or "REVRI" in t:
        return "REVRI"
    elif "000022" in t or "ECE" in t:
        return "ECE"
    elif "0002739" in t or "FORT COLOR" in t or "FORTCOLOR" in t:
        return "FORT COLOR"
    elif "000408" in t or "ZINCOBRIL" in t or "ZINCO BRIL" in t:
        return "ZINCOBRIL"
    m = re.search(r"-\s*F\s*-\s*(.+)", t)
    if m:
        return m.group(1).strip()
    return t

def buscar_col_flex(df, lista_padroes, excluir_padroes=None):
    if df.empty or len(df.columns) == 0:
        return None
    excluir = [normalizar_texto(e) for e in (excluir_padroes or [])]
    for c in df.columns:
        c_clean = normalizar_texto(c)
        if any(e in c_clean for e in excluir):
            continue
        for p in lista_padroes:
            if normalizar_texto(p) == c_clean:
                return c
    for c in df.columns:
        c_clean = normalizar_texto(c)
        if any(e in c_clean for e in excluir):
            continue
        for p in lista_padroes:
            if normalizar_texto(p) in c_clean:
                return c
    return None

def ler_excel_completo(fonte, sheet_name=0):
    try:
        return pd.read_excel(fonte, sheet_name=sheet_name, engine="calamine")
    except Exception:
        try:
            return pd.read_excel(fonte, sheet_name=sheet_name, engine="openpyxl")
        except Exception:
            return pd.read_excel(fonte, sheet_name=sheet_name)

@st.cache_data(show_spinner=False)
def gerar_excel_tabela(df_exportar, nome_aba="Dados"):
    output = io.BytesIO()
    if df_exportar.empty:
        return output.getvalue()
    df_clean = df_exportar.copy()

    def sanitizar_val(val):
        if pd.isna(val) or val is None:
            return ""
        s = str(val)
        return "".join(ch for ch in s if ord(ch) >= 32 or ch in "\n\r\t")

    df_clean.columns = [sanitizar_val(c) for c in df_clean.columns]
    df_clean = df_clean.astype(str).map(sanitizar_val)
    aba_segura = re.sub(r"[\\/*?:\[\]]", "", str(nome_aba))[:30]
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_clean.to_excel(writer, index=False, sheet_name=aba_segura)
    return output.getvalue()

def renderizar_botao_copiar_tabela(df_dados, button_id="copy_btn"):
    if df_dados.empty:
        return
    tsv_data = df_dados.to_csv(sep="\t", index=False)
    json_tsv = json.dumps(tsv_data)

    html_code = f"""
    <div style="display:inline-block; margin-right:8px;">
        <button id="{button_id}" style="
            background-color: #21262d;
            color: #c9d1d9;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 5px 12px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: 0.2s;
        " onmouseover="this.style.backgroundColor='#30363d'" onmouseout="this.style.backgroundColor='#21262d'">
            📋 Copiar Tabela
        </button>
    </div>
    <script>
        document.getElementById('{button_id}').addEventListener('click', function() {{
            const textToCopy = {json_tsv};
            navigator.clipboard.writeText(textToCopy).then(function() {{
                const btn = document.getElementById('{button_id}');
                btn.innerHTML = '✅ Copiado!';
                btn.style.borderColor = '#2ea043';
                btn.style.color = '#3fb950';
                setTimeout(() => {{
                    btn.innerHTML = '📋 Copiar Tabela';
                    btn.style.borderColor = '#30363d';
                    btn.style.color = '#c9d1d9';
                }}, 2000);
            }}).catch(function(err) {{
                alert('Erro ao copiar dados.');
            }});
        }});
    </script>
    """
    components.html(html_code, height=38)

def obter_mtimes(pasta_base=STORAGE_DIR):
    return (
        os.path.getmtime(os.path.join(pasta_base, "base_op.parquet")) if os.path.exists(os.path.join(pasta_base, "base_op.parquet")) else 0,
        os.path.getmtime(os.path.join(pasta_base, "base_romaneio.parquet")) if os.path.exists(os.path.join(pasta_base, "base_romaneio.parquet")) else 0,
        os.path.getmtime(os.path.join(pasta_base, "base_compras.parquet")) if os.path.exists(os.path.join(pasta_base, "base_compras.parquet")) else 0,
        os.path.getmtime(os.path.join(pasta_base, "base_sc.parquet")) if os.path.exists(os.path.join(pasta_base, "base_sc.parquet")) else 0,
    )

@st.cache_data(show_spinner=False)
def processar_todas_as_bases(mtimes, pasta_base=STORAGE_DIR):
    p_op = os.path.join(pasta_base, "base_op.parquet")
    p_rom = os.path.join(pasta_base, "base_romaneio.parquet")
    p_comp = os.path.join(pasta_base, "base_compras.parquet")
    p_sc = os.path.join(pasta_base, "base_sc.parquet")

    df_op_raw = pd.read_parquet(p_op) if os.path.exists(p_op) else pd.DataFrame()
    df_rom_raw = pd.read_parquet(p_rom) if os.path.exists(p_rom) else pd.DataFrame()
    df_comp_raw = pd.read_parquet(p_comp) if os.path.exists(p_comp) else pd.DataFrame()
    df_sc_raw = pd.read_parquet(p_sc) if os.path.exists(p_sc) else pd.DataFrame()

    catalogo_descricoes = {}

    # 1. OP
    df_op = pd.DataFrame()
    if not df_op_raw.empty:
        col_obs_op = buscar_col_flex(df_op_raw, ["OBSERVAÇÃO", "OBSERVAÇÕES", "OBSERVACAO", "OBSERVACOES", "OBS", "PROJETO", "LOTE"])
        if not col_obs_op:
            if len(df_op_raw.columns) >= 2 and "OBSERV" in normalizar_texto(df_op_raw.columns[1]):
                col_obs_op = df_op_raw.columns[1]
            elif len(df_op_raw.columns) >= 12:
                col_obs_op = df_op_raw.columns[11]

        col_prod_op = buscar_col_flex(df_op_raw, ["PRODUTO", "COD PROD", "CODIGO"])
        col_desc_op = buscar_col_flex(df_op_raw, ["DESC. PROD", "DESCRICAO", "DESCRIÇÃO", "DESC PROD"])
        col_qtd_op = buscar_col_flex(df_op_raw, ["QUANTIDADE", "QUANTI", "QTD PLAN"])
        col_prodz_op = buscar_col_flex(df_op_raw, ["QTD.PRODUZID", "PRODUZIDO", "QTD PRODUZIDA", "QTD.PRODUZ"])
        col_mes_op = buscar_col_flex(df_op_raw, ["MÊS-ANO", "MES-ANO", "MÊS", "MES"])
        col_dt_fim = buscar_col_flex(df_op_raw, ["DT REAL FIM", "REAL FIM", "DATA FIM", "DATA"])

        df_op = df_op_raw.copy()
        df_op["OBS_NORM"] = df_op[col_obs_op].apply(normalizar_texto) if col_obs_op else ""
        df_op["COD_PECA"] = df_op[col_prod_op].apply(limpar_cod) if col_prod_op else ""
        df_op["DESC_PECA"] = df_op[col_desc_op].fillna("-").astype(str) if col_desc_op else "-"
        df_op["QTD_PLAN"] = df_op[col_qtd_op].apply(converter_num) if col_qtd_op else 0.0
        df_op["QTD_PROD"] = df_op[col_prodz_op].apply(converter_num) if col_prodz_op else 0.0
        df_op["MES_ANO"] = df_op[col_mes_op].astype(str).str.strip() if col_mes_op else "Geral"
        df_op["ANO"] = df_op["MES_ANO"].str.extract(r"^(\d{4})")[0]
        df_op["MES"] = df_op["MES_ANO"].str.extract(r"/(\d{2})")[0]
        df_op["DT_FABR"] = df_op[col_dt_fim].apply(formatar_data_br) if col_dt_fim else "-"

        for _, r in df_op[["COD_PECA", "DESC_PECA"]].dropna().iterrows():
            c, d = str(r["COD_PECA"]).strip(), str(r["DESC_PECA"]).strip()
            if c and d and d not in ["-", "NAN", "NONE", ""]:
                catalogo_descricoes[c] = d

    # 2. Romaneio
    df_rom = pd.DataFrame()
    if not df_rom_raw.empty:
        col_obs_rom = buscar_col_flex(df_rom_raw, ["OBSERVAÇÕES", "OBSERVACOES", "OBSERVAÇÃO", "OBSERVACAO", "OBS", "PROJETO", "LOTE"])
        if col_obs_rom is None and len(df_rom_raw.columns) >= 16:
            col_obs_rom = df_rom_raw.columns[15]

        col_prod_rom = buscar_col_flex(df_rom_raw, ["PRODUTO", "COD. PRODUTO", "COD PROD"], excluir_padroes=["PINTURA", "DESC", "TRATAMENTO"])
        col_desc_rom = buscar_col_flex(df_rom_raw, ["DESCRIÇÃO", "DESCRICAO", "DESC. PROD", "DESC"])
        col_qtd_rom = buscar_col_flex(df_rom_raw, ["QTD", "QTDE", "QUANTIDADE"], excluir_padroes=["RET", "SALDO"])
        col_ret_rom = buscar_col_flex(df_rom_raw, ["QT RET", "QT_RET", "RETORNADO", "QTD RET", "QT"])

        if col_ret_rom == col_qtd_rom:
            cols_disp = [c for c in df_rom_raw.columns if "QT" in normalizar_texto(c) or "RET" in normalizar_texto(c)]
            if len(cols_disp) >= 2:
                col_qtd_rom, col_ret_rom = cols_disp[0], cols_disp[1]

        col_saldo_rom = buscar_col_flex(df_rom_raw, ["SALDO", "SALD", "SALDO "])
        col_forn_rom = buscar_col_flex(df_rom_raw, ["CLIENTE/FORN", "CLIENTE/FC", "CLIENTE / FORN", "CLIENTE", "FORNECEDOR"], excluir_padroes=["PROD", "COD", "COR", "PECA", "PEÇA", "DESC", "PINTURA"])
        col_doc_rom = buscar_col_flex(df_rom_raw, ["DOC.ORIGINAL", "DOC.ORIGIR", "DOC.ORIGEM", "DOC ORIGEM", "ROMANEIO", "Nº ROMANEIO", "DOC"])
        col_dt_envio_rom = buscar_col_flex(df_rom_raw, ["DT EMISSÃO", "DT EMISSÃ", "DT EMISSAO", "DT. EMISSAO", "DATA EMISSAO", "DATA ENVIO", "DT ENVIO"])
        col_nf_ret_rom = buscar_col_flex(df_rom_raw, ["NF RET", "NF_RET", "NOTA RET", "NF RETORNO"])
        col_dt_ret_rom = buscar_col_flex(df_rom_raw, ["DT RET", "DT_RET", "DATA RET", "DATA RETORNO"])

        df_rom = df_rom_raw.copy()
        df_rom["OBS_NORM"] = df_rom[col_obs_rom].apply(normalizar_texto) if col_obs_rom else ""
        df_rom["COD_PECA"] = df_rom[col_prod_rom].apply(limpar_cod) if col_prod_rom else ""
        df_rom["DESC_PECA"] = df_rom[col_desc_rom].fillna("-").astype(str) if col_desc_rom else "-"
        df_rom["QTD_ENV"] = df_rom[col_qtd_rom].apply(converter_num) if col_qtd_rom else 0.0
        df_rom["QTD_RET"] = df_rom[col_ret_rom].apply(converter_num) if col_ret_rom else 0.0
        df_rom["SALDO_RUA"] = df_rom[col_saldo_rom].apply(converter_num) if col_saldo_rom else 0.0
        df_rom["DOC_ROMANEIO"] = df_rom[col_doc_rom].fillna("-").astype(str) if col_doc_rom else "-"
        df_rom["DATA_ENVIO"] = df_rom[col_dt_envio_rom].apply(formatar_data_br) if col_dt_envio_rom else "-"
        df_rom["NF_RETORNO"] = df_rom[col_nf_ret_rom].fillna("-").astype(str) if col_nf_ret_rom else "-"
        df_rom["DATA_RETORNO"] = df_rom[col_dt_ret_rom].apply(formatar_data_br) if col_dt_ret_rom else "-"
        df_rom["FORNECEDOR_TRAT"] = df_rom[col_forn_rom].apply(padronizar_fornecedor_romaneio) if col_forn_rom else "-"

        if col_desc_rom:
            for _, r in df_rom[["COD_PECA", "DESC_PECA"]].dropna().iterrows():
                c, d = str(r["COD_PECA"]).strip(), str(r["DESC_PECA"]).strip()
                if c and d and d not in ["-", "NAN", "NONE", ""] and c not in catalogo_descricoes:
                    catalogo_descricoes[c] = d

    # 3. Compras
    df_comp = pd.DataFrame()
    if not df_comp_raw.empty:
        col_obs_comp = (
            df_comp_raw.columns[11] if len(df_comp_raw.columns) >= 12 else buscar_col_flex(
                df_comp_raw, ["OBSERVAÇÃO", "OBSERVAÇÕES", "OBSERVACAO", "OBSERVACOES", "OBS", "LOTE", "PROJETO"]
            )
        )
        col_prod_comp = buscar_col_flex(df_comp_raw, ["PRODUTO", "COD PROD", "CODIGO"])
        col_desc_comp = buscar_col_flex(df_comp_raw, ["DESCRIÇÃO", "DESCRICAO", "DESC. PROD"])
        col_forn_comp = buscar_col_flex(df_comp_raw, ["FORNECEDOR"])
        col_qt_comp = buscar_col_flex(df_comp_raw, ["QT", "QUANTIDADE", "QTD"])
        col_ent_comp = buscar_col_flex(df_comp_raw, ["QTD ENTREGUE", "QTD.ENTREGUE", "ENTREGUE"])
        col_dt_comp = buscar_col_flex(df_comp_raw, ["DT ENT.", "DT ENT", "DATA ENTREGA"])
        col_nf_comp = buscar_col_flex(df_comp_raw, ["NF ENT.", "NF ENT", "NOTA FISCAL", "NF"])
        col_dt_forn = buscar_col_flex(df_comp_raw, ["DATA FORNECEDOR", "DT FORNECEDOR"])

        df_comp = df_comp_raw.copy()
        df_comp["OBS_NORM"] = df_comp[col_obs_comp].apply(normalizar_texto) if col_obs_comp else ""
        df_comp["COD_PECA"] = df_comp[col_prod_comp].apply(limpar_cod) if col_prod_comp else ""
        df_comp["Descricao"] = df_comp[col_desc_comp].fillna("-").astype(str) if col_desc_comp else "-"
        df_comp["Fornecedor"] = df_comp[col_forn_comp].fillna("-").astype(str) if col_forn_comp else "-"
        df_comp["Qtd_Comprada"] = df_comp[col_qt_comp].apply(converter_num) if col_qt_comp else 0.0
        df_comp["Qtd_Entregue"] = df_comp[col_ent_comp].apply(converter_num) if col_ent_comp else 0.0
        
        # O saldo de falta sempre é calculado matematicamente de forma robusta
        df_comp["Saldo_Falta_Entregar"] = (df_comp["Qtd_Comprada"] - df_comp["Qtd_Entregue"]).clip(lower=0.0)

        df_comp["Data_Entrega"] = df_comp[col_dt_comp].apply(formatar_data_br) if col_dt_comp else "-"
        df_comp["NF_Entrega"] = df_comp[col_nf_comp].fillna("-").astype(str) if col_nf_comp else "-"
        df_comp["Data_Fornecedor"] = df_comp[col_dt_forn].apply(formatar_data_br) if col_dt_forn else "-"

        def calc_status_compra(r):
            if r["Qtd_Entregue"] >= r["Qtd_Comprada"] and r["Qtd_Comprada"] > 0:
                return "✅ 100% Entregue"
            elif r["Qtd_Entregue"] > 0:
                return "🚚 Entregue Parcial"
            else:
                return "⏳ Aguardando Fornecedor"

        df_comp["Status_Compra"] = df_comp.apply(calc_status_compra, axis=1)

        for _, r in df_comp[["COD_PECA", "Descricao"]].dropna().iterrows():
            c, d = str(r["COD_PECA"]).strip(), str(r["Descricao"]).strip()
            if c and d and d not in ["-", "NAN", "NONE", ""] and c not in catalogo_descricoes:
                catalogo_descricoes[c] = d

    # 4. SC
    df_sc = pd.DataFrame()
    if not df_sc_raw.empty:
        col_filial_sc = buscar_col_flex(df_sc_raw, ["FILIAL"])
        col_num_sc = buscar_col_flex(df_sc_raw, ["Nº SOLICITAÇÃO", "NUM SOLICITACAO", "SOLICITACAO", "SC", "Nº SC"])
        col_item_sc = buscar_col_flex(df_sc_raw, ["ITEM"])
        col_prod_sc = buscar_col_flex(df_sc_raw, ["PRODUTO", "COD PROD", "CODIGO"])
        col_um_sc = buscar_col_flex(df_sc_raw, ["UM", "UN"])
        col_desc_sc = buscar_col_flex(df_sc_raw, ["DESCRIÇÃO", "DESCRICAO"])
        col_qtd_sc = buscar_col_flex(df_sc_raw, ["QTDE DA SC", "QTD SC", "QUANTIDADE", "QTD"])
        col_nec_sc = buscar_col_flex(df_sc_raw, ["NECESSIDADE", "DT NECESSIDADE", "DATA NECESSIDADE"])
        col_obs_sc = (
            df_sc_raw.columns[8] if len(df_sc_raw.columns) >= 9 else buscar_col_flex(
                df_sc_raw, ["OBSERVAÇÃO", "OBSERVAÇÕES", "OBSERVACAO", "OBSERVACOES", "OBS", "LOTE", "PROJETO"]
            )
        )
        col_emis_sc = buscar_col_flex(df_sc_raw, ["EMISSÃO", "EMISSAO", "DT EMISSAO"])
        col_solic_sc = buscar_col_flex(df_sc_raw, ["SOLICITANTE", "NOME SOLICITANTE"])
        col_classe_sc = buscar_col_flex(df_sc_raw, ["CLASSE VALOR", "CLASSE"])
        col_ped_sc = buscar_col_flex(df_sc_raw, ["PEDIDO", "NUM PEDIDO"])

        df_sc = df_sc_raw.copy()
        df_sc["OBS_NORM"] = df_sc[col_obs_sc].apply(normalizar_texto) if col_obs_sc else ""
        df_sc["COD_PECA"] = df_sc[col_prod_sc].apply(limpar_cod) if col_prod_sc else ""
        df_sc["Filial"] = df_sc[col_filial_sc].fillna("-").astype(str) if col_filial_sc else "-"
        df_sc["Num_SC"] = df_sc[col_num_sc].fillna("-").astype(str) if col_num_sc else "-"
        df_sc["Item"] = df_sc[col_item_sc].fillna("-").astype(str) if col_item_sc else "-"
        df_sc["UM"] = df_sc[col_um_sc].fillna("PC").astype(str) if col_um_sc else "PC"
        df_sc["Descricao"] = df_sc[col_desc_sc].fillna("-").astype(str) if col_desc_sc else "-"
        df_sc["Qtd_SC"] = df_sc[col_qtd_sc].apply(converter_num) if col_qtd_sc else 0.0
        df_sc["Necessidade"] = df_sc[col_nec_sc].apply(formatar_data_br) if col_nec_sc else "-"
        df_sc["Emissao"] = df_sc[col_emis_sc].apply(formatar_data_br) if col_emis_sc else "-"
        df_sc["Solicitante"] = df_sc[col_solic_sc].fillna("-").astype(str) if col_solic_sc else "-"
        df_sc["Classe_Valor"] = df_sc[col_classe_sc].fillna("-").astype(str) if col_classe_sc else "-"
        df_sc["Pedido"] = df_sc[col_ped_sc].fillna("-").astype(str) if col_ped_sc else "-"

        for _, r in df_sc[["COD_PECA", "Descricao"]].dropna().iterrows():
            c, d = str(r["COD_PECA"]).strip(), str(r["Descricao"]).strip()
            if c and d and d not in ["-", "NAN", "NONE", ""] and c not in catalogo_descricoes:
                catalogo_descricoes[c] = d

    # 5. Cruzamento Exato
    def format_unique_join(x):
        vals = [str(v) for v in x if str(v) not in ["-", "", "nan", "None"]]
        return ", ".join(sorted(set(vals))) or "-"

    op_obs = (
        df_op.groupby(["OBS_NORM", "COD_PECA"], as_index=False).agg(
            Descricao=("DESC_PECA", "first"),
            Qtd_OP=("QTD_PLAN", "sum"),
            Qtd_Fabr=("QTD_PROD", "sum"),
            Data_Fabricacao=("DT_FABR", format_unique_join),
        )
        if not df_op.empty
        else pd.DataFrame(columns=["OBS_NORM", "COD_PECA", "Descricao", "Qtd_OP", "Qtd_Fabr", "Data_Fabricacao"])
    )

    rom_obs = (
        df_rom.groupby(["OBS_NORM", "COD_PECA"], as_index=False).agg(
            Descricao_Rom=("DESC_PECA", "first"),
            Env_Pintura=("QTD_ENV", "sum"),
            Ret_Pintura=("QTD_RET", "sum"),
            Saldo_Rua=("SALDO_RUA", "sum"),
            Doc_Romaneio=("DOC_ROMANEIO", format_unique_join),
            Data_Envio=("DATA_ENVIO", format_unique_join),
            NF_Retorno=("NF_RETORNO", format_unique_join),
            Data_Retorno=("DATA_RETORNO", format_unique_join),
            Fornecedor_Tratamento=("FORNECEDOR_TRAT", format_unique_join),
        )
        if not df_rom.empty
        else pd.DataFrame(columns=[
            "OBS_NORM", "COD_PECA", "Descricao_Rom", "Env_Pintura", "Ret_Pintura",
            "Saldo_Rua", "Doc_Romaneio", "Data_Envio", "NF_Retorno", "Data_Retorno", "Fornecedor_Tratamento"
        ])
    )

    df_cruz_obs = pd.merge(op_obs, rom_obs, on=["OBS_NORM", "COD_PECA"], how="outer")

    if not df_cruz_obs.empty:
        if "Descricao" not in df_cruz_obs.columns:
            df_cruz_obs["Descricao"] = "-"
        if "Descricao_Rom" in df_cruz_obs.columns:
            cond_desc_vazia = df_cruz_obs["Descricao"].isna() | df_cruz_obs["Descricao"].isin(["-", "", "None", "nan"])
            df_cruz_obs["Descricao"] = df_cruz_obs["Descricao"].where(~cond_desc_vazia, df_cruz_obs["Descricao_Rom"])
            df_cruz_obs.drop(columns=["Descricao_Rom"], inplace=True)

        def resolver_desc_catalogo(r):
            d = str(r["Descricao"]).strip()
            if d and d not in ["-", "NAN", "NONE", ""]:
                return d
            return catalogo_descricoes.get(str(r["COD_PECA"]).strip(), "-")

        df_cruz_obs["Descricao"] = df_cruz_obs.apply(resolver_desc_catalogo, axis=1)

        for col_num in ["Qtd_OP", "Qtd_Fabr", "Env_Pintura", "Ret_Pintura", "Saldo_Rua"]:
            if col_num not in df_cruz_obs.columns:
                df_cruz_obs[col_num] = 0.0
            df_cruz_obs[col_num] = df_cruz_obs[col_num].fillna(0.0).astype(float)

        for col_str in ["Data_Fabricacao", "Doc_Romaneio", "Data_Envio", "NF_Retorno", "Data_Retorno", "Fornecedor_Tratamento"]:
            df_cruz_obs[col_str] = df_cruz_obs[col_str].fillna("-").astype(str)

        df_cruz_obs.loc[df_cruz_obs["Env_Pintura"] == 0, "Fornecedor_Tratamento"] = "-"
        df_cruz_obs["Saldo_Pendente_Pintura"] = (df_cruz_obs["Env_Pintura"] - df_cruz_obs["Ret_Pintura"]).clip(lower=0.0)
        df_cruz_obs["Aguardando_Envio"] = (df_cruz_obs["Qtd_Fabr"] - df_cruz_obs["Env_Pintura"]).clip(lower=0.0)
        df_cruz_obs["Falta_Fabricar"] = (df_cruz_obs["Qtd_OP"] - df_cruz_obs["Qtd_Fabr"]).clip(lower=0.0)

        def calc_status(r):
            if r["Ret_Pintura"] >= r["Qtd_OP"] and r["Qtd_OP"] > 0 and r["Saldo_Pendente_Pintura"] == 0 and r["Falta_Fabricar"] == 0:
                return "✅ 100% Entregue"
            elif r["Falta_Fabricar"] > 0:
                return "⚙️ Falta Fabricar Internamente"
            elif r["Aguardando_Envio"] > 0 and r["Env_Pintura"] == 0:
                return "🚚 Fabricado (Não Enviado)"
            elif r["Saldo_Pendente_Pintura"] > 0:
                return "⏳ Em Tratamento Externo"
            elif r["Ret_Pintura"] > 0:
                return "🚚 Entregue Parcial"
            else:
                return "⏳ Aguardando Produção"

        df_cruz_obs["Status"] = df_cruz_obs.apply(calc_status, axis=1)

    return (
        df_cruz_obs, df_comp, df_sc, df_op, df_rom,
        df_op_raw, df_rom_raw, df_comp_raw, df_sc_raw,
    )

# --- MENU LATERAL (SIDEBAR) ---
with st.sidebar:
    try:
        st.image("image_aa4e28.png", use_container_width=True)
    except Exception:
        st.markdown("### 🏭")
    
    st.markdown("## FCM Metálicos")
    
    meta_atual = carregar_meta()
    data_atualizacao = meta_atual.get("ultima_atualizacao", "Nenhum arquivo salvo ainda")
    st.caption(f"🕒 **Última carga:** {data_atualizacao}")
    
    st.divider()
    
    st.markdown("### 📥 Atualizar Dados")
    arquivos_enviados = st.file_uploader(
        "Carregar planilhas (OP, Romaneio, Compras e SC):",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=True,
    )
    
    st.divider()
    
    st.markdown("### ⏳ Histórico de Versões")
    historicos = listar_historicos_disponiveis()
    opcoes_historico = ["📁 Versão Atual"] + [f"🕒 Backup: {h[1]}" for h in historicos]
    escolha_versao = st.selectbox("Selecione um backup:", opcoes_historico, index=0)

    c_btn_rest, c_btn_clean = st.columns(2)
    with c_btn_rest:
        if escolha_versao != "📁 Versão Atual":
            if st.button("🔄 Restaurar"):
                idx = opcoes_historico.index(escolha_versao) - 1
                pasta_sel = historicos[idx][0]
                restaurar_backup(pasta_sel)
                st.cache_data.clear()
                st.success("Versão restaurada!")
                st.rerun()
    with c_btn_clean:
        if st.button("🧹 Resetar"):
            for fname in ["base_op.parquet", "base_romaneio.parquet", "base_compras.parquet", "base_sc.parquet"]:
                p = os.path.join(STORAGE_DIR, fname)
                if os.path.exists(p):
                    os.remove(p)
            meta_atual["ultima_atualizacao"] = "Nenhum arquivo salvo ainda"
            salvar_meta(meta_atual)
            st.cache_data.clear()
            st.success("Arquivos resetados!")
            st.rerun()

# --- LÓGICA DE UPLOAD ---
if "ultimo_upload_ids" not in st.session_state:
    st.session_state.ultimo_upload_ids = ""

if arquivos_enviados:
    ids_atuais = "_".join([f"{f.name}_{f.size}" for f in arquivos_enviados])
    if ids_atuais != st.session_state.ultimo_upload_ids:
        agora_str = datetime.now(FUSO_BRASILIA).strftime("%d/%m/%Y às %H:%M")
        criar_backup_historico(data_atualizacao)

        for f in arquivos_enviados:
            try:
                file_bytes = f.getvalue()
                f_upper = f.name.upper()

                if not f.name.endswith(".csv"):
                    xl = pd.ExcelFile(io.BytesIO(file_bytes))
                    for s_name in xl.sheet_names:
                        df_sheet_head = pd.read_excel(io.BytesIO(file_bytes), sheet_name=s_name, nrows=5)
                        cols = [normalizar_texto(c) for c in df_sheet_head.columns]
                        s_upper = s_name.upper()
                        caminho_salvar = None

                        if "SOLICITA" in s_upper or any("SOLICITA" in c for c in cols):
                            caminho_salvar = caminho_sc_pqt
                        elif "PEDIDO" in s_upper or (any("QTD ENTREGUE" in c for c in cols) and any("TAT" in c for c in cols)):
                            caminho_salvar = caminho_comp_pqt
                        elif "OP" in f_upper or any("PRODUZID" in c for c in cols) or any("CLASSE VALOR" in c for c in cols):
                            caminho_salvar = caminho_op_pqt
                        elif "ROMANEIO" in f_upper or any("CLIENTE/FORN" in c for c in cols) or any("DOC.ORIG" in c for c in cols):
                            if any("OBSERVA" in c for c in cols) or len(cols) >= 15:
                                caminho_salvar = caminho_rom_pqt

                        if caminho_salvar:
                            df_completo = ler_excel_completo(io.BytesIO(file_bytes), sheet_name=s_name)
                            df_completo = df_completo.astype(str)
                            df_completo.to_parquet(caminho_salvar, index=False)
                else:
                    df_csv = pd.read_csv(io.BytesIO(file_bytes), nrows=5)
                    cols = [normalizar_texto(c) for c in df_csv.columns]
                    caminho_salvar = None
                    if any("SOLICITA" in c for c in cols):
                        caminho_salvar = caminho_sc_pqt
                    elif any("QTD ENTREGUE" in c for c in cols):
                        caminho_salvar = caminho_comp_pqt
                    elif any("CLIENTE/FORN" in c for c in cols) or any("DOC.ORIG" in c for c in cols):
                        caminho_salvar = caminho_rom_pqt
                    elif any("PRODUZID" in c for c in cols):
                        caminho_salvar = caminho_op_pqt

                    if caminho_salvar:
                        df_completo = pd.read_csv(io.BytesIO(file_bytes)).astype(str)
                        df_completo.to_parquet(caminho_salvar, index=False)
            except Exception as e:
                st.error(f"Erro ao processar {f.name}: {e}")

        meta_atual["ultima_atualizacao"] = agora_str
        salvar_meta(meta_atual)
        st.session_state.ultimo_upload_ids = ids_atuais
        st.cache_data.clear()
        st.rerun()

# --- CARREGAMENTO DE DADOS ---
pasta_carregar = STORAGE_DIR
if escolha_versao != "📁 Versão Atual":
    idx = opcoes_historico.index(escolha_versao) - 1
    pasta_carregar = os.path.join(BACKUPS_DIR, historicos[idx][0])

mtimes = obter_mtimes(pasta_carregar)
(
    df_cruz_obs, df_comp, df_sc, df_op, df_rom,
    df_op_raw, df_rom_raw, df_comp_raw, df_sc_raw,
) = processar_todas_as_bases(mtimes, pasta_carregar)

if df_op_raw.empty and df_rom_raw.empty and df_comp_raw.empty and df_sc_raw.empty:
    st.info("👆 Nenhuma planilha salva ainda. Selecione os arquivos no menu lateral para carregar o painel.")
    st.stop()

# --- FILTRO 100% ESTRITO DE PROJETO / OBSERVAÇÃO ---
st.markdown('<div class="sticky-top-panel">', unsafe_allow_html=True)

todas_obs_set = set()
if not df_cruz_obs.empty and "OBS_NORM" in df_cruz_obs.columns:
    todas_obs_set.update(df_cruz_obs["OBS_NORM"].dropna().unique())
if not df_comp.empty and "OBS_NORM" in df_comp.columns:
    todas_obs_set.update(df_comp["OBS_NORM"].dropna().unique())
if not df_sc.empty and "OBS_NORM" in df_sc.columns:
    todas_obs_set.update(df_sc["OBS_NORM"].dropna().unique())

lista_todas_obs = sorted([str(p) for p in todas_obs_set if str(p).strip() and str(p) not in ["-", "NAN", "NONE"]])

col_multisel_obs, col_busca_peca = st.columns([2.8, 1.2])

with col_multisel_obs:
    sel_obs_global = st.multiselect(
        "📝 Digite e Flegue o(s) Lote(s) / Observação:",
        options=lista_todas_obs,
        placeholder="Digite parte do nome ou código (Ex: 11761.01G, COROLLA, RANGER)...",
    )

with col_busca_peca:
    busca_cod = st.text_input("🔍 Buscar Peça:", placeholder="Código ou descrição...").strip().upper()

df_trabalho = df_cruz_obs.copy() if not df_cruz_obs.empty else pd.DataFrame()
df_comp_trabalho = df_comp.copy() if not df_comp.empty else pd.DataFrame()
df_sc_trabalho = df_sc.copy() if not df_sc.empty else pd.DataFrame()

if sel_obs_global:
    if not df_trabalho.empty and "OBS_NORM" in df_trabalho.columns:
        df_trabalho = df_trabalho[df_trabalho["OBS_NORM"].isin(sel_obs_global)]
    if not df_comp_trabalho.empty and "OBS_NORM" in df_comp_trabalho.columns:
        df_comp_trabalho = df_comp_trabalho[df_comp_trabalho["OBS_NORM"].isin(sel_obs_global)]
    if not df_sc_trabalho.empty and "OBS_NORM" in df_sc_trabalho.columns:
        df_sc_trabalho = df_sc_trabalho[df_sc_trabalho["OBS_NORM"].isin(sel_obs_global)]
    projeto_ativo_nome = ", ".join(sel_obs_global[:2]) + ("..." if len(sel_obs_global) > 2 else "")
else:
    projeto_ativo_nome = "Todas as Observações"

if busca_cod:
    if not df_trabalho.empty:
        df_trabalho = df_trabalho[df_trabalho["COD_PECA"].str.contains(busca_cod, na=False) | df_trabalho["Descricao"].str.contains(busca_cod, na=False)]
    if not df_comp_trabalho.empty:
        df_comp_trabalho = df_comp_trabalho[df_comp_trabalho["COD_PECA"].str.contains(busca_cod, na=False) | df_comp_trabalho["Descricao"].str.contains(busca_cod, na=False)]
    if not df_sc_trabalho.empty:
        df_sc_trabalho = df_sc_trabalho[df_sc_trabalho["COD_PECA"].str.contains(busca_cod, na=False) | df_sc_trabalho["Descricao"].str.contains(busca_cod, na=False)]

tot_op = int(df_trabalho["Qtd_OP"].sum()) if not df_trabalho.empty else 0
tot_fab = int(df_trabalho["Qtd_Fabr"].sum()) if not df_trabalho.empty else 0
tot_env = int(df_trabalho["Env_Pintura"].sum()) if not df_trabalho.empty else 0
tot_ret = int(df_trabalho["Ret_Pintura"].sum()) if not df_trabalho.empty else 0
falta_fab = int(df_trabalho["Falta_Fabricar"].sum()) if not df_trabalho.empty else 0
falta_env = int(df_trabalho["Aguardando_Envio"].sum()) if not df_trabalho.empty else 0
saldo_rua = int(df_trabalho["Saldo_Pendente_Pintura"].sum()) if not df_trabalho.empty else 0

tot_comprado = int(df_comp_trabalho["Qtd_Comprada"].sum()) if not df_comp_trabalho.empty else 0
tot_entregue = int(df_comp_trabalho["Qtd_Entregue"].sum()) if not df_comp_trabalho.empty else 0
saldo_compra = int(df_comp_trabalho["Saldo_Falta_Entregar"].sum()) if not df_comp_trabalho.empty else 0

tot_sc_aberto = int(df_sc_trabalho["Qtd_SC"].sum()) if not df_sc_trabalho.empty else 0
qtd_itens_sc = len(df_sc_trabalho) if not df_sc_trabalho.empty else 0

pct_fab = (tot_fab / tot_op * 100) if tot_op > 0 else 0
pct_ret = (tot_ret / tot_op * 100) if tot_op > 0 else 0

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("1. Programado (OP)", f"{tot_op:,} pçs", f"Falta Fabr: {falta_fab:,} pçs", delta_color="inverse" if falta_fab > 0 else "normal")
c2.metric("2. Fabricado Interno", f"{tot_fab:,} pçs", f"{pct_fab:.1f}% Produzido")
c3.metric("3. Enviado Tratamento", f"{tot_env:,} pçs", f"Aguardando: {falta_env:,} pçs", delta_color="inverse" if falta_env > 0 else "normal")
c4.metric("4. Retornado (Pronto)", f"{tot_ret:,} pçs", f"Falta Voltar: {saldo_rua:,} pçs", delta_color="inverse" if saldo_rua > 0 else "normal")
c5.metric("5. Compras Externas", f"{tot_entregue:,} / {tot_comprado:,} pçs", f"Falta: {saldo_compra:,} pçs", delta_color="inverse" if saldo_compra > 0 else "normal")
c6.metric("6. SC em Aberto", f"{tot_sc_aberto:,} pçs", f"{qtd_itens_sc} solicitações", delta_color="inverse" if tot_sc_aberto > 0 else "normal")

st.markdown("</div>", unsafe_allow_html=True)

# --- FUNÇÃO GERADORA DA BASE UNIFICADA (Para as abas de Metálicos) ---
def gerar_df_unificado(df_trab, df_comp_trab, df_sc_trab):
    lista_dfs = []
    
    if not df_trab.empty:
        df_fab_tot = df_trab.copy()
        df_fab_tot["Origem_Tipo"] = "🏭 Fabricação Interna"
        df_fab_tot["Qtd_Total_Demanda"] = df_fab_tot["Qtd_OP"]
        df_fab_tot["Qtd_Entregue_Pronta"] = df_fab_tot["Ret_Pintura"]
        df_fab_tot["Saldo_Pendente_Entrega"] = df_fab_tot["Saldo_Pendente_Pintura"]
        df_fab_tot["Falta_Produzir_Interno"] = df_fab_tot["Falta_Fabricar"]
        df_fab_tot["Fornecedor_Responsavel"] = df_fab_tot["Fornecedor_Tratamento"]
        df_fab_tot["Doc_Origem_Envio"] = df_fab_tot["Doc_Romaneio"]
        df_fab_tot["NF_Retorno_Entrega"] = df_fab_tot["NF_Retorno"]
        df_fab_tot["Data_Movimento"] = df_fab_tot["Data_Retorno"].where(
            df_fab_tot["Data_Retorno"] != "-", df_fab_tot["Data_Envio"]
        )
        df_fab_tot["Status_Unificado"] = df_fab_tot["Status"]
        lista_dfs.append(df_fab_tot)

    if not df_comp_trab.empty:
        df_comp_tot = df_comp_trab.copy()
        df_comp_tot["Origem_Tipo"] = "📦 Compra / Externado"
        df_comp_tot["Qtd_Total_Demanda"] = df_comp_tot["Qtd_Comprada"]
        df_comp_tot["Qtd_Entregue_Pronta"] = df_comp_tot["Qtd_Entregue"]
        df_comp_tot["Saldo_Pendente_Entrega"] = df_comp_tot["Saldo_Falta_Entregar"]
        df_comp_tot["Falta_Produzir_Interno"] = 0.0
        df_comp_tot["Fornecedor_Responsavel"] = df_comp_tot["Fornecedor"]
        df_comp_tot["Doc_Origem_Envio"] = "-"
        df_comp_tot["NF_Retorno_Entrega"] = df_comp_tot["NF_Entrega"]
        df_comp_tot["Data_Movimento"] = df_comp_tot["Data_Entrega"].where(
            df_comp_tot["Data_Entrega"] != "-", df_comp_tot["Data_Fornecedor"]
        )
        df_comp_tot["Status_Unificado"] = df_comp_tot["Status_Compra"]
        lista_dfs.append(df_comp_tot)

    if not df_sc_trab.empty:
        df_sc_tot = df_sc_trab.copy()
        df_sc_tot["Origem_Tipo"] = "📋 SC (Pendente de Pedido)"
        df_sc_tot["Qtd_Total_Demanda"] = df_sc_tot["Qtd_SC"]
        df_sc_tot["Qtd_Entregue_Pronta"] = 0.0
        df_sc_tot["Saldo_Pendente_Entrega"] = df_sc_tot["Qtd_SC"]
        df_sc_tot["Falta_Produzir_Interno"] = 0.0
        df_sc_tot["Fornecedor_Responsavel"] = df_sc_tot["Solicitante"]
        df_sc_tot["Doc_Origem_Envio"] = df_sc_tot["Num_SC"]
        df_sc_tot["NF_Retorno_Entrega"] = "-"
        df_sc_tot["Data_Movimento"] = df_sc_tot["Necessidade"]
        df_sc_tot["Status_Unificado"] = "⏳ SC em Aberto"
        lista_dfs.append(df_sc_tot)

    if lista_dfs:
        return pd.concat(lista_dfs, ignore_index=True)
    return pd.DataFrame()

df_unificado_global = gerar_df_unificado(df_trabalho, df_comp_trabalho, df_sc_trabalho)

colunas_view_unificada = [
    "Status_Unificado", "Data_Movimento", "Origem_Tipo", "OBS_NORM", "COD_PECA", 
    "Descricao", "Fornecedor_Responsavel", "Qtd_Total_Demanda", "Qtd_Entregue_Pronta", 
    "Saldo_Pendente_Entrega", "Falta_Produzir_Interno", "Doc_Origem_Envio", "NF_Retorno_Entrega"
]
nomes_colunas_unificadas = {
    "Status_Unificado": "Status do Item", "Data_Movimento": "Data Entrega / Previsão", 
    "Origem_Tipo": "Origem do Item", "OBS_NORM": "Observação (Lote)", "COD_PECA": "Código da Peça", 
    "Descricao": "Descrição", "Fornecedor_Responsavel": "Fornecedor / Responsável", 
    "Qtd_Total_Demanda": "Programado / Comprado", "Qtd_Entregue_Pronta": "Já Entregue / Pronto", 
    "Saldo_Pendente_Entrega": "Falta Entregar (Saldo)", "Falta_Produzir_Interno": "Falta Fabricar (Fábrica)", 
    "Doc_Origem_Envio": "Romaneio Envio", "NF_Retorno_Entrega": "NF Entrega / Retorno"
}

# --- ABAS DETALHADAS ---
(
    tab_mobile,
    tab_metalicos_falta,
    tab_metalicos_total,
    tab_fabricadas,
    tab_retornadas,
    tab_pend_trat,
    tab_aguard_envio,
    tab_falta_fab,
    tab_compras,
    tab_sc,
    tab_dados_brutos,
) = st.tabs([
    "📱 Resumo Executivo (Celular)",
    "🚨 Metálicos Total Falta",
    "📊 Metálicos Total (Geral)",
    "🏭 Peças Fabricadas",
    "✅ Peças Retornadas",
    "🚨 Falta Retorno",
    "🚚 Aguardando Envio",
    "⚙️ Falta Fabricar",
    "📦 Compras Externas",
    "📋 SC em Aberto",
    "📂 Bases de Dados",
])

# ==============================================================================
# 1. ABA RESUMO EXECUTIVO (CELULAR / MOBILE FIRST)
# ==============================================================================
with tab_mobile:
    pct_pronto = (
        (tot_ret / tot_op * 100)
        if tot_op > 0
        else (100.0 if tot_op == 0 and tot_ret > 0 else 0.0)
    )

    st.markdown(f"### 📱 Diagnóstico Rápido: `{projeto_ativo_nome}`")

    if (
        saldo_rua == 0
        and falta_fab == 0
        and falta_env == 0
        and saldo_compra == 0
        and tot_sc_aberto == 0
        and (tot_ret > 0 or tot_entregue > 0)
    ):
        status_geral_badge = '<span class="badge-status badge-ok">✅ PROJETO 100% PRONTO & LIBERADO PARA MONTAGEM</span>'
    elif saldo_rua > 0:
        status_geral_badge = f'<span class="badge-status badge-warn">⏳ AGUARDANDO RETORNO DE PINTURA ({saldo_rua} pçs na rua)</span>'
    elif falta_fab > 0:
        status_geral_badge = f'<span class="badge-status badge-alert">⚙️ GARGALO NA FÁBRICA ({falta_fab} pçs a produzir)</span>'
    else:
        status_geral_badge = '<span class="badge-status badge-ok">🚀 FLUXO NORMAL EM ANDAMENTO</span>'

    st.markdown(status_geral_badge, unsafe_allow_html=True)
    st.progress(min(max(pct_pronto / 100.0, 0.0), 1.0))
    st.caption(f"**Prontidão Metálica Total:** `{pct_pronto:.1f}%` ({tot_ret:,} de {tot_op:,} peças prontas)")

    m1, m2 = st.columns(2)
    with m1:
        st.markdown(
            f"""
            <div class="card-mobile-clean">
                <span style="font-size:0.75rem; color:#8b949e; font-weight:600;">🏗️ ESTRUTURA METÁLICA (FÁBRICA)</span><br>
                <b style="font-size:1.15rem; color:#58a6ff;">{tot_fab:,} / {tot_op:,} pçs</b><br>
                <span style="font-size:0.75rem; color:{'#ff7b72' if falta_fab > 0 else '#3fb950'}; font-weight:600;">
                    {'⚠️ Falta fabricar: ' + str(falta_fab) + ' pçs' if falta_fab > 0 else '✅ 100% Produzido na fábrica'}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div class="card-mobile-clean">
                <span style="font-size:0.75rem; color:#8b949e; font-weight:600;">🚚 EXPEDIÇÃO / DESPACHO</span><br>
                <b style="font-size:1.15rem; color:#d29922;">{falta_env:,} pçs</b><br>
                <span style="font-size:0.75rem; color:{'#d29922' if falta_env > 0 else '#3fb950'}; font-weight:600;">
                    {'⏳ Fabricado aguardando envio' if falta_env > 0 else '✅ Todas as peças fabricadas foram enviadas'}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f"""
            <div class="card-mobile-clean">
                <span style="font-size:0.75rem; color:#8b949e; font-weight:600;">🎨 TRATAMENTO / PINTURA</span><br>
                <b style="font-size:1.15rem; color:#58a6ff;">{tot_ret:,} / {tot_env:,} pçs</b><br>
                <span style="font-size:0.75rem; color:{'#ff7b72' if saldo_rua > 0 else '#3fb950'}; font-weight:600;">
                    {'🚨 Na rua (pendente): ' + str(saldo_rua) + ' pçs' if saldo_rua > 0 else '✅ 100% Retornado da pintura'}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div class="card-mobile-clean">
                <span style="font-size:0.75rem; color:#8b949e; font-weight:600;">📦 COMPRAS & SC EXTERNAS</span><br>
                <b style="font-size:1.15rem; color:#58a6ff;">{tot_entregue:,} / {tot_comprado:,} pçs</b><br>
                <span style="font-size:0.75rem; color:{'#ff7b72' if saldo_compra > 0 or tot_sc_aberto > 0 else '#3fb950'}; font-weight:600;">
                    {'🚨 Falta entregar: ' + str(saldo_compra) + ' pçs (' + str(qtd_itens_sc) + ' SCs)' if (saldo_compra > 0 or tot_sc_aberto > 0) else '✅ Compras 100% entregues'}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("#### 🚗 Peças por Tipo / Conjunto do Veículo:")
    if not df_trabalho.empty:
        def classificar_tipo(desc):
            d = str(desc).upper()
            if "DIVISORIA" in d: return "🚪 Divisórias de Cela"
            elif "ESTRIBO" in d: return "🪜 Estribos Laterais"
            elif "CONSOLE" in d or "ACABAMENTO" in d or "CHAPA" in d: return "📐 Chapas & Acabamentos"
            elif "SUP" in d or "SUPORTE" in d: return "🔧 Suportes & Fixações"
            elif "GRADE" in d or "VIDRO" in d: return "🛡️ Grades & Vidros"
            elif "BANCO" in d or "CADEIRA" in d: return "💺 Bancos & Assentos"
            else: return "🔩 Estruturas Diversas"

        df_trabalho_tipo = df_trabalho.copy()
        df_trabalho_tipo["TIPO_CONJUNTO"] = df_trabalho_tipo["Descricao"].apply(classificar_tipo)

        tipos_agg = df_trabalho_tipo.groupby("TIPO_CONJUNTO", as_index=False).agg(
            Total_Necessario=("Qtd_OP", "sum"),
            Ja_Retornado=("Ret_Pintura", "sum"),
            Pendente_Rua=("Saldo_Pendente_Pintura", "sum"),
            Qtd_Itens=("COD_PECA", "count"),
        )

        col_t1, col_t2 = st.columns(2)
        for i, r_tipo in tipos_agg.iterrows():
            alvo_col = col_t1 if i % 2 == 0 else col_t2
            with alvo_col:
                pct_tipo = ((r_tipo["Ja_Retornado"] / r_tipo["Total_Necessario"] * 100) if r_tipo["Total_Necessario"] > 0 else 100.0)
                st.markdown(
                    f"""
                        <div class="card-mobile-clean">
                            <b>{r_tipo['TIPO_CONJUNTO']}</b> ({r_tipo['Qtd_Itens']} modelos)<br>
                            <span style="font-size:0.85rem; color:#58a6ff;"><b>{int(r_tipo['Ja_Retornado']):,} / {int(r_tipo['Total_Necessario']):,} pçs</b> ({pct_tipo:.0f}% prontas)</span><br>
                            <span style="font-size:0.75rem; color:{'#ff7b72' if r_tipo['Pendente_Rua'] > 0 else '#3fb950'};">
                                {'🚨 ' + str(int(r_tipo['Pendente_Rua'])) + ' peças na pintura' if r_tipo['Pendente_Rua'] > 0 else '✅ 100% pronto no estoque'}
                            </span>
                        </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.info("Nenhuma peça metálica encontrada para o filtro selecionado.")

    st.markdown("---")
    st.markdown("#### 📍 Onde estão as peças na rua agora?")
    if not df_trabalho.empty:
        df_na_rua = df_trabalho[df_trabalho["Saldo_Pendente_Pintura"] > 0]
        if not df_na_rua.empty:
            for forn, group in df_na_rua.groupby("Fornecedor_Tratamento"):
                saldo_forn = int(group["Saldo_Pendente_Pintura"].sum())
                with st.expander(f"🔴 **{forn}**: {saldo_forn:,} peças pendentes ({len(group)} itens)"):
                    for _, r in group.iterrows():
                        st.markdown(f"• **`{r['COD_PECA']}`** ({r['Descricao'][:40]}): **{int(r['Saldo_Pendente_Pintura'])} pçs** | Romaneio: `{r['Doc_Romaneio']}` (Envio: {r['Data_Envio']})")
        else:
            st.success("🎉 Nenhuma peça na rua! 100% das peças enviadas para tratamento já retornaram.")

    st.markdown("---")
    st.markdown("#### 📦 Compras e Itens Externos do Projeto:")
    if not df_comp_trabalho.empty or not df_sc_trabalho.empty:
        if saldo_compra == 0 and tot_sc_aberto == 0:
            st.success("🎉 Tudo certo com Compras! Todos os itens comprados foram 100% entregues e não há SCs em aberto.")
        else:
            if not df_comp_trabalho.empty:
                df_comp_pend = df_comp_trabalho[df_comp_trabalho["Saldo_Falta_Entregar"] > 0]
                if not df_comp_pend.empty:
                    with st.expander(f"🚚 **Ordens de Compra Pendentes de Entrega ({len(df_comp_pend)} itens | {saldo_compra:,} pçs)**", expanded=True):
                        for _, rc in df_comp_pend.iterrows():
                            st.markdown(f"• **`{rc['COD_PECA']}`** ({rc['Descricao'][:35]}): Falta **{int(rc['Saldo_Falta_Entregar'])} pçs** | Fornecedor: `{rc['Fornecedor']}` | Previsão: `{rc['Data_Fornecedor']}`")
            if not df_sc_trabalho.empty:
                with st.expander(f"📋 **Solicitações de Compra em Aberto ({qtd_itens_sc} itens | {tot_sc_aberto:,} pçs)**", expanded=True):
                    for _, rsc in df_sc_trabalho.iterrows():
                        st.markdown(f"• **`{rsc['COD_PECA']}`** ({rsc['Descricao'][:35]}): **{int(rsc['Qtd_SC'])} pçs** | SC Nº: `{rsc['Num_SC']}` | Solicitante: `{rsc['Solicitante']}`")
    else:
        st.info("Nenhuma ordem de compra cadastrada para este lote.")

# ==============================================================================
# 2. ABA METÁLICOS TOTAL FALTA
# ==============================================================================
with tab_metalicos_falta:
    if not df_unificado_global.empty:
        # Filtro fixo: Se não é "100% Entregue", é falta (conforme regra de negócio universal)
        df_faltas = df_unificado_global[
            df_unificado_global["Status_Unificado"] != "✅ 100% Entregue"
        ].copy()
        
        if not df_faltas.empty:
            df_view_faltas = df_faltas[colunas_view_unificada].rename(columns=nomes_colunas_unificadas)
            
            c_tit_tot, c_btns_tot = st.columns([3, 2])
            with c_tit_tot:
                st.subheader(f"🚨 Faltas Críticas ({len(df_faltas)} itens pendentes)")
            with c_btns_tot:
                cb1, cb2 = st.columns(2)
                with cb1:
                    renderizar_botao_copiar_tabela(df_view_faltas, "btn_cp_faltas")
                with cb2:
                    st.download_button(
                        "📥 Exportar (.xlsx)", data=gerar_excel_tabela(df_view_faltas, "Faltas_Metalicos"),
                        file_name="Metalicos_Total_Faltas.xlsx", 
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            
            st.dataframe(df_view_faltas, use_container_width=True, hide_index=True, height=650)
        else:
            st.success("🎉 Nenhuma falta pendente encontrada! Todos os itens estão prontos/entregues.")
    else:
        st.info("Nenhum registro encontrado.")

# ==============================================================================
# 3. ABA METÁLICOS TOTAL (GERAL)
# ==============================================================================
with tab_metalicos_total:
    if not df_unificado_global.empty:
        c_origem_tot, _ = st.columns([1, 2])
        with c_origem_tot:
            sel_origem = st.multiselect(
                "Filtrar por Origem do Item:",
                ["🏭 Fabricação Interna", "📦 Compra / Externado", "📋 SC (Pendente de Pedido)"],
                default=["🏭 Fabricação Interna", "📦 Compra / Externado", "📋 SC (Pendente de Pedido)"],
            )

        df_total_view = df_unificado_global[df_unificado_global["Origem_Tipo"].isin(sel_origem)] if sel_origem else df_unificado_global
        df_view = df_total_view[colunas_view_unificada].rename(columns=nomes_colunas_unificadas)
        tot_demanda_geral = int(df_total_view["Qtd_Total_Demanda"].sum())
        tot_pronto_geral = int(df_total_view["Qtd_Entregue_Pronta"].sum())

        c_tit_tot, c_btns_tot = st.columns([3, 2])
        with c_tit_tot:
            st.subheader(f"📊 Visão Geral ({len(df_total_view)} itens | {tot_pronto_geral:,} de {tot_demanda_geral:,} prontos)")
        with c_btns_tot:
            cb1, cb2 = st.columns(2)
            with cb1:
                renderizar_botao_copiar_tabela(df_view, "btn_cp_total")
            with cb2:
                st.download_button(
                    "📥 Exportar (.xlsx)", data=gerar_excel_tabela(df_view, "Metalicos_Geral"),
                    file_name="Metalicos_Visao_Geral.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        st.dataframe(df_view, use_container_width=True, hide_index=True, height=650)
    else:
        st.info("Nenhum registro encontrado para os filtros selecionados.")

# ==============================================================================
# 4. ABA PEÇAS FABRICADAS
# ==============================================================================
with tab_fabricadas:
    if not df_trabalho.empty:
        df_fab_feitas = df_trabalho[df_trabalho["Qtd_Fabr"] > 0].copy()
        if not df_fab_feitas.empty:
            cols_fab_feitas = ["Status", "Data_Fabricacao", "OBS_NORM", "COD_PECA", "Descricao", "Qtd_OP", "Qtd_Fabr", "Env_Pintura", "Aguardando_Envio"]
            df_view_fab = df_fab_feitas[cols_fab_feitas].rename(columns={
                "Status": "Status Atual", "Data_Fabricacao": "Data Conclusão Fabricação", "OBS_NORM": "Observação (Lote)",
                "COD_PECA": "Código Peça", "Descricao": "Descrição", "Qtd_OP": "Programado OP", "Qtd_Fabr": "Total Já Fabricado",
                "Env_Pintura": "Já Saiu p/ Pintura", "Aguardando_Envio": "Saldo no Estoque Fábrica"
            })

            c_tit, c_btns = st.columns([3, 2])
            with c_tit:
                st.subheader(f"🏭 Peças Já Fabricadas ({len(df_fab_feitas)} itens | {tot_fab:,} peças)")
            with c_btns:
                cb1, cb2 = st.columns(2)
                with cb1:
                    renderizar_botao_copiar_tabela(df_view_fab, "btn_cp_fabricadas")
                with cb2:
                    st.download_button(
                        "📥 Exportar (.xlsx)", data=gerar_excel_tabela(df_fab_feitas, "Pecas_Fabricadas"),
                        file_name="Pecas_Fabricadas.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            st.dataframe(df_view_fab, use_container_width=True, hide_index=True, height=650)
        else:
            st.info("Nenhuma peça com fabricação registrada para o filtro.")
    else:
        st.info("Nenhum dado encontrado para o filtro selecionado.")

# ==============================================================================
# 5. ABA PEÇAS RETORNADAS
# ==============================================================================
with tab_retornadas:
    if not df_trabalho.empty:
        df_p2 = df_trabalho[df_trabalho["Ret_Pintura"] > 0].copy()
        forns_ret = sorted([f for f in df_p2["Fornecedor_Tratamento"].unique() if f != "-"])
        if forns_ret:
            sel_forn_ret = st.multiselect("Filtrar por Fornecedor (Quem entregou):", forns_ret, default=[])
            if sel_forn_ret:
                df_p2 = df_p2[df_p2["Fornecedor_Tratamento"].isin(sel_forn_ret)]

        if not df_p2.empty:
            cols_ret_ordem = ["Status", "Data_Retorno", "OBS_NORM", "COD_PECA", "Descricao", "Fornecedor_Tratamento", "Qtd_Fabr", "Env_Pintura", "Ret_Pintura", "NF_Retorno", "Doc_Romaneio", "Data_Envio"]
            df_view_ret = df_p2[cols_ret_ordem].rename(columns={
                "Status": "Status", "Data_Retorno": "Data do Retorno", "OBS_NORM": "Observação (Lote)", "COD_PECA": "Código Peça",
                "Descricao": "Descrição", "Fornecedor_Tratamento": "Fornecedor (Entregou)", "Qtd_Fabr": "Fabricado", "Env_Pintura": "Enviado",
                "Ret_Pintura": "Retornado Pronto", "NF_Retorno": "NF de Retorno", "Doc_Romaneio": "Romaneio de Envio", "Data_Envio": "Data do Envio"
            })

            c_tit, c_btns = st.columns([3, 2])
            with c_tit:
                st.subheader(f"✅ Peças que já Retornaram ({len(df_p2)} itens | {tot_ret:,} peças)")
            with c_btns:
                cb1, cb2 = st.columns(2)
                with cb1:
                    renderizar_botao_copiar_tabela(df_view_ret, "btn_cp_retornadas")
                with cb2:
                    st.download_button(
                        "📥 Exportar (.xlsx)", data=gerar_excel_tabela(df_p2, "Pecas_Retornadas"),
                        file_name="Pecas_Retornadas.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            st.dataframe(df_view_ret, use_container_width=True, hide_index=True, height=650)
        else:
            st.info("ℹ️ Nenhuma peça com retorno registrado para este filtro.")

# ==============================================================================
# 6. ABA FALTA RETORNO
# ==============================================================================
with tab_pend_trat:
    if not df_trabalho.empty:
        df_p1 = df_trabalho[df_trabalho["Saldo_Pendente_Pintura"] > 0].copy()
        forns_pend = sorted([f for f in df_p1["Fornecedor_Tratamento"].unique() if f != "-"])
        if forns_pend:
            sel_forn_pend = st.multiselect("Filtrar por Fornecedor (Onde a peça está):", forns_pend, default=[])
            if sel_forn_pend:
                df_p1 = df_p1[df_p1["Fornecedor_Tratamento"].isin(sel_forn_pend)]

        if not df_p1.empty:
            cols_pen_ordem = ["Data_Envio", "OBS_NORM", "COD_PECA", "Descricao", "Fornecedor_Tratamento", "Qtd_OP", "Qtd_Fabr", "Env_Pintura", "Ret_Pintura", "Saldo_Pendente_Pintura", "Doc_Romaneio"]
            df_view_falta_ret = df_p1[cols_pen_ordem].rename(columns={
                "Data_Envio": "Data do Envio", "OBS_NORM": "Observação (Lote)", "COD_PECA": "Código Peça", "Descricao": "Descrição",
                "Fornecedor_Tratamento": "Fornecedor (Onde está)", "Qtd_OP": "Programado", "Qtd_Fabr": "Fabricado", "Env_Pintura": "Enviado",
                "Ret_Pintura": "Retornado", "Saldo_Pendente_Pintura": "Falta Retorno (Saldo na Rua)", "Doc_Romaneio": "Romaneio / Remessa Envio"
            })

            c_tit, c_btns = st.columns([3, 2])
            with c_tit:
                st.subheader(f"🚨 Falta Retorno de Tratamento Externo ({len(df_p1)} itens | {saldo_rua:,} peças)")
            with c_btns:
                cb1, cb2 = st.columns(2)
                with cb1:
                    renderizar_botao_copiar_tabela(df_view_falta_ret, "btn_cp_falta_ret")
                with cb2:
                    st.download_button(
                        "📥 Exportar (.xlsx)", data=gerar_excel_tabela(df_p1, "Falta_Retorno_Tratamento"),
                        file_name="Falta_Retorno_Tratamento.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            st.dataframe(df_view_falta_ret, use_container_width=True, hide_index=True, height=650)
        else:
            st.success("🎉 Nenhuma peça pendente de retorno de tratamento para este filtro!")

# ==============================================================================
# 7. ABA AGUARDANDO ENVIO
# ==============================================================================
with tab_aguard_envio:
    if not df_trabalho.empty:
        df_p3 = df_trabalho[df_trabalho["Aguardando_Envio"] > 0].copy()
        if not df_p3.empty:
            cols_env = ["Data_Fabricacao", "OBS_NORM", "COD_PECA", "Descricao", "Qtd_OP", "Qtd_Fabr", "Env_Pintura", "Aguardando_Envio"]
            df_view_aguard = df_p3[cols_env].rename(columns={
                "Data_Fabricacao": "Data Fabricação", "OBS_NORM": "Observação (Lote)", "COD_PECA": "Código Peça",
                "Descricao": "Descrição", "Qtd_OP": "Programado OP", "Qtd_Fabr": "Fabricado", "Env_Pintura": "Já Enviado",
                "Aguardando_Envio": "Aguardando Despacho"
            })

            c_tit, c_btns = st.columns([3, 2])
            with c_tit:
                st.subheader(f"🚚 Peças Fabricadas Aguardando Envio ({len(df_p3)} itens | {falta_env:,} peças)")
            with c_btns:
                cb1, cb2 = st.columns(2)
                with cb1:
                    renderizar_botao_copiar_tabela(df_view_aguard, "btn_cp_aguardando")
                with cb2:
                    st.download_button(
                        "📥 Exportar (.xlsx)", data=gerar_excel_tabela(df_p3, "Aguardando_Envio"),
                        file_name="Fabricadas_Aguardando_Envio.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            st.dataframe(df_view_aguard, use_container_width=True, hide_index=True, height=650)
        else:
            if not sel_obs_global:
                st.success("🎉 Todas as peças fabricadas já foram enviadas para tratamento!")
            else:
                st.info("Nenhuma peça aguardando envio para o projeto selecionado.")

# ==============================================================================
# 8. ABA FALTA FABRICAR
# ==============================================================================
with tab_falta_fab:
    if not df_trabalho.empty:
        df_p4 = df_trabalho[df_trabalho["Falta_Fabricar"] > 0].copy()
        if not df_p4.empty:
            cols_fab = ["OBS_NORM", "COD_PECA", "Descricao", "Qtd_OP", "Qtd_Fabr", "Falta_Fabricar"]
            df_view_falta_fab = df_p4[cols_fab].rename(columns={
                "OBS_NORM": "Observação (Lote)", "COD_PECA": "Código Peça", "Descricao": "Descrição",
                "Qtd_OP": "Programado OP", "Qtd_Fabr": "Já Fabricado", "Falta_Fabricar": "Saldo a Produzir"
            })

            c_tit, c_btns = st.columns([3, 2])
            with c_tit:
                st.subheader(f"⚙️ Peças que Faltam Ser Fabricadas ({len(df_p4)} itens | {falta_fab:,} peças)")
            with c_btns:
                cb1, cb2 = st.columns(2)
                with cb1:
                    renderizar_botao_copiar_tabela(df_view_falta_fab, "btn_cp_falta_fab")
                with cb2:
                    st.download_button(
                        "📥 Exportar (.xlsx)", data=gerar_excel_tabela(df_p4, "Falta_Fabricar"),
                        file_name="Falta_Fabricar_Internamente.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            st.dataframe(df_view_falta_fab, use_container_width=True, hide_index=True, height=650)
        else:
            if not sel_obs_global:
                st.success("🎉 100% da programação de fábrica já foi produzida internamente!")
            else:
                st.info("Nenhuma peça pendente de fabricação interna para o projeto selecionado.")

# ==============================================================================
# 9. ABA COMPRAS EXTERNAS
# ==============================================================================
with tab_compras:
    if not df_comp_trabalho.empty:
        col_forn_f, col_st_f = st.columns(2)
        with col_forn_f:
            fornecedores = sorted([str(f) for f in df_comp_trabalho["Fornecedor"].unique() if str(f).strip() and str(f) != "-"])
            sel_forn = st.multiselect("Filtrar por Fornecedor de Compra:", fornecedores, default=[])
        with col_st_f:
            status_comp = sorted([str(s) for s in df_comp_trabalho["Status_Compra"].unique() if str(s).strip() and str(s) != "-"])
            status_pendentes = [s for s in status_comp if "100%" not in s]
            sel_st_comp = st.multiselect("Filtrar por Status de Entrega:", status_comp, default=status_pendentes)

        df_comp_view = df_comp_trabalho.copy()
        if sel_forn:
            df_comp_view = df_comp_view[df_comp_view["Fornecedor"].isin(sel_forn)]
        if sel_st_comp:
            df_comp_view = df_comp_view[df_comp_view["Status_Compra"].isin(sel_st_comp)]

        colunas_comp = ["Status_Compra", "Data_Entrega", "Data_Fornecedor", "OBS_NORM", "COD_PECA", "Descricao", "Fornecedor", "Qtd_Comprada", "Qtd_Entregue", "Saldo_Falta_Entregar", "NF_Entrega"]
        df_view_compras = df_comp_view[colunas_comp].rename(columns={
            "Status_Compra": "Status", "Data_Entrega": "DT Ent.", "Data_Fornecedor": "Data Fornecedor", "OBS_NORM": "Observação (L)",
            "COD_PECA": "Código Peça", "Descricao": "Descrição", "Fornecedor": "Fornecedor", "Qtd_Comprada": "QT Comprada",
            "Qtd_Entregue": "QTD Entregue", "Saldo_Falta_Entregar": "FAL", "NF_Entrega": "NF Ent."
        })

        c_tit, c_btns = st.columns([3, 2])
        with c_tit:
            st.subheader(f"📦 Compras e Projetos Externados ({len(df_comp_trabalho)} itens | {tot_entregue:,} de {tot_comprado:,} entregues)")
        with c_btns:
            cb1, cb2 = st.columns(2)
            with cb1:
                renderizar_botao_copiar_tabela(df_view_compras, "btn_cp_compras")
            with cb2:
                st.download_button(
                    "📥 Exportar (.xlsx)", data=gerar_excel_tabela(df_comp_trabalho, "Compras_Externas"),
                    file_name="Compras_Projetos_Externados.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        st.dataframe(df_view_compras, use_container_width=True, hide_index=True, height=650)
    else:
        st.info("Nenhum item de Compras encontrado para o filtro selecionado.")

# ==============================================================================
# 10. ABA SC EM ABERTO
# ==============================================================================
with tab_sc:
    if not df_sc_trabalho.empty:
        col_solic_f, col_ped_f = st.columns(2)
        with col_solic_f:
            solicitantes = sorted([str(s) for s in df_sc_trabalho["Solicitante"].unique() if str(s).strip() and str(s) != "-"])
            sel_solic = st.multiselect("Filtrar por Solicitante:", solicitantes, default=[])
        with col_ped_f:
            pedidos_sc = sorted([str(p) for p in df_sc_trabalho["Pedido"].unique() if str(p).strip() and str(p) != "-"])
            sel_ped_sc = st.multiselect("Filtrar por Pedido Vinculado:", pedidos_sc, default=[])

        df_sc_view = df_sc_trabalho.copy()
        if sel_solic:
            df_sc_view = df_sc_view[df_sc_view["Solicitante"].isin(sel_solic)]
        if sel_ped_sc:
            df_sc_view = df_sc_view[df_sc_view["Pedido"].isin(sel_ped_sc)]

        colunas_sc = ["Necessidade", "Emissao", "Filial", "Num_SC", "Item", "COD_PECA", "UM", "Descricao", "Qtd_SC", "OBS_NORM", "Pedido", "Solicitante", "Classe_Valor"]
        df_view_sc = df_sc_view[colunas_sc].rename(columns={
            "Necessidade": "Necessidade", "Emissao": "Emissão", "Filial": "Filial", "Num_SC": "Nº Solicitação", "Item": "Item",
            "COD_PECA": "Produto", "UM": "UM", "Descricao": "Descrição", "Qtd_SC": "Qtde da SC", "OBS_NORM": "Observação (I)",
            "Pedido": "Pedido", "Solicitante": "Solicitante", "Classe_Valor": "Classe Valor"
        })

        c_tit, c_btns = st.columns([3, 2])
        with c_tit:
            st.subheader(f"📋 Solicitações de Compras em Aberto ({len(df_sc_trabalho)} itens | {tot_sc_aberto:,} peças)")
        with c_btns:
            cb1, cb2 = st.columns(2)
            with cb1:
                renderizar_botao_copiar_tabela(df_view_sc, "btn_cp_sc")
            with cb2:
                st.download_button(
                    "📥 Exportar (.xlsx)", data=gerar_excel_tabela(df_sc_trabalho, "SC_Em_Aberto"),
                    file_name="Solicitacoes_Compras_Aberto.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        st.dataframe(df_view_sc, use_container_width=True, hide_index=True, height=650)
    else:
        st.info("Nenhuma Solicitação de Compras em aberto encontrada para o filtro selecionado.")

# ==============================================================================
# 11. ABA CONSOLIDADA: BASES DE DADOS
# ==============================================================================
with tab_dados_brutos:
    st.markdown("### 📂 Visualizador de Bases de Dados Brutas")
    
    tipo_base = st.radio(
        "Selecione a base de dados para visualizar:",
        ["📑 OP Fabricação", "🎨 Romaneio de Pintura", "🛒 Compras e Externos"],
        horizontal=True
    )
    
    st.markdown("---")

    if tipo_base == "📑 OP Fabricação":
        if not df_op_raw.empty:
            c_tit_raw, c_btn_raw = st.columns([3, 2])
            with c_tit_raw:
                st.caption(f"Total de registros: {len(df_op_raw):,}")
            with c_btn_raw:
                cb1, cb2 = st.columns(2)
                with cb1:
                    renderizar_botao_copiar_tabela(df_op_raw, "btn_cp_base_op")
                with cb2:
                    st.download_button("📥 Exportar (.xlsx)", data=gerar_excel_tabela(df_op_raw, "Base_OP"), file_name="Base_OP.xlsx")
            
            df_mostrar = df_op_raw[df_op_raw["Produto"].astype(str).str.contains(busca_cod, case=False, na=False)] if busca_cod else df_op_raw
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True, height=600)
        else:
            st.info("Base OP não carregada.")

    elif tipo_base == "🎨 Romaneio de Pintura":
        if not df_rom_raw.empty:
            c_tit_raw, c_btn_raw = st.columns([3, 2])
            with c_tit_raw:
                st.caption(f"Total de registros: {len(df_rom_raw):,}")
            with c_btn_raw:
                cb1, cb2 = st.columns(2)
                with cb1:
                    renderizar_botao_copiar_tabela(df_rom_raw, "btn_cp_base_rom")
                with cb2:
                    st.download_button("📥 Exportar (.xlsx)", data=gerar_excel_tabela(df_rom_raw, "Base_Romaneio"), file_name="Base_Romaneio.xlsx")
            
            df_mostrar = df_rom_raw[df_rom_raw["PRODUTO"].astype(str).str.contains(busca_cod, case=False, na=False)] if busca_cod else df_rom_raw
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True, height=600)
        else:
            st.info("Base Romaneio não carregada.")

    elif tipo_base == "🛒 Compras e Externos":
        if not df_comp_raw.empty:
            c_tit_raw, c_btn_raw = st.columns([3, 2])
            with c_tit_raw:
                st.caption(f"Total de registros: {len(df_comp_raw):,}")
            with c_btn_raw:
                cb1, cb2 = st.columns(2)
                with cb1:
                    renderizar_botao_copiar_tabela(df_comp_raw, "btn_cp_base_comp")
                with cb2:
                    st.download_button("📥 Exportar (.xlsx)", data=gerar_excel_tabela(df_comp_raw, "Base_Compras"), file_name="Base_Compras.xlsx")
            
            if busca_cod:
                col_busca_prod = [c for c in df_comp_raw.columns if "PROD" in str(c).upper() or "COD" in str(c).upper()]
                col_target = col_busca_prod[0] if col_busca_prod else df_comp_raw.columns[2]
                df_mostrar = df_comp_raw[df_comp_raw[col_target].astype(str).str.contains(busca_cod, case=False, na=False)]
            else:
                df_mostrar = df_comp_raw
                
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True, height=600)
        else:
            st.info("Base Compras não carregada.")
