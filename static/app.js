const form = document.getElementById('uploadForm');
const input = document.getElementById('files');
const statusMessage = document.getElementById('status');
const uploadButton = document.getElementById('upload');
const dropzone = document.getElementById('dropzone');
const connection = document.getElementById('connection');
const connectionText = document.getElementById('connectionText');
let retryTimer;

function tamanho(bytes) {
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const index = bytes ? Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1) : 0;
    return `${(bytes / 1024 ** index).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} ${units[index]}`;
}
function mostrarSelecao() {
    const files = [...input.files];
    document.getElementById('selection').textContent = files.length
        ? `${files.length === 1 ? files[0].name : `${files.length} arquivos selecionados`} · ${tamanho(files.reduce((sum, file) => sum + file.size, 0))}`
        : 'Nenhum arquivo selecionado';
}
input.addEventListener('change', mostrarSelecao);
for (const event of ['dragenter', 'dragover']) {
    dropzone.addEventListener(event, e => { e.preventDefault(); if (!input.disabled) dropzone.classList.add('dragging'); });
}
for (const event of ['dragleave', 'drop']) {
    dropzone.addEventListener(event, e => { e.preventDefault(); dropzone.classList.remove('dragging'); });
}
dropzone.addEventListener('drop', event => {
    if (!input.disabled && event.dataTransfer.files.length) {
        input.files = event.dataTransfer.files;
        mostrarSelecao();
    }
});

const catalogFiles = new Map();
const catalogLinks = new Map();
const listingState = {
    files: { page: 0, nodes: new Map() },
    links: { page: 0, nodes: new Map() },
};
let syncRevision = null;
let syncEpoch = '';
let syncPromise;
let syncAgain = false;
let syncFailed = false;
const LIST_PAGE_SIZE = 20;

function createFileRow(file) {
    const row = document.createElement('tr');
    row.className = 'file-row';
    const name = document.createElement('button');
    name.type = 'button';
    name.className = 'file-name btn btn-link text-start text-decoration-none text-body fw-semibold w-100 p-0';
    const type = document.createElement('span');
    type.className = 'file-type';
    type.dataset.kind = file.preview || 'file';
    type.setAttribute('aria-hidden', 'true');
    const extension = file.filename.includes('.') ? file.filename.split('.').pop() : '';
    type.textContent = extension && extension.length <= 5 ? extension.toUpperCase() : 'FILE';
    const label = document.createElement('span');
    label.className = 'file-label';
    label.textContent = file.filename;
    name.append(type, label);
    name.setAttribute('aria-label', `Abrir prévia de ${file.filename}`);
    name.setAttribute('aria-haspopup', 'dialog');
    row.insertCell().appendChild(name);
    row.addEventListener('click', event => {
        if (!event.target.closest('a')) abrirPreview(file);
    });
    row.insertCell().textContent = tamanho(file.size);
    const link = document.createElement('a');
    link.href = `/download/${file.id}`;
    link.textContent = 'Baixar ↓';
    link.className = 'btn btn-outline-primary';
    link.download = file.filename;
    link.setAttribute('aria-label', `Baixar ${file.filename}`);
    const actions = document.createElement('div');
    actions.className = 'file-actions d-flex flex-wrap justify-content-end gap-2';
    actions.append(link);
    row.insertCell().appendChild(actions);
    row.setAttribute('role', 'row');
    for (const cell of row.cells) cell.setAttribute('role', 'cell');

    return row;
}

function createLinkRow(link) {
    const item = document.createElement('li');
    item.className = 'list-group-item rounded-3';
    const anchor = document.createElement('a');
    anchor.className = 'd-block text-break py-2';
    anchor.href = link.url;
    anchor.target = '_blank';
    anchor.rel = 'noopener noreferrer';
    anchor.textContent = link.title;
    const address = document.createElement('small');
    address.className = 'd-block text-secondary text-break';
    address.textContent = link.url;
    item.append(anchor, address);
    return item;
}

