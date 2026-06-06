from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
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
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

app.register_blueprint(auth_bp)
init_auth(app)

UPLOAD_FOLDER = "generated_pdfs"
LOGO_FOLDER   = "uploaded_logos"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(LOGO_FOLDER, exist_ok=True)


@app.route("/favicon.ico")
@app.route("/favicon.png")
def favicon():
    return send_file(
        os.path.join(app.root_path, "static", "img", "favicon.png"),
        mimetype="image/png"
    )


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
    TAM      = 12
    LEAD_15  = TAM * 1.5   # espaço 1,5 — corpo do texto (NBR 14724:2024 §5.2)
    LEAD_SIM = TAM * 1.0   # espaço simples — refs, citações longas, nota de rosto

    base = ParagraphStyle("base", fontName=fonte, fontSize=TAM, leading=LEAD_15,
        textColor=colors.black, alignment=TA_JUSTIFY,
        firstLineIndent=1.25*cm, spaceAfter=0, spaceBefore=0)

    centralizado = ParagraphStyle("centralizado", parent=base,
        alignment=TA_CENTER, firstLineIndent=0)

    centralizado_bold = ParagraphStyle("centralizado_bold", parent=centralizado,
        fontName=fonte_bold)

    # Seção primária: negrito, esquerda, separada do texto por 1,5 linha (§5.2.2)
    secao = ParagraphStyle("secao", parent=base, fontName=fonte_bold,
        alignment=TA_LEFT, firstLineIndent=0,
        spaceBefore=LEAD_15, spaceAfter=LEAD_15)

    # Título sem indicativo numérico: centralizado (§5.2.3) — RESUMO, REFERÊNCIAS
    resumo_titulo = ParagraphStyle("resumo_titulo", parent=centralizado_bold,
        spaceBefore=0, spaceAfter=LEAD_15)

    # Resumo: espaço 1,5, sem recuo, justificado (NBR 6028:2021)
    resumo_texto = ParagraphStyle("resumo_texto", parent=base,
        firstLineIndent=0, alignment=TA_JUSTIFY)

    # Referências: espaço simples, separadas entre si por linha em branco (§5.2)
    referencia = ParagraphStyle("referencia", parent=base,
        fontSize=TAM, leading=LEAD_SIM,
        firstLineIndent=0, alignment=TA_JUSTIFY,
        spaceBefore=0, spaceAfter=LEAD_SIM)

    italico = ParagraphStyle("italico", parent=centralizado,
        fontName=fonte.replace("Helvetica", "Helvetica-Oblique").replace("Arial", "Arial"))

    # Citação longa: fonte 10pt, espaço simples, recuo 4cm esquerda (NBR 10520:2023)
    citacao_longa = ParagraphStyle("citacao_longa", fontName=fonte, fontSize=10,
        leading=10 * 1.0,
        textColor=colors.black, alignment=TA_JUSTIFY,
        firstLineIndent=0, leftIndent=4*cm,
        spaceBefore=LEAD_15, spaceAfter=LEAD_15)

    return {
        "base": base,
        "centralizado": centralizado,
        "centralizado_bold": centralizado_bold,
        "secao": secao,
        "resumo_titulo": resumo_titulo,
        "resumo_texto": resumo_texto,
        "referencia": referencia,
        "italico": italico,
        "citacao_longa": citacao_longa,
    }


def build_cabecalho(fonte, fonte_bold, logo_path, campus, largura_util):
    """
    Retorna uma lista de flowables com cabeçalho centralizado:
    Logo (se houver) centralizada, Campus abaixo da logo, centralizado.
    """
    estilo_campus = ParagraphStyle("cab_campus",
        fontName=fonte_bold, fontSize=12, leading=16,
        textColor=colors.black, alignment=TA_CENTER)

    elementos = []

    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image(logo_path, width=2.8*cm, height=2.8*cm, kind="proportional")
            logo_img.hAlign = "CENTER"
            elementos.append(logo_img)
            if campus:
                elementos.append(Spacer(1, 0.2*cm))
        except Exception:
            pass

    if campus:
        elementos.append(Paragraph(f"<i>Campus</i> {campus}", estilo_campus))

    return elementos


