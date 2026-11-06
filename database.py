import sqlite3

DATABASE = "rapidofn.db"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notas_fiscais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tomador_nome TEXT NOT NULL,
            tomador_cpf_cnpj TEXT NOT NULL,
            servico_descricao TEXT NOT NULL,
            valor REAL NOT NULL,
            aliquota_iss REAL DEFAULT 2.0,
            status TEXT DEFAULT 'emitida',
            data_emissao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Base de dados inicializada com sucesso!")
