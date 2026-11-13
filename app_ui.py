import os
import re
import sqlite3
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, jsonify

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rapidofn.db")


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


def get_config_fiscal() -> dict:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM configuracoes_fiscais WHERE id = 1").fetchone()
        return dict(row)


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS configuracoes_fiscais (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                ambiente_nacional TEXT NOT NULL,
                serie_dps TEXT NOT NULL,
                razao_social TEXT NOT NULL,
                cnpj TEXT NOT NULL,
                inscricao_municipal TEXT NOT NULL,
                cnae_principal TEXT NOT NULL,
                endereco_prestador TEXT NOT NULL,
                municipio_uf TEXT NOT NULL,
                codigo_ibge TEXT NOT NULL,
                telefone_prestador TEXT NOT NULL,
                email_prestador TEXT NOT NULL,
                op_simples_nacional TEXT NOT NULL,
                regime_apuracao_sn TEXT NOT NULL,
                regime_especial_trib TEXT NOT NULL,
                regime_tributario TEXT NOT NULL,
                exigibilidade_issqn TEXT NOT NULL,
                retencao_issqn_csrf TEXT NOT NULL,
                aliquota_das REAL NOT NULL,
                codigo_servico TEXT NOT NULL,
                codigo_nbs TEXT NOT NULL,
                regra_ibs_cbs TEXT NOT NULL,
                contador_responsavel TEXT NOT NULL,
                crc_contador TEXT NOT NULL,
                ultima_atualizacao TEXT NOT NULL
            )
        """)

        # Migração segura caso a tabela já exista de uma execução anterior
        cols_existentes = [r["name"] for r in conn.execute("PRAGMA table_info(configuracoes_fiscais)").fetchall()]
        novas_colunas = {
            "ambiente_nacional": "'1 - Produção (ADN Receita Federal)'",
            "serie_dps": "'00001'",
            "cnae_principal": "'8650-0/03 - Atividades de psicologia e psicanálise'",
            "endereco_prestador": "'Av. General Flores da Cunha, 1250 - Sala 302, Centro - CEP 94910-001'",
            "codigo_ibge": "'4303103'",
            "telefone_prestador": "'(51) 99627-1436'",
            "email_prestador": "'contato@casapsico.com.br'",
            "op_simples_nacional": "'3 - Optante - Microempresa ou Empresa de Pequeno Porte (ME/EPP)'",
            "regime_apuracao_sn": "'1 - Regime de apuração dos tributos federais e municipal pelo SN (DAS)'",
            "regime_especial_trib": "'0 - Nenhum'",
            "exigibilidade_issqn": "'1 - Exigível (Recolhimento via DAS)'",
            "retencao_issqn_csrf": "'1 - Não Retido (Dispensa Simples Nacional)'",
            "codigo_nbs": "'1.2301.21.00 - Serviços de psicologia'",
            "regra_ibs_cbs": "'Transição 2026 (NT 004/009 - Grupo IBS/CBS facultativo no ADN)'",
        }
        for col, default_val in novas_colunas.items():
            if col not in cols_existentes:
                conn.execute(f"ALTER TABLE configuracoes_fiscais ADD COLUMN {col} TEXT NOT NULL DEFAULT {default_val}")

        cfg_exists = conn.execute("SELECT COUNT(*) FROM configuracoes_fiscais WHERE id = 1").fetchone()[0]
        if cfg_exists == 0:
            conn.execute(
                """
                INSERT INTO configuracoes_fiscais
                (id, ambiente_nacional, serie_dps, razao_social, cnpj, inscricao_municipal,
                 cnae_principal, endereco_prestador, municipio_uf, codigo_ibge,
                 telefone_prestador, email_prestador, op_simples_nacional, regime_apuracao_sn,
                 regime_especial_trib, regime_tributario, exigibilidade_issqn, retencao_issqn_csrf,
                 aliquota_das, codigo_servico, codigo_nbs, regra_ibs_cbs,
                 contador_responsavel, crc_contador, ultima_atualizacao)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "1 - Produção (ADN Receita Federal)",
                    "00001",
                    "CASA PSICO PSICOLOGIA CLÍNICA LTDA",
                    "63.897.592/0001-06",
                    "ISENTO / SIMPLES NACIONAL",
                    "8650-0/03 - Atividades de psicologia e psicanálise",
                    "Av. General Flores da Cunha, 1250 - Sala 302, Centro - CEP 94910-001",
                    "Cachoeirinha - RS",
                    "4303103",
                    "(51) 99627-1436",
                    "contato@casapsico.com.br",
                    "3 - Optante - Microempresa ou Empresa de Pequeno Porte (ME/EPP)",
                    "1 - Regime de apuração dos tributos federais e municipal pelo SN (DAS)",
                    "0 - Nenhum",
                    "Simples Nacional — Anexo III (Fator R >= 28%)",
                    "1 - Exigível (Recolhimento via DAS)",
                    "1 - Não Retido (Dispensa Simples Nacional)",
                    6.00,
                    "04.16.01 — Psicologia e Psicanálise (LC 116/03)",
                    "1.2301.21.00 - Serviços de psicologia",
                    "Transição 2026 (NT 004/009 - Grupo IBS/CBS facultativo no ADN)",
                    "Lucas Felipe Apollo Poletti (LUYON Assessoria Contábil)",
                    "CRC/RS Ativo",
                    datetime.now().strftime("%d/%m/%Y %H:%M"),
                ),
            )

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
        total = conn.execute("SELECT COUNT(*) FROM notas_fiscais").fetchone()[0]
        if total == 0:
            iniciais = [
                (
                    "2026001",
                    "Mariana Costa Silva",
                    "529.982.247-25",
                    "Sessão de Psicoterapia Individual (50 min)",
                    180.00,
                    6.00,
                    10.80,
                    "Simples Nacional — Anexo III (Fator R >= 28%)",
                    "AUTORIZADA",
                    "13/11/2026 09:10",
                ),
                (
                    "2026002",
                    "Carlos Eduardo Mendes",
                    "153.509.460-56",
                    "Avaliação Psicológica Clínica",
                    250.00,
                    6.00,
                    15.00,
                    "Simples Nacional — Anexo III (Fator R >= 28%)",
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
    <title>DANFSe Nacional - NFS-e #{{ nota.numero }} - {{ cfg.razao_social }}</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: Arial, Helvetica, sans-serif;
            background: #e2e8f0;
            color: #0f172a;
            margin: 0;
            padding: 20px;
            font-size: 10.5px;
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
            grid-template-columns: 115px 1fr 205px;
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
            font-size: 13.5px;
            text-transform: uppercase;
        }
        .header-title p {
            margin: 3px 0 0 0;
            font-size: 9.5px;
            color: #334155;
        }
        .header-num {
            padding: 6px 8px;
            font-size: 9.5px;
        }
        .header-num div { margin-bottom: 3px; }
        .section-bar {
            background: #e2e8f0;
            border: 1px solid #000000;
            border-top: none;
            font-weight: bold;
            padding: 4px 8px;
            font-size: 9.5px;
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
        .lbl { font-size: 8.5px; color: #475569; text-transform: uppercase; display: block; }
        .val { font-size: 10.5px; font-weight: bold; color: #000000; margin-top: 2px; display: block; }
        .chave {
            font-family: "Courier New", monospace;
            font-size: 10.5px;
            font-weight: bold;
            letter-spacing: 0.5px;
        }
        .desc-box {
            min-height: 68px;
            line-height: 1.45;
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
            font-size: 9px;
            line-height: 1.42;
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
                <span style="font-size:8px; font-weight:bold; margin-top:2px;">PADRÃO NACIONAL</span>
                <span style="font-size:7.5px; color:#475569;">{{ cfg.ambiente_nacional[:12] }}</span>
            </div>
            <div class="header-title">
                <h1>DANFSe — Documento Auxiliar da NFS-e</h1>
                <p>Nota Fiscal de Serviço Eletrônica — Ambiente de Dados Nacional (ADN / Receita Federal)</p>
                <p style="font-weight:bold; color:#065f46;">Emissor Integrado: RápidoNF | Tecnologia Luyon Automações®</p>
            </div>
            <div class="header-num">
                <div><span class="lbl">Número da NFS-e / Série DPS</span><span class="val" style="font-size:12px;">{{ nota.numero }} / Série {{ cfg.serie_dps }}</span></div>
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
                    <span class="val">{{ cfg.razao_social }}</span>
                </div>
                <div>
                    <span class="lbl">CNPJ</span>
                    <span class="val">{{ cfg.cnpj }}</span>
                </div>
                <div>
                    <span class="lbl">Inscrição Municipal</span>
                    <span class="val">{{ cfg.inscricao_municipal }}</span>
                </div>
            </div>
            <div class="row-2" style="margin-top:5px;">
                <div>
                    <span class="lbl">Endereço do Prestador</span>
                    <span class="val" style="font-weight:normal;">{{ cfg.endereco_prestador }}</span>
                </div>
                <div>
                    <span class="lbl">Município / UF (Código IBGE) & Contato</span>
                    <span class="val" style="font-weight:normal;">{{ cfg.municipio_uf }} (IBGE: {{ cfg.codigo_ibge }}) | {{ cfg.telefone_prestador }} | {{ cfg.email_prestador }}</span>
                </div>
            </div>
            <div class="row-2" style="margin-top:5px; border-top:1px dashed #cbd5e1; padding-top:5px;">
                <div>
                    <span class="lbl">Opção Simples Nacional (opSimpNac)</span>
                    <span class="val">{{ cfg.op_simples_nacional }}</span>
                </div>
                <div>
                    <span class="lbl">Regime de Apuração & Enquadramento</span>
                    <span class="val">{{ cfg.regime_tributario }}</span>
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

        <div class="section-bar">Serviço Prestado & Classificação Nacional (LC 116/03 / NBS / CNAE)</div>
        <div class="box">
            <div class="row-3" style="margin-bottom:5px;">
                <div>
                    <span class="lbl">Código Tributação Nacional (cTribNac)</span>
                    <span class="val">{{ cfg.codigo_servico }}</span>
                </div>
                <div>
                    <span class="lbl">Código NBS / CNAE Principal</span>
                    <span class="val">{{ cfg.codigo_nbs }} | {{ cfg.cnae_principal[:9] }}</span>
                </div>
                <div>
                    <span class="lbl">Local da Prestação / Situação</span>
                    <span class="val" style="color:#065f46;">{{ cfg.municipio_uf }} — {{ nota.status }}</span>
                </div>
            </div>
            <div class="desc-box" style="border-top:1px dashed #cbd5e1; padding-top:5px;">
                <span class="lbl">Descrição Detalhada do Serviço</span>
                <span class="val" style="font-weight:normal; margin-top:3px;">
                    {{ nota.servico }}<br>
                    Atendimento clínico realizado conforme prontuário reservado sob sigilo profissional (Resolução CFP nº 010/2005).<br>
                    Parametrização fiscal homologada por: {{ cfg.contador_responsavel }} ({{ cfg.crc_contador }}).
                </span>
            </div>
        </div>

        <div class="section-bar">Tributação Municipal, Apuração Simples Nacional (DAS) & Reforma Tributária</div>
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
                    <span class="lbl">Alíquota Simples Nacional</span>
                    <span class="val">{{ nota.aliquota_fmt }}%</span>
                </div>
                <div>
                    <span class="lbl">Valor do DAS Previsto</span>
                    <span class="val">R$ {{ nota.valor_das_fmt }}</span>
                </div>
            </div>
            <div class="row-4" style="margin-top:5px; border-top:1px dashed #cbd5e1; padding-top:5px;">
                <div>
                    <span class="lbl">Exigibilidade ISSQN</span>
                    <span class="val">{{ cfg.exigibilidade_issqn }}</span>
                </div>
                <div>
                    <span class="lbl">Retenção ISSQN / CSRF (NT 007)</span>
                    <span class="val">{{ cfg.retencao_issqn_csrf }}</span>
                </div>
                <div>
                    <span class="lbl">Grupo IBS/CBS (NT 004/009)</span>
                    <span class="val">{{ cfg.regra_ibs_cbs[:34] }}</span>
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
                1. Documento emitido em conformidade com o Guia do Emissor Público Nacional NFS-e (v1.3) e NT 004/007/009.<br>
                2. {{ cfg.regime_apuracao_sn }}. Não gera direito a crédito de IPI/ICMS.<br>
                3. Código Verificador: <strong>RNF-{{ nota.numero }}-CASAPSICO-SNIII</strong> | Contador: <strong>{{ cfg.contador_responsavel }}</strong>.
            </div>
            <div class="qr-box">
                <svg width="64" height="64" viewBox="0 0 25 25" shape-rendering="crispEdges">
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
    <title>RápidoNF | Emissão Inteligente NFS-e - {{ cfg.razao_social }}</title>
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
        .container { max-width: 1180px; margin: 0 auto; }
        header {
            display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;
            background: var(--card-bg); padding: 16px 24px; border-radius: 10px;
            border: 2px solid var(--border); margin-bottom: 20px;
        }
        .brand { font-weight: 800; font-size: 1.3em; }
        .badge-luyon { font-size: 0.78em; color: var(--muted-text); display: block; margin-top: 2px; }
        .a11y-bar { display: flex; flex-wrap: wrap; gap: 8px; }
        .a11y-bar button {
            background: transparent; color: var(--text-color); border: 2px solid var(--border);
            padding: 8px 14px; border-radius: 6px; cursor: pointer; font-weight: 700;
        }
        .a11y-bar button.btn-pacientes {
            background: var(--primary); color: #ffffff; border-color: var(--primary);
        }
        .a11y-bar button.btn-fiscal {
            background: #1e293b; color: #ffffff; border-color: #1e293b;
        }
        body.high-contrast .a11y-bar button.btn-pacientes,
        body.high-contrast .a11y-bar button.btn-fiscal {
            background: #ffff00; color: #000000; border-color: #ffff00;
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
        label { display: block; font-weight: 700; margin-top: 10px; margin-bottom: 3px; font-size: 0.9em; }
        input, select {
            width: 100%; padding: 9px 10px; border-radius: 6px; border: 2px solid var(--border);
            background: var(--bg-color); color: var(--text-color); font-size: 0.95em; box-sizing: border-box;
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
            border-radius: 10px; padding: 22px; max-width: 840px; width: 94%; max-height: 90vh; overflow-y: auto;
        }
        dialog::backdrop { background: rgba(0, 0, 0, 0.65); }
        .section-divider {
            margin-top: 16px; padding-bottom: 4px; border-bottom: 2px solid var(--border);
            font-weight: 800; font-size: 0.88em; text-transform: uppercase; color: var(--primary);
        }
        .modal-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .modal-grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
        @media (max-width: 700px) {
            .modal-grid-2, .modal-grid-3 { grid-template-columns: 1fr; }
        }
        .fiscal-meta {
            margin-top: 14px; padding: 10px; border-radius: 6px;
            background: var(--bg-color); border: 1px solid var(--border); font-size: 0.82em;
        }
    </style>
</head>
<body>
<div class="container">
    <header role="banner">
        <div>
            <span class="brand">RápidoNF — Clínica Casa Psico</span>
            <span class="badge-luyon">
                Tecnologia Luyon Automações® | {{ cfg.regime_tributario }} (Alíquota {{ aliquota_fmt }}%)
            </span>
        </div>
        <div class="a11y-bar" role="region" aria-label="Menus Operacionais, Contábeis e de Acessibilidade">
            <button type="button" class="btn-fiscal" onclick="document.getElementById('modal-fiscal').showModal()">
                Configurações Fiscais (Contador)
            </button>
            <button type="button" class="btn-pacientes" onclick="document.getElementById('modal-pacientes').showModal()">
                Pacientes Cadastrados ({{ pacientes|length }})
            </button>
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

    {% if config_salva %}
    <div class="alert-success" role="status">
        <span>Parâmetros fiscais do Padrão Nacional NFS-e atualizados no banco SQLite por {{ cfg.contador_responsavel }}!</span>
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
            <div class="kpi-label">DAS Previsto (Alíquota {{ aliquota_fmt }}%)</div>
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

                <label for="servico">Descrição do Serviço Clínico ({{ cfg.codigo_servico[:8] }})</label>
                <select id="servico" name="servico">
                    <option>Sessão de Psicoterapia Individual (50 min)</option>
                    <option>Psicoterapia Infantil / Orientação Parental</option>
                    <option>Avaliação Neuropsicológica Clínica</option>
                </select>

                <label for="valor">Valor da Sessão (R$)</label>
                <input id="valor" name="valor" type="text" inputmode="decimal" value="180,00" required>
                <div id="valor-erro" class="field-error">Informe um valor válido maior que R$ 0,00.</div>

                <div class="tax-box" id="tax-preview">
                    <strong>Enquadramento Ativo (Banco):</strong> {{ cfg.regime_tributario }}<br>
                    <strong>Valor do DAS Estimado ({{ aliquota_fmt }}%):</strong> R$ <span id="das-calc">{{ das_padrao_fmt }}</span>
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
                            <small>DAS ({{ n.aliquota_fmt }}%): R$ {{ n.valor_das_fmt }}</small>
                        </td>
                        <td>
                            <span class="status-ok">{{ n.status }}</span>
                            <div class="actions-cell">
                                <a href="/nota/{{ n.numero }}/pdf" target="_blank" class="btn-pdf">Gerar PDF</a>
                                <button type="button" class="btn-recibo"
                                    onclick="abrirRecibo('{{ n.numero }}', '{{ n.paciente }}', '{{ n.cpf }}', '{{ n.servico }}', '{{ n.valor_fmt }}', '{{ n.valor_das_fmt }}', '{{ n.aliquota_fmt }}', '{{ n.data_emissao }}')">
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

<!-- Modal: Parametrização Fiscal Completa (Leiaute DPS / DANFSe Nacional) -->
<dialog id="modal-fiscal">
    <h3 style="margin-top:0;">Parametrização Fiscal — Padrão Nacional NFS-e (Área do Contador)</h3>
    <p style="font-size:0.85em; color:var(--muted-text); margin-top:-6px;">
        Campos estruturados conforme o <strong>Guia do Emissor Público Nacional NFS-e (v1.3)</strong> e <strong>Notas Técnicas 004/007/009</strong>, gravados na tabela <code>configuracoes_fiscais</code> do SQLite.
    </p>
    <form method="POST" action="/configurar-fiscal">

        <div class="section-divider">1. Identificação da DPS & Ambiente Nacional (ADN)</div>
        <div class="modal-grid-2">
            <div>
                <label for="cfg-amb">Ambiente de Transmissão (tpAmb)</label>
                <select id="cfg-amb" name="ambiente_nacional">
                    <option value="1 - Produção (ADN Receita Federal)" {% if '1 - Produção' in cfg.ambiente_nacional %}selected{% endif %}>
                        1 - Produção (ADN Receita Federal)
                    </option>
                    <option value="2 - Homologação / Produção Restrita" {% if '2 - Homologação' in cfg.ambiente_nacional %}selected{% endif %}>
                        2 - Homologação / Produção Restrita
                    </option>
                </select>
            </div>
            <div>
                <label for="cfg-serie">Série da DPS (serie)</label>
                <input id="cfg-serie" name="serie_dps" type="text" maxlength="5" value="{{ cfg.serie_dps }}" required>
            </div>
        </div>

        <div class="section-divider">2. Dados Cadastrais do Prestador (Emitente)</div>
        <div class="modal-grid-3">
            <div>
                <label for="cfg-razao">Razão Social</label>
                <input id="cfg-razao" name="razao_social" type="text" value="{{ cfg.razao_social }}" required>
            </div>
            <div>
                <label for="cfg-cnpj">CNPJ</label>
                <input id="cfg-cnpj" name="cnpj" type="text" value="{{ cfg.cnpj }}" required>
            </div>
            <div>
                <label for="cfg-im">Inscrição Municipal (IM)</label>
                <input id="cfg-im" name="inscricao_municipal" type="text" value="{{ cfg.inscricao_municipal }}" required>
            </div>
        </div>

        <div class="modal-grid-3">
            <div>
                <label for="cfg-end">Endereço Completo (Logradouro / CEP)</label>
                <input id="cfg-end" name="endereco_prestador" type="text" value="{{ cfg.endereco_prestador }}" required>
            </div>
            <div>
                <label for="cfg-mun">Município / UF</label>
                <input id="cfg-mun" name="municipio_uf" type="text" value="{{ cfg.municipio_uf }}" required>
            </div>
            <div>
                <label for="cfg-ibge">Código IBGE Município</label>
                <input id="cfg-ibge" name="codigo_ibge" type="text" maxlength="7" value="{{ cfg.codigo_ibge }}" required>
            </div>
        </div>

        <div class="modal-grid-3">
            <div>
                <label for="cfg-cnae">CNAE Principal</label>
                <input id="cfg-cnae" name="cnae_principal" type="text" value="{{ cfg.cnae_principal }}" required>
            </div>
            <div>
                <label for="cfg-tel">Telefone (Impresso DANFSe)</label>
                <input id="cfg-tel" name="telefone_prestador" type="text" value="{{ cfg.telefone_prestador }}" required>
            </div>
            <div>
                <label for="cfg-mail">E-mail Institucional</label>
                <input id="cfg-mail" name="email_prestador" type="email" value="{{ cfg.email_prestador }}" required>
            </div>
        </div>

        <div class="section-divider">3. Classificação do Serviço & Reforma Tributária (LC 116 / NBS / IBS-CBS)</div>
        <div class="modal-grid-3">
            <div>
                <label for="cfg-cod">Código Tributação Nacional (cTribNac)</label>
                <input id="cfg-cod" name="codigo_servico" type="text" value="{{ cfg.codigo_servico }}" required>
            </div>
            <div>
                <label for="cfg-nbs">Código NBS (Nomenclatura Bras. Serviços)</label>
                <input id="cfg-nbs" name="codigo_nbs" type="text" value="{{ cfg.codigo_nbs }}" required>
            </div>
            <div>
                <label for="cfg-ibscbs">Regra IBS / CBS (NT 004/009 - LC 214/25)</label>
                <input id="cfg-ibscbs" name="regra_ibs_cbs" type="text" value="{{ cfg.regra_ibs_cbs }}" required>
            </div>
        </div>

        <div class="section-divider">4. Regimes de Tributação & Apuração Simples Nacional (DAS)</div>
        <div class="modal-grid-2">
            <div>
                <label for="cfg-opsn">Opção Simples Nacional (opSimpNac)</label>
                <select id="cfg-opsn" name="op_simples_nacional">
                    <option value="3 - Optante - Microempresa ou Empresa de Pequeno Porte (ME/EPP)" {% if '3 - Optante' in cfg.op_simples_nacional %}selected{% endif %}>
                        3 - Optante - Microempresa ou Empresa de Pequeno Porte (ME/EPP)
                    </option>
                    <option value="2 - Optante - Microempreendedor Individual (MEI)" {% if '2 - Optante' in cfg.op_simples_nacional %}selected{% endif %}>
                        2 - Optante - Microempreendedor Individual (MEI)
                    </option>
                    <option value="1 - Não Optante" {% if '1 - Não Optante' in cfg.op_simples_nacional %}selected{% endif %}>
                        1 - Não Optante
                    </option>
                </select>
            </div>
            <div>
                <label for="cfg-regap">Regime de Apuração SN (regApTribSN)</label>
                <select id="cfg-regap" name="regime_apuracao_sn">
                    <option value="1 - Regime de apuração dos tributos federais e municipal pelo SN (DAS)" {% if '1 - Regime' in cfg.regime_apuracao_sn %}selected{% endif %}>
                        1 - Regime de apuração dos tributos federais e municipal pelo SN (DAS)
                    </option>
                    <option value="2 - Apuração federais pelo SN e ISSQN por fora (Sublimite)" {% if '2 - Apuração' in cfg.regime_apuracao_sn %}selected{% endif %}>
                        2 - Apuração federais pelo SN e ISSQN por fora (Sublimite)
                    </option>
                </select>
            </div>
        </div>

        <div class="modal-grid-3">
            <div>
                <label for="cfg-regime">Enquadramento / Anexo</label>
                <select id="cfg-regime" name="regime_tributario">
                    <option value="Simples Nacional — Anexo III (Fator R >= 28%)" {% if 'Anexo III' in cfg.regime_tributario %}selected{% endif %}>
                        Simples Nacional — Anexo III (Fator R &gt;= 28%)
                    </option>
                    <option value="Simples Nacional — Anexo V (Fator R < 28%)" {% if 'Anexo V' in cfg.regime_tributario %}selected{% endif %}>
                        Simples Nacional — Anexo V (Fator R &lt; 28%)
                    </option>
                    <option value="Lucro Presumido — ISS Municipal + Federais" {% if 'Lucro Presumido' in cfg.regime_tributario %}selected{% endif %}>
                        Lucro Presumido — ISS Municipal + Federais
                    </option>
                </select>
            </div>
            <div>
                <label for="cfg-aliq">Alíquota Efetiva DAS (%)</label>
                <input id="cfg-aliq" name="aliquota_das" type="text" inputmode="decimal" value="{{ aliquota_fmt }}" required>
            </div>
            <div>
                <label for="cfg-regesp">Regime Especial (regEspTrib)</label>
                <select id="cfg-regesp" name="regime_especial_trib">
                    <option value="0 - Nenhum" {% if '0 - Nenhum' in cfg.regime_especial_trib %}selected{% endif %}>0 - Nenhum</option>
                    <option value="4 - Sociedade de Profissionais" {% if '4 - Sociedade' in cfg.regime_especial_trib %}selected{% endif %}>4 - Sociedade de Profissionais</option>
                </select>
            </div>
        </div>

        <div class="modal-grid-2">
            <div>
                <label for="cfg-exig">Exigibilidade do ISSQN (exigISSQN)</label>
                <select id="cfg-exig" name="exigibilidade_issqn">
                    <option value="1 - Exigível (Recolhimento via DAS)" {% if '1 - Exigível' in cfg.exigibilidade_issqn %}selected{% endif %}>
                        1 - Exigível (Recolhimento via DAS)
                    </option>
                    <option value="2 - Exportação de Serviços" {% if '2 - Exportação' in cfg.exigibilidade_issqn %}selected{% endif %}>
                        2 - Exportação de Serviços
                    </option>
                </select>
            </div>
            <div>
                <label for="cfg-ret">Retenção ISSQN / CSRF (NT 007)</label>
                <select id="cfg-ret" name="retencao_issqn_csrf">
                    <option value="1 - Não Retido (Dispensa Simples Nacional)" {% if '1 - Não Retido' in cfg.retencao_issqn_csrf %}selected{% endif %}>
                        1 - Não Retido (Dispensa Simples Nacional)
                    </option>
                    <option value="2 - Retido pelo Tomador" {% if '2 - Retido' in cfg.retencao_issqn_csrf %}selected{% endif %}>
                        2 - Retido pelo Tomador
                    </option>
                </select>
            </div>
        </div>

        <div class="section-divider">5. Responsabilidade Técnica Contábil</div>
        <div class="modal-grid-2">
            <div>
                <label for="cfg-cont">Contador / Assessoria Responsável</label>
                <input id="cfg-cont" name="contador_responsavel" type="text" value="{{ cfg.contador_responsavel }}" required>
            </div>
            <div>
                <label for="cfg-crc">Registro Profissional (CRC)</label>
                <input id="cfg-crc" name="crc_contador" type="text" value="{{ cfg.crc_contador }}" required>
            </div>
        </div>

        <div class="fiscal-meta">
            <strong>Última Homologação Gravada no Banco:</strong> {{ cfg.ultima_atualizacao }} |
            <strong>Responsável Técnico:</strong> {{ cfg.contador_responsavel }} ({{ cfg.crc_contador }})
        </div>

        <button type="submit" class="btn-submit">Salvar Parâmetros Fiscais no Banco SQLite</button>
        <button type="button" class="btn-recibo" style="width:100%; margin-top:8px; padding:10px;"
            onclick="document.getElementById('modal-fiscal').close()">
            Cancelar / Fechar
        </button>
    </form>
</dialog>

<!-- Modal: Pacientes Cadastrados -->
<dialog id="modal-pacientes">
    <h3 style="margin-top:0;">Base de Pacientes Cadastrados (Tomadores)</h3>
    <p style="font-size:0.88em; color:var(--muted-text); margin-top:-6px;">
        Selecione um paciente cadastrado para preencher automaticamente o formulário de emissão de NFS-e.
    </p>
    <table>
        <thead>
            <tr>
                <th>Paciente</th>
                <th>CPF Validado</th>
                <th>Sessões / Total</th>
                <th>Ação</th>
            </tr>
        </thead>
        <tbody>
            {% for p in pacientes %}
            <tr>
                <td><strong>{{ p.paciente }}</strong></td>
                <td>{{ p.cpf }}</td>
                <td>
                    {{ p.qtd_notas }} nota(s)<br>
                    <small>R$ {{ p.total_fmt }}</small>
                </td>
                <td>
                    <button type="button" class="btn-pdf"
                        onclick="selecionarPaciente('{{ p.paciente }}', '{{ p.cpf }}')">
                        Usar na Nota
                    </button>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    <button type="button" class="btn-recibo" style="width:100%; margin-top:14px; padding:10px;"
        onclick="document.getElementById('modal-pacientes').close()">
        Fechar Base de Pacientes
    </button>
</dialog>

<!-- Modal: Espelho da NFS-e -->
<dialog id="modal-recibo">
    <h3 style="margin-top:0;">Espelho da NFS-e Autorizada</h3>
    <p><strong>Prestador:</strong> {{ cfg.razao_social }} (CNPJ {{ cfg.cnpj }})</p>
    <p><strong>Regime Tributário:</strong> {{ cfg.regime_tributario }}</p>
    <hr>
    <p id="recibo-detalhes" style="line-height:1.6;"></p>
    <a id="modal-btn-pdf" href="#" target="_blank" class="btn-submit">Gerar PDF Oficial (DANFSe Nacional)</a>
    <button type="button" class="btn-recibo" style="width:100%; margin-top:8px; padding:10px;" onclick="document.getElementById('modal-recibo').close()">Fechar Espelho</button>
</dialog>

<script>
    const ALIQUOTA_DAS = {{ cfg.aliquota_das / 100.0 }};

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

    function selecionarPaciente(nome, cpf) {
        const campoPac = document.getElementById("paciente");
        const campoCPF = document.getElementById("cpf");
        campoPac.value = nome;
        campoCPF.value = cpf;
        campoCPF.setCustomValidity("");
        document.getElementById("cpf-erro").style.display = "none";
        document.getElementById("modal-pacientes").close();
        document.getElementById("valor").focus();
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

    function abrirRecibo(num, pac, cpf, serv, val, das, aliq, data) {
        document.getElementById("recibo-detalhes").innerHTML =
            `<strong>Número NFS-e:</strong> #${num}<br>` +
            `<strong>Data/Hora Autorização:</strong> ${data}<br>` +
            `<strong>Tomador:</strong> ${pac} (CPF: ${cpf})<br>` +
            `<strong>Serviço:</strong> ${serv}<br>` +
            `<strong>Valor Bruto da Sessão:</strong> R$ ${val}<br>` +
            `<strong>Valor do DAS Previsto (${aliq}%):</strong> R$ ${das}<br>` +
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
    cfg = get_config_fiscal()
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM notas_fiscais ORDER BY id DESC").fetchall()
        pac_rows = conn.execute("""
            SELECT paciente, cpf, COUNT(*) AS qtd_notas, SUM(valor) AS total_valor
            FROM notas_fiscais
            GROUP BY cpf, paciente
            ORDER BY MAX(id) DESC
        """).fetchall()

    notas = []
    for r in rows:
        item = dict(r)
        item["valor_fmt"] = fmt_brl(item["valor"])
        item["valor_das_fmt"] = fmt_brl(item["valor_das"])
        item["aliquota_fmt"] = fmt_brl(item["aliquota_das"])
        notas.append(item)

    pacientes = []
    for p in pac_rows:
        item_p = dict(p)
        item_p["total_fmt"] = fmt_brl(item_p["total_valor"])
        pacientes.append(item_p)

    total_faturado = sum(n["valor"] for n in notas)
    total_das = sum(n["valor_das"] for n in notas)
    das_padrao = round(180.00 * (cfg["aliquota_das"] / 100.0), 2)

    return render_template_string(
        HTML_TEMPLATE,
        cfg=cfg,
        aliquota_fmt=fmt_brl(cfg["aliquota_das"]),
        das_padrao_fmt=fmt_brl(das_padrao),
        notas=notas,
        pacientes=pacientes,
        total_faturado_fmt=fmt_brl(total_faturado),
        total_das_fmt=fmt_brl(total_das),
        emitida=request.args.get("emitida"),
        config_salva=request.args.get("config_salva"),
        erro=request.args.get("erro"),
    )


@app.route("/configurar-fiscal", methods=["POST"])
def configurar_fiscal():
    ambiente_nacional = request.form.get("ambiente_nacional", "").strip()
    serie_dps = request.form.get("serie_dps", "").strip()
    razao_social = request.form.get("razao_social", "").strip()
    cnpj = request.form.get("cnpj", "").strip()
    inscricao_municipal = request.form.get("inscricao_municipal", "").strip()
    cnae_principal = request.form.get("cnae_principal", "").strip()
    endereco_prestador = request.form.get("endereco_prestador", "").strip()
    municipio_uf = request.form.get("municipio_uf", "").strip()
    codigo_ibge = request.form.get("codigo_ibge", "").strip()
    telefone_prestador = request.form.get("telefone_prestador", "").strip()
    email_prestador = request.form.get("email_prestador", "").strip()
    op_simples_nacional = request.form.get("op_simples_nacional", "").strip()
    regime_apuracao_sn = request.form.get("regime_apuracao_sn", "").strip()
    regime_especial_trib = request.form.get("regime_especial_trib", "").strip()
    regime_tributario = request.form.get("regime_tributario", "").strip()
    exigibilidade_issqn = request.form.get("exigibilidade_issqn", "").strip()
    retencao_issqn_csrf = request.form.get("retencao_issqn_csrf", "").strip()
    aliquota_das = parse_valor_brl(request.form.get("aliquota_das", "6,00"))
    codigo_servico = request.form.get("codigo_servico", "").strip()
    codigo_nbs = request.form.get("codigo_nbs", "").strip()
    regra_ibs_cbs = request.form.get("regra_ibs_cbs", "").strip()
    contador_responsavel = request.form.get("contador_responsavel", "").strip()
    crc_contador = request.form.get("crc_contador", "").strip()

    if aliquota_das <= 0 or aliquota_das > 35:
        return redirect(url_for("index", erro="Falha na parametrização fiscal: informe uma alíquota válida entre 0,01% e 35,00%."))

    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    with get_db() as conn:
        conn.execute(
            """
            UPDATE configuracoes_fiscais
            SET ambiente_nacional = ?, serie_dps = ?, razao_social = ?, cnpj = ?,
                inscricao_municipal = ?, cnae_principal = ?, endereco_prestador = ?,
                municipio_uf = ?, codigo_ibge = ?, telefone_prestador = ?, email_prestador = ?,
                op_simples_nacional = ?, regime_apuracao_sn = ?, regime_especial_trib = ?,
                regime_tributario = ?, exigibilidade_issqn = ?, retencao_issqn_csrf = ?,
                aliquota_das = ?, codigo_servico = ?, codigo_nbs = ?, regra_ibs_cbs = ?,
                contador_responsavel = ?, crc_contador = ?, ultima_atualizacao = ?
            WHERE id = 1
            """,
            (
                ambiente_nacional,
                serie_dps,
                razao_social,
                cnpj,
                inscricao_municipal,
                cnae_principal,
                endereco_prestador,
                municipio_uf,
                codigo_ibge,
                telefone_prestador,
                email_prestador,
                op_simples_nacional,
                regime_apuracao_sn,
                regime_especial_trib,
                regime_tributario,
                exigibilidade_issqn,
                retencao_issqn_csrf,
                aliquota_das,
                codigo_servico,
                codigo_nbs,
                regra_ibs_cbs,
                contador_responsavel,
                crc_contador,
                agora,
            ),
        )
        conn.commit()

    return redirect(url_for("index", config_salva="1"))


@app.route("/emitir", methods=["POST"])
def emitir():
    cfg = get_config_fiscal()
    paciente = request.form.get("paciente", "").strip()
    cpf = request.form.get("cpf", "").strip()
    servico = request.form.get("servico", "").strip()
    valor = parse_valor_brl(request.form.get("valor", "0"))

    if not cpf_valido(cpf):
        return redirect(url_for("index", erro="Falha na emissão: CPF inválido ou sequência repetida bloqueada pela validação fiscal."))

    if valor <= 0 or valor > 999999.99:
        return redirect(url_for("index", erro="Falha na emissão: informe um valor monetário válido maior que R$ 0,00."))

    aliquota_atual = cfg["aliquota_das"]
    valor_das = round(valor * (aliquota_atual / 100.0), 2)
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
                aliquota_atual,
                valor_das,
                f"{cfg['regime_tributario']} (Alíquota {fmt_brl(aliquota_atual)}%)",
                "AUTORIZADA",
                data_emissao,
            ),
        )
        conn.commit()

    return redirect(url_for("index", emitida=novo_num))


@app.route("/nota/<numero>/pdf", methods=["GET"])
def baixar_pdf_nota(numero):
    cfg = get_config_fiscal()
    with get_db() as conn:
        row = conn.execute("SELECT * FROM notas_fiscais WHERE numero = ?", (numero,)).fetchone()
    if not row:
        return redirect(url_for("index", erro=f"Nota fiscal #{numero} não encontrada."))

    nota = dict(row)
    nota["valor_fmt"] = fmt_brl(nota["valor"])
    nota["valor_das_fmt"] = fmt_brl(nota["valor_das"])
    nota["aliquota_fmt"] = fmt_brl(nota["aliquota_das"])
    chave_acesso = f"{cfg['codigo_ibge']}22{re.sub(r'\\D', '', cfg['cnpj'])}000000000{nota['numero']}2611139874"
    return render_template_string(DANFSE_NACIONAL_TEMPLATE, nota=nota, cfg=cfg, chave_acesso=chave_acesso)


@app.route("/health", methods=["GET"])
def health():
    cfg = get_config_fiscal()
    with get_db() as conn:
        total_notas = conn.execute("SELECT COUNT(*) FROM notas_fiscais").fetchone()[0]
    return jsonify({
        "status": "UP",
        "service": "RapidoNF-MVP",
        "client": cfg["razao_social"],
        "ambiente_nacional": cfg["ambiente_nacional"],
        "regime": cfg["regime_tributario"],
        "aliquota_das": cfg["aliquota_das"],
        "codigo_ibge": cfg["codigo_ibge"],
        "contador_responsavel": cfg["contador_responsavel"],
        "database": "SQLite Connected",
        "notas_registradas": total_notas,
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)