function renderListing(kind) {
    const isFile = kind === 'files';
    const source = isFile ? catalogFiles : catalogLinks;
    const state = listingState[kind];
    const values = [...source.values()].reverse();
    const pages = Math.max(1, Math.ceil(values.length / LIST_PAGE_SIZE));
    state.page = Math.min(state.page, pages - 1);
    const visible = values.slice(state.page * LIST_PAGE_SIZE, (state.page + 1) * LIST_PAGE_SIZE);
    const container = document.getElementById(isFile ? 'filesTable' : 'sharedLinks');
    const ids = new Set(visible.map(item => item.id));
    for (const [id, cached] of state.nodes) {
        if (!ids.has(id)) { cached.node.remove(); state.nodes.delete(id); }
    }
    for (const placeholder of container.querySelectorAll(':scope > :not([data-id])')) placeholder.remove();
    visible.forEach((item, position) => {
        const signature = JSON.stringify(item);
        let cached = state.nodes.get(item.id);
        if (!cached || cached.signature !== signature) {
            const node = isFile ? createFileRow(item) : createLinkRow(item);
            node.dataset.id = item.id;
            if (cached) cached.node.replaceWith(node);
            cached = { node, signature };
            state.nodes.set(item.id, cached);
        }
        const current = container.children[position];
        if (current !== cached.node) container.insertBefore(cached.node, current || null);
    });
    if (!visible.length) {
        const empty = document.createElement(isFile ? 'tr' : 'li');
        if (isFile) {
            const cell = empty.insertCell();
            cell.colSpan = 3;
            cell.className = 'empty text-center text-secondary py-4';
            cell.textContent = 'Tudo pronto para compartilhar. Envie o primeiro arquivo!';
        } else {
            empty.className = 'list-group-item rounded-3 text-secondary';
            empty.textContent = 'Nenhum link compartilhado ainda.';
        }
        container.append(empty);
    }
    document.getElementById(isFile ? 'count' : 'linkCount').textContent = `${values.length} ${isFile ? (values.length === 1 ? 'arquivo' : 'arquivos') : (values.length === 1 ? 'link' : 'links')}`;
    document.getElementById(`${kind}Page`).textContent = `Página ${state.page + 1} de ${pages}`;
    document.getElementById(`${kind}Previous`).disabled = state.page === 0;
    document.getElementById(`${kind}Next`).disabled = state.page + 1 === pages;
}

for (const kind of ['files', 'links']) {
    for (const [control, increment] of [['Previous', -1], ['Next', 1]]) {
        document.getElementById(`${kind}${control}`).addEventListener('click', () => {
            listingState[kind].page += increment;
            renderListing(kind);
        });
    }
}

function syncCatalog() {
    syncAgain = true;
    if (syncPromise) return syncPromise;
    syncPromise = (async () => {
        clearTimeout(retryTimer);
        while (syncAgain) {
            syncAgain = false;
            const params = new URLSearchParams({ epoch: syncEpoch });
            if (syncRevision !== null) params.set('since', syncRevision);
            const response = await fetch(`/sync/?${params}`, { cache: 'no-store' });
            if (!response.ok) throw new Error('Falha ao sincronizar');
            const change = await response.json();
            if (change.reset) { catalogFiles.clear(); catalogLinks.clear(); }
            change.deleted.forEach(id => catalogFiles.delete(id));
            change.files.forEach(item => catalogFiles.set(item.id, item));
            change.links.forEach(item => catalogLinks.set(item.id, item));
            syncRevision = change.revision;
            syncEpoch = change.epoch;
            if (syncFailed || change.reset || change.files.length || change.deleted.length) renderListing('files');
            if (syncFailed || change.reset || change.links.length) renderListing('links');
            syncFailed = false;
        }
    })().catch(() => {
        syncFailed = true;
        document.getElementById('count').textContent = 'Tentando sincronizar…';
        retryTimer = setTimeout(syncCatalog, 3000);
    }).finally(() => { syncPromise = null; });
    return syncPromise;
}
const carregarArquivos = syncCatalog;
const carregarLinks = syncCatalog;

