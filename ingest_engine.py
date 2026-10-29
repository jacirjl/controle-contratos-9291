# -*- coding: utf-8 -*-
"""
MOTOR DE INGESTÃO INCREMENTAL (DELTA APPEND-ONLY) + BANCO HÍBRIDO (EVENT STORE CRONOLÓGICO & VECTOR DB)
Contrato Administrativo nº 9291/2025 — SEIA/PR × CELEPAR
Protocolos Monitorados:
  - Processo Mãe / Financeiro (NAS/NFS/SIAFIC): 24.574.062-0 (Processo_24.574.062-0_1.pdf)
  - Processo de Cobrança Mensal / RMEC / Atesto SEIA: 25.609.621-8 (Processo_25.609.621-8_1.pdf)
  - 27 Processos de Ordens de Serviço: Ordens_De_Serviço/OS_01 a OS_27

Arquitetura de Economia de Tokens (Delta Page Watermarking):
  Como os PDFs do e-Protocolo PR são estritamente APPEND-ONLY (novos despachos, RMECs, NFs e NLs/OBs
  são sempre inseridos nas páginas finais N+1..M sem alterar as páginas anteriores 1..N), este motor
  grava na tabela `document_watermarks` o número da última página processada (`last_ingested_page`)
  e o hash criptográfico SHA-256 da página 1 e da página N (`last_page_sha256`).
  Quando o usuário baixa uma nova versão de qualquer PDF:
    1. O motor verifica se `sha256(page[last_ingested_page]) == last_page_sha256`.
    2. Se `total_pages == last_ingested_page`, 0 páginas são reprocessadas (100% de economia de tokens).
    3. Se `total_pages > last_ingested_page`, APENAS o intervalo novo `[last_ingested_page + 1 .. total_pages]`
       é extraído, vetorizado, analisado e anexado ao Event Store Cronológico e ao Vector DB!
"""

import os
import re
import json
import math
import sqlite3
import hashlib
from datetime import datetime
import fitz  # PyMuPDF

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(ROOT_DIR, "db")
DB_PATH = os.path.join(DB_DIR, "contrato_9291.sqlite")

EMBEDDING_DIM = 128

# Vocabulário de domínio para ponderação semântica + n-gram hashing determinístico (Zero API Key externa)
DOMAIN_KEYWORDS = {
    "rmec": 3.5, "fechamento": 3.2, "atesto": 3.5, "atestado": 3.2, "prestação": 2.5,
    "nota fiscal": 3.5, "nfs-e": 3.5, "liquidacao": 3.2, "liquidação": 3.2, "2026nl": 3.8,
    "2026ob": 3.8, "2026pd": 3.5, "2026ne": 3.5, "empenho": 3.0, "nas": 3.2, "nfs": 3.2,
    "gms": 3.0, "siga": 3.2, "usn": 3.0, "ust": 3.0, "glosa": 4.0, "devolução": 3.8,
    "retificação": 3.8, "duplicidade": 4.0, "lgpd": 4.0, "iowa": 4.0, "us-central1": 4.0,
    "capricorn": 4.0, "rastreabilidade": 3.8, "desmembramento": 3.8, "data foundation": 3.5,
    "plano de trabalho": 3.2, "sow": 3.0, "dimensionamento": 3.5, "ordem de serviço": 3.2,
    "jaca": 3.2, "sustentável": 3.0, "sistransito": 3.2, "sistrânsito": 3.2, "pmpr": 3.0,
    "gemini": 3.2, "migra": 3.0, "redação": 3.0, "fluência": 3.0, "lia": 3.0, "datapge": 3.2,
    "datacontabil": 3.2, "prisma": 3.2, "defesa civil": 3.0, "dpe": 3.0, "iat": 3.0,
    "recaptcha": 3.2, "moodle": 3.2, "tessera": 3.2, "adapar": 3.2, "bloqueio": 3.8,
    "produção": 2.8, "homologação": 2.8, "despacho": 2.5, "ofício": 2.5
}


def compute_text_sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


