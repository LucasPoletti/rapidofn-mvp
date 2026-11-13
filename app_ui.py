from flask import Flask, render_template_string, request, redirect, url_for
from datetime import datetime

app = Flask(__name__)

# Base em memória com dados iniciais reais da Casa Psico
notas_emitidas = [
    {
        "numero": "2026001",
        "paciente": "Mariana Costa Silva",
        "cpf": "123.456.789-00",
        "servico": "Sessão de Psicoterapia Individual (50 min)",
        "valor": 180.00,
        "status": "AUTORIZADA",
        "data": "13/11/2026 09:10"
    },
    {
        "numero": "2026002",
        "paciente": "Carlos Eduardo Mendes",
        "cpf": "987.654.321-11",
        "servico": "Avaliação Psicológica Clínica",
        "valor": 250.00,
        "status": "AUTORIZADA",
        "data": "13/11/2026 09:22"
    }
]

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>RápidoNF | Emissão Inteligente NFS-e - Casa Psico</title>
    <style>
        :root {
            --bg-color: #f4f7f9;
            --card-bg: #ffffff;
            --text-color: #1e293b;
            --primary: #0f766e;
            --primary-hover: #115e59;
            --border: #cbd5e1;
            --font-scale: 1rem;
        }
        body.high-contrast {
            --bg-color: #000000;
            --card-bg: #111111;
            --text-color: #ffff00;
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
        .container { max-width: 960px; margin: 0 auto; }
        header {
            display: flex; justify-content: space-between; align-items: center;
            background: var(--card-bg); padding: 16px 24px; border-radius: 10px;
            border: 2px solid var(--border); margin-bottom: 20px;
        }
        .brand { font-weight: 800; font-size: 1.3em; }
        .badge-luyon { font-size: 0.75em; opacity: 0.85; display: block; }
        .a11y-bar button {
            background: transparent; color: var(--text-color); border: 2px solid var(--border);
            padding: 8px 12px; border-radius: 6px; cursor: pointer; font-weight: 700; margin-left: 8px;
        }
        .grid { display: grid; grid-template-columns: 1fr 1.4fr; gap: 20px; }
        .card {
            background: var(--card-bg); padding: 20px; border-radius: 10px;
            border: 2px solid var(--border);
        }
        label { display: block; font-weight: 700; margin-top: 12px; margin-bottom: 4px; }
        input, select {
            width: 100%; padding: 10px; border-radius: 6px; border: 2px solid var(--border);
            background: var(--bg-color); color: var(--text-color); font-size: 1em; box-sizing: border-box;
        }
        .btn-submit {
            margin-top: 18px; width: 100%; padding: 12px; border: none; border-radius: 6px;
            background: var(--primary); color: #ffffff; font-weight: 800; font-size: 1em; cursor: pointer;
        }
        body.high-contrast .btn-submit { color: #000000; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { text-align: left; padding: 10px; border-bottom: 1px solid var(--border); }
        .status-ok {
            background: #dcfce7; color: #166534; padding: 4px 8px; border-radius: 4px; font-weight: 700; font-size: 0.85em;
        }
        body.high-contrast .status-ok { background: #ffff00; color: #000000; }
    </style>
</head>
<body>
<div class="container">
    <header role="banner">
        <div>
            <span class="brand">RápidoNF — Clínica Casa Psico</span>
            <span class="badge-luyon">Tecnologia Luyon Automações® | Simples Nacional (ISS)</span>
        </div>
        <div class="a11y-bar" role="region" aria-label="Controles de Acessibilidade">
            <button type="button" onclick="document.body.classList.toggle('high-contrast')" aria-pressed="false">
                Alto Contraste
            </button>
            <button type="button" onclick="document.body.classList.toggle('large-font')" aria-pressed="false">
                Aumentar Fonte (A+)
            </button>
        </div>
    </header>

    <div class="grid">
        <section class="card" aria-labelledby="titulo-emissao">
            <h2 id="titulo-emissao" style="margin-top:0;">Emitir Nova NFS-e</h2>
            <form method="POST" action="/emitir">
                <label for="paciente">Nome do Paciente (Tomador)</label>
                <input id="paciente" name="paciente" type="text" placeholder="Ex: Fernanda Oliveira" required>

                <label for="cpf">CPF do Paciente</label>
                <input id="cpf" name="cpf" type="text" placeholder="000.000.000-00" required>

                <label for="servico">Descrição do Serviço Clínico</label>
                <select id="servico" name="servico">
                    <option>Sessão de Psicoterapia Individual (50 min)</option>
                    <option>Psicoterapia Infantil / Orientação Parental</option>
                    <option>Avaliação Neuropsicológica</option>
                </select>

                <label for="valor">Valor da Sessão (R$)</label>
                <input id="valor" name="valor" type="number" step="0.01" value="180.00" required>

                <button type="submit" class="btn-submit">Transmitir NFS-e Agora</button>
            </form>
        </section>

        <section class="card" aria-labelledby="titulo-historico">
            <h2 id="titulo-historico" style="margin-top:0;">Notas Fiscais Emitidas (Tempo Real)</h2>
            <table>
                <thead>
                    <tr>
                        <th>NFS-e</th>
                        <th>Paciente</th>
                        <th>Valor</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {% for n in notas %}
                    <tr>
                        <td><strong>#{{ n.numero }}</strong><br><small>{{ n.data }}</small></td>
                        <td>{{ n.paciente }}<br><small>{{ n.servico }}</small></td>
                        <td>R$ {{ "%.2f"|format(n.valor) }}</td>
                        <td><span class="status-ok">{{ n.status }}</span></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </section>
    </div>
</div>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_TEMPLATE, notas=notas_emitidas)

@app.route("/emitir", methods=["POST"])
def emitir():
    novo_num = f"202600{len(notas_emitidas) + 1}"
    notas_emitidas.insert(0, {
        "numero": novo_num,
        "paciente": request.form.get("paciente"),
        "cpf": request.form.get("cpf"),
        "servico": request.form.get("servico"),
        "valor": float(request.form.get("valor", 180.00)),
        "status": "AUTORIZADA",
        "data": datetime.now().strftime("%d/%m/%Y %H:%M")
    })
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True, port=5050)