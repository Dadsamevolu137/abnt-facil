from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from flask_session import Session
from dotenv import load_dotenv
import os, uuid
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from database import init_db, get_connection
from auth import auth_bp, init_auth, get_usuario, pode_gerar_pdf, registrar_geracao

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "chave-secreta-local")
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = "./flask_session"
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
Session(app)

app.register_blueprint(auth_bp)
init_auth(app)

UPLOAD_FOLDER = "generated_pdfs"
LOGO_FOLDER   = "uploaded_logos"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(LOGO_FOLDER, exist_ok=True)
os.makedirs("flask_session", exist_ok=True)


def registrar_arial():
    caminhos = ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/Arial.ttf"]
    for path in caminhos:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("Arial", path))
                bold = path.lower().replace("arial.ttf", "arialbd.ttf")
                if os.path.exists(bold):
                    pdfmetrics.registerFont(TTFont("Arial-Bold", bold))
                    return "Arial", "Arial-Bold"
                return "Arial", "Helvetica-Bold"
            except Exception:
                pass
    return "Helvetica", "Helvetica-Bold"


def get_estilos(fonte, fonte_bold):
    TAM  = 12
    LEAD = TAM * 1.5

    base = ParagraphStyle("base", fontName=fonte, fontSize=TAM, leading=LEAD,
        textColor=colors.black, alignment=TA_JUSTIFY,
        firstLineIndent=1.25*cm, spaceAfter=0, spaceBefore=0)

    centralizado = ParagraphStyle("centralizado", parent=base,
        alignment=TA_CENTER, firstLineIndent=0)

    centralizado_bold = ParagraphStyle("centralizado_bold", parent=centralizado,
        fontName=fonte_bold)

    secao = ParagraphStyle("secao", parent=base, fontName=fonte_bold,
        alignment=TA_LEFT, firstLineIndent=0,
        spaceBefore=0.5*cm, spaceAfter=0.3*cm)

    resumo_titulo = ParagraphStyle("resumo_titulo", parent=centralizado_bold,
        spaceBefore=0, spaceAfter=0.5*cm)

    resumo_texto = ParagraphStyle("resumo_texto", parent=base,
        firstLineIndent=0, alignment=TA_JUSTIFY)

    referencia = ParagraphStyle("referencia", parent=base,
        firstLineIndent=0, alignment=TA_JUSTIFY, spaceAfter=0.2*cm)

    italico = ParagraphStyle("italico", parent=centralizado,
        fontName=fonte.replace("Helvetica", "Helvetica-Oblique").replace("Arial", "Arial"))

    return {
        "base": base,
        "centralizado": centralizado,
        "centralizado_bold": centralizado_bold,
        "secao": secao,
        "resumo_titulo": resumo_titulo,
        "resumo_texto": resumo_texto,
        "referencia": referencia,
        "italico": italico,
    }


def build_cabecalho(fonte, fonte_bold, logo_path, campus, largura_util):
    """
    Retorna uma Table que representa o cabeçalho:
    [LOGO]  |  [Instituição / Campus]
    Centralizado, logo à esquerda, texto à direita (ou só texto se sem logo).
    """
    from reportlab.platypus import Table, TableStyle

    estilo_campus = ParagraphStyle("cab_campus",
        fontName=fonte_bold, fontSize=12, leading=16,
        textColor=colors.black, alignment=TA_CENTER)

    estilo_inst = ParagraphStyle("cab_inst",
        fontName=fonte, fontSize=10, leading=14,
        textColor=colors.black, alignment=TA_CENTER)

    col_texto = []
    if campus:
        col_texto.append(Paragraph(f"<i>Campus</i> {campus}", estilo_campus))

    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image(logo_path, width=2.8*cm, height=2.8*cm, kind="proportional")
            logo_img.hAlign = "CENTER"
            data = [[logo_img, col_texto if col_texto else Paragraph("", estilo_campus)]]
            col_widths = [3*cm, largura_util - 3*cm]
        except Exception:
            logo_img = None
            data = [[col_texto if col_texto else Paragraph("", estilo_campus)]]
            col_widths = [largura_util]
    else:
        data = [[col_texto if col_texto else Paragraph("", estilo_campus)]]
        col_widths = [largura_util]

    # Se col_texto é lista, embrulha numa sub-tabela vertical
    if isinstance(data[0][-1], list):
        sub = data[0][-1]
        from reportlab.platypus import KeepInFrame
        cell_content = sub
        data[0][-1] = cell_content

    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("VALIGN",    (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",     (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
    ]))
    return t