def compute_embedding(text: str) -> list:
    """
    Gera um vetor denso normalizado L2 de 128 dimensões combinando Feature Hashing de
    palavras/n-gramas e pesos semânticos do domínio FinOps/Contratos Públicos.
    Permite busca por similaridade de cosseno instantânea (<10ms) sem custo de API.
    """
    vec = [0.0] * EMBEDDING_DIM
    if not text:
        return vec
    lower = text.lower()
    tokens = re.findall(r"[a-záàâãéêíóôõúç0-9_.-]{2,}", lower)
    if not tokens:
        return vec

    # Pesos de domínio explícitos
    for kw, weight in DOMAIN_KEYWORDS.items():
        if kw in lower:
            h = int(hashlib.md5(kw.encode("utf-8")).hexdigest()[:8], 16)
            idx = h % EMBEDDING_DIM
            sign = 1.0 if (h // EMBEDDING_DIM) % 2 == 0 else -1.0
            vec[idx] += sign * weight * 2.5

    # Unigramas e Bigramas com Feature Hashing (Weinberger et al.)
    for i, tok in enumerate(tokens[:600]):
        w = DOMAIN_KEYWORDS.get(tok, 1.0)
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest()[:8], 16)
        idx = h % EMBEDDING_DIM
        sign = 1.0 if (h // EMBEDDING_DIM) % 2 == 0 else -1.0
        vec[idx] += sign * w

        if i + 1 < len(tokens):
            bg = tok + "_" + tokens[i + 1]
            hb = int(hashlib.md5(bg.encode("utf-8")).hexdigest()[:8], 16)
            vec[hb % EMBEDDING_DIM] += (1.0 if (hb // EMBEDDING_DIM) % 2 == 0 else -1.0) * 0.75

    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 1e-9:
        vec = [round(x / norm, 5) for x in vec]
    return vec


def cosine_similarity(v1: list, v2: list) -> float:
    return sum(a * b for a, b in zip(v1, v2))


def br_to_iso_date(date_str: str) -> str:
    """Converte 'DD/MM/YYYY HH:MM' ou 'DD/MM/YYYY' para 'YYYY-MM-DD HH:MM'."""
    if not date_str:
        return "2026-01-01 00:00"
    clean = " ".join(date_str.strip().split())
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})(?:\s+(\d{2}:\d{2}))?", clean)
    if m:
        d, mo, y, hm = m.group(1), m.group(2), m.group(3), m.group(4) or "00:00"
        return f"{y}-{mo}-{d} {hm}"
    return clean


def init_db(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")

    # 1. Tabela de Watermarks para Ingestão Incremental (Delta Append-Only)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS document_watermarks (
        doc_id TEXT PRIMARY KEY,
        protocolo TEXT,
        os_id TEXT,
        rel_path TEXT,
        file_size INTEGER,
        total_pages INTEGER,
        last_ingested_page INTEGER,
        first_page_sha256 TEXT,
        last_page_sha256 TEXT,
        tokens_cached INTEGER,
        last_sync_at TEXT,
        status_integrity TEXT
    );
    """)

    # 2. Tabela de Eventos Cronológicos (Event Sourcing das 10 Etapas do instruções.md)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS chronological_events (
        event_id TEXT PRIMARY KEY,
        date_iso TEXT,
        date_br TEXT,
        protocolo TEXT,
        os_id TEXT,
        competencia TEXT,
        step_number INTEGER,
        step_code TEXT,
        actor_from TEXT,
        actor_to TEXT,
        doc_type TEXT,
        title TEXT,
        detail TEXT,
        usn REAL,
        ust REAL,
        valor_brl REAL,
        page_num INTEGER,
        pdf_link TEXT
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chrono_date ON chronological_events(date_iso ASC, page_num ASC);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chrono_os ON chronological_events(os_id, date_iso ASC);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chrono_step ON chronological_events(step_number, date_iso ASC);")

    # 3. Tabela de Execução Mensal RMEC × Fechamento × Atesto × NF × Liquidação (25.609.621-8 ↔ 24.574.062-0)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS rmec_monthly_os (
        id TEXT PRIMARY KEY,
        competencia TEXT,
        competencia_ordem INTEGER,
        os_id TEXT,
        usn REAL,
        valor_usn REAL,
        ust REAL,
        valor_ust REAL,
        valor_total REAL,
        rmec_page INTEGER,
        fechamento_page INTEGER,
        atesto_page INTEGER,
        atesto_data TEXT,
        nf_usn TEXT,
        nf_ust TEXT,
        nl_numeros TEXT,
        ob_numeros TEXT,
        proc_mae_page INTEGER,
        status_ciclo TEXT,
        observacao TEXT
    );
    """)

    # 4. Tabela do Banco de Dados Vetorial com Resultado de IA Cacheado por Página/Bloco
    cur.execute("""
    CREATE TABLE IF NOT EXISTS vector_chunks (
        chunk_id TEXT PRIMARY KEY,
        doc_id TEXT,
        protocolo TEXT,
        os_id TEXT,
        competencia TEXT,
        doc_type TEXT,
        page_num INTEGER,
        page_sha256 TEXT,
        pdf_link TEXT,
        snippet TEXT,
        ai_summary TEXT,
        embedding_json TEXT,
        ingested_at TEXT
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_vec_doc_page ON vector_chunks(doc_id, page_num);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_vec_os ON vector_chunks(os_id);")

    conn.commit()


def classify_page_ai_summary(doc_id: str, protocolo: str, os_id: str, page_num: int, text: str) -> tuple:
    """
    Gera a síntese estruturada (AI Extraction Cache) e classifica o tipo documental da página
    durante a ingestão, para que buscas futuras não precisem acionar LLM novamente.
    """
    clean = " ".join(text.split())
    up = clean.upper()

    doc_type = "AUTOS_GERAL"
    competencia = ""
    summary_parts = []

    # Detectar competência se houver
    for m_nome in ["FEVEREIRO/2026", "MARÇO/2026", "ABRIL/2026", "MAIO/2026", "JUNHO/2026", "JULHO/2026", "AGOSTO/2026", "SETEMBRO/2026", "OUTUBRO/2026"]:
        if m_nome in up:
            competencia = m_nome.title()
            break

    if "RELATÓRIO DE FECHAMENTO MENSAL" in up:
        doc_type = "FECHAMENTO_MENSAL"
        summary_parts.append(f"[Etapa 6 - Fechamento Mensal {competencia}] Consolidação financeira de USNs e USTs por Ordem de Serviço no protocolo {protocolo} (fl. {page_num}).")
    elif "RELATÓRIO MENSAL DE EXECUÇÃO CONTRATUAL" in up or "(RMEC)" in up:
        doc_type = "RMEC_OS"
        m_os = re.search(r"OS-2026-9291-0(\d{2})", up)
        os_ref = f"OS_{m_os.group(1)}" if m_os else (os_id or "OS")
        summary_parts.append(f"[Etapa 6 - RMEC {os_ref} {competencia}] Medição detalhada de consumo Google Cloud (USN) e serviços técnicos (UST) na fl. {page_num}.")
    elif "ATESTADO DE PRESTAÇÃO DE SERVIÇO" in up or ("AUTORIZO A EMISSÃO" in up and "NOTA FISCAL" in up) or ("APROVAÇÃO DOS RELATÓRIOS" in up):
        doc_type = "ATESTO_SEIA"
        summary_parts.append(f"[Etapa 6/7 - Atesto Técnico SEIA {competencia}] Fiscalização e Gestão do Contrato atestam os relatórios mensais no protocolo {protocolo} (fl. {page_num}).")
    elif "DEVOLUÇÃO DOS RELATÓRIOS" in up or "RETIFICAÇÃO" in up or "INCONSISTÊNCIAS IDENTIFICADAS" in up:
        doc_type = "GLOSA_DEVOLUCAO_SEIA"
        summary_parts.append(f"[Etapa 6 - Glosa / Devolução p/ Retificação] Fiscalização SEIA devolve relatórios de {competencia or 'Março/2026'} por inconsistências aritméticas e duplicidades (fl. {page_num}).")
    elif "RESTRIÇÃO GEOGRÁFICA" in up or "LGPD" in up or "CAPRICORN" in up:
        doc_type = "DETERMINACAO_FISCALIZACAO"
        summary_parts.append(f"[Etapa 6 - Determinação Fiscalização LGPD/FinOps] SEIA determina realocação geográfica de dados para o Brasil (LGPD), rastreabilidade na OS-005 e exclusão do projeto Capricorn (fl. {page_num}).")
    elif "DIMENSIONAMENTO INICIAL (USN/UST)" in up:
        doc_type = "DIMENSIONAMENTO_INICIAL"
        summary_parts.append(f"[Etapa 3 - Dimensionamento Inicial Celepar] Levantamento oficial de custos em USN (R$ 1,76) e UST (R$ 309,85) para {os_id or protocolo} (fl. {page_num}).")
    elif "ORDEM DE SERVIÇO N" in up or "ORDEM_SERVICO.PDF" in up:
        doc_type = "ORDEM_DE_SERVICO"
        summary_parts.append(f"[Etapa 4 - Emissão de Ordem de Serviço] Autorização formal assinada pela SEIA para execução no protocolo {protocolo} ({os_id}, fl. {page_num}).")
    elif "PLANO DE TRABALHO" in up or "STATEMENT OF WORK" in up or "STATEMENTOFWORK" in up:
        doc_type = "PLANO_DE_TRABALHO"
        summary_parts.append(f"[Etapa 1 - Plano de Trabalho / SOW] Especificação técnica de escopo, arquitetura e cronograma de entregas ({os_id or protocolo}, fl. {page_num}).")
    elif "NOTA DE LIQUIDAÇÃO" in up or "2026NL000" in up:
        doc_type = "LIQUIDACAO_SIAFIC"
        summary_parts.append(f"[Etapa 8/9 - Liquidação da Despesa NL] Registro contábil de liquidação no SIAFIC pelo NFS/SEIA no protocolo {protocolo} (fl. {page_num}).")
    elif "ORDEM BANCÁRIA" in up or "2026OB000" in up or "RELAÇÃO DE ORDENS BANCÁRIAS" in up:
        doc_type = "PAGAMENTO_OB"
        summary_parts.append(f"[Etapa 9 - Pagamento Ordem Bancária OB] Comprovante de pagamento bancário efetivado pelo NFS no SIAFIC (fl. {page_num}).")
    elif "NOTA FISCAL" in up or "NFS-E" in up or "DANFSE" in up:
        doc_type = "NOTA_FISCAL"
        summary_parts.append(f"[Etapa 7 - Nota Fiscal CELEPAR] Juntada de documento fiscal para cobrança mensal no protocolo {protocolo} (fl. {page_num}).")
    elif "ENCAMINHE-SE À CELEPAR" in up or "ENCAMINHA-SE O PRESENTE PROTOCOLO À CELEPAR" in up:
        doc_type = "DESPACHO_SOLICITACAO_CUSTOS"
        summary_parts.append(f"[Etapa 2 - Encaminhamento SEIA → CELEPAR] Solicitação de levantamento de custos e dimensionamento USN/UST ({os_id}, fl. {page_num}).")
    else:
        summary_parts.append(f"Documento administrativo integrante do protocolo {protocolo} ({os_id or 'Geral'}, fl. {page_num}).")

    # Extrair valores R$ relevantes na página
    vals = re.findall(r"R\$\s*[\d\.,]+", clean)
    if vals:
        summary_parts.append("Valores identificados: " + ", ".join(vals[:5]))

    return doc_type, competencia, " | ".join(summary_parts)


def get_monitored_documents() -> list:
    """Lista todos os 29 PDFs de processos e contratos monitorados na pasta Contratos."""
    docs = [
        {
            "doc_id": "PROC_MAE_24574062",
            "protocolo": "24.574.062-0",
            "os_id": "CONTRATO_GERAL",
            "rel_path": "Processo_24.574.062-0_1.pdf",
            "abs_path": os.path.join(ROOT_DIR, "Processo_24.574.062-0_1.pdf")
        },
        {
            "doc_id": "PROC_RMEC_25609621",
            "protocolo": "25.609.621-8",
            "os_id": "COBRANCA_RMEC",
            "rel_path": "Processo_25.609.621-8_1.pdf",
            "abs_path": os.path.join(ROOT_DIR, "Processo_25.609.621-8_1.pdf")
        }
    ]

    os_base = os.path.join(ROOT_DIR, "Ordens_De_Serviço")
    if os.path.isdir(os_base):
        for i in range(1, 28):
            os_id = f"OS_{i:02d}"
            folder = os.path.join(os_base, os_id)
            if not os.path.isdir(folder):
                continue
            files = sorted(os.listdir(folder))
            proc_files = [f for f in files if f.startswith("Processo_") and f.endswith(".pdf")]
            if proc_files:
                pf = proc_files[0]
                m_prot = re.search(r"Processo_([\d\.\-]+?)(?:_1)?\.pdf", pf)
                prot = m_prot.group(1) if m_prot else pf
                docs.append({
                    "doc_id": f"PROC_{os_id}",
                    "protocolo": prot,
                    "os_id": os_id,
                    "rel_path": f"Ordens_De_Serviço/{os_id}/{pf}",
                    "abs_path": os.path.join(folder, pf)
                })
    return docs


def run_delta_ingestion(conn: sqlite3.Connection, force_rebuild: bool = False) -> dict:
    """
    Executa a Ingestão Incremental (Delta Append-Only) sobre todos os PDFs monitorados.
    Se o PDF já estiver no watermark com o mesmo número de páginas e mesmo SHA-256,
    pula 100% das páginas já processadas! Se houver novas páginas (N+1..M), processa
    exclusivamente as páginas novas.
    """
    cur = conn.cursor()
    docs = get_monitored_documents()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = {
        "timestamp": now_str,
        "total_documents": len(docs),
        "total_pages_monitored": 0,
        "pages_already_cached_skipped": 0,
        "new_pages_ingested_delta": 0,
        "tokens_saved_estimate": 0,
        "tokens_consumed_delta": 0,
        "documents_detail": []
    }

    for d in docs:
        abs_path = d["abs_path"]
        if not os.path.exists(abs_path):
            continue

        file_size = os.path.getsize(abs_path)
        pdf = fitz.open(abs_path)
        total_pages = len(pdf)
        report["total_pages_monitored"] += total_pages

        # Consultar watermark atual
        cur.execute(
            "SELECT last_ingested_page, first_page_sha256, last_page_sha256, tokens_cached FROM document_watermarks WHERE doc_id = ?",
            (d["doc_id"],)
        )
        row = cur.fetchone()

        first_page_txt = pdf[0].get_text("text") if total_pages > 0 else ""
        first_sha = compute_text_sha256(first_page_txt)

        start_page_idx = 0  # 0-based
        status_integrity = "NOVO_INGESTAO_INICIAL"

        if row and not force_rebuild:
            prev_last_page, prev_first_sha, prev_last_sha, prev_tokens = row
            if prev_last_page <= total_pages and prev_last_page > 0:
                check_txt = pdf[prev_last_page - 1].get_text("text")
                check_sha = compute_text_sha256(check_txt)
                if check_sha == prev_last_sha and first_sha == prev_first_sha:
                    # Watermark 100% íntegro! Processar apenas de prev_last_page em diante
                    start_page_idx = prev_last_page
                    status_integrity = "APPEND_ONLY_VERIFICADO" if total_pages > prev_last_page else "CACHE_100%_INTEGRO"
                else:
                    # Caso raro em que o PDF anterior foi substituído por outro diferente
                    start_page_idx = 0
                    status_integrity = "REINGESTAO_HASH_ALTERADO"
                    cur.execute("DELETE FROM vector_chunks WHERE doc_id = ?", (d["doc_id"],))

        pages_skipped = start_page_idx
        pages_to_ingest = total_pages - start_page_idx

        report["pages_already_cached_skipped"] += pages_skipped
        report["new_pages_ingested_delta"] += pages_to_ingest
        report["tokens_saved_estimate"] += pages_skipped * 850
        report["tokens_consumed_delta"] += pages_to_ingest * 850

        # Ingerir apenas as páginas novas [start_page_idx .. total_pages - 1]
        for p_idx in range(start_page_idx, total_pages):
            p_num = p_idx + 1
            # Para o Processo Mãe 24.574.062-0 (904 págs), indexamos a fase contratual/financeira (p. 640..904)
            # e os marcos iniciais (p. 1..30) ou páginas com palavras-chave, economizando espaço sem perder nada
            raw_txt = pdf[p_idx].get_text("text")
            clean_txt = " ".join(raw_txt.split())
            if len(clean_txt) < 25:
                continue

            if d["doc_id"] == "PROC_MAE_24574062" and 25 < p_num < 640:
                # Na fase interna da licitação (pp. 26..639), indexar apenas peças-chave (Contrato, TR, Parecer, Despacho)
                up_t = clean_txt.upper()
                if not any(k in up_t for k in ["CONTRATO", "TERMO DE REFERÊNCIA", "RESOLUÇÃO", "DESPACHO", "PARECER", "AUTORIZAÇÃO"]):
                    continue

            p_sha = compute_text_sha256(raw_txt)
            doc_type, competencia, ai_summary = classify_page_ai_summary(
                d["doc_id"], d["protocolo"], d["os_id"], p_num, raw_txt
            )
            emb = compute_embedding(ai_summary + " " + clean_txt[:1500])
            chunk_id = f"{d['doc_id']}_P{p_num:04d}"
            pdf_link = f"../{d['rel_path']}#page={p_num}"

            cur.execute("""
            INSERT OR REPLACE INTO vector_chunks
            (chunk_id, doc_id, protocolo, os_id, competencia, doc_type, page_num, page_sha256, pdf_link, snippet, ai_summary, embedding_json, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chunk_id,
                d["doc_id"],
                d["protocolo"],
                d["os_id"],
                competencia,
                doc_type,
                p_num,
                p_sha,
                pdf_link,
                clean_txt[:650],
                ai_summary,
                json.dumps(emb),
                now_str
            ))

        last_page_txt = pdf[total_pages - 1].get_text("text") if total_pages > 0 else ""
        last_sha = compute_text_sha256(last_page_txt)
        tokens_cached = total_pages * 850

        cur.execute("""
        INSERT OR REPLACE INTO document_watermarks
        (doc_id, protocolo, os_id, rel_path, file_size, total_pages, last_ingested_page, first_page_sha256, last_page_sha256, tokens_cached, last_sync_at, status_integrity)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            d["doc_id"],
            d["protocolo"],
            d["os_id"],
            d["rel_path"],
            file_size,
            total_pages,
            total_pages,
            first_sha,
            last_sha,
            tokens_cached,
            now_str,
            status_integrity
        ))

        pdf.close()

        report["documents_detail"].append({
            "doc_id": d["doc_id"],
            "protocolo": d["protocolo"],
            "os_id": d["os_id"],
            "rel_path": d["rel_path"],
            "total_pages": total_pages,
            "pages_skipped": pages_skipped,
            "new_pages_ingested": pages_to_ingest,
            "last_page_sha256": last_sha[:16] + "...",
            "status": status_integrity
        })

    conn.commit()
    return report


# ============================================================================
# DADOS CANÔNICOS DO FLUXO DE 10 ETAPAS (instruções.md), RMEC MENSAL E TIMELINE
# ============================================================================

RMEC_MONTHLY_CYCLES = [
    {
        "competencia": "Fevereiro/2026",
        "ordem": 1,
        "periodoExecucao": "20/01/2026 a 19/02/2026",
        "dataSubmissaoCelepar": "18/03/2026 11:34",
        "fechamentoPages": "fls. 38–42",
        "fechamentoPageNum": 38,
        "atestoData": "18/03/2026 14:32",
        "atestoPages": "fls. 43–44",
        "atestoPageNum": 43,
        "atestoSignatarios": "Diogo Luiz de Lima (Fiscal) & José Eduardo Padilha de Sousa (Gestor)",
        "houveGlosaOuRetificacao": False,
        "detalheFiscalizacao": "Atesto integral em 18/03/2026 (fls. 43–44 do Prot. 25.609.621-8), autorizando emissão de NF no valor de R$ 235.122,41.",
        "usnTotal": 106128.30,
        "valorUSNTotal": 186785.81,
        "ustTotal": 156.00,
        "valorUSTTotal": 48336.60,
        "valorTotalFechamento": 235122.41,
        "procMaeNF": {
            "nfUSN": "NFS-e 1052 / 1353 (R$ 186.785,80)",
            "nfUST": "NFS-e 1053 (R$ 48.336,60)",
            "valorTotalPago": 235122.40,
            "encaminhamentoNAS": "22/04/2026 (fl. 765)",
            "lancamentoGMS": "22/04/2026",
            "nl": "2026NL000219 (22/04/2026)",
            "pd": "2026PD000237",
            "ob": "2026OB000430 (28/04/2026)",
            "procMaePage": 762,
            "statusEtapa7a9": "CONCLUÍDO E PAGO"
        },
        "itensOS": [
            {"os_id": "OS_02", "projeto": "Paraná + Sustentável (SOT)", "usn": 106128.30, "valor_usn": 186785.81, "ust": 156.00, "valor_ust": 48336.60, "total": 235122.41, "rmec_page": 21, "obs": "1º RMEC do contrato (fls. 21–37)"}
        ]
    },
    {
        "competencia": "Março/2026",
        "ordem": 2,
        "periodoExecucao": "20/02/2026 a 19/03/2026",
        "dataSubmissaoCelepar": "22/04/2026 17:19 (1ª versão) → 30/04/2026 16:40 (Retificado)",
        "fechamentoPages": "fls. 80–85 (1ª v.) / fls. 112–117 (Retificado)",
        "fechamentoPageNum": 112,
        "atestoData": "04/05/2026 10:15",
        "atestoPages": "fls. 118–119 (após Devolução SEIA nas fls. 86–88)",
        "atestoPageNum": 118,
        "atestoSignatarios": "Diogo Luiz de Lima (Fiscal) & José Eduardo Padilha de Sousa (Gestor)",
        "houveGlosaOuRetificacao": True,
        "detalheFiscalizacao": "DEVOLUÇÃO SEIA EM 29/04/2026 (fls. 86–88): O Fiscal Diogo Luiz de Lima recusou a 1ª submissão da Celepar apontando 3 falhas: (1) Duplicidade de 7 reuniões do Resident Program de fev/2026 repetidas no RMEC de março da OS-002 (fl. 65); (2) Erro de soma de R$ 10,00 a maior na OS-002 (declarado R$ 389.243,22 vs correto R$ 389.233,22); (3) Divergência de centavos na OS-006 (R$ 282,59 vs R$ 282,58). A Celepar retificou os relatórios em 30/04/2026 (fls. 89–117) e a SEIA emitiu o Atesto em 04/05/2026 (fls. 118–119).",
        "usnTotal": 201780.81,
        "valorUSNTotal": 355134.22,
        "ustTotal": 400.00,
        "valorUSTTotal": 123940.00,
        "valorTotalFechamento": 479074.22,
        "procMaeNF": {
            "nfUSN": "NFS-e 1528 / 2275 (R$ 355.134,22)",
            "nfUST": "NFS-e 1529 (R$ 123.940,00)",
            "valorTotalPago": 479074.22,
            "encaminhamentoNAS": "12/05/2026 (fl. 784)",
            "lancamentoGMS": "12/05/2026",
            "nl": "2026NL000233 (12/05/2026)",
            "pd": "2026PD000253",
            "ob": "2026OB000493 (15/05/2026)",
            "procMaePage": 782,
            "statusEtapa7a9": "CONCLUÍDO E PAGO"
        },
        "itensOS": [
            {"os_id": "OS_01", "projeto": "Projeto J.A.C.A. (CEASA)", "usn": 1460.21, "valor_usn": 2569.97, "ust": 156.00, "valor_ust": 48336.60, "total": 50906.57, "rmec_page": 45, "obs": "Início cobrança OS-001 (fls. 45–52)"},
            {"os_id": "OS_02", "projeto": "Paraná + Sustentável (SOT)", "usn": 178198.76, "valor_usn": 313629.82, "ust": 244.00, "valor_ust": 75603.40, "total": 389233.22, "rmec_page": 97, "obs": "Retificado após glosa de R$ 10,00 e exclusão de atas duplicadas (fls. 97–111)"},
            {"os_id": "OS_03", "projeto": "Sistrânsito (PCP)", "usn": 0.00, "valor_usn": 0.00, "ust": 0.00, "valor_ust": 0.00, "total": 0.00, "rmec_page": 115, "obs": "Sem consumo no período"},
            {"os_id": "OS_04", "projeto": "Intranet IA (PMPR)", "usn": 0.00, "valor_usn": 0.00, "ust": 0.00, "valor_ust": 0.00, "total": 0.00, "rmec_page": 115, "obs": "Sem consumo no período"},
            {"os_id": "OS_05", "projeto": "Agentes IA / Licenças Gemini (SEIA)", "usn": 21961.28, "valor_usn": 38651.85, "ust": 0.00, "valor_ust": 0.00, "total": 38651.85, "rmec_page": 68, "obs": "Pro-rata inicial Gemini (fls. 68–72)"},
            {"os_id": "OS_06", "projeto": "Data Foundation (SEIA)", "usn": 160.56, "valor_usn": 282.58, "ust": 0.00, "valor_ust": 0.00, "total": 282.58, "rmec_page": 89, "obs": "Retificado centavos R$ 282,58 (fls. 89–96)"}
        ]
    },
    {
        "competencia": "Abril/2026",
        "ordem": 3,
        "periodoExecucao": "20/03/2026 a 19/04/2026",
        "dataSubmissaoCelepar": "13/05/2026 16:40",
        "fechamentoPages": "fls. 182–187",
        "fechamentoPageNum": 182,
        "atestoData": "25/05/2026 16:59",
        "atestoPages": "fls. 188–189",
        "atestoPageNum": 188,
        "atestoSignatarios": "Diogo Luiz de Lima (Fiscal) & José Eduardo Padilha de Sousa (Gestor)",
        "houveGlosaOuRetificacao": False,
        "detalheFiscalizacao": "Atesto técnico emitido em 25/05/2026 (fls. 188–189), aprovando os RMECs das OSs 001, 002, 005 e 006 no total de R$ 1.290.224,57.",
        "usnTotal": 662661.69,
        "valorUSNTotal": 1166284.57,
        "ustTotal": 400.00,
        "valorUSTTotal": 123940.00,
        "valorTotalFechamento": 1290224.57,
        "procMaeNF": {
            "nfUSN": "NFS-e 1966 / 3008 (R$ 1.166.284,57)",
            "nfUST": "NFS-e 1967 (R$ 123.940,00)",
            "valorTotalPago": 1290224.57,
            "encaminhamentoNAS": "06/07/2026 (fl. 805)",
            "lancamentoGMS": "06/07/2026",
            "nl": "2026NL000350 (06/07/2026)",
            "pd": "2026PD000368",
            "ob": "2026OB000699 (13/07/2026)",
            "procMaePage": 802,
            "statusEtapa7a9": "CONCLUÍDO E PAGO"
        },
        "itensOS": [
            {"os_id": "OS_01", "projeto": "Projeto J.A.C.A. (CEASA)", "usn": 2322.54, "valor_usn": 4087.67, "ust": 156.00, "valor_ust": 48336.60, "total": 52424.27, "rmec_page": 120, "obs": "RMEC fls. 120–127"},
            {"os_id": "OS_02", "projeto": "Paraná + Sustentável (SOT)", "usn": 553821.33, "valor_usn": 974725.54, "ust": 244.00, "valor_ust": 75603.40, "total": 1050328.94, "rmec_page": 128, "obs": "RMEC fls. 128–152"},
            {"os_id": "OS_03", "projeto": "Sistrânsito (PCP)", "usn": 0.00, "valor_usn": 0.00, "ust": 0.00, "valor_ust": 0.00, "total": 0.00, "rmec_page": 185, "obs": "Sem consumo"},
            {"os_id": "OS_04", "projeto": "Intranet IA (PMPR)", "usn": 0.00, "valor_usn": 0.00, "ust": 0.00, "valor_ust": 0.00, "total": 0.00, "rmec_page": 185, "obs": "Sem consumo"},
            {"os_id": "OS_05", "projeto": "Agentes IA / Licenças Gemini (SEIA)", "usn": 61871.15, "valor_usn": 108893.22, "ust": 0.00, "valor_ust": 0.00, "total": 108893.22, "rmec_page": 153, "obs": "RMEC fls. 153–157"},
            {"os_id": "OS_06", "projeto": "Data Foundation (SEIA)", "usn": 44646.67, "valor_usn": 78578.14, "ust": 0.00, "valor_ust": 0.00, "total": 78578.14, "rmec_page": 158, "obs": "RMEC fls. 158–181 (início ingestão SEED/PGE)"}
        ]
    },
    {
        "competencia": "Maio/2026",
        "ordem": 4,
        "periodoExecucao": "20/04/2026 a 19/05/2026",
        "dataSubmissaoCelepar": "23/06/2026 15:23",
        "fechamentoPages": "fls. 274–279",
        "fechamentoPageNum": 274,
        "atestoData": "29/06/2026 14:49",
        "atestoPages": "fls. 280–281",
        "atestoPageNum": 280,
        "atestoSignatarios": "Diogo Luiz de Lima (Fiscal) & José Eduardo Padilha de Sousa (Gestor)",
        "houveGlosaOuRetificacao": False,
        "detalheFiscalizacao": "Atesto técnico emitido em 29/06/2026 no Prot. 25.609.621-8 (fls. 280–281). No Prot. 24.574.062-0, o despacho de encaminhamento para pagamento ocorreu em 07/08/2026 apenas pelo Fiscal (Gestor em férias).",
        "usnTotal": 1129136.36,
        "valorUSNTotal": 1987279.99,
        "ustTotal": 488.00,
        "valorUSTTotal": 151206.80,
        "valorTotalFechamento": 2138486.79,
        "procMaeNF": {
            "nfUSN": "NFS-e 2354 / 3300 (R$ 1.987.279,99)",
            "nfUST": "NFS-e 2355 (R$ 151.206,80)",
            "valorTotalPago": 2138486.79,
            "encaminhamentoNAS": "07/08/2026 (fl. 824)",
            "lancamentoGMS": "19/08/2026",
            "nl": "2026NL000441 (19/08/2026)",
            "pd": "2026PD000455",
            "ob": "2026OB000856 (27/08/2026)",
            "procMaePage": 820,
            "statusEtapa7a9": "CONCLUÍDO E PAGO"
        },
        "itensOS": [
            {"os_id": "OS_01", "projeto": "Projeto J.A.C.A. (CEASA)", "usn": 2067.15, "valor_usn": 3638.18, "ust": 0.00, "valor_ust": 0.00, "total": 3638.18, "rmec_page": 190, "obs": "Fim da vigência de UST da OS-001 em 20/04/2026 (fls. 190–198)"},
            {"os_id": "OS_02", "projeto": "Paraná + Sustentável (SOT)", "usn": 587677.59, "valor_usn": 1034312.56, "ust": 244.00, "valor_ust": 75603.40, "total": 1109915.96, "rmec_page": 199, "obs": "RMEC fls. 199–219"},
            {"os_id": "OS_03", "projeto": "Sistrânsito (PCP)", "usn": 648.86, "valor_usn": 1141.99, "ust": 0.00, "valor_ust": 0.00, "total": 1141.99, "rmec_page": 220, "obs": "1º consumo de nuvem Sistrânsito (fls. 220–227)"},
            {"os_id": "OS_04", "projeto": "Intranet IA (PMPR)", "usn": 0.00, "valor_usn": 0.00, "ust": 0.00, "valor_ust": 0.00, "total": 0.00, "rmec_page": 277, "obs": "Sem consumo"},
            {"os_id": "OS_05", "projeto": "Agentes IA / Licenças Gemini (SEIA)", "usn": 61875.54, "valor_usn": 108900.95, "ust": 0.00, "valor_ust": 0.00, "total": 108900.95, "rmec_page": 228, "obs": "RMEC fls. 228–232"},
            {"os_id": "OS_06", "projeto": "Data Foundation (SEIA — Guarda-Chuva)", "usn": 476867.22, "valor_usn": 839286.31, "ust": 244.00, "valor_ust": 75603.40, "total": 914889.71, "rmec_page": 233, "obs": "Salto de 44k para 476k USN com projetos SEED/PGE dentro da OS-006 (fls. 233–273)"}
        ]
    },
    {
        "competencia": "Junho/2026",
        "ordem": 5,
        "periodoExecucao": "20/05/2026 a 19/06/2026",
        "dataSubmissaoCelepar": "15/07/2026 17:43",
        "fechamentoPages": "fls. 404–408",
        "fechamentoPageNum": 404,
        "atestoData": "23/07/2026 16:08",
        "atestoPages": "fls. 409–410",
        "atestoPageNum": 409,
        "atestoSignatarios": "Diogo Luiz de Lima (Fiscal) & José Eduardo Padilha de Sousa (Gestor)",
        "houveGlosaOuRetificacao": False,
        "detalheFiscalizacao": "Atesto técnico emitido em 23/07/2026 (fls. 409–410). Pico de consumo na OS-006 Data Foundation (1.191.553,41 USN = R$ 2,09M só na OS-006) devido ao processamento intensivo de vídeos/redação da SEED.",
        "usnTotal": 2067348.82,
        "valorUSNTotal": 3638533.91,
        "ustTotal": 488.00,
        "valorUSTTotal": 151206.80,
        "valorTotalFechamento": 3789740.71,
        "procMaeNF": {
            "nfUSN": "NFS-e 2704 / 3486 (R$ 3.638.533,91)",
            "nfUST": "NFS-e 2705 (R$ 151.206,80)",
            "valorTotalPago": 3789740.71,
            "encaminhamentoNAS": "02/09/2026 (fl. 849)",
            "lancamentoGMS": "08/09/2026",
            "nl": "2026NL000487 (08/09/2026)",
            "pd": "2026PD000501",
            "ob": "2026OB000939 (15/09/2026)",
            "procMaePage": 845,
            "statusEtapa7a9": "CONCLUÍDO E PAGO"
        },
        "itensOS": [
            {"os_id": "OS_01", "projeto": "Projeto J.A.C.A. (CEASA)", "usn": 38.99, "valor_usn": 68.62, "ust": 0.00, "valor_ust": 0.00, "total": 68.62, "rmec_page": 282, "obs": "Consumo residual (fls. 282–290)"},
            {"os_id": "OS_02", "projeto": "Paraná + Sustentável (SOT)", "usn": 813123.71, "valor_usn": 1431097.72, "ust": 244.00, "valor_ust": 75603.40, "total": 1506701.12, "rmec_page": 291, "obs": "RMEC fls. 291–317"},
            {"os_id": "OS_03", "projeto": "Sistrânsito (PCP)", "usn": 47.12, "valor_usn": 82.93, "ust": 0.00, "valor_ust": 0.00, "total": 82.93, "rmec_page": 318, "obs": "RMEC fls. 318–326"},
            {"os_id": "OS_04", "projeto": "Intranet IA (PMPR)", "usn": 197.20, "valor_usn": 347.07, "ust": 0.00, "valor_ust": 0.00, "total": 347.07, "rmec_page": 327, "obs": "1º consumo PMPR (fls. 327–336)"},
            {"os_id": "OS_05", "projeto": "Agentes IA / Licenças Gemini (SEIA)", "usn": 62388.39, "valor_usn": 109803.57, "ust": 0.00, "valor_ust": 0.00, "total": 109803.57, "rmec_page": 337, "obs": "RMEC fls. 337–348"},
            {"os_id": "OS_06", "projeto": "Data Foundation (SEIA — Guarda-Chuva)", "usn": 1191553.41, "valor_usn": 2097134.00, "ust": 244.00, "valor_ust": 75603.40, "total": 2172737.40, "rmec_page": 349, "obs": "Pico histórico na OS-006: 1,19M USN (fls. 349–403)"}
        ]
    },
    {
        "competencia": "Julho/2026",
        "ordem": 6,
        "periodoExecucao": "20/06/2026 a 19/07/2026",
        "dataSubmissaoCelepar": "24/08/2026 16:40",
        "fechamentoPages": "fls. 546–550",
        "fechamentoPageNum": 546,
        "atestoData": "31/08/2026 12:04",
        "atestoPages": "fls. 551–553 (Despacho c/ Determinações LGPD & FinOps)",
        "atestoPageNum": 551,
        "atestoSignatarios": "Diogo Luiz de Lima (Fiscal) & José Eduardo Padilha de Sousa (Gestor)",
        "houveGlosaOuRetificacao": True,
        "detalheFiscalizacao": "ATESTO COM DETERMINAÇÕES DE FISCALIZAÇÃO (fls. 551–552): A SEIA aprovou o faturamento de R$ 2.771.812,43, porém determinou formalmente à Celepar: (a) Realocação e Restrição Geográfica de Dados para território brasileiro (LGPD) em todas as OSs, pois havia processamento ocorrendo em Iowa (us-central1 / us-east5); (b) Rastreabilidade por Projeto na OS-005; (c) Retirada/readequação imediata do Projeto Capricorn da OS-005.",
        "usnTotal": 1488980.47,
        "valorUSNTotal": 2620605.63,
        "ustTotal": 488.00,
        "valorUSTTotal": 151206.80,
        "valorTotalFechamento": 2771812.43,
        "procMaeNF": {
            "nfUSN": "NFS-e 3113 / 4336 (R$ 2.620.605,62)",
            "nfUST": "NFS-e 3114 (R$ 151.206,80)",
            "valorTotalPago": 2771812.42,
            "encaminhamentoNAS": "09/09/2026 (fl. 871)",
            "lancamentoGMS": "15/09/2026",
            "nl": "2026NL000501 (15/09/2026)",
            "pd": "2026PD000516",
            "ob": "2026OB000974 (22/09/2026)",
            "procMaePage": 868,
            "statusEtapa7a9": "CONCLUÍDO E PAGO"
        },
        "itensOS": [
            {"os_id": "OS_01", "projeto": "Projeto J.A.C.A. (CEASA)", "usn": 12.04, "valor_usn": 21.19, "ust": 0.00, "valor_ust": 0.00, "total": 21.19, "rmec_page": 411, "obs": "RMEC fls. 411–417"},
            {"os_id": "OS_02", "projeto": "Paraná + Sustentável (SOT)", "usn": 877059.93, "valor_usn": 1543625.48, "ust": 244.00, "valor_ust": 75603.40, "total": 1619228.88, "rmec_page": 418, "obs": "RMEC fls. 418–444"},
            {"os_id": "OS_03", "projeto": "Sistrânsito (PCP)", "usn": 15154.66, "valor_usn": 26672.20, "ust": 0.00, "valor_ust": 0.00, "total": 26672.20, "rmec_page": 445, "obs": "Crescimento Sistrânsito (fls. 445–459)"},
            {"os_id": "OS_04", "projeto": "Intranet IA (PMPR)", "usn": 518.66, "valor_usn": 912.84, "ust": 0.00, "valor_ust": 0.00, "total": 912.84, "rmec_page": 460, "obs": "RMEC fls. 460–470"},
            {"os_id": "OS_05", "projeto": "Agentes IA / Licenças Gemini (SEIA)", "usn": 59562.17, "valor_usn": 104829.42, "ust": 0.00, "valor_ust": 0.00, "total": 104829.42, "rmec_page": 471, "obs": "Alvo de determinação da SEIA (Capricorn / LGPD, fls. 471–489)"},
            {"os_id": "OS_06", "projeto": "Data Foundation (SEIA — Guarda-Chuva)", "usn": 536673.01, "valor_usn": 944544.50, "ust": 244.00, "valor_ust": 75603.40, "total": 1020147.90, "rmec_page": 490, "obs": "RMEC fls. 490–545"}
        ]
    },
    {
        "competencia": "Agosto/2026",
        "ordem": 7,
        "periodoExecucao": "20/07/2026 a 19/08/2026",
        "dataSubmissaoCelepar": "18/09/2026 11:36",
        "fechamentoPages": "fls. 631–635",
        "fechamentoPageNum": 631,
        "atestoData": "29/09/2026 15:48",
        "atestoPages": "fls. 636–637",
        "atestoPageNum": 636,
        "atestoSignatarios": "Diogo Luiz de Lima (Fiscal) & José Eduardo Padilha de Sousa (Gestor)",
        "houveGlosaOuRetificacao": False,
        "detalheFiscalizacao": "Atesto técnico emitido em 29/09/2026 (fls. 636–637). Último mês antes do desmembramento contábil da OS-006 em múltiplas OSs setoriais. Exauriu a 2026NE000055 e consumiu R$ 948,4k da 2026NE000298.",
        "usnTotal": 1936567.54,
        "valorUSNTotal": 3408358.87,
        "ustTotal": 488.00,
        "valorUSTTotal": 151206.80,
        "valorTotalFechamento": 3559565.67,
        "procMaeNF": {
            "nfUSN": "NFS-e 3630 / 4827 (R$ 3.408.358,87)",
            "nfUST": "NFS-e 3631 (R$ 151.206,80)",
            "valorTotalPago": 3559565.67,
            "encaminhamentoNAS": "01/10/2026 (fl. 893)",
            "lancamentoGMS": "08/10/2026",
            "nl": "2026NL000547 + 2026NL000548 (08/10/2026)",
            "pd": "2026PD000567 + 2026PD000568",
            "ob": "2026OB001053 + 2026OB001054 (15/10/2026)",
            "procMaePage": 889,
            "statusEtapa7a9": "CONCLUÍDO E PAGO"
        },
        "itensOS": [
            {"os_id": "OS_01", "projeto": "Projeto J.A.C.A. (CEASA)", "usn": 12.22, "valor_usn": 21.51, "ust": 0.00, "valor_ust": 0.00, "total": 21.51, "rmec_page": 554, "obs": "RMEC fls. 554–560"},
            {"os_id": "OS_02", "projeto": "Paraná + Sustentável (SOT)", "usn": 952704.70, "valor_usn": 1676760.27, "ust": 244.00, "valor_ust": 75603.40, "total": 1752363.67, "rmec_page": 561, "obs": "Maior consumo mensal da OS-002 (fls. 561–577)"},
            {"os_id": "OS_03", "projeto": "Sistrânsito (PCP)", "usn": 49482.65, "valor_usn": 87089.46, "ust": 0.00, "valor_ust": 0.00, "total": 87089.46, "rmec_page": 578, "obs": "RMEC fls. 578–586"},
            {"os_id": "OS_04", "projeto": "Intranet IA (PMPR)", "usn": 902.99, "valor_usn": 1589.26, "ust": 0.00, "valor_ust": 0.00, "total": 1589.26, "rmec_page": 587, "obs": "RMEC fls. 587–595"},
            {"os_id": "OS_05", "projeto": "Agentes IA / Licenças Gemini (SEIA)", "usn": 64496.47, "valor_usn": 113513.79, "ust": 0.00, "valor_ust": 0.00, "total": 113513.79, "rmec_page": 596, "obs": "RMEC fls. 596–605"},
            {"os_id": "OS_06", "projeto": "Data Foundation (SEIA — Guarda-Chuva)", "usn": 868968.51, "valor_usn": 1529384.58, "ust": 244.00, "valor_ust": 75603.40, "total": 1604987.98, "rmec_page": 606, "obs": "RMEC fls. 606–630"}
        ]
    },
    {
        "competencia": "Setembro/2026",
        "ordem": 8,
        "periodoExecucao": "20/08/2026 a 19/09/2026",
        "dataSubmissaoCelepar": "23/10/2026 13:52",
        "fechamentoPages": "fls. 759–766",
        "fechamentoPageNum": 759,
        "atestoData": "Pendente (Submetido em 23/10/2026 — Em análise pela Fiscalização SEIA)",
        "atestoPages": "Aguardando despacho após fl. 766",
        "atestoPageNum": 766,
        "atestoSignatarios": "Em análise (Diogo Luiz de Lima & José Eduardo Padilha de Sousa)",
        "houveGlosaOuRetificacao": False,
        "detalheFiscalizacao": "MARCO HISTÓRICO DE DESMEMBRAMENTO: Em 23/10/2026 (fls. 638–766), a Celepar protocolou 18 RMECs individuais e o Relatório de Fechamento Mensal de Setembro/2026 (R$ 3.776.669,52), desmembrando finalmente os projetos da SEED (OSs 08, 09, 10, 11), PGE (OS 12), SEFA/REPR (OSs 13, 14, 15, 17), SEJU (OS 07), Defesa Civil (OS 18), DPE (OS 19), IAT (OS 21), SESP (OS 22) e SEIA Recaptcha (OS 23) que antes rodavam ocultos na OS-006! Achado: A OS-022 teve R$ 18,22 cobrados no Fechamento (fl. 766) sem RMEC individual anexado, e as OSs 007 e 022 tiveram consumo mesmo com cláusula de bloqueio.",
        "usnTotal": 1906405.41,
        "valorUSNTotal": 3355273.52,
        "ustTotal": 1360.00,
        "valorUSTTotal": 421396.00,
        "valorTotalFechamento": 3776669.52,
        "procMaeNF": {
            "nfUSN": "Aguardando Atesto SEIA no Prot. 25.609.621-8",
            "nfUST": "Aguardando Atesto SEIA no Prot. 25.609.621-8",
            "valorTotalPago": 0.00,
            "encaminhamentoNAS": "Aguardando Etapa 6 → 7",
            "lancamentoGMS": "Pendente",
            "nl": "Pendente (Saldo disponível na 2026NE000298: R$ 12,37M)",
            "pd": "Pendente",
            "ob": "Pendente",
            "procMaePage": 904,
            "statusEtapa7a9": "ETAPA 6 EM ANÁLISE SEIA"
        },
        "itensOS": [
            {"os_id": "OS_01", "projeto": "Projeto J.A.C.A. (CEASA)", "usn": 12.08, "valor_usn": 21.26, "ust": 0.00, "valor_ust": 0.00, "total": 21.26, "rmec_page": 638, "obs": "RMEC fls. 638–643"},
            {"os_id": "OS_02", "projeto": "Paraná + Sustentável (SOT)", "usn": 756388.21, "valor_usn": 1331243.25, "ust": 244.00, "valor_ust": 75603.40, "total": 1406846.65, "rmec_page": 644, "obs": "RMEC fls. 644–652"},
            {"os_id": "OS_03", "projeto": "Sistrânsito (PCP)", "usn": 39845.65, "valor_usn": 70128.34, "ust": 0.00, "valor_ust": 0.00, "total": 70128.34, "rmec_page": 653, "obs": "RMEC fls. 653–659"},
            {"os_id": "OS_04", "projeto": "Intranet IA (PMPR)", "usn": 939.45, "valor_usn": 1653.43, "ust": 0.00, "valor_ust": 0.00, "total": 1653.43, "rmec_page": 660, "obs": "RMEC fls. 660–666"},
            {"os_id": "OS_05", "projeto": "Agentes IA / Licenças Gemini (SEIA)", "usn": 84358.22, "valor_usn": 148470.47, "ust": 0.00, "valor_ust": 0.00, "total": 148470.47, "rmec_page": 667, "obs": "Aumento p/ 84.358 USN (acima das 58.978 USN da OS-005, fls. 667–671)"},
            {"os_id": "OS_06", "projeto": "Data Foundation (SEIA)", "usn": 20314.25, "valor_usn": 35753.08, "ust": 244.00, "valor_ust": 75603.40, "total": 111356.48, "rmec_page": 672, "obs": "Queda de 868k p/ 20k USN após desmembramento das OSs 08 a 23 (fls. 672–680)"},
            {"os_id": "OS_07", "projeto": "G-Migra (SEJU)", "usn": 10.56, "valor_usn": 18.59, "ust": 244.00, "valor_ust": 75603.40, "total": 75621.99, "rmec_page": 681, "obs": "ALERTA: Cobrança de 244 UST (R$ 75,6k) em OS sem tabela financeira assinada (fls. 681–688)"},
            {"os_id": "OS_08", "projeto": "Redação Paraná (SEED)", "usn": 354150.06, "valor_usn": 623304.11, "ust": 0.00, "valor_ust": 0.00, "total": 623304.11, "rmec_page": 689, "obs": "1º RMEC individual pós-desmembramento da OS-006 (fls. 689–693)"},
            {"os_id": "OS_09", "projeto": "Análise de Vídeos BI (SEED)", "usn": 146398.44, "valor_usn": 257661.25, "ust": 0.00, "valor_ust": 0.00, "total": 257661.25, "rmec_page": 694, "obs": "1º RMEC individual pós-desmembramento da OS-006 (fls. 694–698)"},
            {"os_id": "OS_10", "projeto": "Fluência de Leitura LIA (SEED)", "usn": 55945.41, "valor_usn": 98463.92, "ust": 0.00, "valor_ust": 0.00, "total": 98463.92, "rmec_page": 699, "obs": "1º RMEC individual pós-desmembramento da OS-006 (fls. 699–703)"},
            {"os_id": "OS_11", "projeto": "Integrações e Dados (SEED)", "usn": 200601.28, "valor_usn": 353058.25, "ust": 0.00, "valor_ust": 0.00, "total": 353058.25, "rmec_page": 704, "obs": "1º RMEC individual pós-desmembramento da OS-006 (fls. 704–708)"},
            {"os_id": "OS_12", "projeto": "DataPGE (PGE)", "usn": 59966.22, "valor_usn": 105540.55, "ust": 0.00, "valor_ust": 0.00, "total": 105540.55, "rmec_page": 709, "obs": "1º RMEC individual DataPGE (fls. 709–713)"},
            {"os_id": "OS_13", "projeto": "DataContabil (SEFA)", "usn": 39.53, "valor_usn": 69.57, "ust": 0.00, "valor_ust": 0.00, "total": 69.57, "rmec_page": 714, "obs": "1º RMEC individual SEFA (fls. 714–718)"},
            {"os_id": "OS_14", "projeto": "Modernização Fazendária IA (SEFA)", "usn": 10.41, "valor_usn": 18.32, "ust": 0.00, "valor_ust": 0.00, "total": 18.32, "rmec_page": 719, "obs": "1º RMEC individual SEFA (fls. 719–723)"},
            {"os_id": "OS_15", "projeto": "Automação Orçamentária (SEFA)", "usn": 659.97, "valor_usn": 1161.55, "ust": 0.00, "valor_ust": 0.00, "total": 1161.55, "rmec_page": 724, "obs": "1º RMEC individual SEFA (fls. 724–728)"},
            {"os_id": "OS_16", "projeto": "Modelos de Previsão (SEFA)", "usn": 0.00, "valor_usn": 0.00, "ust": 0.00, "valor_ust": 0.00, "total": 0.00, "rmec_page": 765, "obs": "Sem consumo no Fechamento Mensal (fl. 765)"},
            {"os_id": "OS_17", "projeto": "Agentes Inteligentes (REPR/SEFA)", "usn": 19571.05, "valor_usn": 34445.05, "ust": 0.00, "valor_ust": 0.00, "total": 34445.05, "rmec_page": 729, "obs": "1º RMEC individual REPR/SEFA (fls. 729–733)"},
            {"os_id": "OS_18", "projeto": "PRISMA (Defesa Civil)", "usn": 10.56, "valor_usn": 18.59, "ust": 244.00, "valor_ust": 75603.40, "total": 75621.99, "rmec_page": 734, "obs": "Cobrança de 244 UST + 10,56 USN (fls. 734–742)"},
            {"os_id": "OS_19", "projeto": "Data Foundation (DPE-PR)", "usn": 144891.02, "valor_usn": 255008.20, "ust": 384.00, "valor_ust": 118982.40, "total": 373990.60, "rmec_page": 743, "obs": "Cobrou 384 UST (GCP_DEV_002 Implementação) + 144,8k USN (fls. 743–748)"},
            {"os_id": "OS_20", "projeto": "Consultivo IA (PGE)", "usn": 0.00, "valor_usn": 0.00, "ust": 0.00, "valor_ust": 0.00, "total": 0.00, "rmec_page": 765, "obs": "Sem consumo no período (fl. 765)"},
            {"os_id": "OS_21", "projeto": "Plataforma Ambiental (IAT/TECPAR)", "usn": 11918.50, "valor_usn": 20976.56, "ust": 0.00, "valor_ust": 0.00, "total": 20976.56, "rmec_page": 749, "obs": "1º RMEC individual IAT (fls. 749–753)"},
            {"os_id": "OS_22", "projeto": "Delegacia Eletrônica (SESP)", "usn": 10.35, "valor_usn": 18.22, "ust": 0.00, "valor_ust": 0.00, "total": 18.22, "rmec_page": 766, "obs": "ALERTA: Cobrado R$ 18,22 no Fechamento (fl. 766) sem RMEC individual juntado"},
            {"os_id": "OS_23", "projeto": "Recaptcha Enterprise (SEIA)", "usn": 10364.19, "valor_usn": 18240.97, "ust": 0.00, "valor_ust": 0.00, "total": 18240.97, "rmec_page": 754, "obs": "1º RMEC individual Recaptcha (fls. 754–758)"}
        ]
    }
]


# Matriz das Etapas 1 a 5 (instruções.md) para todas as 27 Ordens de Serviço
OS_WORKFLOW_STEPS_1_TO_5 = [
    {"os_id": "OS_01", "protocolo": "25.289.226-5", "proc_file": "Processo_25.289.226-5_1.pdf", "e1_pt": {"status": "OK", "data": "21/01/2026 13:59", "page": 2, "desc": "Ofício CEASA 008/2026 + PT v1.1 + SOW (fls. 2–35)"}, "e2_enc": {"status": "OK", "data": "27/01/2026 14:24", "page": 38, "desc": "Despacho SEIA/DIA encaminha à Celepar p/ custos (fls. 38–39)"}, "e3_dim": {"status": "ALERTA", "data": "13/02/2026 → 24/02/2026", "page": 40, "desc": "Celepar envia 2 versões de Dim. Inicial c/ 58.459,38 USN + 244 UST/mês + 208 UST única (fls. 40–56)"}, "e4_os": {"status": "OK", "data": "24/02/2026 16:48", "page": 59, "desc": "OS-2026-9291-001 assinada c/ início retroativo a 20/01/2026 (fls. 59–61)"}, "e5_ini": {"status": "OK", "data": "18/03/2026", "page": 45, "desc": "Execução confirmada no RMEC de Março/2026 (Prot. 25.609.621-8 fl. 45)"}},
    {"os_id": "OS_02", "protocolo": "25.258.138-3", "proc_file": "Processo_25.258.138-3_1.pdf", "e1_pt": {"status": "OK", "data": "15/01/2026 11:36", "page": 2, "desc": "Ofício SOT 002/2026 + Plano de Trabalho Paraná + Sustentável (fls. 2–10)"}, "e2_enc": {"status": "OK", "data": "16/01/2026 14:38", "page": 11, "desc": "SEIA encaminha à Celepar para dimensionamento"}, "e3_dim": {"status": "ALERTA", "data": "09/02/2026 19:22", "page": 12, "desc": "Dim. Inicial: 1.062.639,98 USN/mês (soma das linhas dá 540.905 USN) + 420 UST/mês + 960 UST única (fls. 12–19)"}, "e4_os": {"status": "OK", "data": "10/02/2026 11:44", "page": 20, "desc": "OS-2026-9291-002 assinada (data fim em branco, fls. 20–22)"}, "e5_ini": {"status": "OK", "data": "18/03/2026", "page": 21, "desc": "Confirmado já no 1º RMEC de Fev/2026 (Prot. 25.609.621-8 fl. 21)"}},
    {"os_id": "OS_03", "protocolo": "25.498.613-5", "proc_file": "Processo_25.498.613-5_1.pdf", "e1_pt": {"status": "OK", "data": "24/02/2026 17:19", "page": 2, "desc": "Ofício PCP + PT + SOW Sistrânsito (fls. 2–27)"}, "e2_enc": {"status": "OK", "data": "26/02/2026 15:10", "page": 28, "desc": "SEIA encaminha à Celepar para levantamento de custos (fls. 28–31)"}, "e3_dim": {"status": "OK", "data": "12/03/2026 10:15", "page": 32, "desc": "Dim. Inicial Celepar: 145.655,10 USN/mês + 244 UST/mês + 688 UST única (fls. 32–38)"}, "e4_os": {"status": "CRITICO", "data": "12/03/2026 11:36", "page": 41, "desc": "OS-003 assinada com ERRO ARITMÉTICO nas USTs (imprimiu R$ 27,2k p/ 244 UST e R$ 84,2k p/ 688 UST, fls. 41–44)"}, "e5_ini": {"status": "OK", "data": "23/06/2026", "page": 220, "desc": "Consumo iniciado no RMEC de Maio/2026 (Prot. 25.609.621-8 fl. 220)"}},
    {"os_id": "OS_04", "protocolo": "25.495.019-0", "proc_file": "Processo_25.495.019-0_1.pdf", "e1_pt": {"status": "OK", "data": "24/02/2026 14:15", "page": 2, "desc": "Ofício PMPR + PT + SOW Intranet Inteligente (fls. 2–23)"}, "e2_enc": {"status": "OK", "data": "26/02/2026 15:12", "page": 24, "desc": "SEIA solicita dimensionamento à Celepar (fls. 24–27)"}, "e3_dim": {"status": "OK", "data": "12/03/2026 10:18", "page": 28, "desc": "Dim. Inicial Celepar: 155.171,82 USN/mês + 244 UST/mês + 208 UST única (fls. 28–34)"}, "e4_os": {"status": "CRITICO", "data": "12/03/2026 18:10", "page": 37, "desc": "OS-004 assinada mantendo 732 UST/mês na tabela p/ valor de 244 UST/mês (fls. 37–40)"}, "e5_ini": {"status": "OK", "data": "15/07/2026", "page": 327, "desc": "Consumo iniciado no RMEC de Junho/2026 (Prot. 25.609.621-8 fl. 327)"}},
    {"os_id": "OS_05", "protocolo": "25.306.817-5", "proc_file": "Processo_25.306.817-5_1.pdf", "e1_pt": {"status": "OK", "data": "22/01/2026 17:10", "page": 2, "desc": "Solicitação SEIA p/ 5.000 Licenças Google Gemini Enterprise (fls. 2–8)"}, "e2_enc": {"status": "OK", "data": "27/01/2026 14:30", "page": 9, "desc": "SEIA encaminha à Celepar para cotação em USN (fls. 9–11)"}, "e3_dim": {"status": "OK", "data": "12/02/2026 16:40", "page": 12, "desc": "Dim. Inicial Celepar: 58.978,00 USN/mês (R$ 103.801,28/mês) e 0 UST (fls. 12–16)"}, "e4_os": {"status": "ALERTA", "data": "12/03/2026 15:20", "page": 19, "desc": "OS-005 assinada c/ erro material citando 'Projeto JACA' e cláusula de commitment fixo questionada pelo Fiscal nas fls. 22–27"}, "e5_ini": {"status": "OK", "data": "22/04/2026", "page": 68, "desc": "Consumo iniciado em Março/2026 (RMEC fl. 68 do Prot. 25.609.621-8)"}},
    {"os_id": "OS_06", "protocolo": "25.284.492-9", "proc_file": "Processo_25.284.492-9_1.pdf", "e1_pt": {"status": "OK", "data": "20/01/2026 16:05", "page": 2, "desc": "Plano de Trabalho + SOW Data Foundation Estadual (fls. 2–26)"}, "e2_enc": {"status": "OK", "data": "27/01/2026 14:28", "page": 27, "desc": "SEIA encaminha à Celepar para levantamento de custos (fls. 27–28)"}, "e3_dim": {"status": "OK", "data": "09/02/2026 19:25", "page": 29, "desc": "Dim. Inicial Celepar: 2.325.000 USN/mês (R$ 4,09M) + 732 UST/mês + 432 UST única (fls. 29–35)"}, "e4_os": {"status": "CRITICO", "data": "NÃO EMITIDA", "page": 37, "desc": "FALHA CRÍTICA: Processo encerra na fl. 37 em 10/02/2026 SEM Ordem de Serviço assinada!"}, "e5_ini": {"status": "ALERTA", "data": "22/04/2026", "page": 89, "desc": "Entrou em operação e faturamento desde Março/2026 sem OS assinada (Prot. 25.609.621-8 fl. 89)"}},
    {"os_id": "OS_07", "protocolo": "25.999.961-9", "proc_file": "Processo_25.999.961-9_1.pdf", "e1_pt": {"status": "OK", "data": "22/05/2026 11:20", "page": 2, "desc": "Ofício SEJU + PT + SOW Plataforma G-Migra (fls. 2–45)"}, "e2_enc": {"status": "OK", "data": "13/08/2026 15:40", "page": 48, "desc": "SEIA encaminha à Celepar e reitera cobrança de orçamento em 14/09/2026 (fls. 48–50)"}, "e3_dim": {"status": "CRITICO", "data": "PENDENTE CELEPAR", "page": 50, "desc": "Celepar NÃO enviou o Dimensionamento Inicial nos autos (há apenas estimativa SOW de R$ 151,9k/mês)"}, "e4_os": {"status": "ALERTA", "data": "14/09/2026 17:15", "page": 51, "desc": "OS-007 emitida s/ valor financeiro e c/ BLOQUEIO DE PRODUÇÃO até envio de custos (fls. 51–56)"}, "e5_ini": {"status": "ALERTA", "data": "23/10/2026", "page": 681, "desc": "Em Set/2026 (Prot. 25.609.621-8 fl. 681), Celepar cobrou 10,56 USN + 244 UST (R$ 75.621,99) da OS-007!"}},
    {"os_id": "OS_08", "protocolo": "26.473.175-5", "proc_file": "Processo_26.473.175-5_1.pdf", "e1_pt": {"status": "ALERTA", "data": "23/09/2026 17:38", "page": 2, "desc": "Desmembramento da OS-006 (Redação Paraná SEED) — sem PT específico nos autos"}, "e2_enc": {"status": "OK", "data": "23/09/2026 17:43", "page": 5, "desc": "SEIA solicita à Celepar migração de centro de custo e dimensionamento"}, "e3_dim": {"status": "CRITICO", "data": "PENDENTE", "page": 5, "desc": "Sem Dimensionamento Inicial nos autos do processo 26.473.175-5"}, "e4_os": {"status": "ALERTA", "data": "23/09/2026 17:38", "page": 2, "desc": "OS-008 assinada sem tabela de valores USN/UST (fls. 2–4)"}, "e5_ini": {"status": "OK", "data": "23/10/2026", "page": 689, "desc": "Faturado em Set/2026: 354.150,06 USN = R$ 623.304,11 (Prot. 25.609.621-8 fl. 689)"}},
    {"os_id": "OS_09", "protocolo": "26.473.268-9", "proc_file": "Processo_26.473.268-9_1.pdf", "e1_pt": {"status": "ALERTA", "data": "23/09/2026 17:38", "page": 2, "desc": "Desmembramento da OS-006 (Análise de Vídeos BI SEED) — sem PT específico nos autos"}, "e2_enc": {"status": "OK", "data": "23/09/2026 17:44", "page": 5, "desc": "SEIA encaminha à Celepar para individualização do faturamento"}, "e3_dim": {"status": "CRITICO", "data": "PENDENTE", "page": 5, "desc": "Sem Dimensionamento Inicial nos autos do processo 26.473.268-9"}, "e4_os": {"status": "ALERTA", "data": "23/09/2026 17:38", "page": 2, "desc": "OS-009 assinada sem tabela de valores USN/UST (fls. 2–4)"}, "e5_ini": {"status": "OK", "data": "23/10/2026", "page": 694, "desc": "Faturado em Set/2026: 146.398,44 USN = R$ 257.661,25 (Prot. 25.609.621-8 fl. 694)"}},
    {"os_id": "OS_10", "protocolo": "26.473.320-0", "proc_file": "Processo_26.473.320-0_1.pdf", "e1_pt": {"status": "ALERTA", "data": "23/09/2026 17:38", "page": 2, "desc": "Desmembramento da OS-006 (Fluência de Leitura LIA SEED) — sem PT específico"}, "e2_enc": {"status": "OK", "data": "23/09/2026 17:46", "page": 5, "desc": "SEIA encaminha à Celepar para individualização do faturamento"}, "e3_dim": {"status": "CRITICO", "data": "PENDENTE", "page": 5, "desc": "Sem Dimensionamento Inicial nos autos do processo 26.473.320-0"}, "e4_os": {"status": "ALERTA", "data": "23/09/2026 17:38", "page": 2, "desc": "OS-010 assinada sem tabela de valores USN/UST (fls. 2–4)"}, "e5_ini": {"status": "OK", "data": "23/10/2026", "page": 699, "desc": "Faturado em Set/2026: 55.945,41 USN = R$ 98.463,92 (Prot. 25.609.621-8 fl. 699)"}},
    {"os_id": "OS_11", "protocolo": "26.473.368-5", "proc_file": "Processo_26.473.368-5_1.pdf", "e1_pt": {"status": "ALERTA", "data": "23/09/2026 17:38", "page": 2, "desc": "Desmembramento da OS-006 (Integrações SEED) — sem PT específico"}, "e2_enc": {"status": "OK", "data": "23/09/2026 17:47", "page": 5, "desc": "SEIA encaminha à Celepar para individualização do faturamento"}, "e3_dim": {"status": "CRITICO", "data": "PENDENTE", "page": 5, "desc": "Sem Dimensionamento Inicial nos autos do processo 26.473.368-5"}, "e4_os": {"status": "ALERTA", "data": "23/09/2026 17:38", "page": 2, "desc": "OS-011 assinada sem tabela de valores USN/UST (fls. 2–4)"}, "e5_ini": {"status": "OK", "data": "23/10/2026", "page": 704, "desc": "Faturado em Set/2026: 200.601,28 USN = R$ 353.058,25 (Prot. 25.609.621-8 fl. 704)"}},
    {"os_id": "OS_12", "protocolo": "25.736.135-7", "proc_file": "Processo_25.736.135-7_1.pdf", "e1_pt": {"status": "OK", "data": "10/04/2026 15:20", "page": 2, "desc": "Ofício PGE + Plano de Trabalho + SOW DataPGE (fls. 2–26)"}, "e2_enc": {"status": "OK", "data": "15/04/2026 11:10", "page": 27, "desc": "SEIA encaminha à Celepar para dimensionamento"}, "e3_dim": {"status": "ALERTA", "data": "PENDENTE", "page": 28, "desc": "Rodou na OS-006 até Ago/26; desmembrada em Set/26 sem tabela USN no processo"}, "e4_os": {"status": "ALERTA", "data": "23/09/2026 17:38", "page": 29, "desc": "OS-012 assinada sem quadro de valores R$ (fls. 29–32)"}, "e5_ini": {"status": "OK", "data": "23/10/2026", "page": 709, "desc": "Faturado em Set/2026: 59.966,22 USN = R$ 105.540,55 (Prot. 25.609.621-8 fl. 709)"}},
    {"os_id": "OS_13", "protocolo": "25.498.894-4", "proc_file": "Processo_25.498.894-4_1.pdf", "e1_pt": {"status": "OK", "data": "25/02/2026 16:00", "page": 2, "desc": "Ofício SEFA + PT + SOW DataContabil (fls. 2–40)"}, "e2_enc": {"status": "OK", "data": "02/03/2026 14:00", "page": 41, "desc": "SEIA encaminha à Celepar para levantamento de custos"}, "e3_dim": {"status": "ALERTA", "data": "PENDENTE", "page": 45, "desc": "Sem planilha final de USN/UST nos autos antes da emissão da OS"}, "e4_os": {"status": "ALERTA", "data": "23/09/2026 17:38", "page": 48, "desc": "OS-013 assinada sem quadro de valores R$ (fls. 48–52)"}, "e5_ini": {"status": "OK", "data": "23/10/2026", "page": 714, "desc": "Faturado em Set/2026: 39,53 USN = R$ 69,57 (Prot. 25.609.621-8 fl. 714)"}},
    {"os_id": "OS_14", "protocolo": "25.980.025-1", "proc_file": "Processo_25.980.025-1_1.pdf", "e1_pt": {"status": "OK", "data": "20/05/2026 14:30", "page": 2, "desc": "Ofício SEFA + PT Modernização Fazendária IA (fls. 2–28)"}, "e2_enc": {"status": "OK", "data": "25/05/2026 10:00", "page": 29, "desc": "SEIA encaminha p/ dimensionamento"}, "e3_dim": {"status": "OK", "data": "10/06/2026", "page": 30, "desc": "Estimativa técnica nos autos: 29.031 USN/mês (R$ 51.094,56/mês)"}, "e4_os": {"status": "ALERTA", "data": "23/09/2026 17:38", "page": 35, "desc": "OS-014 assinada sem transcrever os 29.031 USN/mês para a OS (fls. 35–38)"}, "e5_ini": {"status": "OK", "data": "23/10/2026", "page": 719, "desc": "Faturado em Set/2026: 10,41 USN = R$ 18,32 (Prot. 25.609.621-8 fl. 719)"}},
    {"os_id": "OS_15", "protocolo": "25.980.422-2", "proc_file": "Processo_25.980.422-2_1.pdf", "e1_pt": {"status": "OK", "data": "20/05/2026 15:10", "page": 2, "desc": "Ofício SEFA + PT Automação Orçamentária (fls. 2–26)"}, "e2_enc": {"status": "OK", "data": "25/05/2026 10:15", "page": 27, "desc": "SEIA encaminha p/ dimensionamento"}, "e3_dim": {"status": "OK", "data": "10/06/2026", "page": 28, "desc": "Estimativa técnica nos autos: 13.615 USN/mês (R$ 23.962,40/mês)"}, "e4_os": {"status": "ALERTA", "data": "23/09/2026 17:38", "page": 33, "desc": "OS-015 assinada sem transcrever os 13.615 USN/mês para a OS (fls. 33–36)"}, "e5_ini": {"status": "OK", "data": "23/10/2026", "page": 724, "desc": "Faturado em Set/2026: 659,97 USN = R$ 1.161,55 (Prot. 25.609.621-8 fl. 724)"}},
    {"os_id": "OS_16", "protocolo": "25.982.581-5", "proc_file": "Processo_25.982.581-5_1.pdf", "e1_pt": {"status": "OK", "data": "20/05/2026 16:00", "page": 2, "desc": "Ofício SEFA + PT Modelos de Previsão (fls. 2–28)"}, "e2_enc": {"status": "OK", "data": "25/05/2026 10:30", "page": 29, "desc": "SEIA encaminha p/ dimensionamento"}, "e3_dim": {"status": "OK", "data": "10/06/2026", "page": 30, "desc": "Estimativa técnica nos autos: 14.520 USN/mês (R$ 25.555,20/mês)"}, "e4_os": {"status": "ALERTA", "data": "23/09/2026 17:38", "page": 34, "desc": "OS-016 assinada sem transcrever valores R$ (fls. 34–38)"}, "e5_ini": {"status": "ALERTA", "data": "23/10/2026", "page": 765, "desc": "Listada no Fechamento de Set/2026 sem consumo no mês (Prot. 25.609.621-8 fl. 765)"}},
    {"os_id": "OS_17", "protocolo": "25.982.893-8", "proc_file": "Processo_25.982.893-8_1.pdf", "e1_pt": {"status": "OK", "data": "20/05/2026 16:40", "page": 2, "desc": "Ofício REPR/SEFA + PT Agentes Inteligentes (fls. 2–26)"}, "e2_enc": {"status": "OK", "data": "25/05/2026 10:45", "page": 27, "desc": "SEIA encaminha p/ dimensionamento"}, "e3_dim": {"status": "OK", "data": "10/06/2026", "page": 28, "desc": "Estimativa técnica nos autos: 57.976 USN/mês (R$ 102.037,76/mês)"}, "e4_os": {"status": "ALERTA", "data": "23/09/2026 17:38", "page": 33, "desc": "OS-017 assinada sem transcrever valores R$ (fls. 33–36)"}, "e5_ini": {"status": "OK", "data": "23/10/2026", "page": 729, "desc": "Faturado em Set/2026: 19.571,05 USN = R$ 34.445,05 (Prot. 25.609.621-8 fl. 729)"}},
    {"os_id": "OS_18", "protocolo": "25.814.379-5", "proc_file": "Processo_25.814.379-5_1.pdf", "e1_pt": {"status": "OK", "data": "24/04/2026 14:00", "page": 2, "desc": "Ofício Defesa Civil + PT + SOW Plataforma PRISMA (fls. 2–38)"}, "e2_enc": {"status": "OK", "data": "30/04/2026 11:20", "page": 39, "desc": "SEIA encaminha à Celepar para levantamento de custos"}, "e3_dim": {"status": "OK", "data": "18/06/2026", "page": 42, "desc": "Dim. Inicial Celepar: 180.448,74 USN/mês + 244 UST/mês + 688 UST única = R$ 393,2k/mês (fls. 42–50)"}, "e4_os": {"status": "ALERTA", "data": "23/09/2026 17:38", "page": 53, "desc": "OS-018 assinada omitindo o quadro de R$ 393,2k/mês já aprovado nos autos (fls. 53–57)"}, "e5_ini": {"status": "OK", "data": "23/10/2026", "page": 734, "desc": "Faturado em Set/2026: 10,56 USN + 244 UST = R$ 75.621,99 (Prot. 25.609.621-8 fl. 734)"}},
    {"os_id": "OS_19", "protocolo": "26.197.434-7", "proc_file": "Processo_26.197.434-7_1.pdf", "e1_pt": {"status": "OK", "data": "02/07/2026 15:30", "page": 2, "desc": "Ofício DPE-PR + PT + SOW Data Foundation Defensoria (fls. 2–42)"}, "e2_enc": {"status": "OK", "data": "10/07/2026 14:00", "page": 43, "desc": "SEIA encaminha à Celepar para levantamento de custos"}, "e3_dim": {"status": "OK", "data": "14/08/2026", "page": 46, "desc": "Dim. Inicial: 142.045,00 USN/mês + 156 UST/mês = R$ 298,3k/mês (fls. 46–52)"}, "e4_os": {"status": "ALERTA", "data": "23/09/2026 17:38", "page": 54, "desc": "OS-019 assinada sem transcrever a tabela de R$ 298,3k/mês (fls. 54–57)"}, "e5_ini": {"status": "OK", "data": "23/10/2026", "page": 743, "desc": "Faturado em Set/2026: 144.891,02 USN + 384 UST = R$ 373.990,60 (Prot. 25.609.621-8 fl. 743)"}},
    {"os_id": "OS_20", "protocolo": "26.135.424-1", "proc_file": "Processo_26.135.424-1_1.pdf", "e1_pt": {"status": "OK", "data": "18/06/2026 16:10", "page": 2, "desc": "Ofício PGE + PT + SOW Projeto Consultivo IA (fls. 2–30)"}, "e2_enc": {"status": "OK", "data": "25/06/2026 11:00", "page": 31, "desc": "SEIA encaminha à Celepar para levantamento de custos"}, "e3_dim": {"status": "CRITICO", "data": "PENDENTE CELEPAR", "page": 34, "desc": "Celepar não enviou o Dimensionamento Inicial nos autos"}, "e4_os": {"status": "ALERTA", "data": "14/09/2026 17:20", "page": 35, "desc": "Emitida c/ numeração colidente ('OS 013/2026') e c/ BLOQUEIO DE PRODUÇÃO até orçamento (fls. 35–38)"}, "e5_ini": {"status": "OK", "data": "23/10/2026", "page": 765, "desc": "Listada sem consumo (R$ 0,00) no Fechamento de Set/2026 (Prot. 25.609.621-8 fl. 765)"}},
    {"os_id": "OS_21", "protocolo": "25.565.814-0", "proc_file": "Processo_25.565.814-0_1.pdf", "e1_pt": {"status": "OK", "data": "05/03/2026 14:20", "page": 2, "desc": "Ofício IAT/TECPAR + PT Plataforma Inteligência Ambiental (fls. 2–58)"}, "e2_enc": {"status": "OK", "data": "12/03/2026 11:00", "page": 59, "desc": "SEIA encaminha à Celepar para levantamento de custos"}, "e3_dim": {"status": "ALERTA", "data": "PENDENTE", "page": 64, "desc": "Rodou na OS-006; desmembrada em Set/2026 sem tabela USN no processo"}, "e4_os": {"status": "ALERTA", "data": "23/09/2026 17:38", "page": 66, "desc": "OS-021 assinada sem quadro de valores R$ (fls. 66–70)"}, "e5_ini": {"status": "OK", "data": "23/10/2026", "page": 749, "desc": "Faturado em Set/2026: 11.918,50 USN = R$ 20.976,56 (Prot. 25.609.621-8 fl. 749)"}},
    {"os_id": "OS_22", "protocolo": "26.259.656-7", "proc_file": "Processo_26.259.656-7_1.pdf", "e1_pt": {"status": "OK", "data": "15/07/2026 15:00", "page": 2, "desc": "Ofício SESP + PT + SOW Delegacia Eletrônica IA (fls. 2–38)"}, "e2_enc": {"status": "OK", "data": "22/07/2026 14:10", "page": 39, "desc": "SEIA encaminha à Celepar para levantamento de custos"}, "e3_dim": {"status": "CRITICO", "data": "PENDENTE CELEPAR", "page": 43, "desc": "Celepar não enviou o Dimensionamento Inicial nos autos"}, "e4_os": {"status": "ALERTA", "data": "18/09/2026 16:30", "page": 44, "desc": "OS-022 assinada c/ BLOQUEIO DE PRODUÇÃO até envio do orçamento (fls. 44–47)"}, "e5_ini": {"status": "CRITICO", "data": "23/10/2026", "page": 766, "desc": "ALERTA: No Fechamento de Set/2026 (fl. 766), Celepar cobrou 10,35 USN (R$ 18,22) da OS-022 sem RMEC individual!"}},
    {"os_id": "OS_23", "protocolo": "26.528.882-0", "proc_file": "Processo_26.528.882-0_1.pdf", "e1_pt": {"status": "OK", "data": "01/10/2026 16:20", "page": 2, "desc": "Termo de Demanda SEIA Recaptcha Enterprise (fls. 2–6)"}, "e2_enc": {"status": "OK", "data": "01/10/2026 16:30", "page": 4, "desc": "Desmembramento imediato da OS-006 p/ controle de consumo Recaptcha"}, "e3_dim": {"status": "OK", "data": "01/10/2026", "page": 5, "desc": "Dimensionado em 16.000 USN/mês (R$ 28.160,00/mês) e 0 UST"}, "e4_os": {"status": "OK", "data": "02/10/2026 11:15", "page": 6, "desc": "OS-023 assinada com valor explícito de R$ 28.160,00/mês (fls. 6–8)"}, "e5_ini": {"status": "OK", "data": "23/10/2026", "page": 754, "desc": "Faturado em Set/2026: 10.364,19 USN = R$ 18.240,97 (Prot. 25.609.621-8 fl. 754)"}},
    {"os_id": "OS_24", "protocolo": "26.647.584-5", "proc_file": "Processo_26.647.584-5_1.pdf", "e1_pt": {"status": "OK", "data": "13/10/2026 14:10", "page": 2, "desc": "Ofício SESP + PT + SOW Moodle / Ensino Policial (fls. 2–38)"}, "e2_enc": {"status": "OK", "data": "16/10/2026 17:00", "page": 42, "desc": "SEIA solicita precificação em USN/UST à Celepar após emitir OS"}, "e3_dim": {"status": "CRITICO", "data": "AGUARDANDO CELEPAR", "page": 42, "desc": "Orçamento solicitado a posteriori (prazo de 10 dias úteis até 30/10/2026)"}, "e4_os": {"status": "CRITICO", "data": "16/10/2026 16:50", "page": 39, "desc": "OS-024 assinada liberando PRODUÇÃO IMEDIATA sem orçamento prévio (fls. 39–41)"}, "e5_ini": {"status": "ALERTA", "data": "AGUARDANDO", "page": 42, "desc": "Emitida em 16/10/2026; entrará no RMEC de Outubro/2026"}},
    {"os_id": "OS_25", "protocolo": "26.666.085-5", "proc_file": "Processo_26.666.085-5_1.pdf", "e1_pt": {"status": "ALERTA", "data": "14/10/2026 15:20", "page": 2, "desc": "Ofício SESP + SOW Projeto Tessera (sem PT no modelo SEIA, fls. 2–23)"}, "e2_enc": {"status": "OK", "data": "16/10/2026 17:05", "page": 27, "desc": "SEIA solicita precificação em USN/UST à Celepar"}, "e3_dim": {"status": "CRITICO", "data": "AGUARDANDO CELEPAR", "page": 27, "desc": "Orçamento solicitado a posteriori"}, "e4_os": {"status": "CRITICO", "data": "16/10/2026 16:55", "page": 24, "desc": "OS-025 assinada liberando PRODUÇÃO IMEDIATA sem orçamento prévio (fls. 24–26)"}, "e5_ini": {"status": "ALERTA", "data": "AGUARDANDO", "page": 27, "desc": "Emitida em 16/10/2026; entrará no RMEC de Outubro/2026"}},
    {"os_id": "OS_26", "protocolo": "26.693.860-8", "proc_file": "Processo_26.693.860-8_1.pdf", "e1_pt": {"status": "OK", "data": "15/10/2026 16:00", "page": 2, "desc": "Ofício SESP + PT + SOW Data Lake Segurança Pública (fls. 2–23)"}, "e2_enc": {"status": "OK", "data": "16/10/2026 17:10", "page": 27, "desc": "SEIA solicita precificação em USN/UST à Celepar"}, "e3_dim": {"status": "CRITICO", "data": "AGUARDANDO CELEPAR", "page": 27, "desc": "Orçamento solicitado a posteriori"}, "e4_os": {"status": "CRITICO", "data": "16/10/2026 16:58", "page": 24, "desc": "OS-026 assinada liberando PRODUÇÃO IMEDIATA sem orçamento prévio (fls. 24–26)"}, "e5_ini": {"status": "ALERTA", "data": "AGUARDANDO", "page": 27, "desc": "Emitida em 16/10/2026; entrará no RMEC de Outubro/2026"}},
    {"os_id": "OS_27", "protocolo": "26.800.501-3", "proc_file": "Processo_26.800.501-3_1.pdf", "e1_pt": {"status": "CRITICO", "data": "27/10/2026 11:30", "page": 2, "desc": "FALHA DOCUMENTAL: Protocolo tem apenas 4 páginas; PT e SOW citados na OS NÃO foram anexados!"}, "e2_enc": {"status": "OK", "data": "27/10/2026 12:00", "page": 4, "desc": "Encaminhado à Celepar com a OS-027 já assinada"}, "e3_dim": {"status": "CRITICO", "data": "SEM ORÇAMENTO", "page": 4, "desc": "Nenhum levantamento de custos USN/UST nos autos"}, "e4_os": {"status": "CRITICO", "data": "27/10/2026 11:50", "page": 3, "desc": "OS-027 (Censo Rebanhos ADAPAR) assinada liberando PRODUÇÃO IMEDIATA sem PT e sem orçamento (fls. 3–4)"}, "e5_ini": {"status": "ALERTA", "data": "AGUARDANDO", "page": 4, "desc": "Emitida em 27/10/2026 (há 2 dias da data de corte)"}}
]


def populate_structured_tables(conn: sqlite3.Connection):
    """Popula `rmec_monthly_os` e `chronological_events` com todos os marcos auditados."""
    cur = conn.cursor()
    cur.execute("DELETE FROM rmec_monthly_os;")
    cur.execute("DELETE FROM chronological_events;")

    # 1. Inserir todos os registros de RMEC mensal por OS
    for cycle in RMEC_MONTHLY_CYCLES:
        comp = cycle["competencia"]
        ordem = cycle["ordem"]
        nf_info = cycle["procMaeNF"]
        for item in cycle["itensOS"]:
            rec_id = f"RMEC_{ordem:02d}_{item['os_id']}"
            cur.execute("""
            INSERT INTO rmec_monthly_os
            (id, competencia, competencia_ordem, os_id, usn, valor_usn, ust, valor_ust, valor_total, rmec_page, fechamento_page, atesto_page, atesto_data, nf_usn, nf_ust, nl_numeros, ob_numeros, proc_mae_page, status_ciclo, observacao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rec_id, comp, ordem, item["os_id"],
                item["usn"], item["valor_usn"], item["ust"], item["valor_ust"], item["total"],
                item["rmec_page"], cycle["fechamentoPageNum"], cycle["atestoPageNum"], cycle["atestoData"],
                nf_info["nfUSN"], nf_info["nfUST"], nf_info["nl"], nf_info["ob"], nf_info["procMaePage"],
                nf_info["statusEtapa7a9"], item["obs"]
            ))

    # 2. Construir a Linha do Tempo Cronológica Unificada (Contrato + 27 OSs Etapas 1..5 + 8 Ciclos Mensais Etapas 6..10)
    events = [
        {
            "event_id": "EVT_CONTRATO_01",
            "date_br": "18/11/2025 16:00",
            "protocolo": "24.574.062-0",
            "os_id": "CONTRATO_GERAL",
            "competencia": "Novembro/2025",
            "step_number": 0,
            "step_code": "MARCO_CONTRATUAL",
            "actor_from": "SEIA/PR",
            "actor_to": "CELEPAR",
            "doc_type": "CONTRATO_ASSINADO",
            "title": "Assinatura do Contrato Administrativo nº 9291/2025 (GMS 47396/2025)",
            "detail": "Celebrado por Dispensa nº 23/2025 no valor global de R$ 133.155.352,08 para 36 meses (68.089.068 USN @ R$ 1,76 + 42.984 UST @ R$ 309,85).",
            "usn": 68089068.0,
            "ust": 42984.0,
            "valor_brl": 133155352.08,
            "page_num": 685,
            "pdf_link": "../Contratoseia_ASSINADO.pdf"
        },
        {
            "event_id": "EVT_CONTRATO_02",
            "date_br": "24/11/2025 09:00",
            "protocolo": "24.574.062-0",
            "os_id": "CONTRATO_GERAL",
            "competencia": "Novembro/2025",
            "step_number": 0,
            "step_code": "MARCO_CONTRATUAL",
            "actor_from": "SEIA/GAB",
            "actor_to": "Comissão Fiscalização",
            "doc_type": "RESOLUCAO_FISCALIZACAO",
            "title": "Publicação da Resolução SEIA nº 129/2025 (Designação de Gestor e Fiscal)",
            "detail": "Designa José Eduardo Padilha de Sousa como Gestor e Diogo Luiz de Lima como Fiscal Técnico do Contrato 9291/2025 (sem designar suplentes).",
            "usn": 0.0,
            "ust": 0.0,
            "valor_brl": 0.0,
            "page_num": 698,
            "pdf_link": "../Processo_24.574.062-0_1.pdf#page=698"
        },
        {
            "event_id": "EVT_NE_2025",
            "date_br": "11/12/2025 14:00",
            "protocolo": "24.574.062-0",
            "os_id": "CONTRATO_GERAL",
            "competencia": "Dezembro/2025",
            "step_number": 0,
            "step_code": "EMPENHO_SIAFIC",
            "actor_from": "SEIA/NFS",
            "actor_to": "SIAFIC",
            "doc_type": "NOTA_EMPENHO",
            "title": "Emissão da Nota de Empenho Inicial 2025NE000365 (R$ 3.200.000,00)",
            "detail": "Primeiro empenho emitido no exercício de 2025 (não executado em 2025).",
            "usn": 0.0,
            "ust": 0.0,
            "valor_brl": 3200000.00,
            "page_num": 710,
            "pdf_link": "../Processo_24.574.062-0_1.pdf#page=710"
        },
        {
            "event_id": "EVT_NE_2026_01",
            "date_br": "27/02/2026 11:00",
            "protocolo": "24.574.062-0",
            "os_id": "CONTRATO_GERAL",
            "competencia": "Fevereiro/2026",
            "step_number": 0,
            "step_code": "EMPENHO_SIAFIC",
            "actor_from": "SEIA/NFS",
            "actor_to": "SIAFIC",
            "doc_type": "NOTA_EMPENHO",
            "title": "Emissão da Nota de Empenho 2026NE000055 (R$ 13.315.536,00 — 10% do Contrato)",
            "detail": "Cobertura orçamentária do 1º semestre de 2026 (posteriormente 100% consumida pelas NFs de Fev a Ago/2026).",
            "usn": 0.0,
            "ust": 0.0,
            "valor_brl": 13315536.00,
            "page_num": 755,
            "pdf_link": "../Processo_24.574.062-0_1.pdf#page=755"
        },
        {
            "event_id": "EVT_NE_2026_02",
            "date_br": "07/10/2026 15:30",
            "protocolo": "24.574.062-0",
            "os_id": "CONTRATO_GERAL",
            "competencia": "Outubro/2026",
            "step_number": 0,
            "step_code": "EMPENHO_SIAFIC",
            "actor_from": "SEIA/NFS",
            "actor_to": "SIAFIC",
            "doc_type": "NOTA_EMPENHO",
            "title": "Emissão da Nota de Empenho Complementar 2026NE000298 (R$ 13.315.536,00)",
            "detail": "Suplementação aprovada no Prot. 26.551.047-7 totalizando R$ 26.631.072,00 empenhados em 2026 (exatos 20,00% do teto contratual do Ano 1).",
            "usn": 0.0,
            "ust": 0.0,
            "valor_brl": 13315536.00,
            "page_num": 898,
            "pdf_link": "../Processo_24.574.062-0_1.pdf#page=898"
        }
    ]

    # Adicionar eventos das Etapas 1 a 4 para cada uma das 27 OSs (com datas reais extraídas)
    for row in OS_WORKFLOW_STEPS_1_TO_5:
        os_id = row["os_id"]
        prot = row["protocolo"]
        pf = row["proc_file"]
        pdf_base = f"../Ordens_De_Serviço/{os_id}/{pf}"

        # Etapa 1: Solicitação + PT
        if re.search(r"\d{2}/\d{2}/\d{4}", row["e1_pt"]["data"]):
            events.append({
                "event_id": f"EVT_{os_id}_E1",
                "date_br": row["e1_pt"]["data"],
                "protocolo": prot,
                "os_id": os_id,
                "competencia": "",
                "step_number": 1,
                "step_code": "ETAPA_01_SOLICITACAO_PT",
                "actor_from": "Órgão Demandante",
                "actor_to": "SEIA",
                "doc_type": "PLANO_DE_TRABALHO",
                "title": f"[Etapa 1 - {os_id}] Abertura da Demanda, Plano de Trabalho e Cronograma",
                "detail": row["e1_pt"]["desc"],
                "usn": 0.0,
                "ust": 0.0,
                "valor_brl": 0.0,
                "page_num": row["e1_pt"]["page"],
                "pdf_link": f"{pdf_base}#page={row['e1_pt']['page']}"
            })

        # Etapa 2: Encaminhamento SEIA -> Celepar
        if re.search(r"\d{2}/\d{2}/\d{4}", row["e2_enc"]["data"]):
            events.append({
                "event_id": f"EVT_{os_id}_E2",
                "date_br": row["e2_enc"]["data"],
                "protocolo": prot,
                "os_id": os_id,
                "competencia": "",
                "step_number": 2,
                "step_code": "ETAPA_02_ENCAMINHAMENTO_CELEPAR",
                "actor_from": "SEIA/DIA",
                "actor_to": "CELEPAR",
                "doc_type": "DESPACHO_SOLICITACAO_CUSTOS",
                "title": f"[Etapa 2 - {os_id}] SEIA encaminha protocolo à CELEPAR para levantar custos",
                "detail": row["e2_enc"]["desc"],
                "usn": 0.0,
                "ust": 0.0,
                "valor_brl": 0.0,
                "page_num": row["e2_enc"]["page"],
                "pdf_link": f"{pdf_base}#page={row['e2_enc']['page']}"
            })

        # Etapa 3: Retorno de Custos Celepar (Dimensionamento Inicial)
        m_d3 = re.search(r"\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2})?", row["e3_dim"]["data"])
        if m_d3:
            events.append({
                "event_id": f"EVT_{os_id}_E3",
                "date_br": m_d3.group(0),
                "protocolo": prot,
                "os_id": os_id,
                "competencia": "",
                "step_number": 3,
                "step_code": "ETAPA_03_RETORNO_CUSTOS_CELEPAR",
                "actor_from": "CELEPAR",
                "actor_to": "SEIA/DIA",
                "doc_type": "DIMENSIONAMENTO_INICIAL",
                "title": f"[Etapa 3 - {os_id}] CELEPAR retorna Dimensionamento Inicial (Custos USN/UST)",
                "detail": row["e3_dim"]["desc"],
                "usn": 0.0,
                "ust": 0.0,
                "valor_brl": 0.0,
                "page_num": row["e3_dim"]["page"],
                "pdf_link": f"{pdf_base}#page={row['e3_dim']['page']}"
            })

        # Etapa 4: Emissão da OS pela SEIA
        m_d4 = re.search(r"\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2})?", row["e4_os"]["data"])
        if m_d4:
            events.append({
                "event_id": f"EVT_{os_id}_E4",
                "date_br": m_d4.group(0),
                "protocolo": prot,
                "os_id": os_id,
                "competencia": "",
                "step_number": 4,
                "step_code": "ETAPA_04_EMISSAO_OS_SEIA",
                "actor_from": "SEIA/DIA",
                "actor_to": "CELEPAR",
                "doc_type": "ORDEM_DE_SERVICO",
                "title": f"[Etapa 4 - {os_id}] SEIA emite Ordem de Serviço para execução pela CELEPAR",
                "detail": row["e4_os"]["desc"],
                "usn": 0.0,
                "ust": 0.0,
                "valor_brl": 0.0,
                "page_num": row["e4_os"]["page"],
                "pdf_link": f"{pdf_base}#page={row['e4_os']['page']}"
            })

    # Adicionar eventos das Etapas 6 a 10 para cada um dos 8 ciclos mensais (Fev a Set/2026)
    for cycle in RMEC_MONTHLY_CYCLES:
        comp = cycle["competencia"]
        ord_num = cycle["ordem"]
        nf_info = cycle["procMaeNF"]
        m_sub = re.search(r"\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2})?", cycle["dataSubmissaoCelepar"])
        dt_sub = m_sub.group(0) if m_sub else "18/03/2026 11:34"

        # Etapa 6A: Submissão dos RMECs e Fechamento Mensal pela Celepar no 25.609.621-8
        events.append({
            "event_id": f"EVT_CICLO_{ord_num:02d}_E6_RMEC",
            "date_br": dt_sub,
            "protocolo": "25.609.621-8",
            "os_id": "COBRANCA_RMEC",
            "competencia": comp,
            "step_number": 6,
            "step_code": "ETAPA_06_RMEC_E_ATESTO_SEIA",
            "actor_from": "CELEPAR/GPVR",
            "actor_to": "SEIA/Fiscalização",
            "doc_type": "FECHAMENTO_MENSAL",
            "title": f"[Etapa 6 - {comp}] CELEPAR protocola RMECs ({len(cycle['itensOS'])} OSs) e Relatório de Fechamento Mensal",
            "detail": f"Medição mensal referente ao período {cycle['periodoExecucao']}: {cycle['usnTotal']:,.2f} USN (R$ {cycle['valorUSNTotal']:,.2f}) + {cycle['ustTotal']:,.2f} UST (R$ {cycle['valorUSTTotal']:,.2f}) = Total R$ {cycle['valorTotalFechamento']:,.2f} ({cycle['fechamentoPages']} do Prot. 25.609.621-8).",
            "usn": cycle["usnTotal"],
            "ust": cycle["ustTotal"],
            "valor_brl": cycle["valorTotalFechamento"],
            "page_num": cycle["fechamentoPageNum"],
            "pdf_link": f"../Processo_25.609.621-8_1.pdf#page={cycle['fechamentoPageNum']}"
        })

        # Se for Março/2026, adicionar o evento explícito da Devolução/Glosa pela SEIA em 29/04/2026 (fls. 86-88) e Retificação em 30/04/2026
        if ord_num == 2:
            events.append({
                "event_id": "EVT_CICLO_02_E6_GLOSA",
                "date_br": "29/04/2026 10:35",
                "protocolo": "25.609.621-8",
                "os_id": "OS_02",
                "competencia": comp,
                "step_number": 6,
                "step_code": "ETAPA_06_RMEC_E_ATESTO_SEIA",
                "actor_from": "SEIA/Fiscalização",
                "actor_to": "CELEPAR",
                "doc_type": "GLOSA_DEVOLUCAO_SEIA",
                "title": "[Etapa 6 - Março/2026] SEIA devolve relatórios de cobrança à CELEPAR para retificação (Glosa Técnica)",
                "detail": "Fiscal Diogo Luiz de Lima recusa a 1ª submissão (fls. 86–88): aponta duplicidade de 7 atas de fev/2026 na OS-002, erro de soma de R$ 10,00 na OS-002 (R$ 389.243,22 vs R$ 389.233,22) e divergência de centavos na OS-006. Celepar junta versão retificada em 30/04/2026 (fls. 89–117).",
                "usn": 201780.81,
                "ust": 400.0,
                "valor_brl": 479074.22,
                "page_num": 86,
                "pdf_link": "../Processo_25.609.621-8_1.pdf#page=86"
            })

        # Etapa 6B: Atesto Técnico da SEIA no 25.609.621-8
        m_at = re.search(r"\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2})?", cycle["atestoData"])
        if m_at:
            events.append({
                "event_id": f"EVT_CICLO_{ord_num:02d}_E6_ATESTO",
                "date_br": m_at.group(0),
                "protocolo": "25.609.621-8",
                "os_id": "COBRANCA_RMEC",
                "competencia": comp,
                "step_number": 6,
                "step_code": "ETAPA_06_RMEC_E_ATESTO_SEIA",
                "actor_from": "SEIA/Fiscal & Gestor",
                "actor_to": "CELEPAR / SEIA-NAS",
                "doc_type": "ATESTO_SEIA",
                "title": f"[Etapa 6 - {comp}] SEIA emite Atesto de Prestação de Serviço no Prot. 25.609.621-8 ({cycle['atestoPages']})",
                "detail": cycle["detalheFiscalizacao"],
                "usn": cycle["usnTotal"],
                "ust": cycle["ustTotal"],
                "valor_brl": cycle["valorTotalFechamento"],
                "page_num": cycle["atestoPageNum"],
                "pdf_link": f"../Processo_25.609.621-8_1.pdf#page={cycle['atestoPageNum']}"
            })

        # Etapas 7, 8 e 9 no Processo Mãe 24.574.062-0 (para Fev a Ago/2026)
        m_nas = re.search(r"\d{2}/\d{2}/\d{4}", nf_info["encaminhamentoNAS"])
        if m_nas:
            events.append({
                "event_id": f"EVT_CICLO_{ord_num:02d}_E7_NAS",
                "date_br": m_nas.group(0) + " 14:00",
                "protocolo": "24.574.062-0",
                "os_id": "CONTRATO_GERAL",
                "competencia": comp,
                "step_number": 7,
                "step_code": "ETAPA_07_NF_ATESTO_PARA_NAS",
                "actor_from": "SEIA/Fiscalização",
                "actor_to": "SEIA/NAS",
                "doc_type": "NOTA_FISCAL",
                "title": f"[Etapa 7 - {comp}] Juntada das Notas Fiscais ({nf_info['nfUSN']} + {nf_info['nfUST']}) + Atesto e envio ao NAS",
                "detail": f"No Processo Mãe 24.574.062-0 (fl. {nf_info['procMaePage']}), são anexadas as NFs de USN e UST somando R$ {nf_info['valorTotalPago']:,.2f} e encaminhadas ao Núcleo Administrativo Setorial (NAS).",
                "usn": cycle["usnTotal"],
                "ust": cycle["ustTotal"],
                "valor_brl": nf_info["valorTotalPago"],
                "page_num": nf_info["procMaePage"],
                "pdf_link": f"../Processo_24.574.062-0_1.pdf#page={nf_info['procMaePage']}"
            })

        if re.search(r"\d{2}/\d{2}/\d{4}", nf_info["lancamentoGMS"]):
            events.append({
                "event_id": f"EVT_CICLO_{ord_num:02d}_E8_GMS",
                "date_br": nf_info["lancamentoGMS"] + " 15:30",
                "protocolo": "24.574.062-0",
                "os_id": "CONTRATO_GERAL",
                "competencia": comp,
                "step_number": 8,
                "step_code": "ETAPA_08_NAS_GMS_PARA_NFS",
                "actor_from": "SEIA/NAS",
                "actor_to": "SEIA/NFS",
                "doc_type": "LIQUIDACAO_SIAFIC",
                "title": f"[Etapa 8 - {comp}] NAS realiza lançamento no GMS e encaminha ao NFS para liquidação ({nf_info['nl']})",
                "detail": f"Núcleo Administrativo Setorial registra o recebimento no GMS 47396/2025 e remete ao Núcleo Financeiro Setorial (NFS), que emite a {nf_info['nl']}.",
                "usn": cycle["usnTotal"],
                "ust": cycle["ustTotal"],
                "valor_brl": nf_info["valorTotalPago"],
                "page_num": nf_info["procMaePage"] + 4,
                "pdf_link": f"../Processo_24.574.062-0_1.pdf#page={nf_info['procMaePage'] + 4}"
            })

        m_ob = re.search(r"(\d{2}/\d{2}/\d{4})", nf_info["ob"])
        if m_ob:
            events.append({
                "event_id": f"EVT_CICLO_{ord_num:02d}_E9_OB",
                "date_br": m_ob.group(1) + " 17:00",
                "protocolo": "24.574.062-0",
                "os_id": "CONTRATO_GERAL",
                "competencia": comp,
                "step_number": 9,
                "step_code": "ETAPA_09_NFS_PAGAMENTO_OB_NAS",
                "actor_from": "SEIA/NFS",
                "actor_to": "SEIA/NAS",
                "doc_type": "PAGAMENTO_OB",
                "title": f"[Etapa 9 - {comp}] NFS efetua pagamento via Ordem Bancária ({nf_info['ob']}) e devolve ao NAS",
                "detail": f"Pagamento bancário de R$ {nf_info['valorTotalPago']:,.2f} efetivado no SIAFIC ({nf_info['pd']} / {nf_info['ob']}), comprovantes juntados ao protocolo 24.574.062-0 e autos devolvidos ao NAS para arquivamento.",
                "usn": cycle["usnTotal"],
                "ust": cycle["ustTotal"],
                "valor_brl": nf_info["valorTotalPago"],
                "page_num": nf_info["procMaePage"] + 10,
                "pdf_link": f"../Processo_24.574.062-0_1.pdf#page={nf_info['procMaePage'] + 10}"
            })

    # Ordenar eventos estritamente por data ISO + página
    for ev in events:
        ev["date_iso"] = br_to_iso_date(ev["date_br"])

    events.sort(key=lambda x: (x["date_iso"], x["page_num"]))

    for ev in events:
        cur.execute("""
        INSERT INTO chronological_events
        (event_id, date_iso, date_br, protocolo, os_id, competencia, step_number, step_code, actor_from, actor_to, doc_type, title, detail, usn, ust, valor_brl, page_num, pdf_link)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ev["event_id"], ev["date_iso"], ev["date_br"], ev["protocolo"], ev["os_id"],
            ev["competencia"], ev["step_number"], ev["step_code"], ev["actor_from"], ev["actor_to"],
            ev["doc_type"], ev["title"], ev["detail"], ev["usn"], ev["ust"], ev["valor_brl"],
            ev["page_num"], ev["pdf_link"]
        ))

    conn.commit()
    return events


def semantic_vector_search(conn: sqlite3.Connection, query: str, top_k: int = 15, filter_os: str = "TODOS") -> list:
    """
    Executa busca híbrida (Similaridade Vetorial de Cosseno + Match Léxico BM25) no SQLite
    retornando as páginas exatas e o resultado pré-processado pela IA (Zero consumo de tokens!).
    """
    q_clean = (query or "").strip()
    if not q_clean:
        return []
    q_emb = compute_embedding(q_clean)
    q_tokens = [t for t in re.findall(r"[a-záàâãéêíóôõúç0-9_.-]{2,}", q_clean.lower())]

    cur = conn.cursor()
    if filter_os and filter_os != "TODOS":
        cur.execute("SELECT chunk_id, doc_id, protocolo, os_id, competencia, doc_type, page_num, pdf_link, snippet, ai_summary, embedding_json FROM vector_chunks WHERE os_id = ?", (filter_os,))
    else:
        cur.execute("SELECT chunk_id, doc_id, protocolo, os_id, competencia, doc_type, page_num, pdf_link, snippet, ai_summary, embedding_json FROM vector_chunks")

    scored = []
    for row in cur.fetchall():
        chunk_id, doc_id, protocolo, os_id, competencia, doc_type, page_num, pdf_link, snippet, ai_summary, emb_json = row
        emb = json.loads(emb_json)
        cos_sim = cosine_similarity(q_emb, emb)

        haystack = (ai_summary + " " + snippet + " " + protocolo + " " + os_id + " " + doc_type).lower()
        lex_boost = 0.0
        for qt in q_tokens:
            if qt in haystack:
                lex_boost += 0.18
        if q_clean.lower() in haystack:
            lex_boost += 0.35

        final_score = round(cos_sim + lex_boost, 4)
        if final_score > 0.08:
            scored.append({
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "protocolo": protocolo,
                "os_id": os_id,
                "competencia": competencia,
                "doc_type": doc_type,
                "page_num": page_num,
                "pdf_link": pdf_link,
                "snippet": snippet,
                "ai_summary": ai_summary,
                "score": final_score
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def patch_frontend_data_js(conn: sqlite3.Connection, ingestion_report: dict, events: list):
    """
    Atualiza `plataforma-controle-9291/js/data.js`:
    1. Corrige todos os caminhos `Processo_XX.XXX.XXX-X.pdf` das 27 OSs para `_1.pdf` (nomes reais na pasta).
    2. Atualiza os status de RMEC das OSs que possuem RMEC no Processo 25.609.621-8.
    3. Injeta `window.CONTRACT_DATA.fluxoInstrucoes`, `window.CONTRACT_DATA.ciclosRMEC`,
       `window.CONTRACT_DATA.linhaTempoCronologica` e `window.CONTRACT_DATA.vectorDBStatus`.
    """
    data_js_path = os.path.join(ROOT_DIR, "plataforma-controle-9291", "js", "data.js")
    with open(data_js_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Corrigir links dos processos nas subpastas OS_01 a OS_27 para incluir _1.pdf
    content = re.sub(
        r'(\.\./Ordens_De_Serviço/OS_\d{2}/Processo_[\d\.\-]+)(?<!_1)\.pdf',
        r'\1_1.pdf',
        content
    )

    # 2. Corrigir páginas do Processo Mãe 24.574.062-0_1.pdf (904 páginas reais no PDF)
    page_replacements = {
        "fls. 1477–1492": "fls. 762–780 (RMEC Fev/26: Prot. 25.609.621-8 fls. 21–44)",
        "#page=1477": "#page=762",
        "fls. 1493–1511": "fls. 782–800 (RMEC Mar/26: Prot. 25.609.621-8 fls. 45–119)",
        "#page=1493": "#page=782",
        "fls. 1512–1530": "fls. 802–819 (RMEC Abr/26: Prot. 25.609.621-8 fls. 120–189)",
        "#page=1512": "#page=802",
        "fls. 1531–1550": "fls. 820–844 (RMEC Mai/26: Prot. 25.609.621-8 fls. 190–281)",
        "#page=1531": "#page=820",
        "fls. 1551–1570": "fls. 845–867 (RMEC Jun/26: Prot. 25.609.621-8 fls. 282–410)",
        "#page=1551": "#page=845",
        "fls. 1571–1588": "fls. 868–888 (RMEC Jul/26: Prot. 25.609.621-8 fls. 411–553)",
        "#page=1571": "#page=868",
        "fls. 1589–1613": "fls. 889–904 (RMEC Ago/26: Prot. 25.609.621-8 fls. 554–637)",
        "#page=1589": "#page=889",
        "#page=1470": "#page=755"
    }
    for old_s, new_s in page_replacements.items():
        content = content.replace(old_s, new_s)

    # Remover bloco extra anterior se já existir
    marker = "// === INICIO_EXTENSAO_CRONOLOGICA_VETORIAL ==="
    if marker in content:
        content = content.split(marker)[0].rstrip()

    # Consultar watermarks do banco para embutir no snapshot inicial do frontend
    cur = conn.cursor()
    cur.execute("SELECT doc_id, protocolo, os_id, rel_path, file_size, total_pages, last_ingested_page, first_page_sha256, last_page_sha256, tokens_cached, last_sync_at, status_integrity FROM document_watermarks ORDER BY doc_id")
    watermarks = [
        {
            "doc_id": r[0], "protocolo": r[1], "os_id": r[2], "rel_path": r[3],
            "file_size": r[4], "total_pages": r[5], "last_ingested_page": r[6],
            "first_page_sha256": r[7][:16], "last_page_sha256": r[8][:16],
            "tokens_cached": r[9], "last_sync_at": r[10], "status_integrity": r[11]
        }
        for r in cur.fetchall()
    ]

    cur.execute("SELECT COUNT(*) FROM vector_chunks")
    total_chunks = cur.fetchone()[0]

    extension_payload = {
        "protocoloRMEC": "25.609.621-8",
        "linkProtocoloRMEC": "../Processo_25.609.621-8_1.pdf",
        "ciclosRMEC": RMEC_MONTHLY_CYCLES,
        "fluxoInstrucoesOS": OS_WORKFLOW_STEPS_1_TO_5,
        "linhaTempoCronologica": events,
        "vectorDBStatus": {
            "dbPath": "db/contrato_9291.sqlite",
            "engine": "SQLite Hybrid Event-Store + Normalized L2 Vector Index (128-dim) + SHA-256 Page Watermark",
            "totalDocuments": len(watermarks),
            "totalPagesMonitored": sum(w["total_pages"] for w in watermarks),
            "totalVectorChunks": total_chunks,
            "totalTokensCached": sum(w["tokens_cached"] for w in watermarks),
            "lastSyncAt": ingestion_report["timestamp"],
            "watermarks": watermarks
        }
    }

    ext_js = (
        f"\n\n{marker}\n"
        f"Object.assign(window.CONTRACT_DATA, {json.dumps(extension_payload, ensure_ascii=False, indent=2)});\n"
        f"// Atualizar flag rmecApresentado nas OSs com medição comprovada no Processo 25.609.621-8\n"
        f"(function() {{\n"
        f"  const osComRMEC = new Set(['OS_01','OS_02','OS_03','OS_04','OS_05','OS_06','OS_07','OS_08','OS_09','OS_10','OS_11','OS_12','OS_13','OS_14','OS_15','OS_17','OS_18','OS_19','OS_21','OS_23']);\n"
        f"  window.CONTRACT_DATA.ordensServico.forEach(os => {{\n"
        f"    if (osComRMEC.has(os.id)) {{\n"
        f"      os.camadaExecucao.rmecApresentado = true;\n"
        f"      os.camadaExecucao.evidencias += ' • RMEC juntado no Processo 25.609.621-8.';\n"
        f"    }}\n"
        f"  }});\n"
        f"  // Adicionar o Processo 25.609.621-8 na lista de documentos estruturantes\n"
        f"  if (!window.CONTRACT_DATA.documentos.some(d => d.protocolo === '25.609.621-8')) {{\n"
        f"    window.CONTRACT_DATA.documentos.splice(2, 0, {{\n"
        f"      categoria: 'Medição RMEC & Atestos SEIA',\n"
        f"      titulo: 'Processo de Relatórios de Execução (RMEC), Fechamentos Mensais e Atestos SEIA',\n"
        f"      protocolo: '25.609.621-8',\n"
        f"      paginas: '766 págs.',\n"
        f"      caminho: '../Processo_25.609.621-8_1.pdf#page=21',\n"
        f"      destaque: 'Contém todos os RMECs por OS, Relatórios de Fechamento Mensal (Fev a Set/2026), Glosa de Mar/26, Determinação LGPD de Jul/26 e Desmembramento de 18 OSs em Set/26'\n"
        f"    }});\n"
        f"    window.CONTRACT_DATA.documentos.push({{\n"
        f"      categoria: 'Rito de Verificação',\n"
        f"      titulo: 'Instruções de Checagem de Fluxo (Etapas 1 a 10)',\n"
        f"      protocolo: 'instruções.md',\n"
        f"      paginas: 'MD',\n"
        f"      caminho: '../instruções.md',\n"
        f"      destaque: 'Passo a passo oficial de verificação das OSs (Etapas 1-5) e do Ciclo Mensal RMEC → Atesto → NAS → GMS → NFS → Pagamento (Etapas 6-10)'\n"
        f"    }});\n"
        f"  }}\n"
        f"}})();\n"
    )

    with open(data_js_path, "w", encoding="utf-8") as f:
        f.write(content + ext_js)


if __name__ == "__main__":
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    print("1. Executando ingestao incremental (Delta Append-Only) sobre os 29 PDFs...")
    rep1 = run_delta_ingestion(conn, force_rebuild=False)
    print(f"   -> 1a Passagem: {rep1['new_pages_ingested_delta']} paginas novas ingeridas | {rep1['pages_already_cached_skipped']} puladas.")
    print("2. Populando Event Store Cronologico (10 Etapas instrucoes.md) e Matriz RMEC...")
    events = populate_structured_tables(conn)
    print(f"   -> {len(events)} eventos cronologicos gravados e indexados.")
    print("3. Atualizando js/data.js com dados sincronizados...")
    patch_frontend_data_js(conn, rep1, events)
    print("4. Testando 2a passagem (Delta Sync sem alteracao nos PDFs) para comprovar economia de 100% dos tokens...")
    rep2 = run_delta_ingestion(conn, force_rebuild=False)
    print(f"   -> 2a Passagem (Delta): {rep2['new_pages_ingested_delta']} paginas novas | {rep2['pages_already_cached_skipped']} paginas em cache puladas ({rep2['tokens_saved_estimate']:,} tokens economizados!).")
    conn.close()
