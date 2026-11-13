import os
import re
import sqlite3
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, Response

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


def gerar_pdf_nfse_bytes(nota: dict) -> bytes:
    """Gera um documento PDF (DANFSe) válido e estruturado em A4 sem dependências externas."""
    def esc(txt: str) -> str:
        return (
            str(txt)
            .replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )

    linhas_conteudo = [
        "q",
        "0.06 0.46 0.43 RG 1.5 w 36 36 523 770 re S",
        "0.06 0.46 0.43 rg 36 742 523 64 re f",
        "1 1 1 rg BT /F2 15 Tf 50 780 Td (DANFSe - DOCUMENTO AUXILIAR DA NFS-e) Tj ET",
        "1 1 1 rg BT /F1 9.5 Tf 50 762 Td (Sistema RapidoNF | Tecnologia Luyon Automacoes - Emissao Simplificada) Tj ET",
        f"1 1 1 rg BT /F2 12 Tf 430 780 Td (NFS-e #{esc(nota['numero'])}) Tj ET",
        f"1 1 1 rg BT /F1 9 Tf 430 762 Td ({esc(nota['data_emissao'])}) Tj ET",
        "0.12 0.16 0.23 rg BT /F2 10 Tf 50 715 Td (1. IDENTIFICACAO DO PRESTADOR DE SERVICOS) Tj ET",
        "0.8 0.84 0.88 RG 0.8 w 50 708 m 545 708 l S",
        "BT /F2 9.5 Tf 50 692 Td (Razao Social:) Tj /F1 9.5 Tf 135 692 Td (CASA PSICO PSICOLOGIA CLINICA LTDA) Tj ET",
        "BT /F2 9.5 Tf 50 676 Td (CNPJ:) Tj /F1 9.5 Tf 135 676 Td (63.897.592/0001-06) Tj ET",
        "BT /F2 9.5 Tf 50 660 Td (Enquadramento:) Tj /F1 9.5 Tf 135 660 Td (Simples Nacional - Anexo III (Aliquota 6,00% inicial)) Tj ET",
        "BT /F2 9.5 Tf 50 644 Td (Codigo Servico:) Tj /F1 9.5 Tf 135 644 Td (LC 116/2003 - Item 04.16 - Psicologia e Psicanalise) Tj ET",
        "BT /F2 10 Tf 50 612 Td (2. IDENTIFICACAO DO TOMADOR (PACIENTE)) Tj ET",
        "50 605 m 545 605 l S",
        f"BT /F2 9.5 Tf 50 589 Td (Nome Completo:) Tj /F1 9.5 Tf 145 589 Td ({esc(nota['paciente'])}) Tj ET",
        f"BT /F2 9.5 Tf 50 573 Td (CPF Validado:) Tj /F1 9.5 Tf 145 573 Td ({esc(nota['cpf'])}) Tj ET",
        "BT /F2 10 Tf 50 541 Td (3. DISCRIMINACAO DOS SERVICOS PRESTADOS) Tj ET",
        "50 534 m 545 534 l S",
        "0.96 0.97 0.98 rg 50 475 495 50 re f",
        "0.8 0.84 0.88 RG 50 475 495 50 re S",
        f"0.12 0.16 0.23 rg BT /F1 10 Tf 60 505 Td ({esc(nota['servico'])}) Tj ET",
        "BT /F1 8.5 Tf 60 488 Td (Atendimento clinico realizado conforme prontuario reservado sob sigilo profissional.) Tj ET",
        "BT /F2 10 Tf 50 445 Td (4. VALORES E APURACAO TRIBUTARIA (SIMPLES NACIONAL)) Tj ET",
        "50 438 m 545 438 l S",
        f"BT /F2 10 Tf 50 418 Td (Valor Bruto dos Servicos:) Tj /F2 11 Tf 220 418 Td (R$ {esc(fmt_brl(nota['valor']))}) Tj ET",
        f"BT /F2 10 Tf 50 398 Td (Aliquota Anexo III (Inicial):) Tj /F1 10 Tf 220 398 Td (6,00%) Tj ET",
        f"BT /F2 10 Tf 50 378 Td (Valor do DAS Previsto (6,00%):) Tj /F2 11 Tf 220 378 Td (R$ {esc(fmt_brl(nota['valor_das']))}) Tj ET",
        f"BT /F2 10 Tf 50 358 Td (Situacao Fiscal:) Tj /F2 10 Tf 220 358 Td ({esc(nota['status'])}) Tj ET",
        "50 110 m 545 110 l S",
        "BT /F2 8.5 Tf 50 94 Td (AUTENTICIDADE E RASTREABILIDADE DIGITAL - RAPIDONF MVP) Tj ET",
        f"BT /F1 8 Tf 50 80 Td (Codigo de Verificacao: RNF-{esc(nota['numero'])}-CASAPSICO-SNIII) Tj ET",
        "BT /F1 8 Tf 50 66 Td (Documento emitido eletronicamente via plataforma RapidoNF (https://rapidonf-mvp.onrender.com).) Tj ET",
        "Q",
    ]

    stream_bytes = "\n".join(linhas_conteudo).encode("latin-1", errors="replace")

    objs = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >> endobj\n",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >> endobj\n",
        f"6 0 obj << /Length {len(stream_bytes)} >> stream\n".encode("ascii") + stream_bytes + b"\nendstream endobj\n",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objs:
        offsets.append(len(pdf))
        pdf.extend(obj)

    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(objs) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("ascii"))

    pdf.extend(
        f"trailer << /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


init_db()

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
            Baixar PDF da NFS-e #{{ emitida }}
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
    <a id="modal-btn-pdf" href="#" target="_blank" class="btn-submit">Baixar PDF Oficial (DANFSe)</a>
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

    pdf_bytes = gerar_pdf_nfse_bytes(dict(row))
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=DANFSe_{numero}_CasaPsico.pdf"
        },
    )


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