function enviarArquivos(data) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/upload/');
        xhr.upload.addEventListener('progress', event => {
            if (event.lengthComputable) {
                const percent = Math.round((event.loaded / event.total) * 100);
                statusMessage.textContent = `Transferindo seus arquivos… ${percent}%`;
            }
        });
        xhr.addEventListener('load', () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                resolve();
                return;
            }
            let message = 'Falha no envio. Verifique sua conexão e tente novamente.';
            try {
                const detail = JSON.parse(xhr.responseText).detail;
                if (detail) message = detail;
            } catch (error) { /* mantém a mensagem padrão */ }
            reject(new Error(message));
        });
        xhr.addEventListener('error', () => reject(new Error('Falha no envio. Verifique sua conexão e tente novamente.')));
        xhr.send(data);
    });
}

form.addEventListener('submit', async event => {
    event.preventDefault();
    const data = new FormData(form);
    uploadButton.disabled = true;
    input.disabled = true;
    uploadButton.textContent = 'Enviando…';
    statusMessage.classList.remove('error');
    statusMessage.textContent = 'Transferindo seus arquivos… 0%';
    try {
        await enviarArquivos(data);
        form.reset();
        mostrarSelecao();
        statusMessage.textContent = 'Arquivos enviados e disponíveis para todos na rede!';
        await carregarArquivos();
    } catch (error) {
        statusMessage.classList.add('error');
        statusMessage.textContent = error.message;
    } finally {
        uploadButton.disabled = false;
        input.disabled = false;
        uploadButton.textContent = 'Enviar arquivos ↑';
    }
});

const previewDialog = document.getElementById('previewDialog');
const previewBody = document.getElementById('previewBody');
const previewNotice = document.getElementById('previewNotice');
let previewController;
let pdfObjectUrl;

function limparPreview() {
    previewController?.abort();
    if (pdfObjectUrl) URL.revokeObjectURL(pdfObjectUrl);
    pdfObjectUrl = null;
    for (const media of previewBody.querySelectorAll('video, audio')) {
        media.pause();
        media.removeAttribute('src');
        media.load();
    }
    previewBody.replaceChildren();
    previewBody.setAttribute('aria-busy', 'false');
}
document.getElementById('closePreview').addEventListener('click', () => previewDialog.close());
previewDialog.addEventListener('close', limparPreview);