def processar_paragrafo(texto, estilos, largura_util):
    """
    Recebe um parágrafo (string) e retorna uma lista de flowables.

    Regras de citação ABNT:
    - [cite]texto[/cite] com ≤ 3 linhas estimadas → citação curta:
      integrada ao parágrafo entre aspas duplas, sem recuo extra.
    - [cite]texto[/cite] com > 3 linhas estimadas → citação longa:
      bloco separado, recuado 4 cm, fonte 10 pt, sem aspas.
    """
    import re

    CHARS_POR_LINHA = int(largura_util / (10 * 0.5))  # estimativa conservadora
    LIMITE_LINHAS   = 3

    partes   = re.split(r'\[cite\](.*?)\[/cite\]', texto, flags=re.DOTALL)
    flowables = []

    texto_acumulado = ""

    def flush_texto(t):
        t = " ".join(t.split())
        if t:
            flowables.append(Paragraph(t, estilos["base"]))
            flowables.append(Spacer(1, 6))

    for idx, parte in enumerate(partes):
        if idx % 2 == 0:
            # Texto normal — acumula
            texto_acumulado += parte
        else:
            # É uma citação
            cite = " ".join(parte.strip().split())
            linhas_est = max(1, len(cite) / max(CHARS_POR_LINHA, 1))

            if linhas_est <= LIMITE_LINHAS:
                # Citação curta: insere inline com aspas no texto acumulado
                texto_acumulado += f' "{cite}"'
            else:
                # Citação longa: flush do texto anterior, depois bloco recuado
                flush_texto(texto_acumulado)
                texto_acumulado = ""
                flowables.append(Paragraph(cite, estilos["citacao_longa"]))

    flush_texto(texto_acumulado)
    return flowables


