import streamlit as st
import pandas as pd
import numpy as np
import os
import re
import io
import json
import shutil
from datetime import datetime, timezone, timedelta

st.set_page_config(
    page_title="Gestão Integrada: Produção, Pintura & Compras",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilização CSS refinada
st.markdown("""
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
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        max-width: 100% !important;
    }
    [data-testid="stSidebar"] { display: none !important; }
    
    .sticky-top-panel {
        position: sticky;
        top: 2.8rem;
        z-index: 999;
        background-color: #0e1117;
        padding: 8px 12px;
        border-bottom: 2px solid #30363d;
        border-radius: 8px;
        margin-bottom: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.6);
    }
    
    [data-testid="stMetricValue"] {
        font-size: 1.05rem !important;
        font-weight: 700 !important;
        color: #1E88E5 !important;
        line-height: 1.1 !important;
    }
    [data-testid="stMetricLabel"] { font-size: 0.72rem !important; line-height: 1.1 !important; }
    [data-testid="stMetricDelta"] { font-size: 0.68rem !important; }
    
    div[data-baseweb="select"] * { font-size: 0.76rem !important; line-height: 1.25 !important; }
    div[data-baseweb="tag"] { 
        background-color: #1f6feb !important; 
        color: #ffffff !important;
        border-radius: 4px !important;
        padding: 1px 6px !important; 
        margin: 1px !important;
    }
    div[data-baseweb="tag"] span { font-size: 0.72rem !important; color: #ffffff !important; }
    
    .stTabs [data-baseweb="tab-list"] { gap: 4px; overflow-x: auto; }
    .stTabs [data-baseweb="tab"] { height: 36px; font-weight: 600; font-size: 0.78rem; padding: 0 8px; white-space: nowrap; }
    
    .card-mobile-kpi {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 8px;
    }
    
    [data-testid="stDataFrame"] {
        width: 100% !important;
        min-height: 500px !important;
    }
    [data-testid="stDataFrame"] > div {
        width: 100% !important;
    }
</style>
""", unsafe_allow_html=True)

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
    
    for fname in ["base_op.parquet", "base_romaneio.parquet", "base_compras.parquet", "base_sc.parquet"]:
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
                except:
                    pass
    return backups

def restaurar_backup(pasta_id):
    pasta_origem = os.path.join(BACKUPS_DIR, pasta_id)
    if os.path.exists(pasta_origem):
        for fname in ["base_op.parquet", "base_romaneio.parquet", "base_compras.parquet", "base_sc.parquet"]:
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
                meta["ultima_atualizacao"] = f"Restaurado de: {info.get('data_formatada')}"
                salvar_meta(meta)

def normalizar_texto(t):
    if pd.isna(t) or t is None: return ""
    s = str(t).replace('\xa0', ' ').replace('\u00a0', ' ').replace('\r', '').replace('\n', ' ')
    return re.sub(r'\s+', ' ', s).strip().upper()

def extrair_tat_base(t):
    t_clean = normalizar_texto(t)
    m = re.search(r'(\d{5}\.\d{2}[A-Z0-9]*)', t_clean)
    if m:
        raiz = re.sub(r'[A-Z].*$', '', m.group(1).strip())
        return f"TAT {raiz}" if not raiz.startswith("TAT") else raiz
    m2 = re.search(r'(TAT\s*[\d\.\w]+)', t_clean)
    if m2:
        return m2.group(1).strip()
    return t_clean.split('-')[0].strip()

def limpar_cod(c):
    if pd.isna(c) or c is None: return ""
    return str(c).replace('\xa0', ' ').replace('\u00a0', ' ').strip().upper()

def converter_num(v):
    if pd.isna(v) or v is None: return 0.0
    try: 
        s = str(v).replace('\xa0', '').replace(' ', '').replace(',', '.')
        return float(s)
    except Exception: 
        return 0.0

def formatar_data_br(val):
    if pd.isna(val) or val is None or str(val).strip() in ["-", "", "nan", "NaT", "None"]:
        return "-"
    s = str(val).strip()
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
    if m: return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    m_br = re.match(r'^(\d{2})/(\d{2})/(\d{4})', s)
    if m_br: return s[:10]
    return s

def padronizar_fornecedor_romaneio(val):
    if pd.isna(val) or not str(val).strip() or str(val).strip() == "-":
        return "-"
    t = normalizar_texto(val)
    if re.match(r'^\d{2}\.[A-Z0-9]+\.', t): return "-"
    if "0002805" in t or "MEGACOLORS PRIME" in t or "PRIME" in t: return "MEGACOLORS PRIME"
    elif "0002695" in t or "MEGACOLORS" in t or "MEGA COLORS" in t: return "MEGACOLORS"
    elif "000092" in t or "REVRI" in t: return "REVRI"
    elif "000022" in t or "ECE" in t: return "ECE"
    elif "0002739" in t or "FORT COLOR" in t or "FORTCOLOR" in t: return "FORT COLOR"
    elif "000408" in t or "ZINCOBRIL" in t or "ZINCO BRIL" in t: return "ZINCOBRIL"
    m = re.search(r'-\s*F\s*-\s*(.+)', t)
    if m: return m.group(1).strip()
    return t

def buscar_col_flex(df, lista_padroes, excluir_padroes=None):
    if df.empty or len(df.columns) == 0: return None
    excluir = [normalizar_texto(e) for e in (excluir_padroes or [])]
    for c in df.columns:
        c_clean = normalizar_texto(c)
        if any(e in c_clean for e in excluir): continue
        for p in lista_padroes:
            if normalizar_texto(p) == c_clean: return c
    for c in df.columns:
        c_clean = normalizar_texto(c)
        if any(e in c_clean for e in excluir): continue
        for p in lista_padroes:
            if normalizar_texto(p) in c_clean: return c
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
    if df_exportar.empty: return output.getvalue()
    df_clean = df_exportar.copy()
    def sanitizar_val(val):
        if pd.isna(val) or val is None: return ""
        s = str(val)
        return "".join(ch for ch in s if ord(ch) >= 32 or ch in "\n\r\t")
    df_clean.columns = [sanitizar_val(c) for c in df_clean.columns]
    df_clean = df_clean.astype(str).map(sanitizar_val)
    aba_segura = re.sub(r'[\\/*?:\[\]]', '', str(nome_aba))[:30]
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_clean.to_excel(writer, index=False, sheet_name=aba_segura)
    return output.getvalue()

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
        col_obs_op = df_op_raw.columns[11] if len(df_op_raw.columns) >= 12 else buscar_col_flex(df_op_raw, ["OBSERVAÇÃO", "OBSERVAÇÕES", "OBSERVACAO", "OBSERVACOES", "OBS"])
        col_tat_op = buscar_col_flex(df_op_raw, ["TAT", "PROJETO", "PROJ", "DESENHO", "OBSERVAÇÃO", "OBS"])
        col_prod_op = buscar_col_flex(df_op_raw, ["PRODUTO", "COD PROD", "CODIGO"])
        col_desc_op = buscar_col_flex(df_op_raw, ["DESC. PROD", "DESCRICAO", "DESCRIÇÃO"])
        col_qtd_op = buscar_col_flex(df_op_raw, ["QUANTIDADE", "QUANTI", "QTD PLAN"])
        col_prodz_op = buscar_col_flex(df_op_raw, ["QTD.PRODUZID", "PRODUZIDO", "QTD PRODUZIDA"])
        col_mes_op = buscar_col_flex(df_op_raw, ["MÊS-ANO", "MES-ANO", "MÊS", "MES"])
        col_dt_fim = buscar_col_flex(df_op_raw, ["DT REAL FIM", "REAL FIM", "DATA FIM", "DATA"])

        df_op = df_op_raw.copy()
        df_op["OBS_NORM"] = df_op[col_obs_op].apply(normalizar_texto) if col_obs_op else ""
        
        if col_tat_op:
            df_op["TAT_BASE"] = df_op[col_tat_op].apply(extrair_tat_base)
        else:
            df_op["TAT_BASE"] = df_op["OBS_NORM"].apply(extrair_tat_base)

        df_op["COD_PECA"] = df_op[col_prod_op].apply(limpar_cod) if col_prod_op else ""
        df_op["DESC_PECA"] = df_op[col_desc_op].fillna("-").astype(str) if col_desc_op else "-"
        df_op["QTD_PLAN"] = df_op[col_qtd_op].apply(converter_num) if col_qtd_op else 0.0
        df_op["QTD_PROD"] = df_op[col_prodz_op].apply(converter_num) if col_prodz_op else 0.0
        df_op["MES_ANO"] = df_op[col_mes_op].astype(str).str.strip() if col_mes_op else "Geral"
        df_op["ANO"] = df_op["MES_ANO"].str.extract(r'^(\d{4})')[0]
        df_op["MES"] = df_op["MES_ANO"].str.extract(r'/(\d{2})')[0]
        df_op["DT_FABR"] = df_op[col_dt_fim].apply(formatar_data_br) if col_dt_fim else "-"

        for _, r in df_op[["COD_PECA", "DESC_PECA"]].dropna().iterrows():
            c, d = str(r["COD_PECA"]).strip(), str(r["DESC_PECA"]).strip()
            if c and d and d not in ["-", "NAN", "NONE", ""]:
                catalogo_descricoes[c] = d

    # 2. Romaneio
    df_rom = pd.DataFrame()
    if not df_rom_raw.empty:
        col_obs_rom = buscar_col_flex(df_rom_raw, ["OBSERVAÇÕES", "OBSERVACOES", "OBSERVAÇÃO", "OBSERVACAO", "OBS"])
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
        df_rom["TAT_BASE"] = df_rom["OBS_NORM"].apply(extrair_tat_base)
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
        col_obs_comp = df_comp_raw.columns[11] if len(df_comp_raw.columns) >= 12 else buscar_col_flex(df_comp_raw, ["OBSERVAÇÃO", "OBSERVAÇÕES", "OBSERVACAO", "OBSERVACOES", "OBS"])
        col_prod_comp = buscar_col_flex(df_comp_raw, ["PRODUTO", "COD PROD", "CODIGO"])
        col_desc_comp = buscar_col_flex(df_comp_raw, ["DESCRIÇÃO", "DESCRICAO", "DESC. PROD"])
        col_forn_comp = buscar_col_flex(df_comp_raw, ["FORNECEDOR"])
        col_qt_comp = buscar_col_flex(df_comp_raw, ["QT", "QUANTIDADE", "QTD"])
        col_ent_comp = buscar_col_flex(df_comp_raw, ["QTD ENTREGUE", "QTD.ENTREGUE", "ENTREGUE"])
        col_fal_comp = buscar_col_flex(df_comp_raw, ["FAL", "FALTA"])
        col_dt_comp = buscar_col_flex(df_comp_raw, ["DT ENT.", "DT ENT", "DATA ENTREGA"])
        col_nf_comp = buscar_col_flex(df_comp_raw, ["NF ENT.", "NF ENT", "NOTA FISCAL", "NF"])
        col_dt_forn = buscar_col_flex(df_comp_raw, ["DATA FORNECEDOR", "DT FORNECEDOR"])

        df_comp = df_comp_raw.copy()
        df_comp["OBS_NORM"] = df_comp[col_obs_comp].apply(normalizar_texto) if col_obs_comp else ""
        df_comp["TAT_BASE"] = df_comp["OBS_NORM"].apply(extrair_tat_base)
        df_comp["COD_PECA"] = df_comp[col_prod_comp].apply(limpar_cod) if col_prod_comp else ""
        df_comp["Descricao"] = df_comp[col_desc_comp].fillna("-").astype(str) if col_desc_comp else "-"
        df_comp["Fornecedor"] = df_comp[col_forn_comp].fillna("-").astype(str) if col_forn_comp else "-"
        df_comp["Qtd_Comprada"] = df_comp[col_qt_comp].apply(converter_num) if col_qt_comp else 0.0
        df_comp["Qtd_Entregue"] = df_comp[col_ent_comp].apply(converter_num) if col_ent_comp else 0.0
        
        if col_fal_comp: df_comp["Saldo_Falta_Entregar"] = df_comp[col_fal_comp].apply(converter_num)
        else: df_comp["Saldo_Falta_Entregar"] = (df_comp["Qtd_Comprada"] - df_comp["Qtd_Entregue"]).clip(lower=0.0)

        df_comp["Data_Entrega"] = df_comp[col_dt_comp].apply(formatar_data_br) if col_dt_comp else "-"
        df_comp["NF_Entrega"] = df_comp[col_nf_comp].fillna("-").astype(str) if col_nf_comp else "-"
        df_comp["Data_Fornecedor"] = df_comp[col_dt_forn].apply(formatar_data_br) if col_dt_forn else "-"
        
        def calc_status_compra(r):
            if r["Qtd_Entregue"] >= r["Qtd_Comprada"] and r["Qtd_Comprada"] > 0: return "✅ 100% Entregue"
            elif r["Qtd_Entregue"] > 0: return "🚚 Entregue Parcial"
            else: return "⏳ Aguardando Fornecedor"
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
        col_obs_sc = df_sc_raw.columns[8] if len(df_sc_raw.columns) >= 9 else buscar_col_flex(df_sc_raw, ["OBSERVAÇÃO", "OBSERVAÇÕES", "OBSERVACAO", "OBSERVACOES", "OBS"])
        col_emis_sc = buscar_col_flex(df_sc_raw, ["EMISSÃO", "EMISSAO", "DT EMISSAO"])
        col_solic_sc = buscar_col_flex(df_sc_raw, ["SOLICITANTE", "NOME SOLICITANTE"])
        col_classe_sc = buscar_col_flex(df_sc_raw, ["CLASSE VALOR", "CLASSE"])
        col_ped_sc = buscar_col_flex(df_sc_raw, ["PEDIDO", "NUM PEDIDO"])

        df_sc = df_sc_raw.copy()
        df_sc["OBS_NORM"] = df_sc[col_obs_sc].apply(normalizar_texto) if col_obs_sc else ""
        df_sc["TAT_BASE"] = df_sc["OBS_NORM"].apply(extrair_tat_base)
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

    # 5. Cruzamento Inteligente
    def format_unique_join(x):
        vals = [str(v) for v in x if str(v) not in ["-", "", "nan", "None"]]
        return ", ".join(sorted(set(vals))) or "-"

    # Dicionários de Produção
    mapa_prod_obs = {}
    mapa_plan_obs = {}
    mapa_prod_tat = {}
    mapa_plan_tat = {}
    
    if not df_op.empty:
        for _, r in df_op.iterrows():
            obs = str(r["OBS_NORM"]).strip()
            tat = str(r["TAT_BASE"]).strip()
            peca = str(r["COD_PECA"]).strip()
            
            mapa_prod_obs[(obs, peca)] = mapa_prod_obs.get((obs, peca), 0.0) + r["QTD_PROD"]
            mapa_plan_obs[(obs, peca)] = mapa_plan_obs.get((obs, peca), 0.0) + r["QTD_PLAN"]
            
            mapa_prod_tat[(tat, peca)] = mapa_prod_tat.get((tat, peca), 0.0) + r["QTD_PROD"]
            mapa_plan_tat[(tat, peca)] = mapa_plan_tat.get((tat, peca), 0.0) + r["QTD_PLAN"]

    op_obs = df_op.groupby(["OBS_NORM", "COD_PECA"], as_index=False).agg(
        TAT_BASE=("TAT_BASE", "first"),
        Descricao=("DESC_PECA", "first"),
        Qtd_OP=("QTD_PLAN", "sum"),
        Qtd_Fabr=("QTD_PROD", "sum"),
        Data_Fabricacao=("DT_FABR", format_unique_join)
    ) if not df_op.empty else pd.DataFrame(columns=["OBS_NORM", "COD_PECA", "TAT_BASE", "Descricao", "Qtd_OP", "Qtd_Fabr", "Data_Fabricacao"])

    rom_obs = df_rom.groupby(["OBS_NORM", "COD_PECA"], as_index=False).agg(
        TAT_BASE=("TAT_BASE", "first"),
        Descricao_Rom=("DESC_PECA", "first"),
        Env_Pintura=("QTD_ENV", "sum"),
        Ret_Pintura=("QTD_RET", "sum"),
        Saldo_Rua=("SALDO_RUA", "sum"),
        Doc_Romaneio=("DOC_ROMANEIO", format_unique_join),
        Data_Envio=("DATA_ENVIO", format_unique_join),
        NF_Retorno=("NF_RETORNO", format_unique_join),
        Data_Retorno=("DATA_RETORNO", format_unique_join),
        Fornecedor_Tratamento=("FORNECEDOR_TRAT", format_unique_join)
    ) if not df_rom.empty else pd.DataFrame(columns=["OBS_NORM", "COD_PECA", "TAT_BASE", "Descricao_Rom", "Env_Pintura", "Ret_Pintura", "Saldo_Rua", "Doc_Romaneio", "Data_Envio", "NF_Retorno", "Data_Retorno", "Fornecedor_Tratamento"])

    df_cruz_obs = pd.merge(op_obs, rom_obs, on=["OBS_NORM", "COD_PECA"], how="outer")

    if not df_cruz_obs.empty:
        if "TAT_BASE_x" in df_cruz_obs.columns:
            df_cruz_obs["TAT_BASE"] = df_cruz_obs["TAT_BASE_x"].fillna(df_cruz_obs["TAT_BASE_y"])
            df_cruz_obs.drop(columns=["TAT_BASE_x", "TAT_BASE_y"], inplace=True)
        elif "TAT_BASE" not in df_cruz_obs.columns:
            df_cruz_obs["TAT_BASE"] = df_cruz_obs["OBS_NORM"].apply(extrair_tat_base)

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
            if col_num not in df_cruz_obs.columns: df_cruz_obs[col_num] = 0.0
            df_cruz_obs[col_num] = df_cruz_obs[col_num].fillna(0.0).astype(float)

        # RECONCILIAÇÃO PRECISA DE FABRICADO E PROGRAMADO
        def reconciliar_fabricado(r):
            q_fab = r["Qtd_Fabr"]
            if q_fab > 0: return q_fab
            obs = str(r["OBS_NORM"]).strip()
            tat = str(r["TAT_BASE"]).strip()
            peca = str(r["COD_PECA"]).strip()
            
            if (obs, peca) in mapa_prod_obs: return mapa_prod_obs[(obs, peca)]
            if (tat, peca) in mapa_prod_tat: return mapa_prod_tat[(tat, peca)]
            return 0.0

        def reconciliar_op(r):
            q_op = r["Qtd_OP"]
            if q_op > 0: return q_op
            obs = str(r["OBS_NORM"]).strip()
            tat = str(r["TAT_BASE"]).strip()
            peca = str(r["COD_PECA"]).strip()
            
            if (obs, peca) in mapa_plan_obs: return mapa_plan_obs[(obs, peca)]
            if (tat, peca) in mapa_plan_tat: return mapa_plan_tat[(tat, peca)]
            return 0.0

        df_cruz_obs["Qtd_Fabr"] = df_cruz_obs.apply(reconciliar_fabricado, axis=1)
        df_cruz_obs["Qtd_OP"] = df_cruz_obs.apply(reconciliar_op, axis=1)

        for col_str in ["Data_Fabricacao", "Doc_Romaneio", "Data_Envio", "NF_Retorno", "Data_Retorno", "Fornecedor_Tratamento"]:
            df_cruz_obs[col_str] = df_cruz_obs[col_str].fillna("-").astype(str)
        
        df_cruz_obs.loc[df_cruz_obs["Env_Pintura"] == 0, "Fornecedor_Tratamento"] = "-"
        df_cruz_obs["Saldo_Pendente_Pintura"] = (df_cruz_obs["Env_Pintura"] - df_cruz_obs["Ret_Pintura"]).clip(lower=0.0)
        df_cruz_obs["Aguardando_Envio"] = (df_cruz_obs["Qtd_Fabr"] - df_cruz_obs["Env_Pintura"]).clip(lower=0.0)
        df_cruz_obs["Falta_Fabricar"] = (df_cruz_obs["Qtd_OP"] - df_cruz_obs["Qtd_Fabr"]).clip(lower=0.0)

        def calc_status(r):
            if r["Qtd_Fabr"] == 0 and r["Qtd_OP"] > 0: return "1. Falta Fabricar Internamente"
            elif r["Aguardando_Envio"] > 0 and r["Env_Pintura"] == 0: return "2. Fabricado (Não Enviado)"
            elif r["Saldo_Pendente_Pintura"] > 0: return "3. Em Tratamento Externo"
            elif r["Ret_Pintura"] >= r["Qtd_Fabr"] and r["Qtd_Fabr"] > 0: return "4. 100% Concluído (Entregue)"
            else: return "5. Parcial / Diversos"
        df_cruz_obs["Status"] = df_cruz_obs.apply(calc_status, axis=1)

    return df_cruz_obs, df_comp, df_sc, df_op, df_rom, df_op_raw, df_rom_raw, df_comp_raw, df_sc_raw

# --- CABEÇALHO COM CONTROLE DE HISTÓRICO ---
col_head_tit, col_head_up = st.columns([1, 3])
meta_atual = carregar_meta()
data_atualizacao = meta_atual.get("ultima_atualizacao", "Nenhum arquivo salvo ainda")

with col_head_tit:
    st.markdown("### 🏭 Gestão Integrada")
    st.caption(f"🕒 **Última carga:** {data_atualizacao}")

with col_head_up:
    col_up, col_btn_acoes = st.columns([2.5, 1.5])
    with col_up:
        arquivos_enviados = st.file_uploader(
            "📁 Carregar planilhas (OP, Romaneio, Compras e SC):", 
            type=["xlsx", "xls", "csv"], 
            accept_multiple_files=True
        )
    with col_btn_acoes:
        historicos = listar_historicos_disponiveis()
        opcoes_historico = ["📁 Versão Atual"] + [f"🕒 Backup: {h[1]}" for h in historicos]
        
        escolha_versao = st.selectbox("⏳ Histórico de Versões:", opcoes_historico, index=0)
        
        c_btn_rest, c_btn_clean = st.columns(2)
        with c_btn_rest:
            if escolha_versao != "📁 Versão Atual":
                if st.button("🔄 Restaurar"):
                    idx = opcoes_historico.index(escolha_versao) - 1
                    pasta_sel = historicos[idx][0]
                    restaurar_backup(pasta_sel)
                    st.cache_data.clear()
                    st.success("Versão restaurada com sucesso!")
                    st.rerun()
        with c_btn_clean:
            if st.button("🧹 Resetar"):
                for fname in ["base_op.parquet", "base_romaneio.parquet", "base_compras.parquet", "base_sc.parquet"]:
                    p = os.path.join(STORAGE_DIR, fname)
                    if os.path.exists(p): os.remove(p)
                meta_atual["ultima_atualizacao"] = "Nenhum arquivo salvo ainda"
                salvar_meta(meta_atual)
                st.cache_data.clear()
                st.success("Arquivos resetados com sucesso!")
                st.rerun()

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
                
                if not f.name.endswith('.csv'):
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

pasta_carregar = STORAGE_DIR
if escolha_versao != "📁 Versão Atual":
    idx = opcoes_historico.index(escolha_versao) - 1
    pasta_carregar = os.path.join(BACKUPS_DIR, historicos[idx][0])

mtimes = obter_mtimes(pasta_carregar)
df_cruz_obs, df_comp, df_sc, df_op, df_rom, df_op_raw, df_rom_raw, df_comp_raw, df_sc_raw = processar_todas_as_bases(mtimes, pasta_carregar)

if df_op_raw.empty and df_rom_raw.empty and df_comp_raw.empty and df_sc_raw.empty:
    st.info("👆 Nenhuma planilha salva ainda. Selecione os arquivos no campo acima para carregar o painel.")
    st.stop()

# --- FILTROS DE OBSERVAÇÃO ---
st.markdown('<div class="sticky-top-panel">', unsafe_allow_html=True)

obs_fabrica_set = set()
if not df_cruz_obs.empty and "OBS_NORM" in df_cruz_obs.columns:
    obs_fabrica_set.update(df_cruz_obs["OBS_NORM"].dropna().unique())
lista_obs_fabrica = sorted([str(p) for p in obs_fabrica_set if str(p).strip() and str(p) not in ["-", "NAN", "NONE"]])

obs_compras_set = set()
if not df_comp.empty and "OBS_NORM" in df_comp.columns:
    obs_compras_set.update(df_comp["OBS_NORM"].dropna().unique())
if not df_sc.empty and "OBS_NORM" in df_sc.columns:
    obs_compras_set.update(df_sc["OBS_NORM"].dropna().unique())
lista_obs_compras = sorted([str(p) for p in obs_compras_set if str(p).strip() and str(p) not in ["-", "NAN", "NONE"]])

col_f_fab, col_f_comp, col_f_busca = st.columns([1.6, 1.6, 1.0])

with col_f_fab:
    sel_obs_fabrica = st.multiselect(
        "🏗️ 1. Lotes Fabricação / Romaneio:",
        options=lista_obs_fabrica,
        placeholder="Digite parte do lote (OP / Pintura)..."
    )

with col_f_comp:
    sel_obs_compras = st.multiselect(
        "📦 2. Lotes Compras / SC:",
        options=lista_obs_compras,
        placeholder="Opcional: vincular manualmente..."
    )

with col_f_busca:
    busca_cod = st.text_input("🔍 Buscar Peça:", placeholder="Código ou descrição...").strip().upper()

df_trabalho = df_cruz_obs.copy() if not df_cruz_obs.empty else pd.DataFrame()
df_comp_trabalho = df_comp.copy() if not df_comp.empty else pd.DataFrame()
df_sc_trabalho = df_sc.copy() if not df_sc.empty else pd.DataFrame()

# 1. Filtra base de Fábrica / Romaneio
if sel_obs_fabrica:
    if not df_trabalho.empty and "OBS_NORM" in df_trabalho.columns:
        df_trabalho = df_trabalho[df_trabalho["OBS_NORM"].isin(sel_obs_fabrica)]

# 2. Vínculo Automático de Compras e SC
if sel_obs_compras:
    if not df_comp_trabalho.empty and "OBS_NORM" in df_comp_trabalho.columns:
        df_comp_trabalho = df_comp_trabalho[df_comp_trabalho["OBS_NORM"].isin(sel_obs_compras)]
    if not df_sc_trabalho.empty and "OBS_NORM" in df_sc_trabalho.columns:
        df_sc_trabalho = df_sc_trabalho[df_sc_trabalho["OBS_NORM"].isin(sel_obs_compras)]
    tit_comp = ", ".join(sel_obs_compras[:1]) + ("..." if len(sel_obs_compras) > 1 else "")
elif sel_obs_fabrica:
    tats_herdados = set([extrair_tat_base(obs) for obs in sel_obs_fabrica if extrair_tat_base(obs)])
    
    if not df_comp_trabalho.empty:
        c_obs_c = df_comp_trabalho["OBS_NORM"].isin(sel_obs_fabrica) if "OBS_NORM" in df_comp_trabalho.columns else False
        c_tat_c = df_comp_trabalho["TAT_BASE"].isin(tats_herdados) if "TAT_BASE" in df_comp_trabalho.columns else False
        df_comp_trabalho = df_comp_trabalho[c_obs_c | c_tat_c]
        
    if not df_sc_trabalho.empty:
        c_obs_s = df_sc_trabalho["OBS_NORM"].isin(sel_obs_fabrica) if "OBS_NORM" in df_sc_trabalho.columns else False
        c_tat_s = df_sc_trabalho["TAT_BASE"].isin(tats_herdados) if "TAT_BASE" in df_sc_trabalho.columns else False
        df_sc_trabalho = df_sc_trabalho[c_obs_s | c_tat_s]
    tit_comp = "Auto-vinculado pela Fábrica"
else:
    tit_comp = "Todas as Compras"

tit_fab = ", ".join(sel_obs_fabrica[:1]) + ("..." if len(sel_obs_fabrica) > 1 else "") if sel_obs_fabrica else "Todas as OPs"
projeto_ativo_nome = f"Fábrica: [{tit_fab}] | Compras: [{tit_comp}]"

if busca_cod:
    if not df_trabalho.empty:
        df_trabalho = df_trabalho[
            df_trabalho["COD_PECA"].str.contains(busca_cod, na=False) | 
            df_trabalho["Descricao"].str.contains(busca_cod, na=False)
        ]
    if not df_comp_trabalho.empty:
        df_comp_trabalho = df_comp_trabalho[
            df_comp_trabalho["COD_PECA"].str.contains(busca_cod, na=False) | 
            df_comp_trabalho["Descricao"].str.contains(busca_cod, na=False)
        ]
    if not df_sc_trabalho.empty:
        df_sc_trabalho = df_sc_trabalho[
            df_sc_trabalho["COD_PECA"].str.contains(busca_cod, na=False) | 
            df_sc_trabalho["Descricao"].str.contains(busca_cod, na=False)
        ]

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

st.markdown('</div>', unsafe_allow_html=True)

# --- ABAS DETALHADAS ---
tab_mobile, tab_metalicos, tab_mensal, tab_retornadas, tab_pend_trat, tab_aguard_envio, tab_falta_fab, tab_compras, tab_sc, tab_base_op, tab_base_rom, tab_base_comp = st.tabs([
    "📱 Resumo Executivo (Celular)", "🏗️ Balanço Metálico", "📈 Produção Mensal", "✅ Peças Retornadas", "🚨 Falta Retorno",
    "🚚 Aguardando Envio", "⚙️ Falta Fabricar", "📦 Compras Externas",
    "📋 SC em Aberto", "📑 Base OP", "🎨 Base Romaneio", "🛒 Base Compras"
])

# 1. RESUMO EXECUTIVO
with tab_mobile:
    st.markdown(f"#### 📱 Resumo: `{projeto_ativo_nome}`")
    pct_pronto = (tot_ret / tot_op * 100) if tot_op > 0 else 0
    st.markdown(f"**Prontidão Geral da Estrutura Metálica: `{pct_pronto:.1f}%`**")
    st.progress(min(max(pct_pronto / 100.0, 0.0), 1.0))
    
    m_c1, m_c2 = st.columns(2)
    with m_c1:
        st.markdown(f"""
        <div class="card-mobile-kpi">
            <span style="font-size:0.8rem; color:#8b949e;">⚙️ FABRICAÇÃO INTERNA</span><br>
            <b style="font-size:1.1rem; color:#1E88E5;">{tot_fab:,} / {tot_op:,} pçs</b><br>
            <span style="font-size:0.75rem; color:{'#ff7b72' if falta_fab > 0 else '#3fb950'};">
                {'⚠️ Falta produzir: ' + str(falta_fab) + ' pçs' if falta_fab > 0 else '✅ 100% Produzido'}
            </span>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="card-mobile-kpi">
            <span style="font-size:0.8rem; color:#8b949e;">🚚 EXPEDIÇÃO / DESPACHO</span><br>
            <b style="font-size:1.1rem; color:#d29922;">{falta_env:,} pçs</b><br>
            <span style="font-size:0.75rem; color:#8b949e;">Aguardando envio p/ tratamento</span>
        </div>
        """, unsafe_allow_html=True)

    with m_c2:
        st.markdown(f"""
        <div class="card-mobile-kpi">
            <span style="font-size:0.8rem; color:#8b949e;">🎨 TRATAMENTO / PINTURA</span><br>
            <b style="font-size:1.1rem; color:#1E88E5;">{tot_ret:,} / {tot_env:,} pçs</b><br>
            <span style="font-size:0.75rem; color:{'#ff7b72' if saldo_rua > 0 else '#3fb950'};">
                {'🚨 Na rua (pendente): ' + str(saldo_rua) + ' pçs' if saldo_rua > 0 else '✅ 100% Retornado'}
            </span>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="card-mobile-kpi">
            <span style="font-size:0.8rem; color:#8b949e;">📦 COMPRAS & SC</span><br>
            <b style="font-size:1.1rem; color:#58a6ff;">{tot_entregue:,}/{tot_comprado:,} pçs</b><br>
            <span style="font-size:0.75rem; color:{'#ff7b72' if tot_sc_aberto > 0 else '#8b949e'};">
                {str(qtd_itens_sc) + ' SC em aberto (' + str(tot_sc_aberto) + ' pçs)' if tot_sc_aberto > 0 else 'Sem SCs pendentes'}
            </span>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("---")
    st.markdown("##### 📍 Onde estão as peças na rua por Fornecedor:")
    if not df_trabalho.empty:
        df_na_rua = df_trabalho[df_trabalho["Saldo_Pendente_Pintura"] > 0]
        if not df_na_rua.empty:
            for forn, group in df_na_rua.groupby("Fornecedor_Tratamento"):
                saldo_forn = int(group["Saldo_Pendente_Pintura"].sum())
                with st.expander(f"🔴 **{forn}**: {saldo_forn:,} peças pendentes ({len(group)} itens)"):
                    for _, r in group.iterrows():
                        st.markdown(f"• **`{r['COD_PECA']}`** ({r['Descricao'][:35]}): **{int(r['Saldo_Pendente_Pintura'])} pçs** | Romaneio: `{r['Doc_Romaneio']}` ({r['Data_Envio']})")
        else:
            st.success("🎉 Todas as peças enviadas para tratamento já retornaram 100% prontas!")
    
    st.markdown("##### ⚠️ O que falta fabricar internamente:")
    if not df_trabalho.empty:
        df_gargalo_fab = df_trabalho[df_trabalho["Falta_Fabricar"] > 0].sort_values("Falta_Fabricar", ascending=False).head(5)
        if not df_gargalo_fab.empty:
            for _, r in df_gargalo_fab.iterrows():
                st.markdown(f"• **`{r['COD_PECA']}`** — Falta: **{int(r['Falta_Fabricar'])} pçs** (Prog: {int(r['Qtd_OP'])}, Fab: {int(r['Qtd_Fabr'])}) | *{r['Descricao'][:40]}*")
        else:
            st.success("🎉 Nenhuma peça pendente de fabricação interna!")

# 2. BALANÇO COMPLETO METÁLICOS (ORDEM EXATA COM TODAS AS COLUNAS)
with tab_metalicos:
    if not df_trabalho.empty:
        c_tit, c_btn = st.columns([4, 1])
        with c_tit: st.markdown(f"**Balanço Metálico ({len(df_trabalho)} itens) — {tit_fab}**")
        with c_btn:
            st.download_button("📥 Exportar Balanço (.xlsx)", data=gerar_excel_tabela(df_trabalho, "Balanco_Metalicos"), file_name="Balanco_Completo_Metalicos.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        colunas_balanco_ordem = [
            "OBS_NORM", "COD_PECA", "Descricao", "Qtd_Fabr", "Env_Pintura", "Ret_Pintura", 
            "Saldo_Pendente_Pintura", "Falta_Fabricar", "Qtd_OP", "Aguardando_Envio", 
            "Doc_Romaneio", "Data_Envio", "Fornecedor_Tratamento", "NF_Retorno", "Data_Retorno", "Status"
        ]
        
        for col_chk in colunas_balanco_ordem:
            if col_chk not in df_trabalho.columns:
                df_trabalho[col_chk] = 0.0 if "Qtd" in col_chk or "Saldo" in col_chk or "Falta" in col_chk or "Env" in col_chk or "Ret" in col_chk else "-"

        st.dataframe(
            df_trabalho[colunas_balanco_ordem].rename(columns={
                "OBS_NORM": "Observação (Lote)",
                "COD_PECA": "Código da Peça",
                "Descricao": "Descrição",
                "Qtd_Fabr": "Já Fabricado",
                "Env_Pintura": "O que Saiu (Enviado)",
                "Ret_Pintura": "O que Voltou (Retornado)",
                "Saldo_Pendente_Pintura": "Falta Retornar (Saldo Rua)",
                "Falta_Fabricar": "Não Produziu (Falta Fabr.)",
                "Qtd_OP": "Total Programado (OP)",
                "Aguardando_Envio": "Aguardando Despacho",
                "Doc_Romaneio": "Romaneio / Remessa Envio",
                "Data_Envio": "Data do Envio",
                "Fornecedor_Tratamento": "Fornecedor (Onde está / Entregou)",
                "NF_Retorno": "NF Retorno",
                "Data_Retorno": "Data do Retorno",
                "Status": "Status do Fluxo"
            }),
            use_container_width=True,
            hide_index=True,
            height=650
        )
    else: st.info("Nenhum dado metálico encontrado para o filtro selecionado.")

# 3. PRODUÇÃO MENSAL
with tab_mensal:
    st.subheader("🗓️ Produção da Fábrica por Período")
    if not df_op.empty:
        col_f_ano, col_f_mes = st.columns(2)
        anos_disp = sorted([a for a in df_op["ANO"].dropna().unique() if len(str(a)) == 4])
        with col_f_ano: sel_anos = st.multiselect("🗓️ Flegar Ano(s):", anos_disp, default=anos_disp)
        df_op_filtrada_data = df_op.copy()
        if sel_anos: df_op_filtrada_data = df_op_filtrada_data[df_op_filtrada_data["ANO"].isin(sel_anos)]
        meses_disp = sorted([m for m in df_op_filtrada_data["MES"].dropna().unique() if str(m).isdigit()])
        with col_f_mes: sel_meses = st.multiselect("📅 Flegar Mês(es):", meses_disp, default=meses_disp)
        if sel_meses: df_op_filtrada_data = df_op_filtrada_data[df_op_filtrada_data["MES"].isin(sel_meses)]
        df_mes_prod = df_op_filtrada_data.groupby("MES_ANO", as_index=False).agg(Qtd_Planejada=("QTD_PLAN", "sum"), Qtd_Produzida=("QTD_PROD", "sum"), Total_OPs=("OP" if "OP" in df_op.columns else "COD_PECA", "nunique")).sort_values("MES_ANO")
        df_mes_prod = df_mes_prod[df_mes_prod["MES_ANO"].str.contains(r'^\d{4}', regex=True, na=False)]
        if not df_mes_prod.empty:
            col_g_mes, col_t_mes = st.columns([2, 1])
            with col_g_mes:
                st.markdown("**Volume Fabricado por Mês (Peças)**")
                st.bar_chart(df_mes_prod.set_index("MES_ANO")[["Qtd_Produzida", "Qtd_Planejada"]], color=["#1E88E5", "#90CAF9"])
            with col_t_mes:
                st.markdown("**Tabela do Período Selecionado**")
                df_mes_view = df_mes_prod.rename(columns={"MES_ANO": "Mês/Ano", "Qtd_Planejada": "Planejado", "Qtd_Produzida": "Fabricado", "Total_OPs": "Qtd OPs"})
                st.dataframe(df_mes_view, use_container_width=True, hide_index=True, height=500)
                st.download_button("📥 Exportar Produção Mensal (.xlsx)", data=gerar_excel_tabela(df_mes_view, "Producao_Mensal"), file_name="Producao_Mensal.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else: st.warning("Base de OP não carregada.")

# 4. PEÇAS RETORNADAS
with tab_retornadas:
    if not df_trabalho.empty:
        df_p2 = df_trabalho[df_trabalho["Ret_Pintura"] > 0].copy()
        forns_ret = sorted([f for f in df_p2["Fornecedor_Tratamento"].unique() if f != "-"])
        if forns_ret:
            sel_forn_ret = st.multiselect("Filtrar por Fornecedor (Quem entregou):", forns_ret, default=[])
            if sel_forn_ret: df_p2 = df_p2[df_p2["Fornecedor_Tratamento"].isin(sel_forn_ret)]

        c_tit, c_btn = st.columns([4, 1])
        with c_tit: st.subheader(f"✅ Peças que já Retornaram ({len(df_p2)} itens | {tot_ret:,} peças)")
        with c_btn:
            st.download_button("📥 Exportar Peças Retornadas (.xlsx)", data=gerar_excel_tabela(df_p2, "Pecas_Retornadas"), file_name="Pecas_Retornadas.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        if not df_p2.empty:
            cols_ret = ["OBS_NORM", "Fornecedor_Tratamento", "COD_PECA", "Descricao", "Qtd_Fabr", "Env_Pintura", "Ret_Pintura", "NF_Retorno", "Data_Retorno", "Doc_Romaneio", "Data_Envio", "Status"]
            st.dataframe(
                df_p2[cols_ret].rename(columns={
                    "OBS_NORM": "Observação (Lote)",
                    "Fornecedor_Tratamento": "Fornecedor (Entregou)",
                    "COD_PECA": "Código Peça", "Descricao": "Descrição",
                    "Qtd_Fabr": "Fabricado", "Env_Pintura": "Enviado", "Ret_Pintura": "Retornado Pronto",
                    "NF_Retorno": "NF de Retorno", "Data_Retorno": "Data do Retorno",
                    "Doc_Romaneio": "Romaneio de Envio", "Data_Envio": "Data do Envio", "Status": "Status"
                }),
                use_container_width=True,
                hide_index=True,
                height=650
            )
        else: st.info("ℹ️ Nenhuma peça com retorno registrado para este filtro.")

# 5. FALTA RETORNO
with tab_pend_trat:
    if not df_trabalho.empty:
        df_p1 = df_trabalho[df_trabalho["Saldo_Pendente_Pintura"] > 0].copy()
        forns_pend = sorted([f for f in df_p1["Fornecedor_Tratamento"].unique() if f != "-"])
        if forns_pend:
            sel_forn_pend = st.multiselect("Filtrar por Fornecedor (Onde a peça está):", forns_pend, default=[])
            if sel_forn_pend: df_p1 = df_p1[df_p1["Fornecedor_Tratamento"].isin(sel_forn_pend)]

        c_tit, c_btn = st.columns([4, 1])
        with c_tit: st.subheader(f"🚨 Falta Retorno de Tratamento Externo ({len(df_p1)} itens | {saldo_rua:,} peças)")
        with c_btn:
            st.download_button("📥 Exportar Falta Retorno (.xlsx)", data=gerar_excel_tabela(df_p1, "Falta_Retorno_Tratamento"), file_name="Falta_Retorno_Tratamento.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        if not df_p1.empty:
            cols_pen = ["OBS_NORM", "Fornecedor_Tratamento", "COD_PECA", "Descricao", "Qtd_OP", "Qtd_Fabr", "Env_Pintura", "Ret_Pintura", "Saldo_Pendente_Pintura", "Doc_Romaneio", "Data_Envio"]
            st.dataframe(
                df_p1[cols_pen].rename(columns={
                    "OBS_NORM": "Observação (Lote)",
                    "Fornecedor_Tratamento": "Fornecedor (Onde está)",
                    "COD_PECA": "Código Peça", "Descricao": "Descrição",
                    "Qtd_OP": "Programado", "Qtd_Fabr": "Fabricado", "Env_Pintura": "Enviado",
                    "Ret_Pintura": "Retornado", "Saldo_Pendente_Pintura": "Falta Retorno (Saldo na Rua)",
                    "Doc_Romaneio": "Romaneio / Remessa Envio", "Data_Envio": "Data do Envio"
                }),
                use_container_width=True,
                hide_index=True,
                height=650
            )
        else: st.success("🎉 Nenhuma peça pendente de retorno de tratamento para este filtro!")

# 6. FABRICADAS AGUARDANDO ENVIO
with tab_aguard_envio:
    if not df_trabalho.empty:
        df_p3 = df_trabalho[df_trabalho["Aguardando_Envio"] > 0].copy()
        c_tit, c_btn = st.columns([4, 1])
        with c_tit: st.subheader(f"🚚 Peças Fabricadas Aguardando Envio ({len(df_p3)} itens | {falta_env:,} peças)")
        with c_btn:
            st.download_button("📥 Exportar Aguardando Envio (.xlsx)", data=gerar_excel_tabela(df_p3, "Aguardando_Envio"), file_name="Fabricadas_Aguardando_Envio.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        if not df_p3.empty:
            cols_env = ["OBS_NORM", "COD_PECA", "Descricao", "Qtd_OP", "Qtd_Fabr", "Env_Pintura", "Aguardando_Envio", "Data_Fabricacao"]
            st.dataframe(
                df_p3[cols_env].rename(columns={"OBS_NORM": "Observação (Lote)", "COD_PECA": "Código Peça", "Descricao": "Descrição", "Qtd_OP": "Programado OP", "Qtd_Fabr": "Fabricado", "Env_Pintura": "Já Enviado", "Aguardando_Envio": "Aguardando Despacho", "Data_Fabricacao": "Data Fabricação"}),
                use_container_width=True,
                hide_index=True,
                height=650
            )
        else: st.success("🎉 Todas as peças fabricadas já foram enviadas para tratamento!")

# 7. FALTA FABRICAR
with tab_falta_fab:
    if not df_trabalho.empty:
        df_p4 = df_trabalho[df_trabalho["Falta_Fabricar"] > 0].copy()
        c_tit, c_btn = st.columns([4, 1])
        with c_tit: st.subheader(f"⚙️ Peças que Faltam Ser Fabricadas ({len(df_p4)} itens | {falta_fab:,} peças)")
        with c_btn:
            st.download_button("📥 Exportar Falta Fabricar (.xlsx)", data=gerar_excel_tabela(df_p4, "Falta_Fabricar"), file_name="Falta_Fabricar_Internamente.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        if not df_p4.empty:
            cols_fab = ["OBS_NORM", "COD_PECA", "Descricao", "Qtd_OP", "Qtd_Fabr", "Falta_Fabricar"]
            st.dataframe(
                df_p4[cols_fab].rename(columns={"OBS_NORM": "Observação (Lote)", "COD_PECA": "Código Peça", "Descricao": "Descrição", "Qtd_OP": "Programado OP", "Qtd_Fabr": "Já Fabricado", "Falta_Fabricar": "Saldo a Produzir"}),
                use_container_width=True,
                hide_index=True,
                height=650
            )
        else: st.success("🎉 100% da programação de fábrica já foi produzida internamente!")

# 8. COMPRAS
with tab_compras:
    if not df_comp_trabalho.empty:
        c_tit, c_btn = st.columns([4, 1])
        with c_tit: st.subheader(f"📦 Compras e Projetos Externados ({len(df_comp_trabalho)} itens | {tot_entregue:,} de {tot_comprado:,} entregues)")
        with c_btn:
            st.download_button("📥 Exportar Compras Filtradas (.xlsx)", data=gerar_excel_tabela(df_comp_trabalho, "Compras_Externas"), file_name="Compras_Projetos_Externados.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        col_forn_f, col_st_f = st.columns(2)
        with col_forn_f:
            fornecedores = sorted([str(f) for f in df_comp_trabalho["Fornecedor"].unique() if str(f).strip() and str(f) != "-"])
            sel_forn = st.multiselect("Filtrar por Fornecedor de Compra:", fornecedores, default=[])
        with col_st_f:
            status_comp = sorted([str(s) for s in df_comp_trabalho["Status_Compra"].unique() if str(s).strip() and str(s) != "-"])
            sel_st_comp = st.multiselect("Filtrar por Status de Entrega:", status_comp, default=[])
        df_comp_view = df_comp_trabalho.copy()
        if sel_forn: df_comp_view = df_comp_view[df_comp_view["Fornecedor"].isin(sel_forn)]
        if sel_st_comp: df_comp_view = df_comp_view[df_comp_view["Status_Compra"].isin(sel_st_comp)]
        colunas_comp = ["OBS_NORM", "COD_PECA", "Descricao", "Fornecedor", "Qtd_Comprada", "Qtd_Entregue", "Saldo_Falta_Entregar", "NF_Entrega", "Data_Entrega", "Data_Fornecedor", "Status_Compra"]
        st.dataframe(
            df_comp_view[colunas_comp].rename(columns={"OBS_NORM": "Observação (L)", "COD_PECA": "Código Peça", "Descricao": "Descrição", "Fornecedor": "Fornecedor", "Qtd_Comprada": "QT Comprada", "Qtd_Entregue": "QTD Entregue", "Saldo_Falta_Entregar": "FAL", "NF_Entrega": "NF Ent.", "Data_Entrega": "DT Ent.", "Data_Fornecedor": "Data Fornecedor", "Status_Compra": "Status"}),
            use_container_width=True,
            hide_index=True,
            height=650
        )
    else: st.info("Nenhuma planilha de Compras carregada ou nenhum item encontrado para o filtro selecionado.")

# 9. SC EM ABERTO
with tab_sc:
    if not df_sc_trabalho.empty:
        c_tit, c_btn = st.columns([4, 1])
        with c_tit: st.subheader(f"📋 Solicitações de Compras em Aberto ({len(df_sc_trabalho)} itens | {tot_sc_aberto:,} peças)")
        with c_btn:
            st.download_button("📥 Exportar SC Filtradas (.xlsx)", data=gerar_excel_tabela(df_sc_trabalho, "SC_Em_Aberto"), file_name="Solicitacoes_Compras_Aberto.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
        col_solic_f, col_ped_f = st.columns(2)
        with col_solic_f:
            solicitantes = sorted([str(s) for s in df_sc_trabalho["Solicitante"].unique() if str(s).strip() and str(s) != "-"])
            sel_solic = st.multiselect("Filtrar por Solicitante:", solicitantes, default=[])
        with col_ped_f:
            pedidos_sc = sorted([str(p) for p in df_sc_trabalho["Pedido"].unique() if str(p).strip() and str(p) != "-"])
            sel_ped_sc = st.multiselect("Filtrar por Pedido Vinculado:", pedidos_sc, default=[])
            
        df_sc_view = df_sc_trabalho.copy()
        if sel_solic: df_sc_view = df_sc_view[df_sc_view["Solicitante"].isin(sel_solic)]
        if sel_ped_sc: df_sc_view = df_sc_view[df_sc_view["Pedido"].isin(sel_ped_sc)]
        
        colunas_sc = ["Filial", "Num_SC", "Item", "COD_PECA", "UM", "Descricao", "Qtd_SC", "Necessidade", "OBS_NORM", "Emissao", "Pedido", "Solicitante", "Classe_Valor"]
        st.dataframe(
            df_sc_view[colunas_sc].rename(columns={
                "Filial": "Filial", "Num_SC": "Nº Solicitação", "Item": "Item",
                "COD_PECA": "Produto", "UM": "UM", "Descricao": "Descrição",
                "Qtd_SC": "Qtde da SC", "Necessidade": "Necessidade", "OBS_NORM": "Observação (I)",
                "Emissao": "Emissão", "Pedido": "Pedido", "Solicitante": "Solicitante",
                "Classe_Valor": "Classe Valor"
            }),
            use_container_width=True,
            hide_index=True,
            height=650
        )
    else:
        st.info("Nenhuma Solicitação de Compras em aberto carregada ou nenhum item encontrado para o filtro selecionado.")

# 10. BASE OP COMPLETA
with tab_base_op:
    st.subheader("📑 Base Completa: OP Fabricação")
    if not df_op_raw.empty:
        st.download_button("📥 Exportar Base OP (.xlsx)", data=gerar_excel_tabela(df_op_raw, "Base_OP"), file_name="Base_OP_Fabricacao.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        if busca_cod: st.dataframe(df_op_raw[df_op_raw["Produto"].astype(str).str.contains(busca_cod, case=False, na=False)], use_container_width=True, hide_index=True, height=650)
        else: st.dataframe(df_op_raw, use_container_width=True, hide_index=True, height=650)

# 11. BASE ROMANEIO COMPLETA
with tab_base_rom:
    st.subheader("🎨 Base Completa: Romaneio de Pintura")
    if not df_rom_raw.empty:
        st.download_button("📥 Exportar Base Romaneio (.xlsx)", data=gerar_excel_tabela(df_rom_raw, "Base_Romaneio"), file_name="Base_Romaneio_Pintura.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        if busca_cod: st.dataframe(df_rom_raw[df_rom_raw["PRODUTO"].astype(str).str.contains(busca_cod, case=False, na=False)], use_container_width=True, hide_index=True, height=650)
        else: st.dataframe(df_rom_raw, use_container_width=True, hide_index=True, height=650)

# 12. BASE COMPRAS COMPLETA
with tab_base_comp:
    st.subheader("🛒 Base Completa: Compras e Alinhamento Externo")
    if not df_comp_raw.empty:
        st.download_button("📥 Exportar Base Compras (.xlsx)", data=gerar_excel_tabela(df_comp_raw, "Base_Compras"), file_name="Base_Compras_Completa.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        if busca_cod:
            col_busca_prod = [c for c in df_comp_raw.columns if "PROD" in str(c).upper() or "COD" in str(c).upper()]
            col_target = col_busca_prod[0] if col_busca_prod else df_comp_raw.columns[2]
            st.dataframe(df_comp_raw[df_comp_raw[col_target].astype(str).str.contains(busca_cod, case=False, na=False)], use_container_width=True, hide_index=True, height=650)
        else: st.dataframe(df_comp_raw, use_container_width=True, hide_index=True, height=650)
