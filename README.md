# ABNT.fácil — Guia de Instalação e Uso

Sistema web para formatar trabalhos acadêmicos em ABNT automaticamente.

---

## REQUISITOS

- Python 3.10 ou superior
- Windows 10/11
- VS Code (opcional, mas recomendado)
- Conexão com a internet (para instalar dependências)

---

## PASSO A PASSO — INSTALAÇÃO

### 1. Instale o Python (se ainda não tiver)

Acesse: https://www.python.org/downloads/
Baixe a versão mais recente e instale.

IMPORTANTE: Durante a instalação, marque a opção:
  [x] Add Python to PATH

Para verificar se instalou corretamente, abra o CMD e digite:
  python --version

Deve aparecer algo como: Python 3.12.x


### 2. Abra o CMD na pasta do projeto

Opção A — pelo Explorador de Arquivos:
  1. Abra a pasta "abnt-saas" no Explorador
  2. Clique na barra de endereço (onde aparece o caminho)
  3. Digite "cmd" e pressione Enter

Opção B — pelo CMD manualmente:
  1. Abra o CMD (Win + R → cmd → Enter)
  2. Navegue até a pasta:
     cd C:\caminho\para\abnt-saas

Opção C — pelo VS Code:
  1. Abra o VS Code
  2. File → Open Folder → selecione a pasta abnt-saas
  3. Terminal → New Terminal


### 3. Crie um ambiente virtual (recomendado)

No CMD, dentro da pasta do projeto:

  python -m venv venv

Ative o ambiente virtual:

  venv\Scripts\activate

Você verá "(venv)" aparecer no início da linha do CMD.
Isso significa que o ambiente virtual está ativo.


### 4. Instale as dependências Python

Com o ambiente virtual ativo:

  pip install -r requirements.txt

Aguarde o download e instalação. Pode demorar alguns minutos na primeira vez.


### 5. Instale o GTK3 (necessário para o WeasyPrint no Windows)

O WeasyPrint precisa do GTK3 para funcionar no Windows.

  a) Acesse: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
  b) Baixe o arquivo mais recente: gtk3-runtime-x.x.x-x-x-ts-win64.exe
  c) Execute o instalador e siga os passos (deixe o caminho padrão)
  d) REINICIE o CMD após a instalação


### 6. Inicie o servidor

No CMD, com o ambiente virtual ativo:

  python app.py

Você verá:
  * Running on http://127.0.0.1:5000
  * Debug mode: on

Isso significa que o servidor está rodando!


### 7. Acesse no navegador

Abra qualquer navegador e acesse:
  http://localhost:5000

O sistema estará funcionando!

---

## USANDO O VS CODE

1. Abra a pasta do projeto: File → Open Folder
2. Instale a extensão "Python" da Microsoft (se não tiver)
3. Selecione o interpretador Python:
   - Ctrl+Shift+P → "Python: Select Interpreter"
   - Escolha o que contém "venv"
4. Abra o terminal integrado: Ctrl+` (acento grave)
5. Ative o venv: venv\Scripts\activate
6. Rode: python app.py
7. Clique no link http://127.0.0.1:5000 que aparecer no terminal


## ESTRUTURA DE ARQUIVOS

  abnt-saas/
  ├── app.py                  ← Servidor principal (Flask)
  ├── requirements.txt        ← Lista de dependências
  ├── README.md               ← Este arquivo
  ├── generated_pdfs/         ← PDFs gerados (criado automaticamente)
  ├── flask_session/          ← Sessões dos usuários (criado automaticamente)
  ├── templates/
  │   └── index.html          ← Interface principal
  └── static/
      ├── css/
      │   └── style.css       ← Estilos visuais
      └── js/
          └── app.js          ← Lógica do frontend


## COMANDOS ÚTEIS

Parar o servidor:           Ctrl + C  (no CMD)
Reativar o venv:            venv\Scripts\activate
Atualizar dependências:     pip install -r requirements.txt
Ver PDFs gerados:           pasta generated_pdfs\


## SOLUÇÃO DE PROBLEMAS

ERRO: "python não é reconhecido como comando"
→ Python não está no PATH. Reinstale marcando "Add Python to PATH"

ERRO: "No module named flask"
→ O ambiente virtual não está ativo. Execute: venv\Scripts\activate

ERRO relacionado ao WeasyPrint / Cairo / Pango
→ GTK3 não instalado ou não reiniciou o CMD após instalar.
   Siga o passo 5 novamente.

ERRO: "Port 5000 already in use"
→ Mude a porta no final do app.py:
   app.run(debug=True, port=5001)
   E acesse: http://localhost:5001

PÁGINA não carrega após iniciar
→ Verifique se aparece "Running on http://127.0.0.1:5000" no CMD
→ Tente http://127.0.0.1:5000 ao invés de localhost:5000


## PUBLICAR NA INTERNET (FUTURO)

Quando quiser colocar online de graça para testar:

1. Crie conta em https://railway.app (gratuito)
2. Conecte seu repositório GitHub
3. O deploy é automático

Ou use o Render.com (também gratuito para projetos pequenos).


---

Dúvidas? Abra uma issue no repositório ou entre em contato.
