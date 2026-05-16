from flask import Blueprint, request, jsonify, session, redirect, url_for
from flask_bcrypt import Bcrypt
from authlib.integrations.flask_client import OAuth
from database import get_connection, get_cursor
import os, re

auth_bp = Blueprint("auth", __name__)
bcrypt  = Bcrypt()
oauth   = OAuth()

def init_auth(app):
    bcrypt.init_app(app)
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"}
    )

def email_valido(email):
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email)

def usuario_logado():
    return session.get("usuario_id") is not None

def get_usuario():
    uid = session.get("usuario_id")
    if not uid:
        return None
    conn = get_connection()
    cur  = get_cursor(conn)
    cur.execute("SELECT * FROM usuarios WHERE id = %s", (uid,))
    u = cur.fetchone()
    cur.close(); conn.close()
    return dict(u) if u else None

def pode_gerar_pdf(usuario):
    if not usuario:
        return False
    return usuario["pdfs_gerados"] < usuario["limite_pdfs"]

def registrar_geracao(usuario_id):
    conn = get_connection()
    cur  = get_cursor(conn)
    cur.execute("UPDATE usuarios SET pdfs_gerados = pdfs_gerados + 1 WHERE id = %s", (usuario_id,))
    conn.commit()
    cur.close(); conn.close()


# ===== ROTAS DE AUTH =====

@auth_bp.route("/auth/cadastro", methods=["POST"])
def cadastro():
    data  = request.get_json()
    nome  = (data.get("nome")  or "").strip()
    email = (data.get("email") or "").strip().lower()
    senha = (data.get("senha") or "").strip()

    if not email or not email_valido(email):
        return jsonify({"erro": "E-mail inválido"}), 400
    if len(senha) < 6:
        return jsonify({"erro": "Senha deve ter pelo menos 6 caracteres"}), 400

    conn = get_connection()
    cur  = get_cursor(conn)
    cur.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
    if cur.fetchone():
        cur.close(); conn.close()
        return jsonify({"erro": "E-mail já cadastrado"}), 409

    hash_senha = bcrypt.generate_password_hash(senha).decode("utf-8")
    cur.execute(
        "INSERT INTO usuarios (nome, email, senha_hash) VALUES (%s, %s, %s) RETURNING id",
        (nome or email.split("@")[0], email, hash_senha)
    )
    uid = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()

    session["usuario_id"]    = uid
    session["usuario_nome"]  = nome or email.split("@")[0]
    session["usuario_email"] = email
    return jsonify({"sucesso": True, "nome": nome or email.split("@")[0]})


@auth_bp.route("/auth/login", methods=["POST"])
def login():
    data  = request.get_json()
    email = (data.get("email") or "").strip().lower()
    senha = (data.get("senha") or "").strip()

    if not email or not senha:
        return jsonify({"erro": "Preencha e-mail e senha"}), 400

    conn = get_connection()
    cur  = get_cursor(conn)
    cur.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
    u = cur.fetchone()
    cur.close(); conn.close()

    if not u or not u.get("senha_hash"):
        return jsonify({"erro": "E-mail ou senha incorretos"}), 401
    if not bcrypt.check_password_hash(u["senha_hash"], senha):
        return jsonify({"erro": "E-mail ou senha incorretos"}), 401

    session["usuario_id"]    = u["id"]
    session["usuario_nome"]  = u["nome"]
    session["usuario_email"] = u["email"]
    return jsonify({"sucesso": True, "nome": u["nome"]})


@auth_bp.route("/auth/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@auth_bp.route("/auth/google")
def google_login():
    redirect_uri = url_for("auth.google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/auth/google/callback")
def google_callback():
    token    = oauth.google.authorize_access_token()
    userinfo = token.get("userinfo") or oauth.google.userinfo()

    google_id  = userinfo["sub"]
    email      = userinfo.get("email", "").lower()
    nome       = userinfo.get("name", email.split("@")[0])
    avatar_url = userinfo.get("picture", "")

    conn = get_connection()
    cur  = get_cursor(conn)

    cur.execute("SELECT * FROM usuarios WHERE google_id = %s OR email = %s", (google_id, email))
    u = cur.fetchone()

    if u:
        if not u.get("google_id"):
            cur.execute("UPDATE usuarios SET google_id = %s, avatar_url = %s WHERE id = %s",
                        (google_id, avatar_url, u["id"]))
            conn.commit()
        uid  = u["id"]
        nome = u["nome"]
    else:
        cur.execute(
            "INSERT INTO usuarios (nome, email, google_id, avatar_url) VALUES (%s, %s, %s, %s) RETURNING id",
            (nome, email, google_id, avatar_url)
        )
        uid = cur.fetchone()["id"]
        conn.commit()

    cur.close(); conn.close()
    session["usuario_id"]    = uid
    session["usuario_nome"]  = nome
    session["usuario_email"] = email
    return redirect(url_for("index"))


@auth_bp.route("/auth/status")
def auth_status():
    u = get_usuario()
    if not u:
        return jsonify({"logado": False})
    return jsonify({
        "logado": True,
        "nome": u["nome"],
        "email": u["email"],
        "pdfs_gerados": u["pdfs_gerados"],
        "limite_pdfs": u["limite_pdfs"],
        "pode_gerar": pode_gerar_pdf(u)
    })
