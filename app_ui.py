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
                aliquota_iss REAL NOT NULL,
                valor_iss REAL NOT NULL,
                regime TEXT NOT NULL,
                status TEXT NOT NULL,
                data_emissao TEXT NOT NULL
            )
        """)
        total = conn.execute("SELECT COUNT(*) FROM notas_fiscais").fetchone()[0]
        if total == 0:
            iniciais = [
                (
                    "2026001",
                    "Mariana Costa Silva",
                    "123.456.789-00",
                    "Sessão de Psicoterapia Individual (50 min)",
                    180.00,
                    2.00,
                    3.60,
                    "Simples Nacional - Anexo III",
                    "AUTORIZADA",
                    "13/11/2026 09:10",
                ),
                (
                    "2026002",
                    "Carlos Eduardo Mendes",
                    "987.654.321-11",
                    "Avaliação Psicológica Clínica",
                    250.00,
                    2.00,
                    5.00,
                    "Simples Nacional - Anexo III",
                    "AUTORIZADA",
                    "13/11/2026 09:22",
                ),
            ]
            conn.executemany(
                """
                INSERT INTO notas_fiscais
                (numero, paciente, cpf, servico, valor, aliquota_iss, valor_iss, regime, status, data_emissao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                iniciais,
            )
        conn.commit()


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
        .container { max-width: 1080px; margin: 0 auto; }
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
        .grid { display: grid; grid-template-columns: 1fr 1.55fr; gap: 20px; }
        @media (max-width: 820px) {
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
        }
        .btn-submit:hover { background: var(--primary-hover); }
        body.high-contrast .btn-submit { color: #000000; }
        .alert-success {
            background: #dcfce7; color: #166534; border: 2px solid #16a34a;
            padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; font-weight: 700;
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
        .btn-recibo {
            background: transparent; color: var(--text-color); border: 1px solid var(--border);
            padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 0.8em; font-weight: 700; margin-top: 4px;
        }
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
            <span class="badge-luyon">Tecnologia Luyon Automações® | Simples Nacional (Anexo III — ISS 2,00%)</span>
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
        NFS-e #{{ emitida }} autorizada e gravada no banco de dados SQLite com sucesso!
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
            <div class="kpi-label">ISS Retido / Apurado (2%)</div>
            <div class="kpi-value">R$ {{ total_iss_fmt }}</div>
        </div>
    </div>

    <div class="grid">
        <section class="card" aria-labelledby="titulo-emissao">
            <h2 id="titulo-emissao" style="margin-top:0;">Emitir Nova NFS-e</h2>
            <form method="POST" action="/emitir" onsubmit="return validarFormulario()">
                <label for="paciente">Nome do Paciente (Tomador)</label>
                <input id="paciente" name="paciente" type="text" placeholder="Ex: Fernanda Oliveira" required>

                <label for="cpf">CPF do Paciente</label>
                <input id="cpf" name="cpf" type="text" maxlength="14" placeholder="000.000.000-00" oninput="mascaraCPF(this)" required>
                <div id="cpf-erro" class="field-error">CPF inválido. Informe um CPF válido com dígitos verificadores reais.</div>

                <label for="servico">Descrição do Serviço Clínico (LC 116/03 - 04.16)</label>
                <select id="servico" name="servico">
                    <option>Sessão de Psicoterapia Individual (50 min)</option>
                    <option>Psicoterapia Infantil / Orientação Parental</option>
                    <option>Avaliação Neuropsicológica Clínica</option>
                </select>

                <label for="valor">Valor da Sessão (R$)</label>
                <input id="valor" name="valor" type="text" inputmode="decimal" value="180,00"
                       oninput="filtrarValor(this)" onblur="formatarValorFinal(this)"
                       onkeydown="tratarEnterValor(event, this)" required>
                <div id="valor-erro" class="field-error">Informe um valor válido maior que R$ 0,00.</div>

                <div class="tax-box" id="tax-preview">
                    <strong>Enquadramento Automático:</strong> Simples Nacional (Anexo III)<br>
                    <strong>ISS Estimado (2,00%):</strong> R$ <span id="iss-calc">3,60</span>
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
                        <th>Valor / ISS</th>
                        <th>Status</th>
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
                            <small>ISS: R$ {{ n.valor_iss_fmt }}</small>
                        </td>
                        <td>
                            <span class="status-ok">{{ n.status }}</span><br>
                            <button type="button" class="btn-recibo"
                                onclick="abrirRecibo('{{ n.numero }}', '{{ n.paciente }}', '{{ n.cpf }}', '{{ n.servico }}', '{{ n.valor_fmt }}', '{{ n.valor_iss_fmt }}', '{{ n.data_emissao }}')">
                                Ver Espelho
                            </button>
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
    <p><strong>Regime Tributário:</strong> Simples Nacional — Anexo III (Alíquota ISS: 2,00%)</p>
    <hr>
    <p id="recibo-detalhes" style="line-height:1.6;"></p>
    <button type="button" class="btn-submit" onclick="document.getElementById('modal-recibo').close()">Fechar Espelho</button>
</dialog>

<script>
    function validarCPFJS(cpf) {
        const nums = cpf.replace(/\\D/g, "");
        if (nums.length !== 11 || /^(\\d)\\1{10}$/.test(nums)) return false;

        let soma = 0;
        for (let i = 0; i < 9; i++) soma += parseInt(nums[i]) * (10 - i);
        let dig1 = (soma * 10) % 11;
        if (dig1 === 10) dig1 = 0;
        if (dig1 !== parseInt(nums[9])) return false;

        soma = 0;
        for (let i = 0; i < 10; i++) soma += parseInt(nums[i]) * (11 - i);
        let dig2 = (soma * 10) % 11;
        if (dig2 === 10) dig2 = 0;
        return dig2 === parseInt(nums[10]);
    }

    function mascaraCPF(campo) {
        let v = campo.value.replace(/\\D/g, "").slice(0, 11);
        v = v.replace(/(\\d{3})(\\d)/, "$1.$2");
        v = v.replace(/(\\d{3})(\\d)/, "$1.$2");
        v = v.replace(/(\\d{3})(\\d{1,2})$/, "$1-$2");
        campo.value = v;

        const erroEl = document.getElementById("cpf-erro");
        if (v.length === 14 && !validarCPFJS(v)) {
            erroEl.style.display = "block";
            campo.setCustomValidity("CPF inválido.");
        } else {
            erroEl.style.display = "none";
            campo.setCustomValidity("");
        }
    }

    function parseValorJS(texto) {
        let limpo = (texto || "").replace(/[^\\d,.]/g, "");
        if (!limpo) return 0;
        if (limpo.includes(",")) {
            limpo = limpo.replace(/\\./g, "").replace(",", ".");
        }
        const num = parseFloat(limpo);
        return isNaN(num) ? 0 : num;
    }

    function formatarBRLJS(num) {
        return num.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function filtrarValor(campo) {
        campo.value = campo.value.replace(/[^\\d,.]/g, "");
        const val = parseValorJS(campo.value);
        document.getElementById("iss-calc").textContent = formatarBRLJS(val * 0.02);
        document.getElementById("valor-erro").style.display = "none";
    }

    function formatarValorFinal(campo) {
        const val = parseValorJS(campo.value);
        const erroEl = document.getElementById("valor-erro");
        if (val <= 0 || val > 999999.99) {
            erroEl.style.display = "block";
            return false;
        }
        erroEl.style.display = "none";
        campo.value = formatarBRLJS(val);
        document.getElementById("iss-calc").textContent = formatarBRLJS(val * 0.02);
        return true;
    }

    function tratarEnterValor(event, campo) {
        if (event.key === "Enter") {
            event.preventDefault();
            if (formatarValorFinal(campo)) {
                campo.blur();
                document.getElementById("btn-transmitir").focus();
            }
        }
    }

    function validarFormulario() {
        const campoCPF = document.getElementById("cpf");
        if (!validarCPFJS(campoCPF.value)) {
            document.getElementById("cpf-erro").style.display = "block";
            campoCPF.focus();
            return false;
        }
        const campoValor = document.getElementById("valor");
        if (!formatarValorFinal(campoValor)) {
            campoValor.focus();
            return false;
        }
        return true;
    }

    function toggleContrast() {
        const active = document.body.classList.toggle("high-contrast");
        document.getElementById("btn-contrast").setAttribute("aria-pressed", active);
    }

    function toggleFont() {
        const active = document.body.classList.toggle("large-font");
        document.getElementById("btn-font").setAttribute("aria-pressed", active);
    }

    function abrirRecibo(num, pac, cpf, serv, val, iss, data) {
        document.getElementById("recibo-detalhes").innerHTML =
            `<strong>Número NFS-e:</strong> #${num}<br>` +
            `<strong>Data/Hora Autorização:</strong> ${data}<br>` +
            `<strong>Tomador:</strong> ${pac} (CPF: ${cpf})<br>` +
            `<strong>Serviço:</strong> ${serv}<br>` +
            `<strong>Valor Bruto:</strong> R$ ${val}<br>` +
            `<strong>ISS Apurado (2%):</strong> R$ ${iss}<br>` +
            `<strong>Situação:</strong> AUTORIZADA`;
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
        item["valor_iss_fmt"] = fmt_brl(item["valor_iss"])
        notas.append(item)

    total_faturado = sum(n["valor"] for n in notas)
    total_iss = sum(n["valor_iss"] for n in notas)
    emitida = request.args.get("emitida")
    erro = request.args.get("erro")
    return render_template_string(
        HTML_TEMPLATE,
        notas=notas,
        total_faturado_fmt=fmt_brl(total_faturado),
        total_iss_fmt=fmt_brl(total_iss),
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

    aliquota_iss = 2.00
    valor_iss = round(valor * (aliquota_iss / 100.0), 2)
    data_emissao = datetime.now().strftime("%d/%m/%Y %H:%M")

    with get_db() as conn:
        ultimo_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM notas_fiscais").fetchone()[0]
        novo_num = f"2026{ultimo_id + 1:03d}"
        conn.execute(
            """
            INSERT INTO notas_fiscais
            (numero, paciente, cpf, servico, valor, aliquota_iss, valor_iss, regime, status, data_emissao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                novo_num,
                paciente,
                cpf,
                servico,
                valor,
                aliquota_iss,
                valor_iss,
                "Simples Nacional - Anexo III",
                "AUTORIZADA",
                data_emissao,
            ),
        )
        conn.commit()

    return redirect(url_for("index", emitida=novo_num))


@app.route("/health", methods=["GET"])
def health():
    with get_db() as conn:
        total_notas = conn.execute("SELECT COUNT(*) FROM notas_fiscais").fetchone()[0]
    return jsonify({
        "status": "UP",
        "service": "RapidoNF-MVP",
        "client": "Casa Psico",
        "database": "SQLite Connected",
        "notas_registradas": total_notas,
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)