def gerar_pdf_abnt(data, filepath, logo_path=None):
    fonte, fonte_bold = registrar_arial()

    titulo         = data.get("titulo", "").strip()
    autores_raw    = data.get("autor", "").strip()
    instituicao    = data.get("instituicao", "").strip()
    campus         = data.get("campus", "").strip()
    curso          = data.get("curso", "").strip()
    cidade         = data.get("cidade", "").strip()
    ano            = data.get("ano", str(datetime.now().year)).strip()
    mes            = data.get("mes", "").strip()
    orientador     = data.get("orientador", "").strip()
    resumo         = data.get("resumo", "").strip()
    palavras_chave = data.get("palavras_chave", "").strip()
    referencias    = data.get("referencias", "").strip()
    tipo_trabalho  = data.get("tipo_trabalho", "Trabalho Acadêmico").strip()
    turma          = data.get("turma", "").strip()
    disciplina     = data.get("disciplina", "").strip()
    secoes         = data.get("secoes", [])

    autores      = [a.strip() for a in autores_raw.split(",") if a.strip()]
    autores_str  = ", ".join(a.upper() for a in autores)

    # Rodapé: "Contagem — Outubro de 2025" ou combinações
    partes_rodape = []
    if cidade: partes_rodape.append(cidade)
    if mes and ano: partes_rodape.append(f"{mes} de {ano}")
    elif ano: partes_rodape.append(ano)
    rodape = " — ".join(partes_rodape)

    doc = SimpleDocTemplate(filepath, pagesize=A4,
        topMargin=3*cm, bottomMargin=2*cm,
        leftMargin=3*cm, rightMargin=2*cm)

    estilos      = get_estilos(fonte, fonte_bold)
    story        = []
    largura_util = A4[0] - 3*cm - 2*cm
    altura_util  = A4[1] - 3*cm - 2*cm

    def add_cabecalho():
        cab = build_cabecalho(fonte, fonte_bold, logo_path, campus, largura_util)
        story.append(cab)
        story.append(Spacer(1, 0.4*cm))

    # ===== CAPA =====
    add_cabecalho()

    story.append(Spacer(1, altura_util * 0.18))
    story.append(Paragraph(autores_str, estilos["centralizado_bold"]))
    story.append(Spacer(1, 1.5*cm))
    story.append(Paragraph(titulo, estilos["centralizado"]))
    story.append(Spacer(1, altura_util * 0.20))

    # Rodapé da capa
    story.append(Paragraph(rodape, estilos["centralizado"]))
    story.append(PageBreak())

    # ===== FOLHA DE ROSTO =====
    add_cabecalho()

    story.append(Spacer(1, 0.8*cm))
    story.append(Paragraph(autores_str, estilos["centralizado_bold"]))
    story.append(Spacer(1, 1.5*cm))
    story.append(Paragraph(titulo, estilos["centralizado"]))
    story.append(Spacer(1, 2*cm))

    # Nota de apresentação
    partes_nota = [tipo_trabalho + " apresentado"]
    if disciplina: partes_nota.append(f"à disciplina {disciplina},")
    if turma:      partes_nota.append(f"Turma {turma},")
    if curso:      partes_nota.append(f"do curso de {curso},")
    if instituicao:partes_nota.append(f"do {instituicao}.")
    else:          partes_nota[-1] = partes_nota[-1].rstrip(",") + "."
    nota_html = " ".join(partes_nota)
    if orientador:
        nota_html += f"<br/>Prof.: {orientador}"

    nota_estilo = ParagraphStyle("nota_direita", parent=estilos["base"],
        fontSize=12, leading=18, firstLineIndent=0,
        alignment=TA_JUSTIFY, leftIndent=largura_util * 0.45)
    story.append(Paragraph(nota_html, nota_estilo))

    # Rodapé da folha de rosto
    story.append(Spacer(1, 2*cm))
    story.append(Paragraph(rodape, estilos["centralizado"]))
    story.append(PageBreak())

    # ===== RESUMO =====
    if resumo:
        story.append(Paragraph("RESUMO", estilos["resumo_titulo"]))
        story.append(Paragraph(resumo, estilos["resumo_texto"]))
        if palavras_chave:
            story.append(Spacer(1, 0.5*cm))
            story.append(Paragraph(
                f"<b>Palavras-chave:</b> {palavras_chave}.",
                estilos["resumo_texto"]))
        story.append(PageBreak())

    # ===== SEÇÕES =====
    for i, secao in enumerate(secoes):
        tit = secao.get("titulo", "").strip()
        txt = secao.get("conteudo", "").strip()
        if not tit or not txt:
            continue
        story.append(Paragraph(f"{i+1}. {tit.upper()}", estilos["secao"]))
        for paragrafo in txt.split("\n\n"):
            paragrafo = paragrafo.strip()
            if not paragrafo: continue
            story.append(Paragraph(" ".join(paragrafo.split("\n")), estilos["base"]))
            story.append(Spacer(1, 6))

    # ===== REFERÊNCIAS =====
    if referencias:
        story.append(PageBreak())
        story.append(Paragraph(f"{len(secoes)+1}. REFERÊNCIAS BIBLIOGRÁFICAS", estilos["secao"]))
        story.append(Spacer(1, 0.3*cm))
        for ref in referencias.strip().split("\n"):
            ref = ref.strip()
            if ref:
                story.append(Paragraph(ref, estilos["referencia"]))

    doc.build(story)


