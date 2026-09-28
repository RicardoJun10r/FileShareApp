# FileShare

**Um ponto de encontro para arquivos e links na sua rede local.**

O FileShare facilita o compartilhamento de arquivos pelo navegador. Envie um arquivo pelo computador e baixe no celular ou faça o caminho inverso, sem instalar NADA!

O servidor roda em Python com FastAPI. A interface usa Bootstrap, funciona em telas pequenas e atualiza as listas automaticamente quando alguém compartilha um arquivo ou link.

![Interface do FileShare com envio de arquivos, compartilhamento de links, QR Code e lista de downloads](docs/images/fileshare-desktop.png)

*Captura real da interface com dados de demonstração. O endereço exibido corresponde ao servidor usado para a captura; na sua instalação, use o IP do computador na rede.*

## O que você pode fazer

- **Enviar e baixar arquivos** entre computadores, celulares e tablets na mesma rede.
- **Compartilhar links** com um título opcional.
- **Receber atualizações em tempo real**, sem recarregar a página.
- **Abrir prévias** clicando no nome ou no item da lista.

| Prévia | Recursos |
| --- | --- |
| Imagens | PNG, JPEG, GIF, WebP e AVIF, conforme suporte do navegador |
| Vídeo e áudio | Player com controles; reprodução depende do formato e codec suportados pelo navegador |
| PDF | Páginas renderizadas no servidor, navegação e sumário clicável a partir dos marcadores do documento |
| Excel | XLSX, XLSM e XLS em tabela, com seleção de abas e paginação |
| CSV e TSV | Detecção de separador, ajuste manual e primeira linha opcional como cabeçalho |
| Texto e código | Exibição como texto, limitada aos primeiros 100 KB |

PDFs sem marcadores mostram uma lista de páginas no lugar dos tópicos. Planilhas mostram 100 linhas por página, até 100 colunas e até 4.000 caracteres por célula. A prévia não reproduz gráficos ou estilos do Excel nem recalcula fórmulas. Os limites da prévia não alteram o arquivo disponível para download.

## Como usar

### 1. Prepare o computador que será o servidor

Você precisa de:

- **Python 3.13 ou superior**. O projeto usa Python 3.13 em `.python-version`.
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** para instalar e executar as dependências.
- **Git**, caso escolha clonar o repositório em vez de baixar o ZIP pelo GitHub.
- **Poppler**, somente para renderizar as páginas de PDFs na prévia.

Clone o projeto e instale as dependências:

```bash
git clone https://github.com/RicardoJun10r/FileShareApp.git
cd FileShareApp
uv sync --locked
```

O Bootstrap e os recursos da interface estão incluídos no projeto: depois da instalação, a interface não depende de uma CDN ou de conexão com a internet. Links externos compartilhados ainda podem precisar de internet para abrir.

### 2. Habilite a prévia de PDFs

O servidor precisa encontrar `pdfinfo` e `pdftoppm` no `PATH`.

**Ubuntu/Debian:**

```bash
sudo apt install poppler-utils
```

**macOS com Homebrew:**

```bash
brew install poppler
```

**Windows:** instale uma distribuição do Poppler para Windows e adicione a pasta que contém `pdfinfo.exe` e `pdftoppm.exe` ao `PATH`. Reabra o terminal após essa alteração.

Confira a instalação:

```bash
pdfinfo -v
pdftoppm -v
```

Sem esses executáveis, o compartilhamento e o download continuam funcionando, mas a renderização de PDFs fica indisponível.

### 3. Inicie o FileShare

Na pasta do projeto:

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

Mantenha esse terminal aberto. Para encerrar, pressione **Ctrl + C**.

No próprio computador, abra:

```text
http://localhost:8000
```

### 4. Acesse pelo celular ou outro computador

1. Conecte os dispositivos à mesma rede local, por Wi-Fi ou cabo.
2. Na página do FileShare, escaneie o QR Code com a câmera do celular.
3. Alternativamente, abra `http://IP-DO-COMPUTADOR:8000` no navegador do outro dispositivo.

Por exemplo, se o IP local for `192.168.1.20`, acesse:

```text
http://192.168.1.20:8000
```

Para descobrir o IP, consulte as configurações de rede do computador ou use `hostname -I` no Linux e `ipconfig` no Windows. Escolha o endereço da conexão usada pelos dispositivos, não o de uma interface virtual.

> `localhost` no celular aponta para o próprio celular. Para acessar o servidor, use o IP do computador. `0.0.0.0` é o endereço de escuta do servidor, não o endereço a digitar no navegador.

### 5. Compartilhe

- **Arquivo:** selecione ou arraste arquivos para a área de envio e clique em **Enviar arquivos**.
- **Prévia:** clique no item da lista; use **Baixar** para salvar o original.
- **Link:** informe um endereço HTTP/HTTPS, adicione um título se quiser e clique em **Enviar link**.

Todos os clientes conectados recebem as atualizações automaticamente.

### Se outro dispositivo não conseguir acessar

- Confira se o servidor está rodando com `--host 0.0.0.0`.
- Verifique se os dispositivos estão na mesma rede; redes de convidados podem bloquear a comunicação entre eles.
- Permita conexões à porta TCP `8000` no firewall pela rede local.
- Use `http://`, não `https://`, na configuração padrão.

