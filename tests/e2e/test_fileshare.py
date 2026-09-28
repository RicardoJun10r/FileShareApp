from io import BytesIO
from pathlib import Path

from playwright.sync_api import expect
from pypdf import PdfReader, PdfWriter

from test_pdf_links import sample_pdf
from test_tabular_preview import xlsx_fixture


def open_app(page, app_url):
    page.goto(app_url)
    expect(page.locator('#connectionText')).to_have_text('Atualização em tempo real')
    expect(page.locator('#count')).not_to_have_text('Carregando…')


def upload(page, name, content, mime='application/octet-stream'):
    page.locator('#files').set_input_files({'name': name, 'mimeType': mime, 'buffer': content})
    page.get_by_role('button', name='Enviar arquivos ↑', exact=True).click()
    expect(page.locator('#status')).to_have_text('Arquivos enviados e disponíveis para todos na rede!')
    return page.get_by_role('button', name=f'Abrir prévia de {name}', exact=True)


def fits(page):
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), 'Página tem overflow horizontal'
    dialog = page.get_by_role('dialog')
    if dialog.is_visible():
        assert dialog.evaluate('(el) => el.scrollWidth <= el.clientWidth + 1'), 'Prévia tem overflow horizontal fora da grade'
        box = page.locator('#closePreview').bounding_box()
        assert box and box['x'] >= 0 and box['x'] + box['width'] <= page.viewport_size['width'] + 1


def test_upload_realtime_preview_download(page, new_context, app_url):
    open_app(page, app_url)
    other = new_context().new_page()
    open_app(other, app_url)
    name = 'arquivo-' + 'nome-longo-' * 12 + '.txt'
    content = b'Conteudo E2E <script>nao executar</script>'
    upload(page, name, content, 'text/plain')
    button = other.get_by_role('button', name=f'Abrir prévia de {name}', exact=True)
    expect(button).to_be_visible()
    fits(page)
    button.click()
    expect(other.locator('#previewBody pre')).to_have_text(content.decode())
    fits(other)
    with other.expect_download() as info:
        other.locator('#previewDownload').click()
    assert Path(info.value.path()).read_bytes() == content
    other.get_by_role('button', name='Fechar prévia').click()
    expect(other.get_by_role('dialog')).not_to_be_visible()


def test_links_and_qr(page, new_context, app_url):
    open_app(page, app_url)
    other = new_context().new_page()
    open_app(other, app_url)
    page.locator('#linkUrl').fill('https://example.com/' + 'long-path-' * 25)
    page.locator('#linkTitle').fill('Link de teste')
    page.get_by_role('button', name='Enviar link ↑').click()
    expect(other.get_by_role('link', name='Link de teste', exact=True)).to_be_visible()
    expect(page.locator('#connectionAddress')).to_have_attribute('href', app_url + '/')
    expect(page.locator('#connectionQR')).to_be_visible()
    page.wait_for_function('document.querySelector("#connectionQR").naturalWidth > 0')
    fits(page)
    fits(other)


def test_pdf_outline_navigation(page, app_url):
    open_app(page, app_url)
    writer = PdfWriter()
    writer.append(PdfReader(BytesIO(sample_pdf())))
    writer.add_outline_item('Introdução', 0)
    writer.add_outline_item('Segunda página', 1)
    output = BytesIO()
    writer.write(output)
    upload(page, 'documento.pdf', output.getvalue(), 'application/pdf').click()
    page.wait_for_function('document.querySelector(".pdf-page")?.naturalWidth > 0')
    expect(page.locator('.pdf-controls')).to_contain_text('Página 1 de 2')
    if not page.locator('.pdf-sidebar').evaluate('(el) => el.open'):
        page.get_by_text('Sumário do documento', exact=True).click()
    page.get_by_role('button', name='Segunda página · p. 2', exact=True).click()
    expect(page.locator('.pdf-controls')).to_contain_text('Página 2 de 2')
    page.get_by_role('button', name='← Anterior', exact=True).click()
    expect(page.locator('.pdf-controls')).to_contain_text('Página 1 de 2')
    fits(page)


def test_csv_pagination_separator_and_mobile_grid(page, app_url):
    open_app(page, app_url)
    raw = ('Nome;Código;Descrição\n' + ''.join(f'Pessoa {i};00{i};"Texto; com separador"\n' for i in range(105))).encode()
    upload(page, 'dados.csv', raw, 'text/csv').click()
    expect(page.locator('.sheet-table tbody tr')).to_have_count(100)
    expect(page.locator('.sheet-table thead')).to_contain_text('Código')
    page.get_by_role('button', name='Próxima →', exact=True).click()
    expect(page.locator('.sheet-table tbody tr')).to_have_count(5)
    expect(page.locator('.sheet-table tbody tr').first).to_contain_text('Pessoa 100')
    page.get_by_label('Separador do CSV').select_option(';')
    expect(page.locator('.sheet-table tbody tr')).to_have_count(100)
    expect(page.locator('.sheet-table tbody tr').first).to_contain_text('Texto; com separador')
    fits(page)
    if page.viewport_size['width'] < 500:
        assert page.locator('.sheet-scroll').evaluate('(el) => el.scrollWidth > el.clientWidth')


def test_excel_tabs(page, app_url):
    open_app(page, app_url)
    upload(page, 'planilha.xlsx', xlsx_fixture()).click()
    expect(page.locator('.sheet-table')).to_contain_text('00123')
    page.get_by_label('Aba da planilha').select_option(label='Vazia')
    expect(page.locator('.sheet-table')).to_contain_text('Nenhuma linha de dados nesta aba.')
    page.get_by_label('Aba da planilha').select_option(label='Dados')
    expect(page.locator('.sheet-table')).to_contain_text('=SUM(B1,2)')
    fits(page)
