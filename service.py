import time
import asyncio
import aiohttp
from pathlib import Path
import io
import os

import pandas as pd
import requests
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils import clean_cnpj, clean_curr

# --- CONFIGURAÇÕES PIPEDRIVE ---
# Token da API do Pipedrive.
# Preferencialmente configure via variÃ¡vel de ambiente `PIPEDRIVE_API_TOKEN`.
# Fallback (pedido pelo usuÃ¡rio): token hardcoded para rodar localmente.
API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN", "09cfb9d8f7250a54cd3da2dc7df187da49bf5022")
BASE_URL = "https://api.pipedrive.com/api/v1" 

# Mapeamento de Custom Fields (Hashes)
FIELD_CNPJ = "a9d521460c01d5201c376d9db43db76ab7199fa0"
FIELD_PHONE = "76c9875a22fc0276dcbd5dcf15c152213876f201"
FIELD_EMAIL = "9d4b0a138ef286d5cce1f8fbd8de01823fd9d3a1"
FIELD_MENSALIDADE = "751bfa06b655238abc28d5b863f036ae8b0454ac"

# Mapeamento de Usuários (Nome no Login -> ID no Pipedrive)
# MANTIDO PARA COMPATIBILIDADE, MAS AGORA USAMOS BUSCA DINÂMICA
USER_MAP = {
    "Andrea Chesini": 24834130,
    "Cácia da Silva": 24145332,
    "Daniel Lázaro": 24909370,
    "Fabiane Serenado": 24807543,
    "Felipi Buettgen": 24535755,
    "João Lourenço": 23911956,
    "Michael Crestani": 24887392,
    "Paulo Franco": 23912033,
    "Raissa Denes": 23911978,
}

# Último erro ao carregar a base Sittax (Google Sheets).
# A UI pode usar isso para avisar o usuário sem derrubar a inicialização do app.
LAST_SITTAX_ERROR: str | None = None


def _norm_str(s: str) -> str:
    """Normaliza texto para buscas (remove acentos, lower, trim)."""
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s


def _build_df_from_sittax(df_sittax: pd.DataFrame, user_name: str) -> pd.DataFrame:
    """
    Fallback: cria um DataFrame compatível com a UI usando somente a planilha.

    Isso permite que o app abra e mostre dados mesmo se a API do Pipedrive não
    retornar negócios (ex.: permissões/token/visibilidade).
    """
    if df_sittax is None or df_sittax.empty:
        return pd.DataFrame(columns=PIPE_BASE_COLUMNS)

    title_series = df_sittax.get("Titulo_Sittax")
    if title_series is None:
        title_series = pd.Series([""] * len(df_sittax))

    etapa_series = df_sittax.get("Etapa_Sittax")
    if etapa_series is None:
        etapa_series = pd.Series(["-"] * len(df_sittax))

    estado_series = df_sittax.get("UF_Sittax")
    if estado_series is None:
        estado_series = df_sittax.get("Estado_Endereco_Sittax")
    if estado_series is None:
        estado_series = pd.Series(["-"] * len(df_sittax))

    df = pd.DataFrame()
    df["Key"] = df_sittax["Key"].astype(str)
    df["Nome"] = title_series.fillna("").astype(str)
    df["Organização - Nome"] = df["Nome"]
    df["Dono"] = user_name
    df["Negócio - Etapa"] = etapa_series.fillna("-").astype(str)
    df["Negócio - Mensalidade"] = df_sittax.get("Vlr_Sittax", 0.0)
    df["Status"] = df_sittax.get("Status_Sittax", "Não Integrado")
    df["Organização - E-mail"] = ""
    df["Organização - Telefone"] = ""
    df["Organização - Estado de Endereço"] = estado_series.fillna("-").astype(str)
    df["Dias_Sem_Ativ"] = 0
    df["Dias_Sem_Etapa"] = 0
    df["Tem_Atividade_Aberta"] = False
    df["id"] = None
    df["Usabilidade"] = df_sittax.get("Usabilidade_Sittax", "-")
    df["Ult_Acesso"] = df_sittax.get("Ult_Acesso_Sittax", "-")

    # Se não houver título, evita quebrar filtros (Nome vazio).
    df["Nome"] = df["Nome"].replace("", df["Key"])
    df["Organização - Nome"] = df["Organização - Nome"].replace("", df["Key"])
    return df

