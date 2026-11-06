from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import database

app = Flask(__name__, template_folder="app/templates", static_folder="app/static")
app.secret_key = "luyon-chave-secreta-mvp"

database.init_db()

@app.route("/")
def index():
    conn = database.get_db()
    notas = conn.execute("SELECT * FROM notas_fiscais ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("index.html", notas=notas)

@app.route("/emitir", methods=["POST"])
def emitir():
    nome = request.form.get("nome", "").strip()
    cpf_cnpj = request.form.get("cpf_cnpj", "").strip()
    servico = request.form.get("servico", "").strip()
    valor_str = request.form.get("valor", "").replace(",", ".").strip()

    if not nome or not cpf_cnpj or not valor_str:
        flash("Preencha todos os campos obrigatórios.", "danger")
        return redirect(url_for("index"))

    try:
        valor = float(valor_str)
        if valor <= 0:
            raise ValueError()
    except ValueError:
        flash("Valor da nota inválido.", "danger")
        return redirect(url_for("index"))

    conn = database.get_db()
    conn.execute(
        "INSERT INTO notas_fiscais (tomador_nome, tomador_cpf_cnpj, servico_descricao, valor) VALUES (?, ?, ?, ?)",
        (nome, cpf_cnpj, servico or "Consulta Psicológica / Psicoterapia", valor)
    )
    conn.commit()
    conn.close()

    flash("Nota Fiscal emitida com sucesso em conformidade fiscal!", "success")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True, port=5000)
