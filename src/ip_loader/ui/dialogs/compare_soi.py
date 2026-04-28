import re
from PySide6.QtCore import QFile
from PySide6.QtGui import QPalette
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QApplication

from .base import VIEWS_DIR

import re
import html as html_mod
import difflib
from bs4 import BeautifulSoup, Comment

SECTION_MARKER = '§§SECTION§§'
MAX_CHARS = 120
import difflib
from html import escape
from PySide6.QtWidgets import (
    QTableWidgetItem, QHeaderView, QListWidgetItem, QDialogButtonBox,
    QFileDialog, QMessageBox, QWidget, QApplication
)
from PySide6.QtGui import QPainter, QColor, QPalette
from PySide6.QtCore import QFile, Qt
from PySide6.QtUiTools import QUiLoader


class DiffRuler(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(12)
        self.changes = []
        self.total_lines = 1

    def update_data(self, changes, total_lines):
        self.changes = changes
        self.total_lines = max(1, total_lines)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        # Check theme to set the track background color
        is_dark = self.palette().color(QPalette.WindowText).lightness() > self.palette().color(
            QPalette.Window).lightness()
        bg_color = QColor("#2b2b2b") if is_dark else QColor("#f0f0f0")
        painter.fillRect(self.rect(), bg_color)

        h = self.height()
        for change_type, line_idx in self.changes:
            y = int((line_idx / self.total_lines) * h)

            if change_type == 'delete':
                color = QColor("#ef9a9a")
            elif change_type == 'insert':
                color = QColor("#a5d6a7")
            else:
                color = QColor("#ffcc80")

            painter.fillRect(0, y, self.width(), 4, color)

def _strip_html(raw):
    if not raw:
        return []
    soup = BeautifulSoup(raw, features='lxml')

    for el in soup(["script", "style", "meta", "link"]):
        el.decompose()
    for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()
    for rev in soup.find_all("revisionhistory"):
        rev.decompose()
    for el in soup.find_all(id=re.compile(r'_test', re.IGNORECASE)):
        el.decompose()
    for el in soup.find_all(style=True):
        if re.search(r'display\s*:\s*none', el.get('style', ''), re.IGNORECASE):
            el.decompose()

    for el in soup.find_all(class_='OperHeader'):
        title = el.get_text(strip=True)
        el.replace_with(soup.new_string(f'\n{SECTION_MARKER}{title}\n'))

    SQL_PAT = re.compile(
        r'^\s*(SELECT|INSERT|UPDATE|DELETE|EXEC|EXECUTE|CREATE|DROP|ALTER|FROM|WHERE|JOIN|UNION)\b',
        re.IGNORECASE
    )

    text = soup.get_text(separator='\n')
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(SECTION_MARKER):
            lines.append(line)
        elif SQL_PAT.match(line):
            continue
        elif re.match(r'Results\s+for\s+\w+\s*:', line, re.IGNORECASE):
            continue
        else:
            lines.append(line)
    return lines


def _split_sections(lines):
    sections, cur_title, cur_lines = [], None, []
    for line in lines:
        if line.startswith(SECTION_MARKER):
            sections.append((cur_title, cur_lines))
            cur_title = line[len(SECTION_MARKER):]
            cur_lines = []
        else:
            cur_lines.append(line)
    sections.append((cur_title, cur_lines))
    return sections


def _build_html(rows, title, is_dark):
    if is_dark:
        bg, fg, border  = '#1e1e1e', '#d4d4d4', '#3c3c3c'
        del_bg, del_fg  = '#3d1515', '#f97583'
        ins_bg, ins_fg  = '#0d2b0d', '#85e89d'
        blank_bg        = '#252526'
        hdr_bg, hdr_fg  = '#252526', '#9e9e9e'
        ln_fg           = '#5a5a5a'
        sec_bg, sec_fg  = '#1c3a6b', '#90caff'
        sec_border      = '#2d5fa6'
    else:
        bg, fg, border  = '#ffffff', '#1f2328', '#e0e0e0'
        del_bg, del_fg  = '#ffebe9', '#cf222e'
        ins_bg, ins_fg  = '#e6ffec', '#1a7f37'
        blank_bg        = '#f6f8fa'
        hdr_bg, hdr_fg  = '#f6f8fa', '#57606a'
        ln_fg           = '#b0b0b0'
        sec_bg, sec_fg  = '#dbeafe', '#1e40af'
        sec_border      = '#93c5fd'

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    line-height: 18px;
    background: {bg};
    color: {fg};
  }}
  .hdr {{
    padding: 4px 10px;
    background: {hdr_bg};
    color: {hdr_fg};
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 12px;
    font-weight: bold;
    border-bottom: 1px solid {border};
  }}
  table {{ width: 100%; border-collapse: collapse; }}
  tr {{ height: 18px; }}
  td {{ vertical-align: top; }}
  td.ln {{
    width: 44px;
    min-width: 44px;
    text-align: right;
    padding: 0 6px;
    color: {ln_fg};
    border-right: 1px solid {border};
    white-space: nowrap;
    line-height: 18px;
  }}
  td.code {{
    padding: 0 8px;
    white-space: pre;
    overflow: hidden;
    line-height: 18px;
  }}
  .del   {{ background: {del_bg}; color: {del_fg}; }}
  .ins   {{ background: {ins_bg}; color: {ins_fg}; }}
  .blank {{ background: {blank_bg}; }}
  tr.section-row td {{
    background: {sec_bg};
    color: {sec_fg};
    font-family: 'Segoe UI', Arial, sans-serif;
    font-weight: bold;
    font-size: 11.5px;
    padding: 3px 8px;
    height: 22px;
    line-height: 22px;
    border-top: 2px solid {sec_border};
border-bottom: 1px solid {sec_border};
  }}
  tr.sec-del td {{
    background: {del_bg};
    color: {del_fg};
    font-family: 'Segoe UI', Arial, sans-serif;
    font-weight: bold;
    font-size: 11.5px;
    padding: 3px 8px;
    height: 22px;
    line-height: 22px;
    border-top: 2px solid {del_fg};
    border-bottom: 1px solid {del_fg};
  }}
  tr.sec-ins td {{
    background: {ins_bg};
    color: {ins_fg};
    font-family: 'Segoe UI', Arial, sans-serif;
    font-weight: bold;
    font-size: 11.5px;
    padding: 3px 8px;
    height: 22px;
    line-height: 22px;
    border-top: 2px solid {ins_fg};
    border-bottom: 1px solid {ins_fg};
  }}
  tr.sec-blank td {{
    background: {blank_bg};
    height: 22px;
    border-top: 2px solid {border};
    border-bottom: 1px solid {border};
  }}