def search_users(term: str):
    """Busca usuários no Pipedrive pelo nome/email."""
    url = f"{BASE_URL}/users/find"
    params = {
        "term": term,
        "search_by_email": 0,
        "api_token": API_TOKEN
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json().get('data', [])
            if data:
                return [{"id": u["id"], "name": u["name"], "email": u["email"]} for u in data]
    except Exception as e:
        print(f"Erro ao buscar usuários: {e}")
    return []


async def list_users_async():
    """
    Lista usuários do Pipedrive (para preencher dropdown sem depender de busca).

    Observação: depende das permissões do token. Se a conta tiver muitos usuários,
    pode demorar alguns segundos.
    """
    sem = asyncio.Semaphore(10)
    users = await fetch_all_data_async("users", {}, sem)
    if not users:
        return []

    result = []
    for u in users:
        if not isinstance(u, dict):
            continue
        uid = u.get("id")
        name = u.get("name")
        email = u.get("email") or ""
        if uid and name:
            result.append({"id": uid, "name": name, "email": email})

    # Ordena por nome para UX melhor no dropdown.
    result.sort(key=lambda x: (x.get("name") or "").lower())
    return result

PIPE_BASE_COLUMNS = [
    "Key",
    "Nome",
    "Organização - Nome",
    "Dono",
    "Negócio - Etapa",
    "Negócio - Mensalidade",
    "Status",
    "Organização - E-mail",
    "Organização - Telefone",
    "Organização - Estado de Endereço",
    "Dias_Sem_Ativ",
    "Dias_Sem_Etapa",
    "Tem_Atividade_Aberta",
    "id"
]

CACHE_DIR = Path("storage/temp/pipedrive_cache")
CACHE_TTL_SECONDS = 5 * 60  # 5 minutos
STAGE_CACHE_TTL = 60 * 60  # 1 hora

CACHE_DIR.mkdir(parents=True, exist_ok=True)

_STAGE_CACHE = {"value": None, "ts": 0.0}


def _get_cache_path(owner_id: int) -> Path:
    return CACHE_DIR / f"user_{owner_id}.pkl"


def _load_cached_pipe(owner_id: int):
    cache_path = _get_cache_path(owner_id)
    if not cache_path.exists():
        return None

    age = time.time() - cache_path.stat().st_mtime
    if age > CACHE_TTL_SECONDS:
        return None

    try:
        print(f"Usando cache local para usuário {owner_id} (idade {int(age)}s)...")
        return pd.read_pickle(cache_path)
    except Exception as exc:
        print(f"Falha ao ler cache {cache_path}: {exc}")
        return None


def _save_cached_pipe(owner_id: int, df: pd.DataFrame) -> None:
    cache_path = _get_cache_path(owner_id)
    try:
        df.to_pickle(cache_path)
    except Exception as exc:
        print(f"Não foi possível salvar cache {cache_path}: {exc}")

# --- ASYNC ENGINE ---

async def fetch_page_async(session, endpoint, params, semaphore):
    """Busca uma única página de forma assíncrona."""
    url = f"{BASE_URL}/{endpoint}"
    
    # Garante que todos os parâmetros sejam strings (aiohttp pode ser chato com ints)
    str_params = {k: str(v) for k, v in params.items()}
    str_params['api_token'] = API_TOKEN
    
    async with semaphore:
        try:
            async with session.get(url, params=str_params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"Erro {response.status} em {endpoint}: {await response.text()}")
                    return None
        except Exception as e:
            print(f"Exception em {endpoint}: {e}")
            return None

async def fetch_all_data_async(endpoint, params, semaphore=None):
    """Busca todos os dados de um endpoint paginado (Async)."""
    if semaphore is None:
        semaphore = asyncio.Semaphore(20)

    all_data = []
    start = 0
    limit = 500
    params['limit'] = limit
    
    print(f"DEBUG: Iniciando {endpoint} (Async)...")

    async with aiohttp.ClientSession() as session:
        while True:
            params['start'] = start
            data_json = await fetch_page_async(session, endpoint, params, semaphore)
            
            if not data_json:
                break

            items = data_json.get('data')
            if items:
                all_data.extend(items)
                # print(f"DEBUG: {endpoint} page fetched. Items: {len(items)}")
            
            pagination = data_json.get('additional_data', {}).get('pagination', {})
            if not pagination.get('more_items_in_collection'):
                break
            
            start = pagination.get('next_start', start + limit)
    
    print(f"DEBUG: {endpoint} finalizado. Total: {len(all_data)}")
    return all_data

async def get_stages_map_async(force_refresh: bool = False):
    """Mapeia ID da etapa -> Nome da etapa com cache em memória (Async)."""
    now_ts = time.time()
    cached_value = _STAGE_CACHE.get("value")
    cache_age = now_ts - _STAGE_CACHE.get("ts", 0.0)
    if not force_refresh and cached_value and cache_age < STAGE_CACHE_TTL:
        return cached_value

    print("Mapeando Etapas (Async)...")
    # Cria semáforo local para esta operação isolada
    sem = asyncio.Semaphore(20)
    stages = await fetch_all_data_async("stages", {}, sem)
    stage_map = {s['id']: s['name'] for s in stages}
    _STAGE_CACHE["value"] = stage_map
    _STAGE_CACHE["ts"] = now_ts
    return stage_map

def extract_smart_field(item, standard_key, custom_hash):
    """Extrai dados de forma robusta (suporta v1 flat e v2 nested/custom_fields)."""
    # 1. Tenta pelo campo padrão
    val_std = item.get(standard_key)
    if isinstance(val_std, list) and len(val_std) > 0:
        return val_std[0].get('value', '')
    if isinstance(val_std, str) and val_std.strip():
        return val_std

    # 2. Tenta pelo Hash (Custom Field)
    custom_fields_dict = item.get('custom_fields')
    val_custom = None
    if isinstance(custom_fields_dict, dict):
        val_custom = custom_fields_dict.get(custom_hash)
    else:
        val_custom = item.get(custom_hash)
    
    if val_custom:
        return str(val_custom)
    return ""

async def fetch_with_retry(session, url, params, semaphore, retries=8, backoff_factor=1.8):
    """Executa requisição GET com retry exponencial para Rate Limits (429)."""
    delay = 1.0
    for i in range(retries):
        async with semaphore:
            try:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:
                        print(f"Rate Limit (429) em {url}. Tentativa {i+1}/{retries}. Aguardando {delay:.1f}s...")
                    else:
                        print(f"Erro {response.status} em {url}: {await response.text()}")
                        return None
            except Exception as e:
                print(f"Exception em {url}: {e}")
                return None
        
        # Se chegou aqui, foi 429 ou erro. Aguarda fora do semáforo para liberar slot.
        await asyncio.sleep(delay)
        delay *= backoff_factor
    
    print(f"Falha após {retries} tentativas em {url}")
    return None

async def get_org_details_async(session, org_id, semaphore):
    """Busca detalhes de uma organização (Async)."""
    if not org_id: return None
    url = f"{BASE_URL}/organizations/{org_id}"
    params = {'api_token': API_TOKEN}
    
    data = await fetch_with_retry(session, url, params, semaphore)
    if data:
        return data.get('data')
    return None

async def get_organizations_map_async(org_ids, semaphore):
    """Busca detalhes de múltiplas organizações em paralelo."""
    unique_ids = list(set([oid for oid in org_ids if oid]))
    print(f"Baixando detalhes de {len(unique_ids)} Organizações (Async)...")
    
    org_map = {}
    async with aiohttp.ClientSession() as session:
        tasks = [get_org_details_async(session, oid, semaphore) for oid in unique_ids]
        results = await asyncio.gather(*tasks)
        
        for org in results:
            if org:
                org_id = org.get('id')
                # Endereço
                addr_obj = org.get('address')
                estado = '-'
                if isinstance(addr_obj, dict):
                    estado = addr_obj.get('admin_area_level_1') or '-'
                elif isinstance(org.get('address_admin_area_level_1'), str):
                     estado = org.get('address_admin_area_level_1')

                # Extração Inteligente
                phone = extract_smart_field(org, 'phone', FIELD_PHONE)
                email = extract_smart_field(org, 'email', FIELD_EMAIL)
                cnpj = extract_smart_field(org, 'dummy_cnpj', FIELD_CNPJ)

                org_map[org_id] = {
                    "name": org.get('name', 'Sem Nome'),
                    "cnpj": cnpj,
                    "phone": phone,
                    "email": email,
                    "estado": estado
                }
    print(f"Mapeamento de Organizações concluído. Total: {len(org_map)}")
    return org_map

async def get_pipedrive_data_optimized(owner_id, stage_map):
    """Versão Async Otimizada do Pipeline de Dados."""
    print("Iniciando download paralelo (Async) de Atividades e Negócios...")
    
    semaphore = asyncio.Semaphore(5) # Reduzido drasticamente para evitar 429

    # 1. Busca Deals e Activities em paralelo
    #
    # Observação: dependendo das permissões/visibilidade do token, o filtro por `user_id`
    # pode retornar 0 negócios mesmo quando existem dados. Aplicamos fallbacks
    # conservadores antes de concluir que a carteira está vazia.
    task_deals = fetch_all_data_async("deals", {"user_id": owner_id, "status": "open"}, semaphore)
    task_activities = fetch_all_data_async("activities", {"user_id": owner_id, "done": 0}, semaphore)

    deals, activities = await asyncio.gather(task_deals, task_activities)
    
    # 2. Processa IDs
    deals_with_open_activity = set(a['deal_id'] for a in activities if a.get('deal_id'))
    
    org_ids = []
    for deal in deals:
        org_data_raw = deal.get('org_id')
        if org_data_raw:
            oid = org_data_raw.get('value') if isinstance(org_data_raw, dict) else org_data_raw
            org_ids.append(oid)
            
    # 3. Busca Organizações em paralelo
    org_map = await get_organizations_map_async(org_ids, semaphore)
    
    processed_data = []
    print(f"Processando {len(deals)} negócios...")

    for deal in deals:
        deal_id = deal.get('id')
        stage_id = deal.get('stage_id')
        stage_name = stage_map.get(stage_id, f"Etapa {stage_id}")

        # Link com Organização
        org_data_raw = deal.get('org_id') 
        org_id = org_data_raw.get('value') if isinstance(org_data_raw, dict) else org_data_raw
        
        # Garante que org_id seja int se possível, para bater com o mapa
        try:
            if org_id is not None:
                org_id = int(org_id)
        except:
            pass

        org_details = org_map.get(org_id, {"name": "", "cnpj": "", "phone": "", "email": "", "estado": "-"})
        
        # Valor (Mensalidade via Custom Field)
        raw_val = deal.get(FIELD_MENSALIDADE)
        if raw_val is None and isinstance(deal.get('custom_fields'), dict):
             raw_val = deal['custom_fields'].get(FIELD_MENSALIDADE)
        
        try:
            val_float = float(raw_val) if raw_val is not None else 0.0
        except (ValueError, TypeError):
            val_float = 0.0

        # --- LÓGICA DE DATAS (PRESERVADA) ---
        now = datetime.now()
        update_time = deal.get('update_time')
        stage_change_time = deal.get('stage_change_time')
        add_time = deal.get('add_time')
        
        dias_etapa = 0
        # Se não tiver stage_change_time (nunca mudou), usa a data de criação (add_time)
        ref_date_str = stage_change_time if stage_change_time else add_time
        
        if ref_date_str:
            try:
                dt_etapa = datetime.strptime(ref_date_str, "%Y-%m-%d %H:%M:%S")
                dias_etapa = (now - dt_etapa).days
            except: pass

        dias_sem_ativ = 0
        last_act_date = deal.get('last_activity_date')
        if last_act_date:
            try:
                dt_ativ = datetime.strptime(last_act_date, "%Y-%m-%d")
                dias_sem_ativ = (now - dt_ativ).days
            except: pass
        elif update_time:
            try:
                dt_upd = datetime.strptime(update_time, "%Y-%m-%d %H:%M:%S")
                dias_sem_ativ = (now - dt_upd).days
            except: pass
        # ------------------------------------

        processed_data.append({
            "Key": clean_cnpj(org_details['cnpj']),
            "Nome": deal.get('title'),
            "Organização - Nome": org_details.get('name', ''),
            "Dono": deal.get('owner_name', 'Desconhecido'),
            "Negócio - Etapa": stage_name,
            "Negócio - Mensalidade": val_float,
            "Status": "Open",
            "Organização - E-mail": org_details['email'],
            "Organização - Telefone": org_details['phone'],
            "Organização - Estado de Endereço": org_details['estado'],
            "Dias_Sem_Ativ": dias_sem_ativ,
            "Dias_Sem_Etapa": dias_etapa,
            "Data_Mudanca_Etapa": stage_change_time, # Nova coluna para gráficos
            "Tem_Atividade_Aberta": deal_id in deals_with_open_activity,
            "id": deal_id
        })

    return pd.DataFrame(processed_data)

def load_sittax():
    """Carrega apenas o Google Sheets (Base estática)"""
    global LAST_SITTAX_ERROR
    # Fonte da base Sittax (Google Sheets -> export CSV).
    # Você pode trocar sem editar o código via variáveis de ambiente:
    #   $env:SITTAX_SHEET_ID="..."
    #   $env:SITTAX_GID="0"
    #
    # Link informado pelo usuário (edit):
    # https://docs.google.com/spreadsheets/d/1aEs_lFrTHuKW_rRx9ZNvfM-1m9mm74-Z5dWlbWpIqo0/edit?usp=sharing
    sheet_id = os.getenv("SITTAX_SHEET_ID", "1aEs_lFrTHuKW_rRx9ZNvfM-1m9mm74-Z5dWlbWpIqo0")
    # Observação: se você não souber o gid, geralmente a primeira aba é gid=0.
    gid_sittax = os.getenv("SITTAX_GID", "0")
    url_sittax = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_sittax}"

    # Reseta o erro anterior para a UI poder refletir o estado atual.
    LAST_SITTAX_ERROR = None

    print("Carregando Sittax (Base)...")
    try:
        # Baixa manualmente para:
        # - aplicar timeout e não travar o app na inicialização
        # - detectar HTTP 410 (endpoint removido) e não quebrar a UI
        # Importante: algumas máquinas têm proxy configurado no Windows/ENV.
        # Para evitar falha "Unable to connect to proxy 127.0.0.1:9", desabilitamos
        # o uso de variáveis de ambiente do requests para esta chamada.
        sess = requests.Session()
        sess.trust_env = False
        r = sess.get(url_sittax, timeout=15)
        if r.status_code == 410:
            # Mantém a aplicação funcionando mesmo sem a base Sittax.
            # A UI pode ler `service.LAST_SITTAX_ERROR` para avisar o usuário.
            LAST_SITTAX_ERROR = (
                "Base Sittax indisponível (HTTP 410: Gone). "
                "A planilha/endpoint pode ter sido removida, movida ou alterada."
            )
            print(f"Erro Sittax: {LAST_SITTAX_ERROR}")
            return pd.DataFrame()
        r.raise_for_status()
        # Google Sheets export retorna CSV em UTF-8. Forçamos decode para evitar
        # "TÃ­tulo" / caracteres quebrados quando o requests auto-detecta encoding errado.
        csv_text = r.content.decode("utf-8", errors="replace")
        df_sittax = pd.read_csv(io.StringIO(csv_text), dtype=str)
    except Exception as e:
        LAST_SITTAX_ERROR = str(e)
        print(f"Erro Sittax: {e}")
        return pd.DataFrame()

    # Se a planilha vier só com cabeçalho (0 linhas), avisamos mas não quebramos o app.
    if df_sittax.empty and len(df_sittax.columns) > 0:
        LAST_SITTAX_ERROR = (
            "Planilha Sittax carregada, mas sem linhas de dados (apenas cabeçalho). "
            "Verifique se você está na aba correta (gid) e se há registros preenchidos."
        )
        print(f"Aviso Sittax: {LAST_SITTAX_ERROR}")
        return df_sittax

    if not df_sittax.empty:
        df_sittax.columns = df_sittax.columns.str.strip()
        cols_norm = {c: _norm_str(c) for c in df_sittax.columns}

        # A planilha pode usar cabeçalhos como:
        # Título | CPF/CNPJ | Vlr. Mensalidade | Estado de endereço | Etapa | Status
        col_cnpj = next(
            (c for c, n in cols_norm.items() if "cpf/cnpj" in n or n == "cpf" or "cnpj" in n),
            "CPF/CNPJ",
        )
        if col_cnpj in df_sittax.columns:
            df_sittax["Key"] = df_sittax[col_cnpj].apply(clean_cnpj)
        else:
            df_sittax["Key"] = ""

        col_titulo = next((c for c, n in cols_norm.items() if "titulo" in n), None)
        df_sittax["Titulo_Sittax"] = df_sittax[col_titulo].fillna("").astype(str) if col_titulo else ""

        # Se a planilha estiver sem CPF/CNPJ preenchido (coluna vazia),
        # ainda assim mantemos as linhas para o app conseguir exibir os registros.
        #
        # 2ª alternativa (pedido): usar o Título como chave quando CPF/CNPJ estiver vazio.
        # Observação: isso não garante merge confiável com Pipedrive (que depende do documento),
        # mas permite listar e filtrar os registros vindos da planilha.
        missing_key_mask = df_sittax["Key"].astype(str).str.strip().eq("")
        if missing_key_mask.any():
            fallback_keys: list[str] = []
            for idx in df_sittax.index[missing_key_mask].to_list():
                titulo = str(df_sittax.at[idx, "Titulo_Sittax"] or "").strip()
                if titulo:
                    base = _norm_str(titulo)
                    # Prefixo para evitar confusão com CPF/CNPJ e diminuir colisões.
                    fallback_keys.append(f"TITLE_{base}_{idx + 1}")
                else:
                    fallback_keys.append(f"ROW_{idx + 1}")

            df_sittax.loc[missing_key_mask, "Key"] = fallback_keys

        col_etapa = next((c for c, n in cols_norm.items() if n == "etapa" or "etapa" in n), None)
        df_sittax["Etapa_Sittax"] = df_sittax[col_etapa].fillna("-").astype(str) if col_etapa else "-"

        col_vlr = next((c for c, n in cols_norm.items() if "mensal" in n and ("vlr" in n or "valor" in n)), "Vlr. Mensalidade")
        if col_vlr in df_sittax.columns:
            df_sittax["Vlr_Sittax"] = df_sittax[col_vlr].apply(clean_curr)
        else:
            df_sittax["Vlr_Sittax"] = 0.0

        col_status = next((c for c, n in cols_norm.items() if "status" in n), None)
        df_sittax["Status_Sittax"] = df_sittax[col_status] if col_status else "Desconhecido"

        col_usa = next((c for c, n in cols_norm.items() if "usabilidade" in n or ("media" in n and "%" in n)), None)
        df_sittax["Usabilidade_Sittax"] = df_sittax[col_usa] if col_usa else "-"

        # UF/Estado: aceita coluna "UF" ou algo como "Estado de endereço"
        col_uf = next((c for c, n in cols_norm.items() if n == "uf"), None)
        col_estado = next((c for c, n in cols_norm.items() if "estado" in n and ("endere" in n or "endereco" in n or n == "estado")), None)
        if col_uf:
            df_sittax["UF_Sittax"] = df_sittax[col_uf].fillna("-").astype(str)
            df_sittax["Estado_Endereco_Sittax"] = df_sittax["UF_Sittax"]
        elif col_estado:
            df_sittax["UF_Sittax"] = df_sittax[col_estado].fillna("-").astype(str)
            df_sittax["Estado_Endereco_Sittax"] = df_sittax["UF_Sittax"]
        else:
            df_sittax["UF_Sittax"] = "-"
            df_sittax["Estado_Endereco_Sittax"] = "-"

        col_acesso = next((c for c, n in cols_norm.items() if "acesso" in n and ("ult" in n or "ultimo" in n)), None)
        df_sittax["Ult_Acesso_Sittax"] = df_sittax[col_acesso] if col_acesso else "-"

        cols_to_keep = [
            "Key",
            "Titulo_Sittax",
            "Etapa_Sittax",
            "Status_Sittax",
            "Vlr_Sittax",
            "Usabilidade_Sittax",
            "UF_Sittax",
            "Estado_Endereco_Sittax",
            "Ult_Acesso_Sittax",
        ]
        cols = [c for c in cols_to_keep if c in df_sittax.columns]
        df_sittax = df_sittax[cols]
    
    return df_sittax

