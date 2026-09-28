"""Leitura de planilhas e CSVs para uma prévia paginada, sem executar fórmulas."""

import csv
from datetime import date, datetime, time
from io import BytesIO, StringIO
from itertools import islice
from pathlib import Path

import xlrd
from fastapi import HTTPException
from openpyxl import load_workbook

PAGE_SIZE = 100
MAX_COLUMNS = 100
MAX_CELL_CHARS = 4000


def display_value(value):
    if value is None:
        return ""
    if isinstance(value, (date, datetime, time)):
        return (
            value.isoformat(sep=" ")
            if isinstance(value, datetime)
            else value.isoformat()
        )
    if isinstance(value, bool):
        return "VERDADEIRO" if value else "FALSO"
    return str(value)


def read_table(content, filename, sheet=0, offset=0, delimiter="auto", header=False):
    extension = Path(filename).suffix.lower()
    workbook = None
    notes = []
    try:
        if extension in (".csv", ".tsv"):
            encoding = (
                "utf-16"
                if content.startswith((b"\xff\xfe", b"\xfe\xff"))
                else "utf-8-sig"
            )
            try:
                text = content.decode(encoding)
            except UnicodeDecodeError:
                encoding = "cp1252"
                text = content.decode(encoding)
            if delimiter == "auto":
                if extension == ".tsv":
                    delimiter = "\t"
                else:
                    try:
                        delimiter = (
                            csv.Sniffer()
                            .sniff(text[:65536], delimiters=",;\t|")
                            .delimiter
                        )
                    except csv.Error:
                        delimiter = ","
            rows = iter(csv.reader(StringIO(text, newline=""), delimiter=delimiter))
            sheets = [filename]
            if sheet != 0:
                raise HTTPException(status_code=404, detail="Aba não encontrada")
            notes.append(f"Codificação: {encoding}. Separador: {delimiter!r}.")
        elif extension in (".xlsx", ".xlsm"):
            workbook = load_workbook(
                BytesIO(content), read_only=True, data_only=False, keep_links=False
            )
            sheets = workbook.sheetnames
            if sheet >= len(sheets):
                raise HTTPException(status_code=404, detail="Aba não encontrada")
            worksheet = workbook[sheets[sheet]]
            rows = worksheet.iter_rows(
                values_only=True,
                max_col=min(worksheet.max_column or 1, MAX_COLUMNS + 1),
            )
            notes.append(
                "Fórmulas aparecem como texto, sem recálculo. Gráficos, imagens e estilos do Excel não são reproduzidos."
            )
        elif extension == ".xls":
            workbook = xlrd.open_workbook(file_contents=content, on_demand=True)
            sheets = workbook.sheet_names()
            if sheet >= len(sheets):
                raise HTTPException(status_code=404, detail="Aba não encontrada")
            worksheet = workbook.sheet_by_index(sheet)

            def xls_rows():
                for index in range(worksheet.nrows):
                    values = []
                    for column in range(min(worksheet.ncols, MAX_COLUMNS + 1)):
                        cell = worksheet.cell(index, column)
                        value = cell.value
                        if cell.ctype == xlrd.XL_CELL_DATE:
                            value = xlrd.xldate_as_datetime(value, workbook.datemode)
                        elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                            value = bool(value)
                        elif cell.ctype == xlrd.XL_CELL_ERROR:
                            value = xlrd.error_text_from_code.get(value, "#ERRO")
                        values.append(value)
                    yield values

            rows = xls_rows()
            notes.append(
                "Exibe os valores salvos no XLS, sem recálculo de fórmulas ou reprodução de gráficos e estilos."
            )
        else:
            raise HTTPException(
                status_code=415, detail="Formato de planilha não suportado"
            )

        headings = list(next(rows, [])) if header else None
        selected = list(islice(rows, offset, offset + PAGE_SIZE + 1))
        has_more = len(selected) > PAGE_SIZE
        selected = selected[:PAGE_SIZE]
        truncated_columns = any(len(row) > MAX_COLUMNS for row in selected) or (
            headings is not None and len(headings) > MAX_COLUMNS
        )
        truncated_cells = False

        def normalize(row):
            nonlocal truncated_cells
            result = []
            for value in row[:MAX_COLUMNS]:
                text = display_value(value)
                if len(text) > MAX_CELL_CHARS:
                    truncated_cells = True
                    text = text[:MAX_CELL_CHARS] + "…"
                result.append(text)
            return result

        data = [normalize(row) for row in selected]
        headings = normalize(headings) if headings is not None else None
        if truncated_columns:
            notes.append("A prévia mostra apenas as primeiras 100 colunas.")
        if truncated_cells:
            notes.append("Células longas foram limitadas a 4.000 caracteres na prévia.")
        return {
            "sheets": sheets,
            "sheet": sheet,
            "offset": offset,
            "rows": data,
            "headers": headings,
            "has_more": has_more,
            "page_size": PAGE_SIZE,
            "first_row": offset + (2 if header else 1),
            "notes": notes,
        }
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=422,
            detail="Não foi possível ler a planilha. Verifique o formato, a codificação ou a proteção por senha.",
        ) from error
    finally:
        if workbook is not None:
            if extension == ".xls":
                workbook.release_resources()
            else:
                workbook.close()
