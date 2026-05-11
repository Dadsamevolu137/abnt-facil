import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "abnt_saas")
    )

def init_db():
    """Cria banco e tabelas se não existirem."""
    # Conecta sem banco para criá-lo
    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "")
    )
    cur = conn.cursor()
    cur.execute("CREATE DATABASE IF NOT EXISTS abnt_saas CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cur.execute("USE abnt_saas")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            nome        VARCHAR(150),
            email       VARCHAR(255) UNIQUE NOT NULL,
            senha_hash  VARCHAR(255),
            google_id   VARCHAR(100),
            avatar_url  VARCHAR(500),
            criado_em   DATETIME DEFAULT CURRENT_TIMESTAMP,
            pdfs_gerados INT DEFAULT 0,
            limite_pdfs  INT DEFAULT 99
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("✓ Banco de dados inicializado.")

if __name__ == "__main__":
    init_db()
