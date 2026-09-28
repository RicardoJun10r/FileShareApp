import unittest
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient

from main import app, db


def xlsx_fixture():
    """Pequena fixture OOXML com duas abas, sem dependência de um editor Excel."""
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>""",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Dados" sheetId="1" r:id="rId1"/><sheet name="Vazia" sheetId="2" r:id="rId2"/></sheets></workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/></Relationships>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:C1"/><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>00123</t></is></c><c r="B1" t="n"><v>0</v></c><c r="C1"><f>SUM(B1,2)</f><v>2</v></c></row></sheetData></worksheet>""",
        )
        archive.writestr(
            "xl/worksheets/sheet2.xml",
            """<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>""",
        )
    return output.getvalue()


class TabularPreviewTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.uploaded = []

    def tearDown(self):
        for file_id in self.uploaded:
            db.pop(file_id, None)
        self.client.close()

    def upload(self, name, data):
        self.client.post("/upload/", files={"files": (name, data)}).raise_for_status()
        file = self.client.get("/files/").json()[-1]
        self.uploaded.append(file["id"])
        self.assertEqual(file["preview"], "spreadsheet")
        return f"/preview/{file['id']}/table"

    def test_csv_quotes_multiline_header_and_original(self):
        raw = (
            '\ufeffNome;Código;Nota\n"João; Silva";00123;"linha 1\nlinha 2"\n'.encode()
        )
        url = self.upload("dados.csv", raw)
        data = self.client.get(url, params={"header": "true"}).json()
        self.assertEqual(data["headers"], ["Nome", "Código", "Nota"])
        self.assertEqual(data["rows"], [["João; Silva", "00123", "linha 1\nlinha 2"]])
        self.assertEqual(self.client.get("/download/" + self.uploaded[-1]).content, raw)

    def test_encodings_pagination_and_manual_separator(self):
        for encoding in ("utf-16", "cp1252"):
            url = self.upload(
                "dados.csv", "Nome;Cidade\nJoão;São Paulo".encode(encoding)
            )
            self.assertEqual(self.client.get(url).json()["rows"][1][0], "João")
        url = self.upload(
            "rows.tsv",
            ("A\tB\n" + "".join(f"{i}\tvalue\n" for i in range(105))).encode(),
        )
        first = self.client.get(url, params={"header": True}).json()
        second = self.client.get(url, params={"header": True, "offset": 100}).json()
        self.assertEqual(len(first["rows"]), 100)
        self.assertTrue(first["has_more"])
        self.assertEqual(second["rows"][0][0], "100")
        self.assertFalse(second["has_more"])
        self.assertEqual(second["first_row"], 102)
        url = self.upload("single.csv", b"a|b\n1|2")
        self.assertEqual(
            self.client.get(url, params={"delimiter": "|"}).json()["rows"][1],
            ["1", "2"],
        )
        self.assertEqual(
            self.client.get(url, params={"delimiter": "invalid"}).status_code, 422
        )

    def test_xlsx_tabs_formulas_empty_and_invalid(self):
        url = self.upload("book.xlsx", xlsx_fixture())
        data = self.client.get(url).json()
        self.assertEqual(data["sheets"], ["Dados", "Vazia"])
        self.assertEqual(data["rows"][0], ["00123", "0", "=SUM(B1,2)"])
        self.assertEqual(self.client.get(url, params={"sheet": 1}).json()["rows"], [])
        self.assertEqual(self.client.get(url, params={"sheet": 2}).status_code, 404)
        url = self.upload("broken.xlsx", b"not excel")
        self.assertEqual(self.client.get(url).status_code, 422)

    def test_limits_and_static_assets(self):
        url = self.upload(
            "wide.csv", (",".join(["x"] * 102) + "\n" + "a" * 5000).encode()
        )
        data = self.client.get(url, params={"delimiter": ","}).json()
        self.assertEqual(len(data["rows"][0]), 100)
        self.assertEqual(len(data["rows"][1][0]), 4001)
        self.assertEqual(len(data["notes"]), 3)
        html = self.client.get("/").text
        self.assertNotIn("<style>", html)
        self.assertNotIn("<script>", html)
        for path in ("/static/styles.css", "/static/app.js"):
            self.assertIn(path, html)
            self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.get("/preview/missing/table").status_code, 404)
