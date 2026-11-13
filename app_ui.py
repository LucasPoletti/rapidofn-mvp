import os
import re
import sqlite3
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, jsonify

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rapidofn.db")
ALIQUOTA_DAS_ANEXO_III = 6.00


def cpf_valido(cpf: str) -> bool:
    numeros = re.sub(r"\D", "", cpf or "")
    if len(numeros) != 11 or numeros == numeros[0] * 11:
        return False

    soma1 = sum(int(numeros[i]) * (10 - i) for i in range(9))
    dig1 = (soma1 * 10 % 11) % 10

    soma2 = sum(int(numeros[i]) * (11 - i) for i in range(10))
    dig2 = (soma2 * 10 % 11) % 10

    return numeros[-2:] == f"{dig1}{dig2}"


def parse_valor_brl(valor_str: str) -> float:
    limpo = re.sub(r"[^\d,.]", "", (valor_str or "").strip())
    if not limpo:
        return 0.0
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    try:
        return round(float(limpo), 2)
    except ValueError:
        return 0.0


def fmt_brl(valor: float) -> str:
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notas_fiscais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT NOT NULL,
                paciente TEXT NOT NULL,
                cpf TEXT NOT NULL,
                servico TEXT NOT NULL,
                valor REAL NOT NULL,
                aliquota_das REAL NOT NULL,
                valor_das REAL NOT NULL,
                regime TEXT NOT NULL,
                status TEXT NOT NULL,
                data_emissao TEXT NOT NULL
            )
        """)
        colunas = [row["name"] for row in conn.execute("PRAGMA table_info(notas_fiscais)").fetchall()]
        if "aliquota_iss" in colunas and "aliquota_das" not in colunas:
            conn.execute("ALTER TABLE notas_fiscais RENAME COLUMN aliquota_iss TO aliquota_das")
        if "valor_iss" in colunas and "valor_das" not in colunas:
            conn.execute("ALTER TABLE notas_fiscais RENAME COLUMN valor_iss TO valor_das")

        conn.execute("""
            DELETE FROM notas_fiscais
            WHERE cpf LIKE '111.111%' OR cpf LIKE '222.222%' OR cpf LIKE '000.000%'
        """)
        conn.execute("""
            UPDATE notas_fiscais
            SET aliquota_das = 6.00,
                valor_das = ROUND(valor * 0.06, 2),
                regime = 'Simples Nacional - Anexo III (Alíquota 6,00% inicial)'
            WHERE aliquota_das != 6.00
        """)
        total = conn.execute("SELECT COUNT(*) FROM notas_fiscais").fetchone()[0]
        if total == 0:
            iniciais = [
                (
                    "2026001",
                    "Mariana Costa Silva",
                    "529.982.247-25",
                    "Sessão de Psicoterapia Individual (50 min)",
                    180.00,
                    ALIQUOTA_DAS_ANEXO_III,
                    round(180.00 * (ALIQUOTA_DAS_ANEXO_III / 100.0), 2),
                    "Simples Nacional - Anexo III (Alíquota 6,00% inicial)",
                    "AUTORIZADA",
                    "13/11/2026 09:10",
                ),
                (
                    "2026002",
                    "Carlos Eduardo Mendes",
                    "153.509.460-56",
                    "Avaliação Psicológica Clínica",
                    250.00,
                    ALIQUOTA_DAS_ANEXO_III,
                    round(250.00 * (ALIQUOTA_DAS_ANEXO_III / 100.0), 2),
                    "Simples Nacional - Anexo III (Alíquota 6,00% inicial)",
                    "AUTORIZADA",
                    "13/11/2026 09:22",
                ),
            ]
            conn.executemany(
                """
                INSERT INTO notas_fiscais
                (numero, paciente, cpf, servico, valor, aliquota_das, valor_das, regime, status, data_emissao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                iniciais,
            )
        conn.commit()


init_db()

