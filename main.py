import sys
import os
import subprocess
import threading
import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QScrollArea, QGridLayout,
    QListWidget, QListWidgetItem, QFileDialog, QProgressBar,
    QMessageBox, QSizePolicy, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QObject
from PyQt5.QtGui import QPixmap, QFont

from scraper import ROMScraper, CONSOLES, EMULATORS

VLC_PATH = r"C:\Program Files\VideoLAN\VLC\vlc.exe"


# ── Worker de download ───────────────────────────────────────────────────────
class DownloadWorker(QObject):
    progress = pyqtSignal(int)
    status   = pyqtSignal(str)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, url, dest_path):
        super().__init__()
        self.url = url
        self.dest_path = dest_path

    def run(self):
        try:
            self.status.emit("Conectando...")
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(self.url, headers=headers, stream=True, timeout=30)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            self.status.emit("Baixando...")
            with open(self.dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            self.progress.emit(int(downloaded * 100 / total))
            self.status.emit("Concluído!")
            self.finished.emit(self.dest_path)
        except Exception as e:
            self.error.emit(str(e))


# ── Card de ROM ──────────────────────────────────────────────────────────────
class ROMCard(QFrame):
    download_clicked = pyqtSignal(dict)
    _img_ready       = pyqtSignal(bytes)   # emitido pela thread daemon → recebido na main thread

    def __init__(self, rom_data):
        super().__init__()
        self.rom_data = rom_data
        self._alive   = True
        self.setObjectName("rom_card")
        self.setFixedSize(220, 310)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setSpacing(6)

        # ── Capa ──
        self.cover = QLabel()
        self.cover.setFixedSize(220, 165)
        self.cover.setAlignment(Qt.AlignCenter)
        self.cover.setStyleSheet("background:#0a0a15; border-radius:14px 14px 0 0;")
        self.cover.setText("🎮")
        self.cover.setFont(QFont("Segoe UI Emoji", 36))
        layout.addWidget(self.cover)

        inner = QVBoxLayout()
        inner.setContentsMargins(10, 0, 10, 0)
        inner.setSpacing(4)

        console_label = QLabel(rom_data.get("console", ""))
        console_label.setObjectName("console_tag")
        console_label.setAlignment(Qt.AlignCenter)
        inner.addWidget(console_label)

        name_label = QLabel(rom_data["name"])
        name_label.setWordWrap(True)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        name_label.setMaximumHeight(48)
        inner.addWidget(name_label)

        self.dl_btn = QPushButton("⬇  Baixar ROM")
        self.dl_btn.setObjectName("download_btn")
        self.dl_btn.setCursor(Qt.PointingHandCursor)
        self.dl_btn.clicked.connect(lambda: self.download_clicked.emit(self.rom_data))
        inner.addWidget(self.dl_btn)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setMaximumHeight(6)
        inner.addWidget(self.progress)

        self.dl_status = QLabel("")
        self.dl_status.setAlignment(Qt.AlignCenter)
        self.dl_status.setStyleSheet("color:#9090b8; font-size:10px;")
        inner.addWidget(self.dl_status)

        layout.addLayout(inner)

        # Conecta sinal de imagem na thread principal
        self._img_ready.connect(self._apply_image)

        # Monta URLs candidatas de capa
        identifier = rom_data.get("identifier", "")
        if identifier:
            cover_urls = [
                f"https://archive.org/download/{identifier}/__ia_thumb.jpg",
                f"https://archive.org/services/img/{identifier}",
            ]
        elif rom_data.get("image"):
            cover_urls = [rom_data["image"]]
        else:
            cover_urls = []

        if cover_urls:
            self._fetch_cover(cover_urls)

    def _fetch_cover(self, urls):
        """Busca capa em background — usa threading.Thread daemon (sem QThread)."""
        def _run():
            hdrs = {"User-Agent": "Mozilla/5.0"}
            for url in urls:
                if not self._alive:
                    return
                try:
                    r = requests.get(url, headers=hdrs, timeout=8)
                    ct = r.headers.get("content-type", "")
                    if r.status_code == 200 and len(r.content) > 1000 and "image" in ct:
                        self._img_ready.emit(r.content)
                        return
                except:
                    pass
        threading.Thread(target=_run, daemon=True).start()

    def _apply_image(self, data):
        """Aplica imagem ao cover label (sempre na thread principal via signal)."""
        if not self._alive:
            return
        px = QPixmap()
        px.loadFromData(data)
        if not px.isNull():
            px = px.scaled(220, 165, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            self.cover.setPixmap(px)
            self.cover.setText("")

    def hideEvent(self, event):
        self._alive = False
        super().hideEvent(event)

    def set_downloading(self, pct, status_text):
        self.progress.setVisible(True)
        self.progress.setValue(pct)
        self.dl_status.setText(status_text)
        if pct >= 100:
            self.dl_btn.setText("✓ Baixado")
            self.dl_btn.setStyleSheet(
                "background:#16a34a; border-radius:8px; color:white; font-weight:600; padding:8px 12px;")


# ── Janela Principal ─────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    status_signal        = pyqtSignal(str)
    results_signal       = pyqtSignal(list)
    _trigger_save_dialog = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.scraper = ROMScraper()
        self.setWindowTitle("ROMView v1.0 — ROM Browser & Downloader")
        self.resize(1280, 860)

        try:
            with open(os.path.join(os.path.dirname(__file__), "styles.qss"), "r") as f:
                self.setStyleSheet(f.read())
        except: pass

        self._ready = False   # evita disparo do console durante inicialização
        self._build_ui()
        self.status_signal.connect(self._set_status)
        self.results_signal.connect(self._render_results)
        self._trigger_save_dialog.connect(self._open_save_dialog)
        self._ready = True

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ──
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(0)

        title = QLabel("ROMVIEW")
        title.setObjectName("sidebar_title")
        sb_layout.addWidget(title)

        sub = QLabel("ROM BROWSER")
        sub.setObjectName("sidebar_sub")
        sb_layout.addWidget(sub)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#1e1e3a;")
        sb_layout.addWidget(sep)

        console_title = QLabel("  CONSOLES")
        console_title.setStyleSheet("color:#444466; font-size:10px; padding:12px 0 4px 12px; letter-spacing:1px;")
        sb_layout.addWidget(console_title)

        self.console_list = QListWidget()
        for name in CONSOLES:
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, CONSOLES[name])
            if name.startswith("───") or CONSOLES[name] is None:
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable & ~Qt.ItemIsEnabled)
                item.setForeground(__import__('PyQt5.QtGui', fromlist=['QColor']).QColor("#333355"))
            self.console_list.addItem(item)
        self.console_list.setCurrentRow(0)
        sb_layout.addWidget(self.console_list)
        sb_layout.addStretch()

        root.addWidget(sidebar)

        # ── Área principal ──
        content = QWidget()
        content.setObjectName("content_area")
        c_layout = QVBoxLayout(content)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(0)

        # Barra de busca
        search_bar = QWidget()
        search_bar.setStyleSheet("background:#0f0f1c; border-bottom:1px solid #1a1a2e;")
        sb = QHBoxLayout(search_bar)
        sb.setContentsMargins(12, 10, 12, 10)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("search_bar")
        self.search_input.setPlaceholderText("🔍  Buscar ROM por nome... (ex: Super Mario, Zelda, Sonic)")
        self.search_input.returnPressed.connect(self.do_search)

        self.search_btn = QPushButton("Buscar")
        self.search_btn.setObjectName("search_btn")
        self.search_btn.clicked.connect(self.do_search)

        sb.addWidget(self.search_input)
        sb.addWidget(self.search_btn)
        c_layout.addWidget(search_bar)

        # Conecta sidebar APÓS adicionar tudo (evita disparo prematuro)
        self.console_list.currentItemChanged.connect(self._on_console_changed)

        # Grid de resultados
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(20, 20, 20, 20)
        self.grid_layout.setSpacing(16)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.scroll.setWidget(self.grid_container)
        c_layout.addWidget(self.scroll)

        self._show_placeholder()

        self.status_bar = QLabel("Selecione um console ou busque uma ROM.")
        self.status_bar.setObjectName("status_bar")
        c_layout.addWidget(self.status_bar)

        root.addWidget(content)

    def _show_placeholder(self):
        placeholder = QLabel("🎮\n\nSelecione um console na sidebar\nou busque uma ROM pelo nome acima")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("color:#2a2a4a; font-size:20px; font-weight:300;")
        self.grid_layout.addWidget(placeholder, 0, 0, 1, 5)

    def _set_status(self, text):
        self.status_bar.setText(text)

    # ── Seleção de console ───────────────────────────────────────────────────
    def _get_selected_console(self):
        selected = self.console_list.currentItem()
        if not selected:
            return ""
        name = selected.text()
        data = selected.data(Qt.UserRole)
        if data is None or name.startswith("───") or name == "All":
            return ""
        return name

    def _on_console_changed(self, item):
        if not self._ready or not item:
            return
        name = item.text()
        data = item.data(Qt.UserRole)
        if data is None or name.startswith("───") or name == "All":
            return
        self._browse_console(name)

    def _browse_console(self, console_name):
        self._set_status(f"Carregando '{console_name}'...")
        self.search_btn.setEnabled(False)
        self.search_input.clear()
        QApplication.processEvents()

        def _run():
            results = self.scraper.browse(console_name)
            self.results_signal.emit(results)
            self.search_btn.setEnabled(True)

        threading.Thread(target=_run, daemon=True).start()

    # ── Busca por nome ───────────────────────────────────────────────────────
    def do_search(self):
        query = self.search_input.text().strip()
        if not query:
            console = self._get_selected_console()
            if console:
                self._browse_console(console)
            return

        console_name = self._get_selected_console()
        self._set_status(f"Buscando '{query}'...")
        self.search_btn.setEnabled(False)
        QApplication.processEvents()

        def _run():
            results = self.scraper.search(query, console_name or "All")
            self.results_signal.emit(results)
            self.search_btn.setEnabled(True)

        threading.Thread(target=_run, daemon=True).start()

    # ── Renderização ─────────────────────────────────────────────────────────
    def _render_results(self, results):
        # Marca cards antigos como mortos antes de remover
        for i in range(self.grid_layout.count()):
            w = self.grid_layout.itemAt(i).widget()
            if isinstance(w, ROMCard):
                w._alive = False

        for i in reversed(range(self.grid_layout.count())):
            w = self.grid_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        if not results:
            self._show_placeholder()
            self.status_signal.emit("Nenhum resultado encontrado.")
            return

        self.status_signal.emit(f"{len(results)} ROM(s) encontrada(s).")
        for i, rom in enumerate(results):
            card = ROMCard(rom)
            card.download_clicked.connect(self._on_download)
            self.grid_layout.addWidget(card, i // 5, i % 5)

    # ── Download ─────────────────────────────────────────────────────────────
    def _on_download(self, rom_data):
        def _resolve():
            self.status_signal.emit(f"Resolvendo '{rom_data['name']}'...")
            result = self.scraper.get_download_url(rom_data)
            if not result or result == (None, None):
                self.status_signal.emit("❌ Link não encontrado.")
                return
            download_url, filename = result
            filename = filename or (rom_data["name"] + ".zip")
            self._pending = (download_url, filename, rom_data)
            self._trigger_save_dialog.emit()

        threading.Thread(target=_resolve, daemon=True).start()

    def _open_save_dialog(self):
        if not hasattr(self, "_pending"):
            return
        download_url, filename, rom_data = self._pending

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Salvar ROM",
            os.path.join(os.path.expanduser("~"), "Downloads", filename),
            "Arquivos de ROM (*.zip *.7z *.rar *.iso *.nes *.gba *.nds *.sfc *.smc *.z64);;Todos (*)"
        )
        if not save_path:
            self.status_signal.emit("Download cancelado.")
            return

        card = self._find_card(rom_data["name"])
        if card:
            card.dl_btn.setEnabled(False)
        self._start_download(download_url, save_path, card, rom_data)

    def _find_card(self, name):
        for i in range(self.grid_layout.count()):
            w = self.grid_layout.itemAt(i).widget()
            if isinstance(w, ROMCard) and w.rom_data["name"] == name:
                return w
        return None

    def _start_download(self, url, dest, card, rom_data):
        worker = DownloadWorker(url, dest)
        thread = QThread(self)
        worker.moveToThread(thread)

        def on_progress(pct):
            if card:
                card.set_downloading(pct, f"{pct}%")
            self.status_signal.emit(f"Baixando {rom_data['name']}... {pct}%")

        def on_finished(path):
            self.status_signal.emit(f"✅ Download concluído: {os.path.basename(path)}")
            if card:
                card.set_downloading(100, "Concluído!")
            thread.quit()

        def on_error(err):
            self.status_signal.emit(f"❌ Erro: {err}")
            QMessageBox.critical(self, "Erro de Download", f"Falha ao baixar:\n{err}")
            thread.quit()

        worker.progress.connect(on_progress)
        worker.status.connect(self.status_signal)
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        thread.started.connect(worker.run)
        thread.start()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
