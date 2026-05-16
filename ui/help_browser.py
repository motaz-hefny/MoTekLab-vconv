"""
Help Browser - Searchable help system for vconv
Supports English (en) and Arabic (ar) with RTL layout
"""
import os
import re
from pathlib import Path
from markdown import markdown

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QTextBrowser, QLineEdit,
    QPushButton, QLabel, QComboBox
)
from PyQt6.QtCore import Qt


HELP_FILES = {
    'en': 'user_guide.md',
    'ar': 'user_guide.ar.md',
}

LANG_NAMES = {
    'en': 'English',
    'ar': 'العربية',
}


def _heading_id(heading_text):
    """Generate heading ID matching the markdown toc extension."""
    text = heading_text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s-]+', '-', text).strip('-')
    return text


def _parse_headings(markdown_text):
    """Parse markdown headings into structured list, skipping code blocks and HTML.

    Handles:
      - Fenced code blocks (```)
      - HTML blocks
      - Lines that look like headings but are in code context
    """
    headings = []
    in_code_block = False
    for line in markdown_text.split('\n'):
        if line.lstrip().startswith('```'):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        # Skip empty lines, horizontal rules, HTML
        if not line.strip() or line.strip().startswith(('<', '---', '___', '===')):
            continue
        # Match headings: optional leading whitespace, then # characters
        match = re.match(r'^(\#{1,6})\s+(.+?)(?:\s+\{#(\S+)\})?$', line)
        if match:
            level = len(match.group(1))
            text = match.group(2).strip()
            anchor = _heading_id(text)
            headings.append((level, text, anchor))
    return headings


def _build_toc_tree(headings):
    """Build nested structure from headings for tree widget."""
    categories = []
    current_cat = None
    current_cat_anchor = None
    current_topics = []
    skip_anchors = {'table-of-contents', 'vconv-user-guide'}

    for level, text, anchor in headings:
        if level == 1 or anchor in skip_anchors:
            continue
        if level == 2:
            if current_cat and current_topics:
                categories.append((current_cat, current_topics))
            current_cat = text
            current_cat_anchor = anchor
            current_topics = []
        else:
            if current_cat:
                current_topics.append((text, anchor))

    if current_cat:
        if not current_topics and current_cat_anchor:
            current_topics = [(current_cat, current_cat_anchor)]
        if current_topics:
            categories.append((current_cat, current_topics))
    return categories


def _inject_heading_ids(html, headings):
    """Inject id attributes into HTML headings by matching exact heading text.
    
    Handles HTML escaping (& -> &amp;) so non-ASCII headings
    (Arabic, Chinese, etc.) work correctly.
    """
    def _esc(text):
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    result = html
    for level, text, anchor in headings:
        escaped = _esc(text)
        old = f'<h{level}>{escaped}</h{level}>'
        new = f'<h{level} id="{anchor}">{escaped}</h{level}>'
        result = result.replace(old, new, 1)
    return result