def gerar_pdf_abnt(data, filepath, logo_path=None):  # noqa: C901
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
    anexos         = data.get("anexos", [])

    autores     = [a.strip() for a in autores_raw.split(",") if a.strip()]
    autores_str = ", ".join(a.upper() for a in autores)

    from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, NextPageTemplate
    from reportlab.lib.utils import ImageReader

    MARGEM_ESQ   = 3 * cm
    MARGEM_DIR   = 2 * cm
    MARGEM_TOP   = 3 * cm
    MARGEM_BOT   = 2 * cm
    PG_W, PG_H   = A4
    largura_util = PG_W - MARGEM_ESQ - MARGEM_DIR
    altura_util  = PG_H - MARGEM_TOP - MARGEM_BOT

    estilos = get_estilos(fonte, fonte_bold)

    # ------------------------------------------------------------------ #
    #  Helpers de posição absoluta (usados nos callbacks onPage)          #
    # ------------------------------------------------------------------ #

    def _desenhar_cabecalho(c):
        """Logo centralizada no topo absoluto da margem, campus logo abaixo."""
        y  = PG_H - MARGEM_TOP      # topo da área útil
        cx = PG_W / 2

        if logo_path and os.path.exists(logo_path):
            try:
                img    = ImageReader(logo_path)
                iw, ih = img.getSize()
                max_d  = 2.8 * cm
                esc    = min(max_d / iw, max_d / ih)
                dw, dh = iw * esc, ih * esc
                c.drawImage(logo_path, cx - dw / 2, y - dh,
                            width=dw, height=dh, mask="auto")
                y -= dh + 0.15 * cm
            except Exception:
                pass

        if campus:
            c.setFont(fonte_bold, 12)
            c.drawCentredString(cx, y - 0.35 * cm, f"Campus {campus}")

    def _altura_cabecalho():
        h = 0
        if logo_path and os.path.exists(logo_path):
            try:
                img    = ImageReader(logo_path)
                iw, ih = img.getSize()
                max_d  = 2.8 * cm
                esc    = min(max_d / iw, max_d / ih)
                h     += ih * esc + 0.15 * cm
            except Exception:
                pass
        if campus:
            h += 0.35 * cm + 14   # espaço + linha de texto (12pt ≈ 14px)
        h += 0.3 * cm             # respiro abaixo do cabeçalho
        return h

    def _desenhar_rodape_capa(c):
        """Cidade na linha de baixo, mês e ano acima dela, ambos centralizados."""
        cx   = PG_W / 2
        lead = 16                  # espaçamento entre linhas
        y    = MARGEM_BOT          # ponto mais baixo da área útil

        linhas = []
        if cidade:
            linhas.append(cidade)
        if mes and ano:
            linhas.append(f"{mes} de {ano}")
        elif ano:
            linhas.append(ano)

        # Desenha de baixo para cima: primeira linha = cidade (mais baixo)
        for linha in linhas:
            c.setFont(fonte, 12)
            c.drawCentredString(cx, y, linha)
            y += lead

    def _altura_rodape():
        n = bool(cidade) + (bool(mes and ano) or bool(ano))
        return n * 16 + 0.1 * cm

    # ------------------------------------------------------------------ #
    #  Conteúdo central — capa                                            #
    # ------------------------------------------------------------------ #
    conteudo_capa = [
        Paragraph(autores_str, estilos["centralizado_bold"]),
        Spacer(1, 1.2 * cm),
        Paragraph(titulo, estilos["centralizado"]),
    ]

    # ------------------------------------------------------------------ #
    #  Conteúdo central — folha de rosto                                  #
    # ------------------------------------------------------------------ #
    partes_nota = [tipo_trabalho + " apresentado"]
    if disciplina:  partes_nota.append(f"à disciplina {disciplina},")
    if turma:       partes_nota.append(f"Turma {turma},")
    if curso:       partes_nota.append(f"do curso de {curso},")
    if instituicao: partes_nota.append(f"do {instituicao}.")
    else:           partes_nota[-1] = partes_nota[-1].rstrip(",") + "."
    nota_html = " ".join(partes_nota)
    if orientador:
        nota_html += f"<br/>Prof.: {orientador}"

    # Nota de apresentação: espaço simples, alinhada do meio da mancha até margem direita
    # NBR 14724:2024 §5.2
    nota_estilo = ParagraphStyle("nota_direita", parent=estilos["base"],
        fontSize=12, leading=12,
        firstLineIndent=0, alignment=TA_JUSTIFY,
        leftIndent=largura_util * 0.5)

    conteudo_rosto = [
        Paragraph(autores_str, estilos["centralizado_bold"]),
        Spacer(1, 1.2 * cm),
        Paragraph(titulo, estilos["centralizado"]),
        Spacer(1, 2 * cm),
        Paragraph(nota_html, nota_estilo),
    ]

    # ------------------------------------------------------------------ #
    #  Pré-calcula página de início da numeração                          #
    # ------------------------------------------------------------------ #
    secoes_validas = [s for s in secoes
                      if s.get("titulo", "").strip() and s.get("conteudo", "").strip()]

    paginas_pre   = 2 + (1 if resumo else 0)
    pagina_inicio = [paginas_pre + 1] if secoes_validas else [None]

    # ------------------------------------------------------------------ #
    #  Callbacks onPage                                                   #
    # ------------------------------------------------------------------ #

    def _on_capa(c, doc):
        """Páginas 1 e 2: cabeçalho no topo, rodapé no fundo, conteúdo centralizado."""
        c.saveState()
        _desenhar_cabecalho(c)
        _desenhar_rodape_capa(c)

        alt_cab  = _altura_cabecalho()
        alt_rod  = _altura_rodape()
        y_topo   = PG_H - MARGEM_TOP - alt_cab
        y_fundo  = MARGEM_BOT + alt_rod
        alt_disp = y_topo - y_fundo

        flowables = list(conteudo_capa) if doc.page == 1 else list(conteudo_rosto)

        # Mede a altura total dos flowables sem KeepInFrame
        altura_total = 0
        wrapped = []
        for fl in flowables:
            w, h = fl.wrap(largura_util, alt_disp)
            wrapped.append((fl, w, h))
            altura_total += h

        # Centraliza verticalmente no espaço disponível
        y_cursor = y_fundo + (alt_disp - altura_total) / 2 + altura_total

        for fl, w, h in wrapped:
            y_cursor -= h
            fl.drawOn(c, MARGEM_ESQ, y_cursor)

        c.restoreState()

    def _on_conteudo(c, doc):
        """Páginas de conteúdo: numeração no canto inferior direito a partir da 1ª seção."""
        inicio = pagina_inicio[0]
        if inicio and doc.page >= inicio:
            numero = (doc.page - inicio) + 2
            c.saveState()
            c.setFont(fonte, 10)
            c.drawRightString(PG_W - 2*cm, 2*cm, str(numero))
            c.restoreState()

    # ------------------------------------------------------------------ #
    #  Monta o documento                                                  #
    # ------------------------------------------------------------------ #
    frame_pg = Frame(MARGEM_ESQ, MARGEM_BOT, largura_util, altura_util,
                     leftPadding=0, rightPadding=0,
                     topPadding=0, bottomPadding=0)

    tmpl_capa     = PageTemplate(id="capa",     frames=[frame_pg], onPage=_on_capa)
    tmpl_conteudo = PageTemplate(id="conteudo", frames=[frame_pg], onPage=_on_conteudo)

    doc = BaseDocTemplate(filepath, pagesize=A4,
                          topMargin=MARGEM_TOP, bottomMargin=MARGEM_BOT,
                          leftMargin=MARGEM_ESQ, rightMargin=MARGEM_DIR)
    doc.addPageTemplates([tmpl_capa, tmpl_conteudo])

    # ------------------------------------------------------------------ #
    #  Story                                                              #
    # ------------------------------------------------------------------ #
    story = [
        NextPageTemplate("capa"),
        Spacer(largura_util, altura_util),   # página 1 — capa
        NextPageTemplate("capa"),            # folha de rosto também usa capa
        PageBreak(),
        Spacer(largura_util, altura_util),   # página 2 — folha de rosto
        NextPageTemplate("conteudo"),        # próxima página já será conteúdo
        PageBreak(),
    ]

    # Resumo
    if resumo:
        story.append(Paragraph("RESUMO", estilos["resumo_titulo"]))
        story.append(Paragraph(resumo, estilos["resumo_texto"]))
        if palavras_chave:
            story.append(Spacer(1, 0.5 * cm))
            story.append(Paragraph(
                f"<b>Palavras-chave:</b> {palavras_chave}.",
                estilos["resumo_texto"]))
        story.append(PageBreak())

    # Seções — numeradas a partir de 1
    import base64, io as _io

    TAMANHOS_IMG_INLINE = {
        "pequeno": (largura_util * 0.40, largura_util * 0.30),
        "medio":   (largura_util * 0.65, largura_util * 0.50),
        "grande":  (largura_util * 1.00, largura_util * 0.75),
    }

    legenda_inline_estilo = ParagraphStyle("legenda_inline",
        fontName=fonte, fontSize=10, leading=13,
        textColor=colors.black, alignment=TA_LEFT,
        firstLineIndent=0, spaceBefore=0.2*cm, spaceAfter=0.1*cm)

    fonte_inline_estilo = ParagraphStyle("fonte_inline",
        fontName=fonte, fontSize=10, leading=13,
        textColor=colors.black, alignment=TA_LEFT,
        firstLineIndent=0, spaceAfter=0.4*cm)

    from reportlab.platypus import KeepTogether
    num_secao = 1
    for secao in secoes_validas:
        tit = secao.get("titulo", "").strip()
        txt = secao.get("conteudo", "").strip()
        imagens_inline = secao.get("imagens", [])

        bloco = [Paragraph(f"{num_secao}. {tit.upper()}", estilos["secao"])]
        for paragrafo in txt.split("\n\n"):
            paragrafo = paragrafo.strip()
            if not paragrafo:
                continue
            bloco.extend(processar_paragrafo(paragrafo, estilos, largura_util))

        # Adiciona imagens inline após o texto da seção
        for img_data in imagens_inline:
            imagem_b64 = img_data.get("imagem", "").strip()
            if imagem_b64 and imagem_b64.startswith("data:image"):
                try:
                    _, data_b64 = imagem_b64.split(",", 1)
                    img_bytes = base64.b64decode(data_b64)
                    img_buffer = _io.BytesIO(img_bytes)
                    tamanho_key = img_data.get("tamanho", "medio").lower()
                    max_w, max_h = TAMANHOS_IMG_INLINE.get(tamanho_key, TAMANHOS_IMG_INLINE["medio"])
                    img_flowable = Image(img_buffer, width=max_w, height=max_h, kind="proportional")
                    img_flowable.hAlign = "LEFT"
                    bloco.append(Spacer(1, 0.3*cm))
                    bloco.append(img_flowable)
                except Exception:
                    pass
            legenda = img_data.get("legenda", "").strip()
            fonte_img = img_data.get("fonte", "").strip()
            if legenda:
                bloco.append(Paragraph(legenda, legenda_inline_estilo))
            if fonte_img:
                bloco.append(Paragraph(f"Fonte: {fonte_img}", fonte_inline_estilo))

        story.append(KeepTogether(bloco[:3] if len(bloco) > 3 else bloco))
        for item in bloco[3:]:
            story.append(item)
        num_secao += 1

    # Referências — numeradas como próxima seção (§5.2.3 NBR 14724:2024)
    # Título em negrito, alinhado à esquerda, sem recuo, tamanho 12pt — igual às seções
    import base64, io as _io

    anexos_validos = [a for a in anexos if a.get("legenda","").strip() or a.get("imagem","").strip()]

    if referencias:
        num_ref = num_secao
        num_secao += 1
        refs_bloco = [Paragraph(f"{num_ref}. REFERÊNCIAS BIBLIOGRÁFICAS", estilos["secao"]),
                      Spacer(1, 0.3 * cm)]
        for ref in referencias.strip().split("\n"):
            ref = ref.strip()
            if ref:
                refs_bloco.append(Paragraph(ref, estilos["referencia"]))

        # Se há anexos, tenta manter referências e cabeçalho dos anexos na mesma área
        # sem forçar quebra de página — o ReportLab fará a quebra naturalmente
        story.append(KeepTogether(refs_bloco[:3] if len(refs_bloco) > 3 else refs_bloco))
        for item in refs_bloco[3:]:
            story.append(item)

    # Estilos de legenda e fonte conforme ABNT NBR 14724:2024 + NBR 6029
    # Legenda: alinhada à esquerda, fonte 10pt, espaço simples, sem recuo
    # Fonte: alinhada à esquerda, fonte 10pt, espaço simples, sem recuo
    legenda_estilo = ParagraphStyle("legenda_anexo",
        fontName=fonte, fontSize=10, leading=13,
        textColor=colors.black, alignment=TA_LEFT,
        firstLineIndent=0, leftIndent=0,
        spaceBefore=0.25 * cm, spaceAfter=0.05 * cm)

    fonte_img_estilo = ParagraphStyle("fonte_img_anexo",
        fontName=fonte, fontSize=10, leading=13,
        textColor=colors.black, alignment=TA_LEFT,
        firstLineIndent=0, leftIndent=0,
        spaceBefore=0, spaceAfter=0.4 * cm)

    # Título de seção de ANEXOS (quando há mais de um, agrupa sob um título-mestre)
    # e cada anexo individual é um sub-bloco
    TAMANHOS_IMG = {
        "pequeno": (largura_util * 0.40, largura_util * 0.30),  # largura, altura máx
        "medio":   (largura_util * 0.65, largura_util * 0.50),
        "grande":  (largura_util * 1.00, largura_util * 0.75),
    }

    num_romano = ["I","II","III","IV","V","VI","VII","VIII","IX","X",
                  "XI","XII","XIII","XIV","XV","XVI","XVII","XVIII","XIX","XX"]

    if anexos_validos:
        num_anx = num_secao
        # Título da seção ANEXOS — mesmo estilo das demais seções
        titulo_anexos = Paragraph(f"{num_anx}. ANEXOS", estilos["secao"])

        # Monta todos os sub-blocos de anexo
        sub_blocos = []
        for idx, anexo in enumerate(anexos_validos):
            rotulo = f"Anexo {num_romano[idx] if idx < len(num_romano) else str(idx+1)}"

            # Estilo do sub-título do anexo: negrito, esquerda, menor espaçamento
            subtitulo_estilo = ParagraphStyle(f"subtitulo_anx_{idx}",
                fontName=fonte_bold, fontSize=12, leading=18,
                textColor=colors.black, alignment=TA_LEFT,
                firstLineIndent=0, spaceBefore=0.6 * cm, spaceAfter=0.3 * cm)

            bloco_anx = [Paragraph(rotulo, subtitulo_estilo)]

            imagem_b64 = anexo.get("imagem", "").strip()
            if imagem_b64 and imagem_b64.startswith("data:image"):
                try:
                    _, data_b64 = imagem_b64.split(",", 1)
                    img_bytes   = base64.b64decode(data_b64)
                    img_buffer  = _io.BytesIO(img_bytes)

                    tamanho_key = anexo.get("tamanho", "medio").lower()
                    max_w, max_h = TAMANHOS_IMG.get(tamanho_key, TAMANHOS_IMG["medio"])

                    img_flowable = Image(img_buffer, width=max_w, height=max_h, kind="proportional")
                    img_flowable.hAlign = "LEFT"
                    bloco_anx.append(img_flowable)
                except Exception:
                    pass

            legenda = anexo.get("legenda", "").strip()
            fonte_anexo = anexo.get("fonte", "").strip()

            if legenda:
                bloco_anx.append(Paragraph(legenda, legenda_estilo))
            if fonte_anexo:
                bloco_anx.append(Paragraph(f"Fonte: {fonte_anexo}", fonte_img_estilo))

            # KeepTogether garante que imagem + legenda + fonte nunca se separam
            sub_blocos.append(KeepTogether(bloco_anx))

        # Primeiro sub-bloco fica junto com o título ANEXOS
        primeiro_bloco = KeepTogether([titulo_anexos, sub_blocos[0]] if sub_blocos else [titulo_anexos])
        story.append(primeiro_bloco)
        for sb in sub_blocos[1:]:
            story.append(sb)

    doc.build(story)


# ===== ROTAS =====

@app.route("/")
def index():
    usuario = get_usuario()
    if not usuario:
        return render_template("landing.html")
    return redirect(url_for("formulario"))

@app.route("/formatar")
def formulario():
    usuario = get_usuario()
    if not usuario:
        return redirect(url_for("index"))
    return render_template("index.html",
        usuario=usuario,
        pode_gerar=pode_gerar_pdf(usuario),
        ano=datetime.now().year)

@app.route("/entrar")
def entrar():
    usuario = get_usuario()
    if usuario:
        return redirect(url_for("formulario"))
    return render_template("login.html")


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

    # Lê o arquivo em memória antes de excluir do disco
    with open(filepath, "rb") as f:
        pdf_bytes = f.read()

    # Exclui imediatamente do servidor após a leitura
    try:
        os.remove(filepath)
    except Exception:
        pass

    from io import BytesIO
    return send_file(
        BytesIO(pdf_bytes),
        as_attachment=True,
        download_name="trabalho_abnt.pdf",
        mimetype="application/pdf"
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)