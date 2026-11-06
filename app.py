from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def index():
    return jsonify({
        "status": "online",
        "app": "RápidoNF",
        "empresa": "Casa Psico",
        "desenvolvimento": "Luyon Automações"
    })

if __name__ == "__main__":
    app.run(debug=True)
