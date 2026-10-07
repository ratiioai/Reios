"""
Turn uploaded files (Word, PDF, CSV, Excel) into MCQs or student rows.

Question documents are free-form, so parsing is heuristic. Every parsed question carries a
`problems` list and the console shows a review screen before anything is saved.

Recognised layout (all parts optional except the question and options):

    Section: Quantitative Aptitude
    1. What is 20% of 150?
    A) 20      B) 25      C) 30      D) 35          <- one per line, or several on one line
    Answer: C                                       <- or "Ans: (c)", "Correct: C", a "*" on the option,
    Explanation: 20/100 x 150 = 30                     or an "Answer key" list at the end ("1. C")
"""
import csv
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

LETTERS = "ABCDEFGH"
MAX_FILE_BYTES = 15 * 1024 * 1024
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class ParseError(ValueError):
    """The file could not be read at all (as opposed to individual questions being incomplete)."""


@dataclass
class Line:
    text: str
    list_key: Optional[Tuple[str, str]] = None  # (numId, level) for Word auto-numbered paragraphs


# ── Reading files into lines / rows ───────────────────────────────────────

def file_kind(filename: str) -> str:
    name = (filename or "").lower()
    for ext, kind in ((".docx", "docx"), (".pdf", "pdf"), (".csv", "csv"), (".xlsx", "xlsx"), (".txt", "txt")):
        if name.endswith(ext):
            return kind
    if name.endswith(".doc"):
        raise ParseError("Old .doc files can't be read. Open it in Word and save as .docx")
    if name.endswith(".xls"):
        raise ParseError("Old .xls files can't be read. Open it in Excel and save as .xlsx")
    raise ParseError("Upload a .docx, .pdf, .csv, .xlsx or .txt file")


def _docx_root(data: bytes):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return ET.fromstring(z.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError):
        raise ParseError("This doesn't look like a valid Word (.docx) file")


def _para_line(p) -> Line:
    text = "".join(
        (t.text or "") if t.tag == W + "t" else ("\t" if t.tag == W + "tab" else "\n")
        for t in p.iter() if t.tag in (W + "t", W + "tab", W + "br")
    )
    num = p.find(f"{W}pPr/{W}numPr")
    key = None
    if num is not None:
        nid = num.find(W + "numId")
        lvl = num.find(W + "ilvl")
        key = (nid.get(W + "val") if nid is not None else "0", lvl.get(W + "val") if lvl is not None else "0")
    else:
        # Numbering can also come from a list paragraph style ("List Number", "List Number 2", …)
        style = p.find(f"{W}pPr/{W}pStyle")
        val = style.get(W + "val") if style is not None else ""
        if re.match(r"(?i)list\s*(number|bullet|paragraph)", val or ""):
            key = ("style:" + val, "0")
    return Line(text, key)


def docx_lines(data: bytes) -> List[Line]:
    body = _docx_root(data).find(W + "body")
    out: List[Line] = []
    for el in body if body is not None else []:
        if el.tag == W + "p":
            line = _para_line(el)
            for i, part in enumerate(line.text.split("\n")):
                out.append(Line(part, line.list_key if i == 0 else None))
        elif el.tag == W + "tbl":
            for cell_p in el.iter(W + "p"):
                out.append(_para_line(cell_p))
    return out


def docx_table_rows(data: bytes) -> List[List[str]]:
    """First table in the document, as text cells."""
    body = _docx_root(data).find(W + "body")
    table = body.find(W + "tbl") if body is not None else None
    if table is None:
        raise ParseError("No table found in the Word file. Put the list in a table with a header row")
    rows = []
    for tr in table.iter(W + "tr"):
        rows.append([" ".join(_para_line(p).text for p in tc.iter(W + "p")).strip() for tc in tr.iter(W + "tc")])
    return rows


def pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        raise ParseError("This PDF couldn't be read")
    if len(text.strip()) < 20:
        raise ParseError("No text found in this PDF. It's probably a scanned image; "
                         "upload the original Word file instead")
    return text


def decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def _norm_header(h) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(h or "").strip().lower()).strip("_")


def table_rows(data: bytes, kind: str) -> List[Dict[str, str]]:
    """CSV / Excel / Word-table / PDF-table -> list of dicts keyed by normalised header."""
    if kind == "csv":
        grid = list(csv.reader(io.StringIO(decode_text(data))))
    elif kind == "xlsx":
        try:
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            grid = [["" if v is None else str(v) for v in row] for row in wb.worksheets[0].iter_rows(values_only=True)]
        except Exception:
            raise ParseError("This doesn't look like a valid Excel (.xlsx) file")
    elif kind == "docx":
        grid = docx_table_rows(data)
    elif kind == "pdf":
        # Cells in extracted PDF text are usually separated by 2+ spaces; good enough for simple lists.
        grid = [re.split(r"\s{2,}|\t|\s*\|\s*", ln.strip()) for ln in pdf_text(data).splitlines() if ln.strip()]
    else:
        raise ParseError("Upload a .csv, .xlsx, .docx or .pdf file")
    grid = [r for r in grid if any(str(c).strip() for c in r)]
    if not grid:
        raise ParseError("The file is empty")
    header = [_norm_header(h) for h in grid[0]]
    rows = []
    for r in grid[1:]:
        rows.append({header[i]: (str(r[i]).strip() if i < len(r) else "") for i in range(len(header)) if header[i]})
    return rows