async function abrirPreview(file) {
    limparPreview();
    const controller = new AbortController();
    previewController = controller;
    document.getElementById('previewTitle').textContent = file.filename;
    const download = document.getElementById('previewDownload');
    download.href = `/download/${file.id}`;
    download.download = file.filename;
    previewNotice.textContent = '';
    previewDialog.showModal();
    if (!file.preview) {
        previewNotice.textContent = 'Este formato não tem prévia disponível. Baixe o arquivo para abri-lo no seu dispositivo.';
        return;
    }
    previewBody.setAttribute('aria-busy', 'true');
    previewNotice.textContent = 'Carregando prévia…';
    const url = `/preview/${file.id}`;
    const failure = () => {
        if (controller.signal.aborted) return;
        previewBody.setAttribute('aria-busy', 'false');
        previewNotice.textContent = 'Não foi possível exibir este arquivo. O formato ou codec pode não ser compatível com seu navegador. Você ainda pode baixá-lo.';
    };
    const ready = () => {
        if (controller.signal.aborted) return;
        previewBody.setAttribute('aria-busy', 'false');
        previewNotice.textContent = '';
    };
    if (file.preview === 'spreadsheet') {
        await abrirTabela(file, controller);
    } else if (file.preview === 'pdf') {
        const controls = document.createElement('div');
        controls.className = 'pdf-controls d-flex flex-wrap align-items-center justify-content-center gap-2 mb-3';
        const previous = document.createElement('button');
        const next = document.createElement('button');
        const label = document.createElement('span');
        label.setAttribute('aria-live', 'polite');
        for (const button of [previous, next]) {
            button.type = 'button';
            button.className = 'btn btn-outline-primary';
        }
        previous.textContent = '← Anterior';
        next.textContent = 'Próxima →';
        const image = document.createElement('img');
        image.className = 'pdf-page';
        image.addEventListener('error', failure);
        const layout = document.createElement('div');
        layout.className = 'pdf-layout';
        const sidebar = document.createElement('details');
        sidebar.className = 'pdf-sidebar bg-body-tertiary rounded-3 p-3';
        sidebar.open = !window.matchMedia('(max-width: 767.98px)').matches;
        const summary = document.createElement('summary');
        summary.textContent = 'Sumário do documento';
        const tocStatus = document.createElement('p');
        tocStatus.textContent = 'Carregando tópicos…';
        const toc = document.createElement('nav');
        toc.setAttribute('aria-label', 'Tópicos do PDF');
        sidebar.append(summary, tocStatus, toc);
        const documentPanel = document.createElement('div');
        let page = 1;
        let pages = 1;
        let pageRequest = 0;
        function highlightTopic() {
            let active;
            for (const button of toc.querySelectorAll('button')) {
                button.removeAttribute('aria-current');
                if (Number(button.dataset.page) <= page && (!active || Number(button.dataset.page) >= Number(active.dataset.page))) active = button;
            }
            active?.setAttribute('aria-current', 'page');
        }
        async function loadPage(target) {
            const version = ++pageRequest;
            previous.disabled = next.disabled = true;
            previewBody.setAttribute('aria-busy', 'true');
            previewNotice.textContent = 'Carregando página…';
            try {
                const response = await fetch(`${url}/pdf?page=${target}`, { signal: controller.signal });
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Não foi possível abrir o PDF.');
                }
                const blob = await response.blob();
                if (controller.signal.aborted || version !== pageRequest) return;
                if (pdfObjectUrl) URL.revokeObjectURL(pdfObjectUrl);
                pdfObjectUrl = URL.createObjectURL(blob);
                image.src = pdfObjectUrl;
                page = target;
                pages = Number(response.headers.get('X-PDF-Pages'));
                image.alt = `${file.filename}, página ${page}`;
                label.textContent = `Página ${page} de ${pages}`;
                highlightTopic();
                ready();
            } catch (error) {
                if (!controller.signal.aborted && version === pageRequest) {
                    previewBody.setAttribute('aria-busy', 'false');
                    previewNotice.textContent = error.message;
                }
            } finally {
                if (!controller.signal.aborted && version === pageRequest) {
                    previous.disabled = page <= 1;
                    next.disabled = page >= pages;
                }
            }
        }
        previous.addEventListener('click', () => loadPage(page - 1));
        next.addEventListener('click', () => loadPage(page + 1));
        controls.append(previous, label, next);
        documentPanel.append(controls, image);
        layout.append(sidebar, documentPanel);
        previewBody.append(layout);
        async function loadOutline() {
            try {
                const response = await fetch(`${url}/outline`, { signal: controller.signal });
                if (!response.ok) throw new Error('Sumário indisponível. Use os botões de página.');
                const outline = await response.json();
                if (controller.signal.aborted) return;
                tocStatus.textContent = outline.source === 'pages'
                    ? 'Este PDF não tem tópicos marcados. Navegue pelas páginas abaixo.' : '';
                for (const entry of outline.items) {
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.className = 'toc-entry btn btn-light w-100 text-start text-break mb-1';
                    button.textContent = `${entry.title} · p. ${entry.page}`;
                    button.dataset.page = entry.page;
                    button.style.paddingLeft = `${10 + Math.min(entry.level, 6) * 12}px`;
                    button.addEventListener('click', () => {
                        loadPage(entry.page);
                        if (window.matchMedia('(max-width: 767.98px)').matches) sidebar.open = false;
                    });
                    toc.appendChild(button);
                }
                highlightTopic();
            } catch (error) {
                if (!controller.signal.aborted) tocStatus.textContent = error.message;
            }
        }
        await Promise.all([loadPage(1), loadOutline()]);
    } else if (file.preview === 'text') {
        try {
            const response = await fetch(url, { signal: controller.signal });
            if (!response.ok) throw new Error('Falha na prévia');
            const text = await response.text();
            if (controller.signal.aborted) return;
            const pre = document.createElement('pre');
            // Mesmo HTML e SVG são exibidos como texto, nunca executados.
            pre.textContent = text;
            previewBody.appendChild(pre);
            ready();
            previewNotice.textContent = response.headers.get('X-Preview-Truncated') === 'true'
                ? 'Exibindo os primeiros 100 KB. Baixe para ver o conteúdo completo.'
                : 'Prévia de texto em UTF-8.';
        } catch (error) { failure(); }
    } else {
        const media = document.createElement(file.preview === 'image' ? 'img' : file.preview);
        media.addEventListener('error', failure);
        if (file.preview === 'image') {
            media.alt = file.filename;
            media.addEventListener('load', ready);
        } else {
            media.controls = true;
            media.preload = 'metadata';
            media.addEventListener('loadedmetadata', ready);
            if (file.preview === 'video') media.playsInline = true;
        }
        media.src = url;
        previewBody.appendChild(media);
    }
}