# ===== ROTAS =====

@app.route("/")
def index():
    usuario = get_usuario()
    if not usuario:
        return render_template("login.html")
    return render_template("index.html",
        usuario=usuario,
        pode_gerar=pode_gerar_pdf(usuario),
        ano=datetime.now().year)


@app.route("/upload-logo", methods=["POST"])
def upload_logo():
    if not get_usuario():
        return jsonify({"erro": "Não autenticado"}), 401
    if "logo" not in request.files:
        return jsonify({"erro": "Nenhum arquivo"}), 400
    file = request.files["logo"]
    ext  = os.path.splitext(file.filename)[1].lower()
    if ext not in [".png", ".jpg", ".jpeg"]:
        return jsonify({"erro": "Apenas PNG ou JPG"}), 400
    filename = f"logo_{uuid.uuid4().hex[:10]}{ext}"
    file.save(os.path.join(LOGO_FOLDER, filename))
    session["logo_file"] = filename
    session.modified = True
    return jsonify({"sucesso": True})


@app.route("/remover-logo", methods=["POST"])
def remover_logo():
    logo_file = session.get("logo_file")
    if logo_file:
        path = os.path.join(LOGO_FOLDER, logo_file)
        if os.path.exists(path): os.remove(path)
        session.pop("logo_file", None)
        session.modified = True
    return jsonify({"sucesso": True})


@app.route("/gerar-pdf", methods=["POST"])
def gerar_pdf():
    usuario = get_usuario()
    if not usuario:
        return jsonify({"erro": "Faça login para gerar PDFs"}), 401
    if not pode_gerar_pdf(usuario):
        return jsonify({"erro": "limite_atingido"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"erro": "Dados inválidos"}), 400

    secoes_validas = [s for s in data.get("secoes", [])
                      if s.get("titulo","").strip() and s.get("conteudo","").strip()]
    if not data.get("titulo") and not secoes_validas:
        return jsonify({"erro": "Preencha o título e pelo menos uma seção."}), 400

    try:
        filename  = f"abnt_{uuid.uuid4().hex[:8]}.pdf"
        filepath  = os.path.join(UPLOAD_FOLDER, filename)
        logo_path = None
        logo_file = session.get("logo_file")
        if logo_file:
            c = os.path.join(LOGO_FOLDER, logo_file)
            if os.path.exists(c): logo_path = c

        gerar_pdf_abnt(data, filepath, logo_path=logo_path)
        registrar_geracao(usuario["id"])
        return jsonify({"sucesso": True, "arquivo": filename})

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"erro": f"Erro ao gerar PDF: {str(e)}"}), 500


@app.route("/download/<filename>")
def download(filename):
    if not get_usuario():
        return redirect(url_for("index"))
    if not filename.endswith(".pdf") or "/" in filename or ".." in filename:
        return "Inválido", 400
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(filepath): return "Não encontrado", 404
    return send_file(filepath, as_attachment=True, download_name="trabalho_abnt.pdf")


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
