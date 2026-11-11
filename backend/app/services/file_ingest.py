"""
CSV, TSV, XLS, and XLSX File Ingestion Service.
Parses uploaded spreadsheets into sanitized SQLite tables so users can
explore, query, chart, and analyze spreadsheet files using SchemaSense's
full NL-to-SQL and visualization pipeline.

Supports:
- .csv / .tsv (stdlib csv with delimiter & encoding detection)
- .xlsx (openpyxl if installed, otherwise built-in ZIP + XML parser)
- .xls (xlrd if installed, XML Spreadsheet 2003 / HTML table exports, and
  built-in pure-Python OLE2 + BIFF8 binary Excel reader)
"""

import csv
import io
import os
import re
import sqlite3
import struct
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from html.parser import HTMLParser
from typing import List, Dict, Any, Tuple, Optional

SQL_RESERVED_WORDS = {
    "select", "from", "where", "group", "order", "by", "having", "limit",
    "join", "inner", "left", "right", "outer", "on", "as", "and", "or", "not",
    "in", "is", "null", "table", "create", "drop", "alter", "insert", "update",
    "delete", "values", "into", "union", "distinct", "case", "when", "then",
    "else", "end", "index", "key", "primary", "foreign", "check", "default"
}


def sanitize_identifier(raw: str, prefix: str = "col", fallback: str = "column") -> str:
    """Converts an arbitrary header or sheet name into a safe lowercase SQL identifier."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", (raw or "").strip().lower()).strip("_")
    if not cleaned:
        cleaned = fallback
    if cleaned[0].isdigit():
        cleaned = f"{prefix}_{cleaned}"
    if cleaned in SQL_RESERVED_WORDS:
        cleaned = f"{cleaned}_{prefix}"
    return cleaned


def deduplicate_names(names: List[str]) -> List[str]:
    seen: Dict[str, int] = {}
    result: List[str] = []
    for name in names:
        if name not in seen:
            seen[name] = 1
            result.append(name)
        else:
            seen[name] += 1
            candidate = f"{name}_{seen[name]}"
            while candidate in seen:
                seen[name] += 1
                candidate = f"{name}_{seen[name]}"
            seen[candidate] = 1
            result.append(candidate)
    return result


def _excel_serial_to_iso(serial: float) -> str:
    """Converts Excel 1900-epoch serial date to ISO YYYY-MM-DD (or YYYY-MM-DD HH:MM:SS)."""
    base = datetime(1899, 12, 30)
    dt = base + timedelta(days=serial)
    if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
        return dt.strftime("%Y-%m-%d")
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _col_letters_to_index(letters: str) -> int:
    idx = 0
    for ch in letters.upper():
        if "A" <= ch <= "Z":
            idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _parse_csv_bytes(data: bytes, ext: str) -> List[Tuple[str, List[List[Any]]]]:
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = data.decode("utf-8", errors="replace")

    delimiter = "\t" if ext == ".tsv" else ","
    sample = text[:4096]
    if sample and ext != ".tsv":
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            delimiter = dialect.delimiter
        except csv.Error:
            pass

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [row for row in reader if any(str(cell).strip() != "" for cell in row)]
    return [("data", rows)]


# =====================================================================
# Pure-Python XLSX Parser (ZIP + XML fallback when openpyxl is absent)
# =====================================================================

def _parse_xlsx_bytes(data: bytes) -> List[Tuple[str, List[List[Any]]]]:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
        sheets: List[Tuple[str, List[List[Any]]]] = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = []
            for row in ws.iter_rows(values_only=True):
                if any(cell is not None and str(cell).strip() != "" for cell in row):
                    rows.append([
                        cell.isoformat() if isinstance(cell, datetime) else cell
                        for cell in row
                    ])
            if rows:
                sheets.append((sheet_name, rows))
        wb.close()
        return sheets
    except ImportError:
        pass

    # Built-in ZIP + XML reader
    sheets = []
    with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
        names = set(zf.namelist())

        # 1. Shared Strings
        shared_strings: List[str] = []
        if "xl/sharedStrings.xml" in names:
            sst_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sst_root.iter():
                if si.tag.endswith("}si") or si.tag == "si":
                    parts = [t.text or "" for t in si.iter() if t.tag.endswith("}t") or t.tag == "t"]
                    shared_strings.append("".join(parts))

        # 2. Detect date styles from xl/styles.xml
        date_xf_indices = set()
        if "xl/styles.xml" in names:
            styles_root = ET.fromstring(zf.read("xl/styles.xml"))
            custom_date_fmt_ids = set(range(14, 23)) | {45, 46, 47}
            for elem in styles_root.iter():
                if elem.tag.endswith("}numFmt") or elem.tag == "numFmt":
                    fmt_id = int(elem.attrib.get("numFmtId", -1))
                    code = elem.attrib.get("formatCode", "").lower()
                    if any(tok in code for tok in ("yy", "dd", "mm/dd", "dd/mm", "yyyy")):
                        custom_date_fmt_ids.add(fmt_id)
            cell_xfs = None
            for elem in styles_root.iter():
                if elem.tag.endswith("}cellXfs") or elem.tag == "cellXfs":
                    cell_xfs = elem
                    break
            if cell_xfs is not None:
                for idx, xf in enumerate(list(cell_xfs)):
                    fmt_id = int(xf.attrib.get("numFmtId", -1))
                    if fmt_id in custom_date_fmt_ids:
                        date_xf_indices.add(idx)

        # 3. Map workbook sheet names -> target xml paths
        rel_map: Dict[str, str] = {}
        if "xl/_rels/workbook.xml.rels" in names:
            rels_root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
            for rel in rels_root:
                rid = rel.attrib.get("Id", "")
                target = rel.attrib.get("Target", "").lstrip("/")
                if not target.startswith("xl/"):
                    target = f"xl/{target}"
                rel_map[rid] = target

        sheet_entries: List[Tuple[str, str]] = []
        if "xl/workbook.xml" in names:
            wb_root = ET.fromstring(zf.read("xl/workbook.xml"))
            for elem in wb_root.iter():
                if elem.tag.endswith("}sheet") or elem.tag == "sheet":
                    s_name = elem.attrib.get("name", f"Sheet{len(sheet_entries)+1}")
                    rid = ""
                    for k, v in elem.attrib.items():
                        if k.endswith("}id") or k == "r:id":
                            rid = v
                            break
                    target = rel_map.get(rid)
                    if target and target in names:
                        sheet_entries.append((s_name, target))

        if not sheet_entries:
            ws_files = sorted(n for n in names if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))
            sheet_entries = [(os.path.splitext(os.path.basename(w))[0], w) for w in ws_files]

        # 4. Parse worksheet rows
        for s_name, ws_path in sheet_entries:
            ws_root = ET.fromstring(zf.read(ws_path))
            parsed_rows: List[Dict[int, Any]] = []
            max_col = 0
            for row_el in ws_root.iter():
                if not (row_el.tag.endswith("}row") or row_el.tag == "row"):
                    continue
                row_dict: Dict[int, Any] = {}
                next_col_idx = 0
                for c_el in list(row_el):
                    if not (c_el.tag.endswith("}c") or c_el.tag == "c"):
                        continue
                    ref = c_el.attrib.get("r", "")
                    col_match = re.match(r"([A-Za-z]+)", ref)
                    col_idx = _col_letters_to_index(col_match.group(1)) if col_match else next_col_idx
                    next_col_idx = col_idx + 1
                    max_col = max(max_col, col_idx)

                    cell_type = c_el.attrib.get("t", "")
                    style_idx = int(c_el.attrib["s"]) if c_el.attrib.get("s", "").isdigit() else -1

                    v_text = None
                    is_text = None
                    for child in list(c_el):
                        if child.tag.endswith("}v") or child.tag == "v":
                            v_text = child.text
                        elif child.tag.endswith("}is") or child.tag == "is":
                            is_text = "".join(t.text or "" for t in child.iter() if t.tag.endswith("}t") or t.tag == "t")

                    val: Any = None
                    if cell_type == "s" and v_text is not None:
                        s_idx = int(v_text)
                        val = shared_strings[s_idx] if 0 <= s_idx < len(shared_strings) else ""
                    elif cell_type == "inlineStr":
                        val = is_text or ""
                    elif cell_type == "str":
                        val = v_text or ""
                    elif cell_type == "b" and v_text is not None:
                        val = v_text == "1"
                    elif cell_type == "e":
                        val = None
                    elif v_text is not None:
                        try:
                            num = float(v_text)
                            if style_idx in date_xf_indices and 1 <= num < 2958466:
                                val = _excel_serial_to_iso(num)
                            elif num.is_integer():
                                val = int(num)
                            else:
                                val = num
                        except ValueError:
                            val = v_text

                    if val is not None and str(val).strip() != "":
                        row_dict[col_idx] = val

                if row_dict:
                    parsed_rows.append(row_dict)

            if parsed_rows:
                dense_rows = [
                    [r.get(i, None) for i in range(max_col + 1)]
                    for r in parsed_rows
                ]
                sheets.append((s_name, dense_rows))

    return sheets


# =====================================================================
# HTML / XML / Pure-Python OLE2 + BIFF8 .XLS Parser
# =====================================================================

class _HTMLTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables: List[List[List[str]]] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._curr_table: List[List[str]] = []
        self._curr_row: List[str] = []
        self._curr_cell: List[str] = []

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t == "table":
            self._in_table = True
            self._curr_table = []
        elif t == "tr" and self._in_table:
            self._in_row = True
            self._curr_row = []
        elif t in ("td", "th") and self._in_row:
            self._in_cell = True
            self._curr_cell = []

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in ("td", "th") and self._in_cell:
            self._in_cell = False
            self._curr_row.append("".join(self._curr_cell).strip())
        elif t == "tr" and self._in_row:
            self._in_row = False
            if any(c != "" for c in self._curr_row):
                self._curr_table.append(self._curr_row)
        elif t == "table" and self._in_table:
            self._in_table = False
            if self._curr_table:
                self.tables.append(self._curr_table)

    def handle_data(self, data):
        if self._in_cell:
            self._curr_cell.append(data)


def _decode_rk(rk_int: int) -> float:
    """Decodes 30-bit Excel RK compressed numeric format."""
    is_div_100 = bool(rk_int & 1)
    is_int = bool(rk_int & 2)
    if is_int:
        # Signed 30-bit integer
        val = struct.unpack("<i", struct.pack("<I", rk_int))[0] >> 2
        result = float(val)
    else:
        raw_upper = rk_int & 0xFFFFFFFC
        ieee_bytes = b"\x00\x00\x00\x00" + struct.pack("<I", raw_upper)
        result = struct.unpack("<d", ieee_bytes)[0]
    if is_div_100:
        result /= 100.0
    if result.is_integer():
        return int(result)
    return result


def _extract_ole2_workbook_stream(data: bytes) -> bytes:
    """Extracts the 'Workbook' (or 'Book') stream from a Microsoft OLE2 Compound File."""
    if len(data) < 512 or data[:8] != b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1":
        raise ValueError("Not a valid OLE2 binary .xls file")

    sector_shift = struct.unpack_from("<H", data, 30)[0]
    mini_sector_shift = struct.unpack_from("<H", data, 32)[0]
    sector_size = 1 << sector_shift
    mini_sector_size = 1 << mini_sector_shift

    num_fat_sectors = struct.unpack_from("<I", data, 44)[0]
    first_dir_sector = struct.unpack_from("<I", data, 48)[0]
    mini_cutoff = struct.unpack_from("<I", data, 56)[0]
    first_minifat_sector = struct.unpack_from("<I", data, 60)[0]
    first_difat_sector = struct.unpack_from("<I", data, 68)[0]

    def read_sector(sec_idx: int) -> bytes:
        offset = 512 + sec_idx * sector_size
        return data[offset:offset + sector_size]

    # Build DIFAT list of FAT sector indices
    fat_sector_ids: List[int] = []
    for i in range(109):
        sid = struct.unpack_from("<I", data, 76 + i * 4)[0]
        if sid < 0xFFFFFFFA:
            fat_sector_ids.append(sid)

    difat_sec = first_difat_sector
    while difat_sec < 0xFFFFFFFA and len(fat_sector_ids) < num_fat_sectors:
        sec_bytes = read_sector(difat_sec)
        entries_per_sec = (sector_size // 4) - 1
        for i in range(entries_per_sec):
            sid = struct.unpack_from("<I", sec_bytes, i * 4)[0]
            if sid < 0xFFFFFFFA:
                fat_sector_ids.append(sid)
        difat_sec = struct.unpack_from("<I", sec_bytes, entries_per_sec * 4)[0]

    # Read FAT table
    fat: List[int] = []
    for fsid in fat_sector_ids:
        sec_bytes = read_sector(fsid)
        for i in range(0, len(sec_bytes), 4):
            fat.append(struct.unpack_from("<I", sec_bytes, i)[0])

    def read_chain(start_sec: int) -> bytes:
        chunks = []
        sec = start_sec
        visited = set()
        while sec < 0xFFFFFFFA and sec not in visited and sec < len(fat):
            visited.add(sec)
            chunks.append(read_sector(sec))
            sec = fat[sec]
        return b"".join(chunks)

    # Read Directory stream & locate Workbook / Book and Root Entry
    dir_bytes = read_chain(first_dir_sector)
    root_start = None
    wb_entry = None
    for off in range(0, len(dir_bytes), 128):
        entry = dir_bytes[off:off + 128]
        if len(entry) < 128:
            break
        name_len = struct.unpack_from("<H", entry, 64)[0]
        obj_type = entry[66]
        if name_len < 2 or obj_type == 0:
            continue
        name = entry[:name_len - 2].decode("utf-16-le", errors="ignore")
        start_sec = struct.unpack_from("<I", entry, 116)[0]
        stream_size = struct.unpack_from("<I", entry, 120)[0]
        if obj_type == 5:
            root_start = start_sec
        elif name in ("Workbook", "Book"):
            wb_entry = (start_sec, stream_size)

    if not wb_entry:
        raise ValueError("No Workbook stream found in .xls file")

    start_sec, stream_size = wb_entry
    if stream_size < mini_cutoff and root_start is not None:
        mini_stream = read_chain(root_start)
        minifat_bytes = read_chain(first_minifat_sector)
        minifat = [struct.unpack_from("<I", minifat_bytes, i)[0] for i in range(0, len(minifat_bytes), 4)]
        chunks = []
        sec = start_sec
        visited = set()
        while sec < 0xFFFFFFFA and sec not in visited and sec < len(minifat):
            visited.add(sec)
            chunks.append(mini_stream[sec * mini_sector_size:(sec + 1) * mini_sector_size])
            sec = minifat[sec]
        return b"".join(chunks)[:stream_size]

    return read_chain(start_sec)[:stream_size]


def _read_biff8_unicode_string(buf: bytes, pos: int, chunks_bounds: Optional[List[int]] = None, cch_bytes: int = 2) -> Tuple[str, int]:
    """Reads a BIFF8 Unicode string across optional CONTINUE record boundaries."""
    if cch_bytes == 1:
        cch = buf[pos]
        pos += 1
    else:
        cch = struct.unpack_from("<H", buf, pos)[0]
        pos += 2

    flags = buf[pos]
    pos += 1
    is_utf16 = bool(flags & 0x01)
    has_asian = bool(flags & 0x04)
    has_richtext = bool(flags & 0x08)

    rt_runs = 0
    if has_richtext:
        rt_runs = struct.unpack_from("<H", buf, pos)[0]
        pos += 2
    asian_sz = 0
    if has_asian:
        asian_sz = struct.unpack_from("<I", buf, pos)[0]
        pos += 4

    chars_left = cch
    out_parts: List[str] = []
    bound_idx = 0
    if chunks_bounds:
        while bound_idx < len(chunks_bounds) and chunks_bounds[bound_idx] <= pos:
            bound_idx += 1

    while chars_left > 0 and pos < len(buf):
        next_bound = chunks_bounds[bound_idx] if (chunks_bounds and bound_idx < len(chunks_bounds)) else len(buf)
        avail_bytes = next_bound - pos
        if avail_bytes <= 0:
            # Crossed into CONTINUE record: first byte in CONTINUE is compression flag!
            if bound_idx < len(chunks_bounds or []):
                is_utf16 = bool(buf[pos] & 0x01)
                pos += 1
                bound_idx += 1
            continue

        step = 2 if is_utf16 else 1
        take_chars = min(chars_left, avail_bytes // step)
        if take_chars == 0:
            break
        raw_slice = buf[pos:pos + take_chars * step]
        out_parts.append(raw_slice.decode("utf-16-le" if is_utf16 else "latin-1", errors="replace"))
        pos += take_chars * step
        chars_left -= take_chars

    pos += rt_runs * 4 + asian_sz
    return "".join(out_parts), pos


def _parse_biff8_xls(data: bytes) -> List[Tuple[str, List[List[Any]]]]:
    stream = _extract_ole2_workbook_stream(data)

    # First pass over workbook globals to collect BOUNDSHEETs and SST
    pos = 0
    sheets_meta: List[Tuple[int, str]] = []
    sst: List[str] = []

    while pos + 4 <= len(stream):
        rec_id, rec_len = struct.unpack_from("<HH", stream, pos)
        payload_start = pos + 4
        payload_end = payload_start + rec_len
        payload = stream[payload_start:payload_end]
        pos = payload_end

        if rec_id == 0x0085:  # BOUNDSHEET
            sheet_offset = struct.unpack_from("<I", payload, 0)[0]
            sheet_name, _ = _read_biff8_unicode_string(payload, 6, cch_bytes=1)
            sheets_meta.append((sheet_offset, sheet_name))
        elif rec_id == 0x00FC:  # SST (may span CONTINUE records 0x003C)
            sst_chunks = [payload]
            chunk_bounds = []
            running_len = len(payload)
            while pos + 4 <= len(stream):
                next_id, next_len = struct.unpack_from("<HH", stream, pos)
                if next_id != 0x003C:
                    break
                chunk_bounds.append(running_len)
                chunk_data = stream[pos + 4:pos + 4 + next_len]
                sst_chunks.append(chunk_data)
                running_len += next_len
                pos += 4 + next_len

            sst_buf = b"".join(sst_chunks)
            total_unique = struct.unpack_from("<I", sst_buf, 4)[0]
            s_pos = 8
            for _ in range(total_unique):
                if s_pos >= len(sst_buf):
                    break
                text, s_pos = _read_biff8_unicode_string(sst_buf, s_pos, chunks_bounds=chunk_bounds, cch_bytes=2)
                sst.append(text)
        elif rec_id == 0x000A:  # EOF of workbook globals
            break

    # Second pass: read each worksheet substream
    results: List[Tuple[str, List[List[Any]]]] = []
    for sheet_offset, sheet_name in sheets_meta:
        s_pos = sheet_offset
        grid: Dict[int, Dict[int, Any]] = {}
        max_col = 0
        last_formula_coord: Optional[Tuple[int, int]] = None

        while s_pos + 4 <= len(stream):
            rec_id, rec_len = struct.unpack_from("<HH", stream, s_pos)
            payload = stream[s_pos + 4:s_pos + 4 + rec_len]
            s_pos += 4 + rec_len

            if rec_id == 0x000A:  # EOF
                break

            if rec_id == 0x00FD and len(payload) >= 10:  # LABELSST
                r, c, _, sst_idx = struct.unpack_from("<HHHI", payload, 0)
                val = sst[sst_idx] if 0 <= sst_idx < len(sst) else ""
                grid.setdefault(r, {})[c] = val
                max_col = max(max_col, c)
            elif rec_id == 0x0204 and len(payload) >= 8:  # LABEL
                r, c, _ = struct.unpack_from("<HHH", payload, 0)
                val, _ = _read_biff8_unicode_string(payload, 6, cch_bytes=2)
                grid.setdefault(r, {})[c] = val
                max_col = max(max_col, c)
            elif rec_id == 0x0203 and len(payload) >= 14:  # NUMBER
                r, c, _ = struct.unpack_from("<HHH", payload, 0)
                num = struct.unpack_from("<d", payload, 6)[0]
                val = int(num) if num.is_integer() else num
                grid.setdefault(r, {})[c] = val
                max_col = max(max_col, c)
            elif rec_id == 0x027E and len(payload) >= 10:  # RK
                r, c, _, rk_val = struct.unpack_from("<HHHI", payload, 0)
                grid.setdefault(r, {})[c] = _decode_rk(rk_val)
                max_col = max(max_col, c)
            elif rec_id == 0x00BD and len(payload) >= 6:  # MULRK
                r, col_first = struct.unpack_from("<HH", payload, 0)
                n_rk = (len(payload) - 6) // 6
                for i in range(n_rk):
                    c = col_first + i
                    _, rk_val = struct.unpack_from("<HI", payload, 4 + i * 6)
                    grid.setdefault(r, {})[c] = _decode_rk(rk_val)
                    max_col = max(max_col, c)
            elif rec_id == 0x0205 and len(payload) >= 8:  # BOOLERR
                r, c, _, bval, is_err = struct.unpack_from("<HHHBB", payload, 0)
                if not is_err:
                    grid.setdefault(r, {})[c] = bool(bval)
                    max_col = max(max_col, c)
            elif rec_id == 0x0006 and len(payload) >= 14:  # FORMULA
                r, c, _ = struct.unpack_from("<HHH", payload, 0)
                last_formula_coord = (r, c)
                # Bytes 6..14 store cached result; if bytes 12..14 != 0xFFFF it's IEEE754 float
                if payload[12:14] != b"\xFF\xFF":
                    num = struct.unpack_from("<d", payload, 6)[0]
                    grid.setdefault(r, {})[c] = int(num) if num.is_integer() else num
                    max_col = max(max_col, c)
            elif rec_id == 0x0207 and last_formula_coord is not None:  # STRING (formula string result)
                r, c = last_formula_coord
                text, _ = _read_biff8_unicode_string(payload, 0, cch_bytes=2)
                grid.setdefault(r, {})[c] = text
                max_col = max(max_col, c)
                last_formula_coord = None

        if grid:
            dense_rows = []
            for r_idx in sorted(grid.keys()):
                row_map = grid[r_idx]
                row_vals = [row_map.get(c_idx, None) for c_idx in range(max_col + 1)]
                if any(v is not None and str(v).strip() != "" for v in row_vals):
                    dense_rows.append(row_vals)
            if dense_rows:
                results.append((sheet_name, dense_rows))

    return results


def _parse_xls_bytes(data: bytes) -> List[Tuple[str, List[List[Any]]]]:
    # 1. Try xlrd if installed
    try:
        import xlrd
        wb = xlrd.open_workbook(file_contents=data)
        sheets: List[Tuple[str, List[List[Any]]]] = []
        for sheet in wb.sheets():
            rows = []
            for r_idx in range(sheet.nrows):
                row_vals = []
                for c_idx in range(sheet.ncols):
                    cell = sheet.cell(r_idx, c_idx)
                    if cell.ctype == xlrd.XL_CELL_DATE:
                        dt_tuple = xlrd.xldate_as_tuple(cell.value, wb.datemode)
                        row_vals.append(f"{dt_tuple[0]:04d}-{dt_tuple[1]:02d}-{dt_tuple[2]:02d}")
                    elif cell.ctype == xlrd.XL_CELL_NUMBER and float(cell.value).is_integer():
                        row_vals.append(int(cell.value))
                    else:
                        row_vals.append(cell.value)
                if any(v is not None and str(v).strip() != "" for v in row_vals):
                    rows.append(row_vals)
            if rows:
                sheets.append((sheet.name, rows))
        return sheets
    except ImportError:
        pass

    # 2. Check if .xls is actually an XLSX ZIP archive
    if data[:4] == b"PK\x03\x04":
        return _parse_xlsx_bytes(data)

    # 3. Check if .xls is XML Spreadsheet 2003 or HTML table export
    head_lower = data[:512].lstrip().lower()
    if head_lower.startswith(b"<?xml") or b"<workbook" in head_lower:
        root = ET.fromstring(data.decode("utf-8", errors="replace"))
        sheets = []
        for ws in root.iter():
            if ws.tag.endswith("}Worksheet") or ws.tag == "Worksheet":
                s_name = ws.attrib.get("{urn:schemas-microsoft-com:office:spreadsheet}Name") or ws.attrib.get("Name") or f"Sheet{len(sheets)+1}"
                rows = []
                for row_el in ws.iter():
                    if row_el.tag.endswith("}Row") or row_el.tag == "Row":
                        row_vals = []
                        for cell_el in list(row_el):
                            if cell_el.tag.endswith("}Cell") or cell_el.tag == "Cell":
                                data_text = None
                                for d in list(cell_el):
                                    if d.tag.endswith("}Data") or d.tag == "Data":
                                        data_text = d.text
                                row_vals.append(data_text)
                        if any(v is not None and str(v).strip() != "" for v in row_vals):
                            rows.append(row_vals)
                if rows:
                    sheets.append((s_name, rows))
        return sheets

    if b"<table" in data[:4096].lower():
        parser = _HTMLTableParser()
        parser.feed(data.decode("utf-8", errors="replace"))
        return [(f"sheet_{i+1}", tbl) for i, tbl in enumerate(parser.tables)]

    # 4. Binary OLE2 + BIFF8 .xls
    return _parse_biff8_xls(data)


# =====================================================================
# Type Inference & SQLite Ingestion
# =====================================================================

_CURRENCY_RE = re.compile(r"^-?\s*[\$€£₹¥]?\s*\d+(?:,\d{3})*(?:\.\d+)?$")


def _strip_currency_symbols(s: str) -> str:
    for sym in ("$", "€", "£", "₹", "¥", ","):
        s = s.replace(sym, "")
    return s.strip()


def _coerce_value(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return raw
    if isinstance(raw, bool):
        return int(raw)
    s = str(raw).strip()
    if s == "":
        return None
    return s


def _infer_column_type(values: List[Any]) -> Tuple[str, bool]:
    """
    Infers SQLite column type ('INTEGER', 'REAL', 'TEXT') and whether numeric values
    have currency/comma formatting to strip.
    """
    non_null = [v for v in values if v is not None and str(v).strip() != ""]
    if not non_null:
        return "TEXT", False

    all_int = True
    all_float = True
    needs_currency_strip = False

    for v in non_null[:500]:
        if isinstance(v, int) and not isinstance(v, bool):
            continue
        if isinstance(v, float):
            all_int = False
            continue
        s = str(v).strip()
        # Preserve leading-zero numeric strings (e.g. ZIP codes '02139') as TEXT
        if len(s) > 1 and s[0] == "0" and s[1].isdigit():
            return "TEXT", False

        try:
            int(s)
            continue
        except ValueError:
            all_int = False

        try:
            float(s)
            continue
        except ValueError:
            pass

        if _CURRENCY_RE.match(s):
            needs_currency_strip = True
            clean_num = _strip_currency_symbols(s)
            try:
                float(clean_num)
                continue
            except ValueError:
                all_float = False
                break
        else:
            all_float = False
            break

    if all_int:
        return "INTEGER", False
    if all_float:
        return "REAL", needs_currency_strip
    return "TEXT", False


def _convert_cell(val: Any, col_type: str, strip_currency: bool) -> Any:
    if val is None:
        return None
    s = str(val).strip()
    if s == "":
        return None
    if col_type == "INTEGER":
        try:
            return int(float(s)) if isinstance(val, str) else int(val)
        except (ValueError, TypeError):
            return None
    if col_type == "REAL":
        if isinstance(val, (int, float)):
            return float(val)
        clean_s = _strip_currency_symbols(s) if strip_currency else s
        try:
            return float(clean_s)
        except ValueError:
            return None
    return s


class FileIngestor:
    @staticmethod
    def parse_file_to_tables(filename: str, content_bytes: bytes) -> List[Tuple[str, List[List[Any]]]]:
        ext = os.path.splitext(filename.lower())[1]
        base_name = os.path.splitext(os.path.basename(filename))[0]

        if ext in (".csv", ".tsv"):
            sheets = _parse_csv_bytes(content_bytes, ext)
            # Use filename as table name for single-table CSV/TSV
            return [(base_name, sheets[0][1])] if sheets else []
        elif ext == ".xlsx":
            sheets = _parse_xlsx_bytes(content_bytes)
            if len(sheets) == 1:
                return [(base_name, sheets[0][1])]
            return [(f"{base_name}_{s_name}", rows) for s_name, rows in sheets]
        elif ext == ".xls":
            sheets = _parse_xls_bytes(content_bytes)
            if len(sheets) == 1:
                return [(base_name, sheets[0][1])]
            return [(f"{base_name}_{s_name}", rows) for s_name, rows in sheets]
        else:
            raise ValueError(f"Unsupported file format '{ext}'. Please upload .csv, .tsv, .xls, or .xlsx files.")

    @staticmethod
    def ingest_files_to_sqlite(files: List[Tuple[str, bytes]], db_path: str) -> List[Dict[str, Any]]:
        """
        Parses one or more CSV/XLS/XLSX files and writes each table/sheet into
        a SQLite database at `db_path`.
        Returns summary metadata for each created table.
        """
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        if os.path.exists(db_path):
            os.remove(db_path)

        raw_tables: List[Tuple[str, List[List[Any]]]] = []
        for fname, content in files:
            parsed = FileIngestor.parse_file_to_tables(fname, content)
            raw_tables.extend(parsed)

        if not raw_tables:
            raise ValueError("No non-empty tables or rows found in the uploaded file(s).")

        sanitized_table_names = deduplicate_names([
            sanitize_identifier(name, prefix="tbl", fallback="uploaded_table")
            for name, _ in raw_tables
        ])

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        ingested_summary: List[Dict[str, Any]] = []

        try:
            for tbl_name, rows in zip(sanitized_table_names, [r for _, r in raw_tables]):
                if not rows:
                    continue

                headers_raw = rows[0]
                data_rows = rows[1:] if len(rows) > 1 else []

                # Determine max width across header and data
                max_cols = max(len(headers_raw), max((len(r) for r in data_rows), default=0))
                padded_headers = [
                    str(headers_raw[i]).strip() if i < len(headers_raw) and headers_raw[i] is not None else f"column_{i+1}"
                    for i in range(max_cols)
                ]
                col_names = deduplicate_names([
                    sanitize_identifier(h, prefix="col", fallback=f"column_{idx+1}")
                    for idx, h in enumerate(padded_headers)
                ])

                # Infer column types
                col_specs: List[Tuple[str, str, bool]] = []
                for c_idx, c_name in enumerate(col_names):
                    col_vals = [_coerce_value(r[c_idx]) if c_idx < len(r) else None for r in data_rows]
                    c_type, strip_curr = _infer_column_type(col_vals)
                    col_specs.append((c_name, c_type, strip_curr))

                # Create table
                col_defs = ", ".join(f'"{c_name}" {c_type}' for c_name, c_type, _ in col_specs)
                cur.execute(f'CREATE TABLE "{tbl_name}" ({col_defs})')

                # Batch insert rows
                if data_rows:
                    placeholders = ", ".join("?" for _ in col_specs)
                    insert_sql = f'INSERT INTO "{tbl_name}" VALUES ({placeholders})'
                    batch = []
                    for r in data_rows:
                        converted_row = tuple(
                            _convert_cell(r[i] if i < len(r) else None, c_type, strip_curr)
                            for i, (_, c_type, strip_curr) in enumerate(col_specs)
                        )
                        batch.append(converted_row)
                    cur.executemany(insert_sql, batch)

                ingested_summary.append({
                    "table_name": tbl_name,
                    "row_count": len(data_rows),
                    "columns": [{"name": cn, "type": ct} for cn, ct, _ in col_specs],
                })

            conn.commit()
        finally:
            conn.close()

        return ingested_summary


file_ingestor = FileIngestor()