def load_user_data(user_name, df_sittax, user_id=None, force_refresh: bool = False):
    """
    Wrapper síncrono.

    Importante (Flet 0.84+): dentro de handlers do Flet já existe um event loop em execução.
    Nesse cenário, `load_user_data()` não pode usar `run_until_complete()` (gera
    "This event loop is already running").

    - Dentro do app: use `await load_user_data_async(...)`
    - Fora do app: pode chamar `load_user_data(...)`
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(load_user_data_async(user_name, df_sittax, user_id=user_id, force_refresh=force_refresh))

    raise RuntimeError("Use `await load_user_data_async(...)` dentro do app Flet.")


async def load_user_data_async(user_name, df_sittax, user_id=None, force_refresh: bool = False):
    """Carrega Pipedrive do usuário selecionado, com cache local e cruzamento Sittax (async, compatível com Flet)."""
    if user_id is None:
        user_id = USER_MAP.get(user_name)

    if not user_id:
        return None

    df_pipe = None if force_refresh else _load_cached_pipe(user_id)
    if df_pipe is None:
        print(f"Iniciando carga Pipedrive para {user_name}...")
        stage_map = await get_stages_map_async()
        df_pipe = await get_pipedrive_data_optimized(user_id, stage_map)

        if df_pipe.empty:
            df_pipe = pd.DataFrame(columns=PIPE_BASE_COLUMNS)
        df_pipe = df_pipe.copy()
        df_pipe["Dono"] = user_name
        _save_cached_pipe(user_id, df_pipe)
    else:
        df_pipe = df_pipe.copy()
        df_pipe["Dono"] = user_name

    # --- MERGE ---
    if "Key" not in df_pipe.columns:
        df_pipe["Key"] = ""
    df_pipe["Key"] = df_pipe["Key"].astype(str)

    # Fallback: se a API não retornar negócios (vazio) mas a planilha tiver dados,
    # usamos a planilha como fonte para não travar o usuário na tela de login.
    if df_pipe.empty and df_sittax is not None and not df_sittax.empty:
        df_final = _build_df_from_sittax(df_sittax, user_name=user_name)
        etapas = []
        if "Negócio - Etapa" in df_final.columns:
            etapas = sorted(x for x in df_final["Negócio - Etapa"].dropna().unique())
        return {"df": df_final, "colaboradores": list(USER_MAP.keys()), "etapas": etapas}

    if not df_sittax.empty:
        df_sittax["Key"] = df_sittax["Key"].astype(str)
        df_final = pd.merge(df_pipe, df_sittax, on="Key", how="left")
    else:
        df_final = df_pipe.copy()

    # Consolidação
    default_len = len(df_final)
    df_final["Status"] = df_final.get("Status_Sittax", pd.Series(["Não Integrado"] * default_len)).fillna("Não Integrado")
    df_final["Usabilidade"] = df_final.get("Usabilidade_Sittax", pd.Series(["-"] * default_len)).fillna("-")
    df_final["UF"] = df_final.get("UF_Sittax", pd.Series(["-"] * default_len)).fillna(
        df_final.get("Organização - Estado de Endereço", "-")
    )
    df_final["Ult_Acesso"] = df_final.get("Ult_Acesso_Sittax", pd.Series(["-"] * default_len)).fillna("-")
    df_final["Vlr_Sittax"] = df_final.get("Vlr_Sittax", pd.Series([0.0] * default_len)).fillna(0.0)

    etapas = []
    if "Negócio - Etapa" in df_final.columns:
        etapas = sorted(x for x in df_final["Negócio - Etapa"].dropna().unique())

    return {"df": df_final, "colaboradores": list(USER_MAP.keys()), "etapas": etapas}

def get_deal_activities(deal_id, owner_id=None):
    """Busca atividades pendentes de um negócio específico (API v1)"""
    try:
        # Endpoint CORRETO para atividades de um deal específico
        url = f"https://api.pipedrive.com/api/v1/deals/{deal_id}/activities"
        params = {
            "api_token": API_TOKEN,
            "done": 0, # 0 = não feito
            "exclude": "", # Garante que não exclua nada por padrão
            "limit": 50
        }
        
        # Timeout curto para não travar a UI
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json().get('data', [])
            if data is None: return [] # API pode retornar None se vazio
            
            # Se owner_id for fornecido, filtra localmente os resultados
            if owner_id:
                # user_id no retorno da API geralmente é int
                data = [a for a in data if str(a.get('user_id')) == str(owner_id)]

            return [{
                "subject": a.get("subject", "Sem título"),
                "due_date": a.get("due_date", "-"),
                "type": a.get("type", "call"),
                "note": a.get("note", "")
            } for a in data]
    except Exception as e:
        print(f"Erro ao buscar atividades do deal {deal_id}: {e}")
    return []