document.getElementById('linkForm').addEventListener('submit', async event => {
    event.preventDefault();
    const button = document.getElementById('sendLink');
    const status = document.getElementById('linkStatus');
    const url = document.getElementById('linkUrl');
    const title = document.getElementById('linkTitle');
    const data = { url: url.value.trim(), title: title.value.trim() };
    button.disabled = url.disabled = title.disabled = true;
    status.textContent = 'Compartilhando…';
    try {
        const response = await fetch('/links/', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
        });
        if (!response.ok) throw new Error('Use um endereço HTTP ou HTTPS válido, sem usuário ou senha.');
        event.target.reset();
        status.textContent = 'Link compartilhado com todos os dispositivos!';
        await carregarLinks();
    } catch (error) {
        status.textContent = error.message;
    } finally {
        button.disabled = url.disabled = title.disabled = false;
    }
});

async function carregarQRCode() {
    const status = document.getElementById('qrStatus');
    try {
        const response = await fetch('/connection/');
        if (!response.ok) throw new Error('Abra a página pelo IP da rede para gerar o QR Code.');
        const data = await response.json();
        const image = document.getElementById('connectionQR');
        image.src = data.qr;
        image.hidden = false;
        const address = document.getElementById('connectionAddress');
        address.href = data.url;
        address.textContent = data.url;
        status.textContent = '';
    } catch (error) { status.textContent = error.message; }
}
carregarQRCode();

// EventSource reconecta automaticamente se a conexão cair.
const events = new EventSource('/events/');
events.onopen = () => {
    connection.classList.add('online');
    connectionText.textContent = 'Atualização em tempo real';
};
events.onmessage = syncCatalog;
events.onerror = () => {
    connection.classList.remove('online');
    connectionText.textContent = 'Reconectando…';
};
syncCatalog();