DANFSE_NACIONAL_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>DANFSe Nacional - NFS-e #{{ nota.numero }} - Casa Psico</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: Arial, Helvetica, sans-serif;
            background: #e2e8f0;
            color: #0f172a;
            margin: 0;
            padding: 20px;
            font-size: 11px;
        }
        .toolbar {
            max-width: 820px;
            margin: 0 auto 14px auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #0f766e;
            color: #ffffff;
            padding: 10px 16px;
            border-radius: 6px;
        }
        .toolbar button, .toolbar a {
            background: #ffffff;
            color: #0f766e;
            border: none;
            padding: 8px 14px;
            border-radius: 4px;
            font-weight: bold;
            cursor: pointer;
            text-decoration: none;
            font-size: 12px;
        }
        .sheet {
            max-width: 820px;
            margin: 0 auto;
            background: #ffffff;
            border: 1.5px solid #000000;
            padding: 12px;
        }
        .header-grid {
            display: grid;
            grid-template-columns: 110px 1fr 195px;
            border: 1px solid #000000;
        }
        .header-logo {
            border-right: 1px solid #000000;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 8px;
            text-align: center;
            background: #f8fafc;
        }
        .badge-nfse {
            font-size: 18px;
            font-weight: 900;
            color: #065f46;
            letter-spacing: -0.5px;
        }
        .header-title {
            border-right: 1px solid #000000;
            padding: 8px 12px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            text-align: center;
        }
        .header-title h1 {
            margin: 0;
            font-size: 14px;
            text-transform: uppercase;
        }
        .header-title p {
            margin: 4px 0 0 0;
            font-size: 10px;
            color: #334155;
        }
        .header-num {
            padding: 6px 8px;
            font-size: 10px;
        }
        .header-num div { margin-bottom: 4px; }
        .section-bar {
            background: #e2e8f0;
            border: 1px solid #000000;
            border-top: none;
            font-weight: bold;
            padding: 4px 8px;
            font-size: 10px;
            text-transform: uppercase;
        }
        .box {
            border: 1px solid #000000;
            border-top: none;
            padding: 6px 8px;
        }
        .row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
        .row-3 { display: grid; grid-template-columns: 1.4fr 1fr 1fr; gap: 8px; }
        .row-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
        .lbl { font-size: 9px; color: #475569; text-transform: uppercase; display: block; }
        .val { font-size: 11px; font-weight: bold; color: #000000; margin-top: 2px; display: block; }
        .chave {
            font-family: "Courier New", monospace;
            font-size: 11px;
            font-weight: bold;
            letter-spacing: 0.6px;
        }
        .desc-box {
            min-height: 74px;
            line-height: 1.5;
        }
        .footer-grid {
            display: grid;
            grid-template-columns: 1fr 105px;
            border: 1px solid #000000;
            border-top: none;
        }
        .footer-info {
            padding: 8px;
            border-right: 1px solid #000000;
            font-size: 9.5px;
            line-height: 1.45;
        }
        .qr-box {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 6px;
            text-align: center;
            font-size: 8px;
        }
        @media print {
            body { background: #ffffff; padding: 0; }
            .toolbar { display: none !important; }
            .sheet { border: 1.5px solid #000000; max-width: 100%; }
        }
    </style>
</head>
<body onload="setTimeout(function(){ window.print(); }, 350)">
    <div class="toolbar">
        <span><strong>DANFSe Padrão Nacional</strong> — Pré-visualização Oficial (NFS-e #{{ nota.numero }})</span>
        <div style="display:flex; gap:8px;">
            <button type="button" onclick="window.print()">Salvar como PDF / Imprimir</button>
            <a href="/">Voltar ao RápidoNF</a>
        </div>
    </div>

    <div class="sheet">
        <div class="header-grid">
            <div class="header-logo">
                <span class="badge-nfse">NFS-e</span>
                <span style="font-size:8.5px; font-weight:bold; margin-top:2px;">PADRÃO NACIONAL</span>
                <span style="font-size:8px; color:#475569;">Ambiente Nacional</span>
            </div>
            <div class="header-title">
                <h1>DANFSe — Documento Auxiliar da NFS-e</h1>
                <p>Nota Fiscal de Serviço Eletrônica — Sistema Nacional NFS-e (LC 116/2003)</p>
                <p style="font-weight:bold; color:#065f46;">Emissor Integrado: RápidoNF | Tecnologia Luyon Automações®</p>
            </div>
            <div class="header-num">
                <div><span class="lbl">Número da NFS-e</span><span class="val" style="font-size:13px;">{{ nota.numero }}</span></div>
                <div><span class="lbl">Competência</span><span class="val">{{ nota.data_emissao[:10] }}</span></div>
                <div><span class="lbl">Data e Hora da Emissão</span><span class="val">{{ nota.data_emissao }}</span></div>
            </div>
        </div>

        <div class="box">
            <span class="lbl">Chave de Acesso da NFS-e (Padrão Nacional 50 Dígitos)</span>
            <span class="chave">{{ chave_acesso }}</span>
        </div>

        <div class="section-bar">Emitente / Prestador do Serviço</div>
        <div class="box">
            <div class="row-3">
                <div>
                    <span class="lbl">Nome / Razão Social</span>
                    <span class="val">CASA PSICO PSICOLOGIA CLÍNICA LTDA</span>
                </div>
                <div>
                    <span class="lbl">CNPJ / CPF</span>
                    <span class="val">63.897.592/0001-06</span>
                </div>
                <div>
                    <span class="lbl">Inscrição Municipal</span>
                    <span class="val">ISENTO / SIMPLES NACIONAL</span>
                </div>
            </div>
            <div class="row-2" style="margin-top:6px;">
                <div>
                    <span class="lbl">Município / UF</span>
                    <span class="val">Porto Alegre - RS</span>
                </div>
                <div>
                    <span class="lbl">Regime Especial de Tributação</span>
                    <span class="val">Optante pelo Simples Nacional — Anexo III (Alíquota 6,00% inicial)</span>
                </div>
            </div>
        </div>

        <div class="section-bar">Tomador do Serviço (Paciente)</div>
        <div class="box">
            <div class="row-2">
                <div>
                    <span class="lbl">Nome / Razão Social</span>
                    <span class="val">{{ nota.paciente }}</span>
                </div>
                <div>
                    <span class="lbl">CPF / CNPJ (Validado Receita Federal)</span>
                    <span class="val">{{ nota.cpf }}</span>
                </div>
            </div>
        </div>

        <div class="section-bar">Serviço Prestado</div>
        <div class="box">
            <div class="row-3" style="margin-bottom:6px;">
                <div>
                    <span class="lbl">Código de Tributação Nacional (LC 116/03)</span>
                    <span class="val">04.16.01 — Psicologia e Psicanálise</span>
                </div>
                <div>
                    <span class="lbl">Local da Prestação</span>
                    <span class="val">Porto Alegre - RS</span>
                </div>
                <div>
                    <span class="lbl">Situação do Documento</span>
                    <span class="val" style="color:#065f46;">{{ nota.status }}</span>
                </div>
            </div>
            <div class="desc-box" style="border-top:1px dashed #cbd5e1; padding-top:6px;">
                <span class="lbl">Descrição do Serviço</span>
                <span class="val" style="font-weight:normal; margin-top:4px;">
                    {{ nota.servico }}<br>
                    Atendimento clínico realizado conforme prontuário reservado sob sigilo profissional (Resolução CFP nº 010/2005).<br>
                    Documento emitido por empresa optante pelo Simples Nacional — Anexo III (Alíquota inicial de 6,00%).
                </span>
            </div>
        </div>

        <div class="section-bar">Tributação Municipal & Apuração Simples Nacional (DAS)</div>
        <div class="box">
            <div class="row-4">
                <div>
                    <span class="lbl">Valor do Serviço</span>
                    <span class="val">R$ {{ nota.valor_fmt }}</span>
                </div>
                <div>
                    <span class="lbl">Base de Cálculo</span>
                    <span class="val">R$ {{ nota.valor_fmt }}</span>
                </div>
                <div>
                    <span class="lbl">Alíquota Simples (Anexo III)</span>
                    <span class="val">6,00%</span>
                </div>
                <div>
                    <span class="lbl">Valor do DAS Previsto</span>
                    <span class="val">R$ {{ nota.valor_das_fmt }}</span>
                </div>
            </div>
            <div class="row-4" style="margin-top:6px; border-top:1px dashed #cbd5e1; padding-top:6px;">
                <div>
                    <span class="lbl">Deduções / Descontos</span>
                    <span class="val">R$ 0,00</span>
                </div>
                <div>
                    <span class="lbl">Retenção ISSQN</span>
                    <span class="val">Não Retido (Recolhimento via DAS)</span>
                </div>
                <div>
                    <span class="lbl">Tributos Federais Retidos</span>
                    <span class="val">R$ 0,00</span>
                </div>
                <div>
                    <span class="lbl">Valor Líquido da NFS-e</span>
                    <span class="val" style="font-size:12px;">R$ {{ nota.valor_fmt }}</span>
                </div>
            </div>
        </div>

        <div class="footer-grid">
            <div class="footer-info">
                <strong>INFORMAÇÕES COMPLEMENTARES E AUTENTICIDADE</strong><br>
                1. Documento emitido em conformidade com o layout do Padrão Nacional da NFS-e.<br>
                2. Não gera direito a crédito de IPI/ICMS. Recolhimento unificado via guia DAS (Simples Nacional — Anexo III).<br>
                3. Código Verificador: <strong>RNF-{{ nota.numero }}-CASAPSICO-SNIII</strong> | Emitido via <strong>RápidoNF MVP</strong>.
            </div>
            <div class="qr-box">
                <svg width="68" height="68" viewBox="0 0 25 25" shape-rendering="crispEdges">
                    <rect width="25" height="25" fill="#fff"/>
                    <path d="M1,1h7v7h-7zM2,2v5h5v-5zM3,3h3v3h-3zM17,1h7v7h-7zM18,2v5h5v-5zM19,3h3v3h-3zM1,17h7v7h-7zM2,18v5h5v-5zM3,19h3v3h-3zM10,2h2v2h-2zM13,3h2v3h-2zM10,6h3v2h-3zM2,10h3v2h-3zM7,10h2v4h-2zM11,10h4v2h-4zM17,10h3v2h-3zM21,11h3v3h-3zM10,14h2v3h-2zM14,14h3v2h-3zM18,16h2v4h-2zM10,19h4v2h-4zM15,21h3v3h-3zM21,20h3v4h-3z" fill="#000"/>
                </svg>
                <span style="margin-top:2px;">Consulta Nacional</span>
            </div>
        </div>
    </div>
</body>
</html>
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RápidoNF | Emissão Inteligente NFS-e - Casa Psico</title>
    <style>
        :root {
            --bg-color: #f4f7f9;
            --card-bg: #ffffff;
            --text-color: #1e293b;
            --muted-text: #475569;
            --primary: #0f766e;
            --primary-hover: #115e59;
            --border: #cbd5e1;
            --font-scale: 1rem;
        }
        body.high-contrast {
            --bg-color: #000000;
            --card-bg: #111111;
            --text-color: #ffff00;
            --muted-text: #ffff00;
            --primary: #ffff00;
            --primary-hover: #e5e500;
            --border: #ffff00;
        }
        body.large-font {
            --font-scale: 1.25rem;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            font-size: var(--font-scale);
            margin: 0;
            padding: 20px;
            transition: all 0.2s ease;
        }
        .container { max-width: 1120px; margin: 0 auto; }
        header {
            display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;
            background: var(--card-bg); padding: 16px 24px; border-radius: 10px;
            border: 2px solid var(--border); margin-bottom: 20px;
        }
        .brand { font-weight: 800; font-size: 1.3em; }
        .badge-luyon { font-size: 0.78em; color: var(--muted-text); display: block; margin-top: 2px; }
        .a11y-bar button {
            background: transparent; color: var(--text-color); border: 2px solid var(--border);
            padding: 8px 14px; border-radius: 6px; cursor: pointer; font-weight: 700; margin-left: 8px;
        }
        .a11y-bar button[aria-pressed="true"] {
            background: var(--primary); color: #ffffff;
        }
        body.high-contrast .a11y-bar button[aria-pressed="true"] {
            color: #000000;
        }
        .kpi-row {
            display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px;
        }
        .kpi-card {
            background: var(--card-bg); padding: 14px 20px; border-radius: 10px;
            border: 2px solid var(--border);
        }
        .kpi-label { font-size: 0.82em; color: var(--muted-text); font-weight: 600; }
        .kpi-value { font-size: 1.35em; font-weight: 800; margin-top: 4px; }
        .grid { display: grid; grid-template-columns: 1fr 1.65fr; gap: 20px; }
        @media (max-width: 860px) {
            .grid, .kpi-row { grid-template-columns: 1fr; }
        }
        .card {
            background: var(--card-bg); padding: 20px; border-radius: 10px;
            border: 2px solid var(--border);
        }
        label { display: block; font-weight: 700; margin-top: 12px; margin-bottom: 4px; }
        input, select {
            width: 100%; padding: 10px; border-radius: 6px; border: 2px solid var(--border);
            background: var(--bg-color); color: var(--text-color); font-size: 1em; box-sizing: border-box;
        }
        .field-error {
            color: #dc2626; font-size: 0.82em; font-weight: 700; margin-top: 4px; display: none;
        }
        body.high-contrast .field-error { color: #ffff00; text-decoration: underline; }
        .tax-box {
            margin-top: 14px; padding: 10px 12px; border-radius: 6px;
            border: 1px dashed var(--border); font-size: 0.85em;
        }
        .btn-submit {
            margin-top: 16px; width: 100%; padding: 12px; border: none; border-radius: 6px;
            background: var(--primary); color: #ffffff; font-weight: 800; font-size: 1em; cursor: pointer;
            text-decoration: none; display: inline-block; text-align: center; box-sizing: border-box;
        }
        .btn-submit:hover { background: var(--primary-hover); }
        body.high-contrast .btn-submit { color: #000000; }
        .alert-success {
            background: #dcfce7; color: #166534; border: 2px solid #16a34a;
            padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; font-weight: 700;
            display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;
        }
        .alert-error {
            background: #fee2e2; color: #991b1b; border: 2px solid #dc2626;
            padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; font-weight: 700;
        }
        body.high-contrast .alert-success, body.high-contrast .alert-error {
            background: #000000; color: #ffff00; border-color: #ffff00;
        }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--border); vertical-align: top; }
        .status-ok {
            background: #dcfce7; color: #166534; padding: 4px 8px; border-radius: 4px;
            font-weight: 700; font-size: 0.8em; display: inline-block;
        }
        body.high-contrast .status-ok { background: #ffff00; color: #000000; }
        .actions-cell { display: flex; flex-direction: column; gap: 4px; margin-top: 4px; }
        .btn-recibo, .btn-pdf {
            background: transparent; color: var(--text-color); border: 1px solid var(--border);
            padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 0.78em; font-weight: 700;
            text-decoration: none; text-align: center; display: inline-block;
        }
        .btn-pdf {
            background: var(--primary); color: #ffffff; border-color: var(--primary);
        }
        body.high-contrast .btn-pdf { background: #ffff00; color: #000000; border-color: #ffff00; }
        dialog {
            background: var(--card-bg); color: var(--text-color); border: 2px solid var(--border);
            border-radius: 10px; padding: 24px; max-width: 480px; width: 90%;
        }
        dialog::backdrop { background: rgba(0, 0, 0, 0.6); }
    </style>
</head>
<body>
<div class="container">
    <header role="banner">
        <div>
            <span class="brand">RápidoNF — Clínica Casa Psico</span>
            <span class="badge-luyon">Tecnologia Luyon Automações® | Simples Nacional — Anexo III (Alíquota 6,00% inicial)</span>
        </div>
        <div class="a11y-bar" role="region" aria-label="Controles de Acessibilidade">
            <button type="button" id="btn-contrast" onclick="toggleContrast()" aria-pressed="false">
                Alto Contraste
            </button>
            <button type="button" id="btn-font" onclick="toggleFont()" aria-pressed="false">
                Aumentar Fonte (A+)
            </button>
        </div>
    </header>

    {% if emitida %}
    <div class="alert-success" role="status">
        <span>NFS-e #{{ emitida }} autorizada e gravada no banco de dados SQLite com sucesso!</span>
        <a href="/nota/{{ emitida }}/pdf" target="_blank" class="btn-pdf" style="padding: 8px 14px; font-size: 0.9em;">
            Baixar PDF DANFSe #{{ emitida }}
        </a>
    </div>
    {% endif %}

    {% if erro %}
    <div class="alert-error" role="alert">
        {{ erro }}
    </div>
    {% endif %}

    <div class="kpi-row">
        <div class="kpi-card">
            <div class="kpi-label">Notas Emitidas (Banco SQLite)</div>
            <div class="kpi-value">{{ notas|length }}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Faturamento Clínico Registrado</div>
            <div class="kpi-value">R$ {{ total_faturado_fmt }}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">DAS Previsto (Simples Nacional 6,00%)</div>
            <div class="kpi-value">R$ {{ total_das_fmt }}</div>
        </div>
    </div>

    <div class="grid">
        <section class="card" aria-labelledby="titulo-emissao">
            <h2 id="titulo-emissao" style="margin-top:0;">Emitir Nova NFS-e</h2>
            <form id="form-nfse" method="POST" action="/emitir">
                <label for="paciente">Nome do Paciente (Tomador)</label>
                <input id="paciente" name="paciente" type="text" placeholder="Ex: Fernanda Oliveira" required>

                <label for="cpf">CPF do Paciente</label>
                <input id="cpf" name="cpf" type="text" maxlength="14" placeholder="000.000.000-00" required>
                <div id="cpf-erro" class="field-error">CPF inválido. Informe um CPF válido com dígitos verificadores reais.</div>

                <label for="servico">Descrição do Serviço Clínico (LC 116/03 - 04.16)</label>
                <select id="servico" name="servico">
                    <option>Sessão de Psicoterapia Individual (50 min)</option>
                    <option>Psicoterapia Infantil / Orientação Parental</option>
                    <option>Avaliação Neuropsicológica Clínica</option>
                </select>

                <label for="valor">Valor da Sessão (R$)</label>
                <input id="valor" name="valor" type="text" inputmode="decimal" value="180,00" required>
                <div id="valor-erro" class="field-error">Informe um valor válido maior que R$ 0,00.</div>

                <div class="tax-box" id="tax-preview">
                    <strong>Enquadramento Automático:</strong> Simples Nacional — Anexo III (Alíquota 6,00% inicial)<br>
                    <strong>Valor do DAS Estimado (6,00%):</strong> R$ <span id="das-calc">10,80</span>
                </div>

                <button type="submit" id="btn-transmitir" class="btn-submit">Transmitir NFS-e Agora</button>
            </form>
        </section>

        <section class="card" aria-labelledby="titulo-historico">
            <h2 id="titulo-historico" style="margin-top:0;">Notas Fiscais Emitidas (Persistência Real)</h2>
            <table>
                <thead>
                    <tr>
                        <th>NFS-e</th>
                        <th>Tomador / Serviço</th>
                        <th>Valor / DAS</th>
                        <th>Ações / PDF</th>
                    </tr>
                </thead>
                <tbody>
                    {% for n in notas %}
                    <tr>
                        <td>
                            <strong>#{{ n.numero }}</strong><br>
                            <small>{{ n.data_emissao }}</small>
                        </td>
                        <td>
                            <strong>{{ n.paciente }}</strong> <small>({{ n.cpf }})</small><br>
                            <small>{{ n.servico }}</small>
                        </td>
                        <td>
                            R$ {{ n.valor_fmt }}<br>
                            <small>DAS (6%): R$ {{ n.valor_das_fmt }}</small>
                        </td>
                        <td>
                            <span class="status-ok">{{ n.status }}</span>
                            <div class="actions-cell">
                                <a href="/nota/{{ n.numero }}/pdf" target="_blank" class="btn-pdf">Gerar PDF</a>
                                <button type="button" class="btn-recibo"
                                    onclick="abrirRecibo('{{ n.numero }}', '{{ n.paciente }}', '{{ n.cpf }}', '{{ n.servico }}', '{{ n.valor_fmt }}', '{{ n.valor_das_fmt }}', '{{ n.data_emissao }}')">
                                    Ver Espelho
                                </button>
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </section>
    </div>
</div>

<dialog id="modal-recibo">
    <h3 style="margin-top:0;">Espelho da NFS-e Autorizada</h3>
    <p><strong>Prestador:</strong> CASA PSICO PSICOLOGIA CLÍNICA LTDA (CNPJ 63.897.592/0001-06)</p>
    <p><strong>Regime Tributário:</strong> Simples Nacional — Anexo III (Alíquota 6,00% inicial)</p>
    <hr>
    <p id="recibo-detalhes" style="line-height:1.6;"></p>
    <a id="modal-btn-pdf" href="#" target="_blank" class="btn-submit">Gerar PDF Oficial (DANFSe Nacional)</a>
    <button type="button" class="btn-recibo" style="width:100%; margin-top:8px; padding:10px;" onclick="document.getElementById('modal-recibo').close()">Fechar Espelho</button>
</dialog>

<script>
    const ALIQUOTA_DAS = 0.06;

    function apenasDigitos(str) {
        let out = "";
        for (let i = 0; i < str.length; i++) {
            const c = str[i];
            if (c >= "0" && c <= "9") out += c;
        }
        return out;
    }

    function validarCPFJS(cpf) {
        const nums = apenasDigitos(cpf);
        if (nums.length !== 11) return false;

        let todosIguais = true;
        for (let i = 1; i < 11; i++) {
            if (nums[i] !== nums[0]) {
                todosIguais = false;
                break;
            }
        }
        if (todosIguais) return false;

        let soma = 0;
        for (let i = 0; i < 9; i++) soma += parseInt(nums[i], 10) * (10 - i);
        let dig1 = (soma * 10) % 11;
        if (dig1 === 10) dig1 = 0;
        if (dig1 !== parseInt(nums[9], 10)) return false;

        soma = 0;
        for (let i = 0; i < 10; i++) soma += parseInt(nums[i], 10) * (11 - i);
        let dig2 = (soma * 10) % 11;
        if (dig2 === 10) dig2 = 0;
        return dig2 === parseInt(nums[10], 10);
    }

    function parseValorJS(texto) {
        let limpo = "";
        for (let i = 0; i < texto.length; i++) {
            const c = texto[i];
            if ((c >= "0" && c <= "9") || c === "," || c === ".") limpo += c;
        }
        if (!limpo) return 0;
        if (limpo.includes(",")) {
            limpo = limpo.split(".").join("").replace(",", ".");
        }
        const num = parseFloat(limpo);
        return isNaN(num) ? 0 : num;
    }

    function formatarBRLJS(num) {
        return num.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    document.addEventListener("DOMContentLoaded", function () {
        const campoCPF = document.getElementById("cpf");
        const erroCPF = document.getElementById("cpf-erro");
        const campoValor = document.getElementById("valor");
        const erroValor = document.getElementById("valor-erro");
        const form = document.getElementById("form-nfse");

        campoCPF.addEventListener("input", function () {
            const d = apenasDigitos(campoCPF.value).slice(0, 11);
            let formatado = d;
            if (d.length > 9) {
                formatado = d.slice(0, 3) + "." + d.slice(3, 6) + "." + d.slice(6, 9) + "-" + d.slice(9);
            } else if (d.length > 6) {
                formatado = d.slice(0, 3) + "." + d.slice(3, 6) + "." + d.slice(6);
            } else if (d.length > 3) {
                formatado = d.slice(0, 3) + "." + d.slice(3);
            }
            campoCPF.value = formatado;

            if (d.length === 11 && !validarCPFJS(formatado)) {
                erroCPF.style.display = "block";
                campoCPF.setCustomValidity("CPF inválido.");
            } else {
                erroCPF.style.display = "none";
                campoCPF.setCustomValidity("");
            }
        });

        function finalizarValor() {
            const val = parseValorJS(campoValor.value);
            if (val <= 0 || val > 999999.99) {
                erroValor.style.display = "block";
                return false;
            }
            erroValor.style.display = "none";
            campoValor.value = formatarBRLJS(val);
            document.getElementById("das-calc").textContent = formatarBRLJS(val * ALIQUOTA_DAS);
            return true;
        }

        campoValor.addEventListener("input", function () {
            let limpo = "";
            for (let i = 0; i < campoValor.value.length; i++) {
                const c = campoValor.value[i];
                if ((c >= "0" && c <= "9") || c === "," || c === ".") limpo += c;
            }
            campoValor.value = limpo;
            const val = parseValorJS(limpo);
            document.getElementById("das-calc").textContent = formatarBRLJS(val * ALIQUOTA_DAS);
            erroValor.style.display = "none";
        });

        campoValor.addEventListener("blur", finalizarValor);

        campoValor.addEventListener("keydown", function (event) {
            if (event.key === "Enter" || event.keyCode === 13) {
                event.preventDefault();
                if (finalizarValor()) {
                    campoValor.blur();
                    document.getElementById("btn-transmitir").focus();
                }
            }
        });

        form.addEventListener("submit", function (event) {
            if (!validarCPFJS(campoCPF.value)) {
                event.preventDefault();
                erroCPF.style.display = "block";
                campoCPF.focus();
                return false;
            }
            if (!finalizarValor()) {
                event.preventDefault();
                campoValor.focus();
                return false;
            }
            return true;
        });
    });

    function toggleContrast() {
        const active = document.body.classList.toggle("high-contrast");
        document.getElementById("btn-contrast").setAttribute("aria-pressed", active);
    }

    function toggleFont() {
        const active = document.body.classList.toggle("large-font");
        document.getElementById("btn-font").setAttribute("aria-pressed", active);
    }

    function abrirRecibo(num, pac, cpf, serv, val, das, data) {
        document.getElementById("recibo-detalhes").innerHTML =
            `<strong>Número NFS-e:</strong> #${num}<br>` +
            `<strong>Data/Hora Autorização:</strong> ${data}<br>` +
            `<strong>Tomador:</strong> ${pac} (CPF: ${cpf})<br>` +
            `<strong>Serviço:</strong> ${serv}<br>` +
            `<strong>Valor Bruto da Sessão:</strong> R$ ${val}<br>` +
            `<strong>Valor do DAS Previsto (6,00%):</strong> R$ ${das}<br>` +
            `<strong>Situação:</strong> AUTORIZADA`;
        document.getElementById("modal-btn-pdf").href = `/nota/${num}/pdf`;
        document.getElementById("modal-recibo").showModal();
    }
</script>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def index():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM notas_fiscais ORDER BY id DESC").fetchall()

    notas = []
    for r in rows:
        item = dict(r)
        item["valor_fmt"] = fmt_brl(item["valor"])
        item["valor_das_fmt"] = fmt_brl(item["valor_das"])
        notas.append(item)

    total_faturado = sum(n["valor"] for n in notas)
    total_das = sum(n["valor_das"] for n in notas)
    emitida = request.args.get("emitida")
    erro = request.args.get("erro")
    return render_template_string(
        HTML_TEMPLATE,
        notas=notas,
        total_faturado_fmt=fmt_brl(total_faturado),
        total_das_fmt=fmt_brl(total_das),
        emitida=emitida,
        erro=erro,
    )


@app.route("/emitir", methods=["POST"])
def emitir():
    paciente = request.form.get("paciente", "").strip()
    cpf = request.form.get("cpf", "").strip()
    servico = request.form.get("servico", "").strip()
    valor = parse_valor_brl(request.form.get("valor", "0"))

    if not cpf_valido(cpf):
        return redirect(url_for("index", erro="Falha na emissão: CPF inválido ou sequência repetida bloqueada pela validação fiscal."))

    if valor <= 0 or valor > 999999.99:
        return redirect(url_for("index", erro="Falha na emissão: informe um valor monetário válido maior que R$ 0,00."))

    valor_das = round(valor * (ALIQUOTA_DAS_ANEXO_III / 100.0), 2)
    data_emissao = datetime.now().strftime("%d/%m/%Y %H:%M")

    with get_db() as conn:
        ultimo_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM notas_fiscais").fetchone()[0]
        novo_num = f"2026{ultimo_id + 1:03d}"
        conn.execute(
            """
            INSERT INTO notas_fiscais
            (numero, paciente, cpf, servico, valor, aliquota_das, valor_das, regime, status, data_emissao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                novo_num,
                paciente,
                cpf,
                servico,
                valor,
                ALIQUOTA_DAS_ANEXO_III,
                valor_das,
                "Simples Nacional - Anexo III (Alíquota 6,00% inicial)",
                "AUTORIZADA",
                data_emissao,
            ),
        )
        conn.commit()

    return redirect(url_for("index", emitida=novo_num))


@app.route("/nota/<numero>/pdf", methods=["GET"])
def baixar_pdf_nota(numero):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM notas_fiscais WHERE numero = ?", (numero,)).fetchone()
    if not row:
        return redirect(url_for("index", erro=f"Nota fiscal #{numero} não encontrada."))

    nota = dict(row)
    nota["valor_fmt"] = fmt_brl(nota["valor"])
    nota["valor_das_fmt"] = fmt_brl(nota["valor_das"])
    chave_acesso = f"43149022263897592000106000000000{nota['numero']}2611139874"
    return render_template_string(DANFSE_NACIONAL_TEMPLATE, nota=nota, chave_acesso=chave_acesso)


@app.route("/health", methods=["GET"])
def health():
    with get_db() as conn:
        total_notas = conn.execute("SELECT COUNT(*) FROM notas_fiscais").fetchone()[0]
    return jsonify({
        "status": "UP",
        "service": "RapidoNF-MVP",
        "client": "Casa Psico",
        "regime": "Simples Nacional - Anexo III (Aliquota 6,00% inicial)",
        "database": "SQLite Connected",
        "notas_registradas": total_notas,
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)