Se o QR Code mostrar o endereço errado em um computador com várias interfaces ou VPN, abra a página usando o IP correto. Você também pode definir `FILESHARE_PUBLIC_URL` antes de iniciar o servidor:

```bash
# Linux/macOS — substitua pelo endereço da sua rede
FILESHARE_PUBLIC_URL=http://192.168.1.20:8000 uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

```powershell
# Windows PowerShell
$env:FILESHARE_PUBLIC_URL = "http://192.168.1.20:8000"
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

Essa variável ajusta o endereço divulgado pelo QR Code; não altera a interface ou a porta em que o servidor escuta.

## Sistemas operacionais e compatibilidade

Há duas partes distintas: o **computador que executa o servidor** e os **dispositivos que acessam pelo navegador**.

| Plataforma | Uso | Situação atual |
| --- | --- | --- |
| Linux | Servidor e navegador | Ambiente em que os testes de integração e E2E foram executados |
| Windows | Servidor e navegador | Execução prevista com Python, uv e dependências; ainda sem validação específica neste sistema |
| macOS | Servidor e navegador | Execução prevista com Python, uv e dependências; ainda sem validação específica neste sistema |
| Android e iOS/iPadOS | Cliente pelo navegador | Interface responsiva; acesso não exige Python no celular. A suíte usa emulação mobile, não aparelhos reais |

A validação automatizada da interface usa **Chromium**, nas larguras de **320, 375, 390, 768 e 1280 pixels**. Firefox, Safari e navegadores móveis reais ainda não têm uma matriz de testes própria. A compatibilidade dos testes Playwright também depende dos [requisitos oficiais do Playwright](https://playwright.dev/python/docs/intro).

A distribuição atual é pelo código-fonte. Ainda não há instalador ou executável pronto incluído no projeto.

## Como o projeto está organizado

```text
FileShareApp/
├── main.py                   # API, upload/download, SSE, links, QR Code e PDF
├── tabular_preview.py        # Leitura e paginação de Excel, CSV e TSV
├── pyproject.toml            # Dependências e configuração do pytest
├── uv.lock                   # Versões resolvidas das dependências
├── .python-version           # Versão de Python usada no projeto
├── static/
│   ├── index.html            # Estrutura da interface
│   ├── app.js                # Upload, prévias e atualização das listas
│   ├── styles.css            # Tema e ajustes responsivos sobre Bootstrap
│   ├── favicon.svg           # Ícone da aba do navegador
│   └── vendor/bootstrap/     # Bootstrap local, licença e informações da versão
├── tests/
│   ├── test_*.py             # Testes de integração e leitura de arquivos
│   └── e2e/
│       ├── conftest.py       # Servidor isolado e tamanhos de tela
│       └── test_fileshare.py # Fluxos no navegador com Playwright
└── docs/images/              # Capturas usadas nesta documentação
```

O navegador envia arquivos e links pela API. O servidor mantém os dados em memória e avisa os clientes por **Server-Sent Events (SSE)**. Ao receber o aviso, o JavaScript atualiza as listas. As prévias são carregadas quando o usuário abre um item.

## Limitações da versão atual

- **Armazenamento temporário:** arquivos e links desaparecem ao encerrar ou reiniciar o servidor. Arquivos grandes consomem a RAM do computador.
- **Um único processo:** use o comando de inicialização sem múltiplos workers. Os dados e as conexões SSE não são compartilhados entre processos.
- **Acesso pela rede:** não há autenticação. Quem conseguir acessar o servidor pode compartilhar e baixar conteúdo; o uso previsto é em uma rede local de confiança.
- **Desenvolvimento:** `--reload` pode ser adicionado ao comando do Uvicorn, mas cada reinicialização provocada por alterações no código apaga os dados em memória.

## Testes automatizados

Instale as dependências de desenvolvimento e o Chromium:

```bash
uv sync --locked --dev
uv run playwright install chromium
```

Execute os testes E2E:

```bash
uv run pytest tests/e2e -v
```

Cada caso inicia e encerra um servidor Uvicorn separado, com porta livre e dados isolados. Não é necessário iniciar o servidor manualmente, e a instância pessoal na porta `8000` não é utilizada.

A suíte cobre upload e download, atualização entre clientes, prévias, links, exibição do QR Code, sumário PDF, paginação CSV, abas Excel, erros JavaScript e rolagem horizontal indevida. A grade de planilhas pode rolar horizontalmente dentro da própria prévia.

```bash
# Todos os testes, incluindo os de integração
uv run pytest tests -v

# Acompanhar o navegador durante os E2E
uv run pytest tests/e2e --headed --slowmo 200

# Apenas a largura de 320 pixels
uv run pytest tests/e2e -k 320px -v
```

Falhas geram screenshots e traces em `test-results/`, ignorado pelo Git. Para abrir um trace, substitua o caminho abaixo pelo arquivo gerado:

```bash
uv run playwright show-trace test-results/<caso>/trace.zip
```

Em Linux, se faltarem bibliotecas do navegador, execute `uv run playwright install-deps chromium` — pode exigir privilégios de administrador. Os testes de PDF precisam do Poppler. O acesso pelo Wi-Fi e as regras do firewall precisam ser conferidos nos dispositivos reais.