async function abrirTabela(file, controller) {
    const toolbar = document.createElement('div');
    toolbar.className = 'sheet-toolbar d-flex align-items-center flex-wrap gap-3 mb-3';
    const sheet = document.createElement('select');
    sheet.className = 'form-select w-auto';
    sheet.setAttribute('aria-label', 'Aba da planilha');
    const separator = document.createElement('select');
    separator.className = 'form-select w-auto';
    separator.setAttribute('aria-label', 'Separador do CSV');
    for (const [value, text] of [['auto', 'Separador automático'], [',', 'Vírgula'], [';', 'Ponto e vírgula'], ['\t', 'Tabulação'], ['|', 'Barra vertical']]) {
        separator.add(new Option(text, value));
    }
    const isCsv = /\.(csv|tsv)$/i.test(file.filename);
    separator.hidden = !isCsv;
    const headerLabel = document.createElement('label');
    headerLabel.className = 'd-flex align-items-center gap-2';
    const header = document.createElement('input');
    header.type = 'checkbox';
    header.className = 'form-check-input mt-0';
    header.checked = isCsv;
    headerLabel.append(header, document.createTextNode('Primeira linha como cabeçalho'));
    const previous = document.createElement('button');
    const next = document.createElement('button');
    for (const button of [previous, next]) {
        button.type = 'button';
        button.className = 'btn btn-outline-primary';
        button.disabled = true;
    }
    previous.textContent = '← Anterior';
    next.textContent = 'Próxima →';
    const label = document.createElement('span');
    label.setAttribute('aria-live', 'polite');
    toolbar.append(sheet, separator, headerLabel, previous, label, next);
    const scroll = document.createElement('div');
    scroll.className = 'sheet-scroll table-responsive border rounded-3';
    scroll.tabIndex = 0;
    scroll.setAttribute('role', 'region');
    scroll.setAttribute('aria-label', 'Conteúdo da planilha, com rolagem horizontal');
    previewBody.append(toolbar, scroll);
    let offset = 0;
    let version = 0;
    let more = false;
    function columnName(index) {
        let name = '';
        for (let n = index + 1; n > 0; n = Math.floor((n - 1) / 26)) name = String.fromCharCode(65 + (n - 1) % 26) + name;
        return name;
    }
    async function load(target = 0) {
        const current = ++version;
        previous.disabled = next.disabled = true;
        previewBody.setAttribute('aria-busy', 'true');
        previewNotice.textContent = 'Carregando tabela…';
        const params = new URLSearchParams({ sheet: sheet.value || '0', offset: target, delimiter: separator.value, header: header.checked });
        try {
            const response = await fetch(`/preview/${file.id}/table?${params}`, { signal: controller.signal });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Não foi possível ler a tabela.');
            if (controller.signal.aborted || current !== version) return;
            if (!sheet.options.length) data.sheets.forEach((name, index) => sheet.add(new Option(name, index)));
            sheet.value = String(data.sheet);
            sheet.hidden = isCsv;
            offset = data.offset;
            more = data.has_more;
            const table = document.createElement('table');
            table.className = 'sheet-table table table-striped table-bordered table-sm mb-0';
            table.setAttribute('aria-label', data.sheets[data.sheet]);
            const columns = Math.max(data.headers?.length || 0, ...data.rows.map(row => row.length), 1);
            const head = table.createTHead();
            head.className = 'table-light';
            const top = head.insertRow();
            for (let index = -1; index < columns; index++) {
                const cell = document.createElement('th');
                cell.scope = 'col';
                cell.textContent = index < 0 ? 'Linha' : (data.headers?.[index] || columnName(index));
                top.appendChild(cell);
            }
            const body = table.createTBody();
            data.rows.forEach((values, index) => {
                const row = body.insertRow();
                const number = document.createElement('th');
                number.scope = 'row';
                number.textContent = data.first_row + index;
                row.appendChild(number);
                for (let col = 0; col < columns; col++) row.insertCell().textContent = values[col] ?? '';
            });
            if (!data.rows.length) {
                const empty = body.insertRow().insertCell();
                empty.colSpan = columns + 1;
                empty.className = 'empty text-center text-secondary py-4';
                empty.textContent = 'Nenhuma linha de dados nesta aba.';
            }
            scroll.replaceChildren(table);
            scroll.scrollTop = 0;
            label.textContent = data.rows.length ? `Linhas ${data.first_row}–${data.first_row + data.rows.length - 1}` : 'Sem linhas';
            previewNotice.textContent = data.notes.join(' ');
        } catch (error) {
            if (!controller.signal.aborted && current === version) previewNotice.textContent = error.message;
        } finally {
            if (!controller.signal.aborted && current === version) {
                previewBody.setAttribute('aria-busy', 'false');
                previous.disabled = offset === 0;
                next.disabled = !more;
            }
        }
    }
    previous.addEventListener('click', () => load(Math.max(0, offset - 100)));
    next.addEventListener('click', () => load(offset + 100));
    for (const control of [sheet, separator, header]) control.addEventListener('change', () => {
        offset = 0;
        more = false;
        scroll.replaceChildren();
        load();
    });
    await load();
}

fetch('/storage/').then(response => {
    if (!response.ok) throw new Error('Limite indisponível');
    return response.json();
}).then(storage => {
    document.getElementById('storageStatus').textContent =
        `Limite total de arquivos: ${tamanho(storage.limit)}. Os arquivos expiram após 2 minutos.`;
}).catch(() => {});