# Students: accept the column names colleges actually use
STUDENT_ALIASES = {
    "roll_no": ["roll_no", "roll_number", "rollno", "roll", "username", "user_name", "hall_ticket",
                "hall_ticket_no", "htno", "reg_no", "registration_no", "register_no", "student_id", "id",
                "team_code", "team_id", "teamcode", "teamid", "team_no", "team_number"],
    "name": ["name", "student_name", "full_name", "candidate_name", "team_name", "teamname", "team"],
    "email": ["email", "email_id", "mail", "e_mail"],
    "phone": ["phone", "mobile", "phone_no", "mobile_no", "phone_number", "mobile_number", "contact"],
    "branch": ["branch", "department", "dept", "course"],
    "section": ["section", "sec", "class"],
    "batch_year": ["batch_year", "batch", "passing_year", "year_of_passing", "pass_out_year", "graduation_year"],
    "password": ["password", "pass", "pwd", "passcode"],
}


def student_rows(data: bytes, filename: str) -> List[Dict[str, str]]:
    kind = file_kind(filename)
    rows = table_rows(data, "csv" if kind == "txt" else kind)
    out = []
    for row in rows:
        mapped = {}
        for field_name, aliases in STUDENT_ALIASES.items():
            for a in aliases:
                if row.get(a):
                    mapped[field_name] = row[a]
                    break
        out.append(mapped)
    if rows and not any("roll_no" in r for r in out):
        raise ParseError("Couldn't find a roll number / username column. "
                         "Name the header 'roll_no' (or 'Roll Number', 'Username')")
    return out


# ── Question documents ────────────────────────────────────────────────────

Q_RE = re.compile(r"^\s*(?:Q(?:uestion)?\s*[.\-:]?\s*)?(\d{1,4})\s*[).:\-–]\s+(.*\S)\s*$", re.I)
QN_ONLY_RE = re.compile(r"^\s*Q(?:uestion)?\s*[.\-:]?\s*(\d{1,4})\s*[).:\-–]?\s*$", re.I)
OPT_RE = re.compile(r"^\s*\(?([A-Ha-h])\s*[).:\]]\s*(.*\S)\s*$")
INLINE_OPT_RE = re.compile(r"(?:^|\s)(\()?([A-Ha-h])([).\]])\s+")
ANS_RE = re.compile(r"^\s*(?:correct\s+(?:answer|option)s?|answers?|ans|key|solution\s+key)\s*[.:\-–=)]\s*(.+)$", re.I)
EXPL_RE = re.compile(r"^\s*(?:explanation|solution|reason|hint)\s*[.:\-–]\s*(.*)$", re.I)
SECTION_RE = re.compile(r"^\s*(?:section|part)\s*(?:[A-Z0-9]{1,3}\s*)?[:\-–]\s*(.+)$", re.I)
KEY_HEADING_RE = re.compile(r"^\s*(?:answer\s*keys?|answers|key)\s*[:\-–]?\s*$", re.I)
KEY_ITEM_RE = re.compile(r"(\d{1,4})\s*[).:\-–=]\s*\(?([A-Ha-h](?:\s*[,&/]\s*[A-Ha-h])*)\)?(?![A-Za-z])")
# "Set 1", "SET - 2", "Paper Set B: Quant" on a line of its own
SET_HEADING_RE = re.compile(r"^\s*(?:question\s+|paper\s+)?set\s*[-#:.]?\s*(\d{1,3}|[A-Za-z])\b\s*(?:[:\-–—)]\s*(.*))?$", re.I)
# "Section: General Knowledge – Set 1" / "(Set 1)" at the end of a section line
SET_SUFFIX_RE = re.compile(r"\s*[-–—,:(]\s*set\s*[-#]?\s*(\d{1,3}|[A-Za-z])\s*\)?\s*$", re.I)
CORRECT_MARK_RE = re.compile(r"\s*(?:\*|✓|✔|\(correct\)|\[correct\])\s*", re.I)


