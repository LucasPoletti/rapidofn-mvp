import pytest
import os
import database
from app import app as flask_app

@pytest.fixture
def client():
    database.DATABASE = "test_rapidofn.db"
    database.init_db()
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as client:
        yield client
    if os.path.exists("test_rapidofn.db"):
        os.remove("test_rapidofn.db")

def test_pagina_inicial(client):
    resposta = client.get("/")
    assert resposta.status_code == 200
    assert b"R\xc3\xa1pidoNF" in resposta.data

def test_emissao_nota_sucesso(client):
    dados = {
        "nome": "Paciente Teste",
        "cpf_cnpj": "123.456.789-00",
        "servico": "Sessão Teste",
        "valor": "150.00"
    }
    resposta = client.post("/emitir", data=dados, follow_redirects=True)
    assert resposta.status_code == 200
    assert b"Paciente Teste" in resposta.data

def test_emissao_nota_valor_invalido(client):
    dados = {
        "nome": "Paciente Invalido",
        "cpf_cnpj": "123.456.789-00",
        "servico": "Sessão Teste",
        "valor": "-50.00"
    }
    resposta = client.post("/emitir", data=dados, follow_redirects=True)
    assert b"Valor da nota" in resposta.data
