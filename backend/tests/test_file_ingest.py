"""
Unit tests for CSV, XLSX, and XLS File Ingestion Service.
"""

import io
import os
import struct
import tempfile
import unittest
import zipfile

from app.db.models import Connection
from app.db.target_db import TargetDatabaseManager
from app.services.file_ingest import FileIngestor, sanitize_identifier


def _build_minimal_xlsx() -> bytes:
    """Builds a minimal valid multi-sheet .xlsx archive in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
            "</Types>",
        )
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        zf.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Sales" sheetId="1" r:id="rId1"/></sheets>'
            "</workbook>",
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
            "</Relationships>",
        )
        zf.writestr(
            "xl/sharedStrings.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="4" uniqueCount="4">'
            "<si><t>Region</t></si>"
            "<si><t>Units</t></si>"
            "<si><t>North</t></si>"
            "<si><t>South</t></si>"
            "</sst>",
        )
        zf.writestr(
            "xl/worksheets/sheet1.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<sheetData>"
            '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="inlineStr"><is><t>Revenue</t></is></c></row>'
            '<row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2"><v>10</v></c><c r="C2"><v>250.5</v></c></row>'
            '<row r="3"><c r="A3" t="s"><v>3</v></c><c r="B3"><v>5</v></c><c r="C3"><v>120.0</v></c></row>'
            "</sheetData>"
            "</worksheet>",
        )
    return buf.getvalue()


def _build_minimal_biff8_xls() -> bytes:
    """Builds a minimal valid binary OLE2 + BIFF8 .xls workbook in memory."""
    def biff_rec(rec_id: int, payload: bytes) -> bytes:
        return struct.pack("<HH", rec_id, len(payload)) + payload

    def biff_str_16(s: str) -> bytes:
        raw = s.encode("latin-1")
        return struct.pack("<HB", len(raw), 0) + raw

    def biff_str_8(s: str) -> bytes:
        raw = s.encode("latin-1")
        return struct.pack("<BB", len(raw), 0) + raw

    # Sheet stream (starts after workbook globals)
    sheet_bof = biff_rec(0x0809, struct.pack("<HHHHII", 0x0600, 0x0010, 0, 0, 0, 0))
    c_00 = biff_rec(0x0204, struct.pack("<HHH", 0, 0, 0) + biff_str_16("Product"))
    c_01 = biff_rec(0x0204, struct.pack("<HHH", 0, 1, 0) + biff_str_16("Amount"))
    c_10 = biff_rec(0x0204, struct.pack("<HHH", 1, 0, 0) + biff_str_16("Widget"))
    c_11 = biff_rec(0x0203, struct.pack("<HHHd", 1, 1, 0, 42.5))
    sheet_eof = biff_rec(0x000A, b"")
    sheet_stream = sheet_bof + c_00 + c_01 + c_10 + c_11 + sheet_eof

    # Globals stream
    glob_bof = biff_rec(0x0809, struct.pack("<HHHHII", 0x0600, 0x0005, 0, 0, 0, 0))
    placeholder_bs = biff_rec(0x0085, struct.pack("<IH", 0, 0) + biff_str_8("LegacySheet"))
    glob_eof = biff_rec(0x000A, b"")
    sheet_offset = len(glob_bof) + len(placeholder_bs) + len(glob_eof)
    boundsheet = biff_rec(0x0085, struct.pack("<IH", sheet_offset, 0) + biff_str_8("LegacySheet"))
    wb_stream = glob_bof + boundsheet + glob_eof + sheet_stream

    # Pad workbook stream to >= 4096 bytes so it sits in regular FAT sectors
    if len(wb_stream) < 4096:
        wb_stream = wb_stream.ljust(4096, b"\x00")
    wb_sectors = (len(wb_stream) + 511) // 512
    wb_stream = wb_stream.ljust(wb_sectors * 512, b"\x00")

    # Sectors layout:
    # Sector 0..wb_sectors-1: Workbook stream
    # Sector wb_sectors: Directory sector
    # Sector wb_sectors+1: FAT sector
    dir_sec_idx = wb_sectors
    fat_sec_idx = wb_sectors + 1

    # Header (512 bytes)
    header = bytearray(512)
    header[0:8] = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
    struct.pack_into("<H", header, 24, 0x003E)  # minor ver
    struct.pack_into("<H", header, 26, 0x0003)  # major ver 3
    struct.pack_into("<H", header, 28, 0xFFFE)  # little endian
    struct.pack_into("<H", header, 30, 9)       # sector shift 512
    struct.pack_into("<H", header, 32, 6)       # mini sector shift 64
    struct.pack_into("<I", header, 44, 1)       # 1 FAT sector
    struct.pack_into("<I", header, 48, dir_sec_idx)
    struct.pack_into("<I", header, 56, 4096)    # mini cutoff
    struct.pack_into("<I", header, 60, 0xFFFFFFFE)
    struct.pack_into("<I", header, 68, 0xFFFFFFFE)
    for i in range(109):
        struct.pack_into("<I", header, 76 + i * 4, fat_sec_idx if i == 0 else 0xFFFFFFFF)

    # Directory sector (4 entries * 128 bytes)
    dir_sec = bytearray(512)
    # Entry 0: Root Entry
    root_name = "Root Entry".encode("utf-16-le") + b"\x00\x00"
    dir_sec[0:len(root_name)] = root_name
    struct.pack_into("<H", dir_sec, 64, len(root_name))
    dir_sec[66] = 5  # Root
    struct.pack_into("<I", dir_sec, 76, 1)  # child = Entry 1
    struct.pack_into("<I", dir_sec, 116, 0xFFFFFFFE)
    # Entry 1: Workbook
    wb_name = "Workbook".encode("utf-16-le") + b"\x00\x00"
    dir_sec[128:128 + len(wb_name)] = wb_name
    struct.pack_into("<H", dir_sec, 128 + 64, len(wb_name))
    dir_sec[128 + 66] = 2  # Stream
    struct.pack_into("<I", dir_sec, 128 + 116, 0)  # starts at sector 0
    struct.pack_into("<I", dir_sec, 128 + 120, len(wb_stream))

    # FAT sector
    fat_sec = bytearray(b"\xFF" * 512)
    for i in range(wb_sectors):
        nxt = i + 1 if i + 1 < wb_sectors else 0xFFFFFFFE
        struct.pack_into("<I", fat_sec, i * 4, nxt)
    struct.pack_into("<I", fat_sec, dir_sec_idx * 4, 0xFFFFFFFE)
    struct.pack_into("<I", fat_sec, fat_sec_idx * 4, 0xFFFFFFFD)  # FATSECT

    return bytes(header) + wb_stream + bytes(dir_sec) + bytes(fat_sec)


class TestFileIngest(unittest.TestCase):
    def test_sanitize_identifier(self):
        self.assertEqual(sanitize_identifier("Total Sales ($)"), "total_sales")
        self.assertEqual(sanitize_identifier("2026 Revenue"), "col_2026_revenue")
        self.assertEqual(sanitize_identifier("order"), "order_col")

    def test_csv_ingestion_and_query(self):
        csv_bytes = (
            b"\xef\xbb\xbfOrder ID,Customer Region,Zip Code,Revenue\n"
            b"1,West,02139,\"$1,250.50\"\n"
            b"2,East,10001,\"$749.50\"\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "csv_test.db")
            summary = FileIngestor.ingest_files_to_sqlite([("Q1 Sales.csv", csv_bytes)], db_path)
            self.assertEqual(len(summary), 1)
            tbl = summary[0]
            self.assertEqual(tbl["table_name"], "q1_sales")
            self.assertEqual(tbl["row_count"], 2)

            types = {c["name"]: c["type"] for c in tbl["columns"]}
            self.assertEqual(types["order_id"], "INTEGER")
            self.assertEqual(types["zip_code"], "TEXT")  # Leading zero preserved
            self.assertEqual(types["revenue"], "REAL")   # Currency stripped cleanly

            conn = Connection(id="c1", dialect="sqlite", database=db_path)
            res = TargetDatabaseManager.execute_query(conn, "SELECT SUM(revenue) AS total FROM q1_sales")
            self.assertEqual(res.rows[0]["total"], 2000.0)

    def test_xlsx_ingestion(self):
        xlsx_bytes = _build_minimal_xlsx()
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "xlsx_test.db")
            summary = FileIngestor.ingest_files_to_sqlite([("regional_sales.xlsx", xlsx_bytes)], db_path)
            self.assertEqual(len(summary), 1)
            self.assertEqual(summary[0]["row_count"], 2)
            conn = Connection(id="c2", dialect="sqlite", database=db_path)
            res = TargetDatabaseManager.execute_query(
                conn, "SELECT region, revenue FROM regional_sales ORDER BY units DESC"
            )
            self.assertEqual(res.rows[0]["region"], "North")
            self.assertEqual(res.rows[0]["revenue"], 250.5)

    def test_xls_xml_html_and_biff8(self):
        # 1. HTML .xls export
        html_xls = b"<table><tr><th>Item</th><th>Qty</th></tr><tr><td>Pen</td><td>12</td></tr></table>"
        # 2. Binary OLE2 + BIFF8 .xls
        biff_xls = _build_minimal_biff8_xls()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "xls_test.db")
            summary = FileIngestor.ingest_files_to_sqlite(
                [("html_export.xls", html_xls), ("binary_legacy.xls", biff_xls)],
                db_path,
            )
            self.assertEqual(len(summary), 2)
            conn = Connection(id="c3", dialect="sqlite", database=db_path)
            r1 = TargetDatabaseManager.execute_query(conn, "SELECT item, qty FROM html_export")
            self.assertEqual(r1.rows[0], {"item": "Pen", "qty": 12})

            r2 = TargetDatabaseManager.execute_query(conn, "SELECT product, amount FROM binary_legacy")
            self.assertEqual(r2.rows[0], {"product": "Widget", "amount": 42.5})


if __name__ == "__main__":
    unittest.main()