@dataclass
class ParsedQuestion:
    number: Optional[int]
    section: str
    question_text: str = ""
    options: List[str] = field(default_factory=list)
    correct_options: List[int] = field(default_factory=list)
    answer_raw: Optional[str] = None
    explanation: Optional[str] = None
    set_label: Optional[str] = None  # "Set 3" when one file holds several sets

    def to_dict(self, marks: float, negative_marks: float) -> dict:
        problems = []
        if not self.question_text.strip():
            problems.append("Question text is empty")
        if len(self.options) < 2:
            problems.append("Needs at least 2 options")
        if len(self.options) > 8:
            problems.append("More than 8 options")
        if not self.correct_options:
            problems.append("Correct answer not found" + (f" (read \"{self.answer_raw}\")" if self.answer_raw else ""))
        return {
            "number": self.number, "section": self.section, "question_text": self.question_text.strip(),
            "options": [o.strip() for o in self.options], "correct_options": sorted(set(self.correct_options)),
            "is_multi": len(set(self.correct_options)) > 1, "explanation": (self.explanation or "").strip() or None,
            "marks": marks, "negative_marks": negative_marks, "difficulty": "medium", "problems": problems,
            "set": self.set_label,
        }


def _resolve_answer(raw: str, options: List[str]) -> List[int]:
    v = re.sub(r"(?i)^options?\s*", "", raw.strip())
    v = re.sub(r"(?i)\s+and\s+", ",", v)
    m = re.match(r"^\(?[A-Ha-h]\)?(?:\s*[,&/]\s*\(?[A-Ha-h]\)?)*(?=$|[\s.:)\-–])", v)
    if m:
        picks = [LETTERS.index(c.upper()) for c in re.findall(r"[A-Ha-h]", m.group(0))]
        return [p for p in picks if p < max(len(options), 1)] or picks
    plain = re.sub(r"\s+", " ", v).strip().lower()
    for i, o in enumerate(options):
        if re.sub(r"\s+", " ", o).strip().lower() == plain:
            return [i]
    if re.fullmatch(r"[1-8]", plain) and int(plain) <= len(options):
        return [int(plain) - 1]
    return []


def _split_inline_options(text: str) -> Optional[List[Tuple[str, str]]]:
    """
    '(a) 20 (b) 25 (c) 30' -> [('a','20'), ...] when the line holds 2+ markers in order.
    Every marker must look the same ("B)" and "C." don't mix), so initials in an option such as
    "B) W. C. Bonnerjee" or "C) A. P. J. Abdul Kalam" stay one option.
    """
    marks = list(INLINE_OPT_RE.finditer(text))
    if len(marks) < 2:
        return None
    if len({(m.group(1) or "", m.group(3)) for m in marks}) != 1:
        return None
    letters = [m.group(2).upper() for m in marks]
    if letters != list(LETTERS[LETTERS.index(letters[0]):LETTERS.index(letters[0]) + len(letters)]):
        return None
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((m.group(2), text[m.end():end].strip()))
    if any(not body or re.fullmatch(r"[A-Za-z]\.", body) for _, body in out):
        return None  # an "option" that is just an initial means these weren't options
    return out