</style></head><body>
  <div class="hdr">{html_mod.escape(title)}</div>
  <table><tbody>
    {''.join(rows)}
  </tbody></table>
</body></html>"""


def generate_aligned_html_diff(source_raw, target_raw, is_dark=False):
    src_sections = _split_sections(_strip_html(source_raw))
    tgt_sections = _split_sections(_strip_html(target_raw))

    src_titles = [s[0] for s in src_sections]
    tgt_titles = [t[0] for t in tgt_sections]

    left_rows, right_rows = [], []
    changes = []
    line_idx = src_ln = tgt_ln = 0

    def c_row(ln, text, cls):
        ln_s = str(ln) if ln else ''
        if text and len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + '…'
        code = html_mod.escape(text) if text else '&nbsp;'
        return f'<tr><td class="ln">{ln_s}</td><td class="code {cls}">{code}</td></tr>\n'

    def blank_row():
        return '<tr><td class="ln"></td><td class="code blank">&nbsp;</td></tr>\n'

    def sec_row(title, cls='section-row'):
        esc = html_mod.escape(title) if title else '&nbsp;'
        return f'<tr class="{cls}"><td colspan="2">{esc}</td></tr>\n'

    def diff_section_lines(src_lines, tgt_lines):
        nonlocal line_idx, src_ln, tgt_ln
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(
                None, src_lines, tgt_lines, autojunk=False).get_opcodes():
            if op == 'equal':
                for i in range(i2 - i1):
                    src_ln += 1; tgt_ln += 1
                    left_rows.append(c_row(src_ln, src_lines[i1+i], ''))
                    right_rows.append(c_row(tgt_ln, tgt_lines[j1+i], ''))
                    line_idx += 1
            elif op == 'delete':
                for i in range(i2 - i1):
                    src_ln += 1
                    left_rows.append(c_row(src_ln, src_lines[i1+i], 'del'))
                    right_rows.append(blank_row())
                    changes.append(('delete', line_idx)); line_idx += 1
            elif op == 'insert':
                for i in range(j2 - j1):
                    tgt_ln += 1
                    left_rows.append(blank_row())
                    right_rows.append(c_row(tgt_ln, tgt_lines[j1+i], 'ins'))
                    changes.append(('insert', line_idx)); line_idx += 1
            elif op == 'replace':
                lc, rc = src_lines[i1:i2], tgt_lines[j1:j2]
                for i in range(max(len(lc), len(rc))):
                    if i < len(lc):
                        src_ln += 1
                        left_rows.append(c_row(src_ln, lc[i], 'del'))
                    else:
                        left_rows.append(blank_row())
                    if i < len(rc):
                        tgt_ln += 1
                        right_rows.append(c_row(tgt_ln, rc[i], 'ins'))
                    else:
                        right_rows.append(blank_row())
                    changes.append(('replace', line_idx)); line_idx += 1
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(
            None, src_titles, tgt_titles, autojunk=False).get_opcodes():

        if op == 'equal':
            for k in range(i2 - i1):
                src_s, tgt_s = src_sections[i1+k], tgt_sections[j1+k]
                if src_s[0] is not None:
                    left_rows.append(sec_row(src_s[0]))
                    right_rows.append(sec_row(tgt_s[0]))
                    line_idx += 1
                diff_section_lines(src_s[1], tgt_s[1])

        elif op == 'delete':
            for k in range(i2 - i1):
                src_s = src_sections[i1+k]
                if src_s[0] is not None:
                    left_rows.append(sec_row(src_s[0], 'sec-del'))
                    right_rows.append(sec_row('', 'sec-blank'))
                    line_idx += 1
                for line in src_s[1]:
                    src_ln += 1
                    left_rows.append(c_row(src_ln, line, 'del'))
                    right_rows.append(blank_row())
                    changes.append(('delete', line_idx)); line_idx += 1

        elif op == 'insert':
            for k in range(j2 - j1):
                tgt_s = tgt_sections[j1+k]
                if tgt_s[0] is not None:
                    left_rows.append(sec_row('', 'sec-blank'))
                    right_rows.append(sec_row(tgt_s[0], 'sec-ins'))
                    line_idx += 1
                for line in tgt_s[1]:
                    tgt_ln += 1
                    left_rows.append(blank_row())
                    right_rows.append(c_row(tgt_ln, line, 'ins'))
                    changes.append(('insert', line_idx)); line_idx += 1

        elif op == 'replace':
            for k in range(max(i2-i1, j2-j1)):
                has_src = k < (i2-i1)
                has_tgt = k < (j2-j1)
                src_s = src_sections[i1+k] if has_src else (None, [])
                tgt_s = tgt_sections[j1+k] if has_tgt else (None, [])
                left_rows.append(sec_row(src_s[0] or '', 'sec-del' if has_src else 'sec-blank'))
                right_rows.append(sec_row(tgt_s[0] or '', 'sec-ins' if has_tgt else 'sec-blank'))
                line_idx += 1
                diff_section_lines(src_s[1], tgt_s[1])

    left_html  = _build_html(left_rows,  'Source', is_dark)
    right_html = _build_html(right_rows, 'Target', is_dark)
    return left_html, right_html, changes, max(line_idx, 1)


class CompareSoiDialogController:
    def __init__(self, loaded_ips, project_mgr, parent=None):
        self.project_mgr = project_mgr

        loader = QUiLoader()
        ui_path = VIEWS_DIR / "compare_soi_dialog.ui"
        ui_file = QFile(str(ui_path))
        ui_file.open(QFile.ReadOnly)
        self.dialog = loader.load(ui_file, parent)
        ui_file.close()

        self.ruler = DiffRuler(self.dialog)
        self.dialog.horizontalSplitter.addWidget(self.ruler)

        # Prevent the user from resizing the ruler
        self.dialog.horizontalSplitter.setStretchFactor(0, 1)  # Left Text
        self.dialog.horizontalSplitter.setStretchFactor(1, 1)  # Right Text
        self.dialog.horizontalSplitter.setStretchFactor(2, 0)

        self.setup_ui(loaded_ips)
        self.connect_signals()

    def setup_ui(self, loaded_ips):
        self.dialog.comboSource.addItems(loaded_ips)
        self.dialog.comboTarget.addItems(loaded_ips)

        if len(loaded_ips) > 1:
            self.dialog.comboTarget.setCurrentIndex(1)

        self.dialog.verticalSplitter.setSizes([600, 200])

    def connect_signals(self):
        self.dialog.btnRunDiff.clicked.connect(self.run_diff)
        self.dialog.btnGenerateAi.clicked.connect(self.generate_ai_summary)

        # Synchronize the vertical scrolling of both rendered HTML pages
        scroll_source = self.dialog.textSource.verticalScrollBar()
        scroll_target = self.dialog.textTarget.verticalScrollBar()

        scroll_source.valueChanged.connect(scroll_target.setValue)
        scroll_target.valueChanged.connect(scroll_source.setValue)

    def fetch_soi_text(self, ip_ln):
        return self.project_mgr.get_soi_text(ip_ln)

    def run_diff(self):
        source_ip = self.dialog.comboSource.currentText()
        target_ip = self.dialog.comboTarget.currentText()

        if not source_ip or not target_ip:
            return

        source_text = self.fetch_soi_text(source_ip)
        target_text = self.fetch_soi_text(target_ip)

        if not source_text or not target_text:
            self.dialog.textSource.setHtml(
                "<h2>Error</h2><p>One of the SOI files is empty or could not be loaded.</p>"
            )
            return

        is_dark = (
                QApplication.palette().color(QPalette.WindowText).lightness()
                > QApplication.palette().color(QPalette.Window).lightness()
        )

        left_html, right_html, changes, total_lines = generate_aligned_html_diff(
            source_text, target_text, is_dark
        )

        self.dialog.textSource.setHtml(left_html)
        self.dialog.textTarget.setHtml(right_html)
        self.ruler.update_data(changes, total_lines)
        self.dialog.btnGenerateAi.setEnabled(True)

    def generate_ai_summary(self):
        self.dialog.btnGenerateAi.setEnabled(False)
        self.dialog.textAiSummary.setHtml("<i>Contacting LLM... Generating summary of changes...</i>")
        # TODO: Fire off the worker to handle the LLM API call

    def exec(self):
        return self.dialog.exec()
