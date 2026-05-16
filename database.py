import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"), sslmode="require")

def get_cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

def init_db():
    conn = get_connection()
    cur  = get_cursor(conn)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id           SERIAL PRIMARY KEY,
            nome         VARCHAR(150),
            email        VARCHAR(255) UNIQUE NOT NULL,
            senha_hash   VARCHAR(255),
            google_id    VARCHAR(100),
            avatar_url   VARCHAR(500),
            criado_em    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            pdfs_gerados INT DEFAULT 0,
            limite_pdfs  INT DEFAULT 1
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("Banco de dados inicializado.")

if __name__ == "__main__":
    init_db()