def parse_question_lines(lines: List[Line], default_section: str = "General", marks: float = 1.0,
                         negative_marks: float = 0.0) -> Tuple[List[dict], List[str]]:
    questions: List[ParsedQuestion] = []
    warnings: List[str] = []
    cur: Optional[ParsedQuestion] = None
    section = default_section
    current_set: Optional[str] = None
    key: Dict[Tuple[Optional[str], int], str] = {}  # (set, question number) -> letters
    in_key = False
    question_list_key = None  # Word list that numbers the questions, when numbering is automatic
    last = None  # "question" | "option" | "explanation": where continuation lines go

    def add_option(text: str):
        nonlocal last
        is_correct = bool(CORRECT_MARK_RE.search(text)) and (
            text.strip().startswith(("*", "✓", "✔")) or text.strip().endswith(("*", "✓", "✔"))
            or re.search(r"(?i)\(correct\)|\[correct\]", text))
        clean = CORRECT_MARK_RE.sub(" ", text).strip() if is_correct else text.strip()
        cur.options.append(clean)
        if is_correct:
            cur.correct_options.append(len(cur.options) - 1)
        last = "option"

    def start(number: Optional[int], text: str):
        nonlocal cur, last
        cur = ParsedQuestion(number=number, section=section, question_text=text, set_label=current_set)
        questions.append(cur)
        last = "question"

    for line in lines:
        t = line.text.replace(" ", " ").strip()
        if not t:
            continue

        if KEY_HEADING_RE.match(t):
            in_key = True
            continue
        if in_key and not SET_HEADING_RE.match(t) and not SECTION_RE.match(t):
            found = KEY_ITEM_RE.findall(t)
            # Only lines made of nothing but key entries ("1. B  2. C"); "1. A cat…" is a question
            if found and not re.search(r"[A-Za-z0-9]", KEY_ITEM_RE.sub("", t)):
                for num, letters in found:
                    key[(current_set, int(num))] = letters
                continue
            in_key = False  # key ended; fall through and read the line normally

        m = SET_HEADING_RE.match(t)
        if m and not Q_RE.match(t) and len(t) <= 80:
            current_set = f"Set {m.group(1).upper()}"
            if m.group(2) and m.group(2).strip():
                section = m.group(2).strip()[:64]
            last = None
            continue

        m = SECTION_RE.match(t)
        if m and not OPT_RE.match(t):
            text = m.group(1).strip()
            sm = SET_SUFFIX_RE.search(text)
            if sm:
                current_set = f"Set {sm.group(1).upper()}"
                text = text[:sm.start()].strip()
                last = None
            if text:
                section = text[:64]
            continue

        if cur is not None:
            m = ANS_RE.match(t)
            if m:
                cur.answer_raw = m.group(1).strip()
                picks = _resolve_answer(cur.answer_raw, cur.options)
                if picks:
                    cur.correct_options = picks
                last = "answer"
                continue
            m = EXPL_RE.match(t)
            if m:
                cur.explanation = m.group(1)
                last = "explanation"
                continue

        m = QN_ONLY_RE.match(t)
        if m:
            start(int(m.group(1)), "")
            continue
        m = Q_RE.match(t)
        if m:
            start(int(m.group(1)), m.group(2))
            continue

        inline = _split_inline_options(t) if cur is not None else None
        if inline and (last in ("question", "option")):
            for _, text in inline:
                add_option(text)
            continue

        m = OPT_RE.match(t)
        if m and cur is not None and last in ("question", "option"):
            add_option(m.group(2))
            continue

        # Word auto-numbering: the numbers and letters aren't in the text, only in list metadata
        if line.list_key is not None:
            # A new question: the first list item, one in the questions' own list, or one after
            # the previous question's answer. Anything else in a list is an option.
            if cur is None or line.list_key == question_list_key or last in ("answer", "explanation"):
                question_list_key = line.list_key
                start(len(questions) + 1, t)
            else:
                add_option(t)
            continue

        if cur is None:
            continue  # title / instructions before the first question
        if last == "question":
            cur.question_text += "\n" + t
        elif last == "option":
            cur.options[-1] += " " + t
        elif last == "explanation":
            cur.explanation = ((cur.explanation or "") + " " + t).strip()

    for q in questions:
        k = (q.set_label, q.number)
        if not q.correct_options and k in key:
            q.answer_raw = key[k]
            q.correct_options = _resolve_answer(key[k], q.options)

    if not questions:
        warnings.append("No questions were recognised. Number each question (1., 2., …) "
                        "and letter its options (A), B), …)")
    return [q.to_dict(marks, negative_marks) for q in questions], warnings


def questions_from_rows(rows: List[Dict[str, str]], default_section: str, marks: float,
                        negative_marks: float) -> List[dict]:
    """CSV / Excel with the same columns as the MCQ bank template."""
    out = []
    for i, row in enumerate(rows, start=1):
        options = []
        for letter in LETTERS.lower():
            v = row.get(f"option_{letter}") or row.get(letter)
            if not v:
                break
            options.append(v)
        q = ParsedQuestion(number=i, section=(row.get("section") or default_section)[:64],
                           question_text=row.get("question") or row.get("question_text") or "",
                           options=options, explanation=row.get("explanation") or None)
        raw = row.get("correct") or row.get("answer") or row.get("correct_answer") or ""
        q.answer_raw = raw or None
        q.correct_options = _resolve_answer(raw, options) if raw else []
        d = q.to_dict(float(row.get("marks") or marks), float(row.get("negative_marks") or negative_marks))
        if row.get("difficulty", "").lower() in ("easy", "medium", "hard"):
            d["difficulty"] = row["difficulty"].lower()
        if row.get("topic"):
            d["topic"] = row["topic"][:128]
        out.append(d)
    return out


def parse_question_file(data: bytes, filename: str, default_section: str = "General",
                        marks: float = 1.0, negative_marks: float = 0.0) -> Tuple[List[dict], List[str]]:
    if len(data) > MAX_FILE_BYTES:
        raise ParseError("File is larger than 15 MB")
    kind = file_kind(filename)
    if kind in ("csv", "xlsx"):
        rows = table_rows(data, kind)
        if rows and "question" not in rows[0] and "question_text" not in rows[0]:
            raise ParseError("The sheet needs a 'question' column (download the template for the full layout)")
        return questions_from_rows(rows, default_section, marks, negative_marks), []
    if kind == "docx":
        lines = docx_lines(data)
    elif kind == "pdf":
        lines = [Line(t) for t in pdf_text(data).splitlines()]
    else:
        lines = [Line(t) for t in decode_text(data).splitlines()]
    return parse_question_lines(lines, default_section, marks, negative_marks)
