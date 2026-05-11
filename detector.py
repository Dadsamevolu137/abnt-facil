import re

# Seções ABNT mais comuns — ordem importa para numeração
SECOES_CONHECIDAS = [
    "resumo", "abstract",
    "introdução", "introducao", "introdução geral",
    "objetivos", "objetivo", "objetivo geral", "objetivo específico", "objetivos específicos",
    "justificativa",
    "referencial teórico", "fundamentação teórica", "revisão de literatura", "revisão bibliográfica",
    "materiais e métodos", "material e método", "metodologia", "materiais e reagentes",
    "procedimentos", "procedimento experimental", "métodos",
    "resultados", "resultados e discussão", "resultados e discussões",
    "discussão", "análise dos resultados",
    "conclusão", "conclusões", "considerações finais",
    "referências", "referências bibliográficas", "bibliografia",
    "anexos", "anexo", "apêndice", "apêndices",
    "agradecimentos",
    "lista de figuras", "lista de tabelas", "lista de abreviaturas",
    "sumário",
]

# Padrões de subseção: "1.1 Texto", "2.3.1 Texto"
RE_SUBSECAO = re.compile(r'^(\d+\.\d+(?:\.\d+)*)\s+(.+)$')
# Padrões de seção numerada: "1 Texto", "1. Texto", "1 - Texto"
RE_SECAO_NUM = re.compile(r'^(\d+)[\.\s\-]+\s*(.+)$')


def normalizar(texto):
    return re.sub(r'[^a-z\s]', '', texto.lower().strip())


def classificar_linha(linha):
    """Retorna ('secao'|'subsecao'|'paragrafo', texto_limpo)"""
    linha = linha.strip()
    if not linha:
        return ('vazio', '')

    # Subseção numerada: 1.1, 2.3.1 etc
    m = RE_SUBSECAO.match(linha)
    if m:
        return ('subsecao', linha)

    # Seção numerada: 1. Introdução
    m = RE_SECAO_NUM.match(linha)
    if m:
        conteudo = m.group(2).strip()
        if len(conteudo) > 2:
            return ('secao', linha)

    # Seção conhecida (sem número)
    norm = normalizar(linha)
    for secao in SECOES_CONHECIDAS:
        if norm == normalizar(secao) or norm.startswith(normalizar(secao) + ' '):
            return ('secao', linha)

    # Linha curta em MAIÚSCULAS sem pontuação final → provavelmente seção
    if linha.isupper() and len(linha) < 80 and not linha.endswith('.'):
        return ('secao', linha)

    # Linha curta com Title Case e sem pontuação → possível seção
    palavras = linha.split()
    if (2 <= len(palavras) <= 8
            and linha[0].isupper()
            and not linha.endswith('.')
            and not linha.endswith(',')
            and not linha.endswith(';')):
        norm2 = normalizar(linha)
        for secao in SECOES_CONHECIDAS:
            if normalizar(secao) in norm2:
                return ('secao', linha)

    return ('paragrafo', linha)


def detectar_estrutura(texto_bruto):
    """
    Recebe texto puro e retorna lista de blocos:
    [{'tipo': 'secao'|'subsecao'|'paragrafo', 'texto': str, 'nivel': int}]
    """
    linhas = texto_bruto.splitlines()
    blocos = []
    paragrafo_atual = []
    secao_count = 0

    def flush_paragrafo():
        if paragrafo_atual:
            texto = ' '.join(paragrafo_atual).strip()
            if texto:
                blocos.append({'tipo': 'paragrafo', 'texto': texto, 'nivel': 0})
            paragrafo_atual.clear()

    for linha in linhas:
        linha = linha.strip()
        tipo, texto = classificar_linha(linha)

        if tipo == 'vazio':
            flush_paragrafo()
            continue

        if tipo == 'secao':
            flush_paragrafo()
            secao_count += 1
            blocos.append({'tipo': 'secao', 'texto': texto, 'nivel': 1})

        elif tipo == 'subsecao':
            flush_paragrafo()
            blocos.append({'tipo': 'subsecao', 'texto': texto, 'nivel': 2})

        else:  # parágrafo
            paragrafo_atual.append(linha)

    flush_paragrafo()
    return blocos


def blocos_para_corpo(blocos):
    """Converte blocos detectados para o formato # / ## que o app.py entende."""
    linhas = []
    for b in blocos:
        if b['tipo'] == 'secao':
            linhas.append(f"# {b['texto']}")
            linhas.append('')
        elif b['tipo'] == 'subsecao':
            linhas.append(f"## {b['texto']}")
            linhas.append('')
        else:
            linhas.append(b['texto'])
            linhas.append('')
    return '\n'.join(linhas)