class HelpBrowser(QDialog):
    """Searchable help browser with dynamic topic index and language support."""

    def __init__(self, parent=None, lang='en'):
        super().__init__(parent)
        self.current_lang = lang if lang in HELP_FILES else 'en'
        self.headings = []
        self.toc_structure = []
        self.html_content = ""
        self.setWindowTitle(self._tr("vconv Help"))
        self.setMinimumSize(850, 580)
        self.resize(950, 650)
        self._setup_ui()
        self._load_help_content()

    def _tr(self, text_en, text_ar=None):
        """Simple translation for UI elements."""
        if self.current_lang == 'ar' and text_ar:
            return text_ar
        return text_en

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        top_layout = QHBoxLayout()

        top_layout.addWidget(QLabel(self._tr("🔍 Search:", "🔍 بحث:")))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self._tr("Type to search help topics...", "اكتب للبحث في مواضيع المساعدة..."))
        self.search_input.textChanged.connect(self._filter_topics)
        top_layout.addWidget(self.search_input)
        clear_btn = QPushButton("✕")
        clear_btn.setMaximumWidth(30)
        clear_btn.clicked.connect(self.search_input.clear)
        top_layout.addWidget(clear_btn)

        top_layout.addStretch()
        top_layout.addWidget(QLabel(self._tr("Language:", "اللغة:")))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("English", 'en')
        self.lang_combo.addItem("العربية", 'ar')
        self.lang_combo.setCurrentIndex(0 if self.current_lang == 'en' else 1)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        top_layout.addWidget(self.lang_combo)

        layout.addLayout(top_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(220)
        self.tree.setMaximumWidth(350)
        self.tree.itemClicked.connect(self._on_topic_selected)
        splitter.addWidget(self.tree)

        self.content = QTextBrowser()
        self.content.setOpenExternalLinks(True)
        self.content.setMinimumWidth(450)
        splitter.addWidget(self.content)

        splitter.setSizes([260, 690])
        layout.addWidget(splitter)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        home_btn = QPushButton(self._tr("🏠 Top", "🏠 أعلى"))
        home_btn.clicked.connect(lambda: self._scroll_to(self._first_anchor()))
        btn_layout.addWidget(home_btn)
        back_btn = QPushButton(self._tr("◀ Back", "◀ رجوع"))
        back_btn.clicked.connect(self.content.backward)
        btn_layout.addWidget(back_btn)
        fwd_btn = QPushButton(self._tr("▶ Forward", "▶ تقدم"))
        fwd_btn.clicked.connect(self.content.forward)
        btn_layout.addWidget(fwd_btn)
        close_btn = QPushButton(self._tr("Close", "إغلاق"))
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _on_language_changed(self, idx):
        lang = self.lang_combo.itemData(idx)
        if lang and lang != self.current_lang:
            self.current_lang = lang
            self._apply_language()

    def _apply_language(self):
        is_ar = self.current_lang == 'ar'
        self.setWindowTitle(self._tr("vconv Help", "مساعدة vconv"))
        self.search_input.setPlaceholderText(self._tr("Type to search...", "اكتب للبحث..."))
        self._load_help_content()

        # RTL support for Arabic
        if is_ar:
            self.content.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            self.tree.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            self.search_input.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        else:
            self.content.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            self.tree.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            self.search_input.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

    def _first_anchor(self):
        for h in self.headings:
            if len(h) >= 3 and h[2]:
                return h[2]
        return None

    def _get_doc_path(self):
        filename = HELP_FILES.get(self.current_lang, 'user_guide.md')
        path = Path(__file__).parent.parent / 'docs' / filename
        if not path.exists():
            path = Path(__file__).parent.parent / 'docs' / 'user_guide.md'
        return path

    def _load_help_content(self):
        doc_path = self._get_doc_path()
        if not doc_path.exists():
            self.content.setHtml(
                "<h1>" + self._tr("Help File Not Found", "ملف المساعدة غير موجود") + "</h1>"
                "<p>" + self._tr("Please reinstall vconv.", "الرجاء إعادة تثبيت vconv.") + "</p>"
            )
            return

        try:
            raw = doc_path.read_text(encoding='utf-8')
            self.headings = _parse_headings(raw)
            self.toc_structure = _build_toc_tree(self.headings)

            html = markdown(raw, extensions=['tables', 'fenced_code'])
            html = _inject_heading_ids(html, self.headings)
            self.html_content = html

            self._populate_index()
            self.content.setHtml(self.html_content)
            self._scroll_to(self._first_anchor())
        except Exception as e:
            self.content.setHtml(
                f"<h1>" + self._tr("Error Loading Help", "خطأ في تحميل المساعدة") + "</h1>"
                f"<pre>{e}</pre>"
            )

    def _populate_index(self):
        self.tree.clear()
        for cat_name, topics in self.toc_structure:
            cat_item = QTreeWidgetItem([cat_name])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            cat_item.setExpanded(True)
            seen = set()
            for topic_name, anchor in topics:
                key = (topic_name, anchor)
                if key not in seen:
                    seen.add(key)
                    topic_item = QTreeWidgetItem([topic_name])
                    topic_item.setData(0, Qt.ItemDataRole.UserRole, anchor)
                    cat_item.addChild(topic_item)
            self.tree.addTopLevelItem(cat_item)

    def _on_topic_selected(self, item, column):
        anchor = item.data(0, Qt.ItemDataRole.UserRole)
        if anchor:
            self._scroll_to(anchor)

    def _scroll_to(self, anchor_id):
        if not anchor_id:
            return
        self.content.scrollToAnchor(anchor_id)

    def _filter_topics(self, text):
        text = text.lower().strip()
        for i in range(self.tree.topLevelItemCount()):
            cat_item = self.tree.topLevelItem(i)
            has_visible = False
            for j in range(cat_item.childCount()):
                topic_item = cat_item.child(j)
                visible = not text or text in topic_item.text(0).lower()
                topic_item.setHidden(not visible)
                if visible:
                    has_visible = True
            cat_item.setHidden(not has_visible)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        super().keyPressEvent(event)


def open_help(parent=None, lang='en'):
    dlg = HelpBrowser(parent, lang)
    dlg.exec()