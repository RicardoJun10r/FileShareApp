FileShare 0.2.0 — transferências rápidas na rede local, com controle de memória e prévias isoladas.

### Novidades

- Arquivos expiram automaticamente **2 minutos após o envio completo**, atualizando todos os dispositivos.
- Quota calculada ao iniciar: até **25% da RAM disponível**, com teto de **512 MiB** e margem de segurança. Uploads são recusados quando não há espaço suficiente.
- Listas de arquivos e links com **20 itens por página**, mais recentes primeiro e sincronização apenas das alterações.
- Progresso de upload e validação do lote inteiro antes de publicar arquivos.
- PDFs e tabelas processados separadamente, com **prazo máximo de 10 segundos**, fila limitada e reaproveitamento de requisições iguais.
- Cache de prévias limitado por memória; CSV/Excel usam índice reutilizável para navegar sem reler o arquivo a cada página.
- Suporte a intervalos HTTP para downloads e reprodução de mídia.
- Correções de concorrência do PDFium e de uploads parcialmente rejeitados.

Prévias aceitam arquivos de até **32 MiB**. Tabelas mostram até **10.000 linhas**, respeitando também o limite do índice; a interface informa quando a prévia é parcial. O original permanece disponível para download até expirar.

### Como usar

1. Baixe o pacote do seu sistema e arquitetura abaixo e extraia a pasta inteira.
2. **Windows x64:** execute `FileShare.exe`.
3. **macOS Apple Silicon ou Intel:** abra `Iniciar FileShare.command` na pasta extraída.
4. **Linux x64:** abra um terminal na pasta extraída e execute `./FileShare`.
5. O navegador abre automaticamente. Escaneie o QR Code no celular conectado à mesma rede Wi-Fi.

Mantenha o terminal aberto. Encerre com **Ctrl+C**. Python e o renderizador PDF já estão incluídos: não precisa instalar Python ou Poppler. Não separe o executável da pasta `_internal`.

### Pacotes e validação

- Linux x86_64: compilado e testado no Ubuntu 22.04 (glibc 2.35 ou superior).
- Windows x86_64: compilado e testado em runner Windows Server 2022; destinado a Windows 10/11 x64, ainda sem teste em desktops físicos.
- macOS arm64: compilado e testado em runner macOS 14 (Apple Silicon).
- macOS x86_64: compilado e testado em runner macOS 15 (Intel).

Cada pacote passa por testes do código e um teste do executável extraído: inicialização, interface local, favicon, Bootstrap, QR Code, upload/download, PDF, Excel, CSV e links. O teste do executável usa um PATH sem ferramentas externas. A abertura automática do navegador é coberta por teste unitário; o smoke test usa `--no-browser`.

### Observações

- Pacotes sem assinatura de editor/notarização; Windows e macOS podem apresentar avisos de origem.
- Arquivos expiram em 2 minutos; links permanecem até encerrar o aplicativo. Reiniciar remove todos os dados.
- Os limites reduzem o consumo de memória, mas não garantem ausência de falta de RAM causada por outros programas ou pelo processamento de arquivos.
- Não há autenticação: utilize uma rede local de confiança e permita a porta exibida no firewall da rede privada.
- Se a porta 8000 estiver ocupada, o inicializador procura uma porta livre até 8010. Use `--port 9000` para escolher outra.
- `SHA256SUMS.txt` contém os hashes dos pacotes publicados.
