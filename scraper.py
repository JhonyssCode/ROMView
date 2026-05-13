import requests
import urllib.parse
import re
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

IA_SEARCH_URL = "https://archive.org/advancedsearch.php"
IA_DOWNLOAD_URL = "https://archive.org/download"
IA_DETAILS_URL = "https://archive.org/metadata"

# Consoles: nome exibido → (coleção archive.org, termos extras de busca)
CONSOLES = {
    "All":                    None,
    "──── NINTENDO ────":     None,
    "NES":                    ("No-Intro_Nintendo_NES", "NES"),
    "Super Nintendo (SNES)":  ("No-Intro_Nintendo_SNES", "SNES"),
    "Game Boy":               ("No-Intro_Nintendo_GB", "Game Boy"),
    "Game Boy Color":         ("No-Intro_Nintendo_GBC", "GBC"),
    "Game Boy Advance":       ("No-Intro_Nintendo_GBA", "GBA"),
    "Nintendo DS":            ("No-Intro_Nintendo_DS", "NDS"),
    "Nintendo 64":            ("No-Intro_Nintendo_N64", "N64"),
    "GameCube":               ("Redump_Nintendo_GCN", "GameCube"),
    "Wii":                    ("Redump_Nintendo_Wii", "Wii"),
    "──── PLAYSTATION ────":  None,
    "PlayStation 1":          ("Redump_Sony_PSX", "PlayStation"),
    "PlayStation 2":          ("Redump_Sony_PS2", "PlayStation 2"),
    "PlayStation 3":          ("Redump_Sony_PS3", "PlayStation 3"),
    "PSP":                    ("Redump_Sony_PSP", "PSP"),
    "──── SEGA ────":         None,
    "Sega Genesis":           ("No-Intro_Sega_Genesis", "Genesis"),
    "Sega Saturn":            ("Redump_Sega_Saturn", "Saturn"),
    "Sega Dreamcast":         ("Redump_Sega_Dreamcast", "Dreamcast"),
    "Sega Game Gear":         ("No-Intro_Sega_GG", "Game Gear"),
    "──── ATARI ────":        None,
    "Atari 2600":             ("No-Intro_Atari_2600", "Atari 2600"),
    "Atari 7800":             ("No-Intro_Atari_7800", "Atari 7800"),
    "──── OUTROS ────":       None,
    "Arcade (MAME)":          ("MAME_Arcade", "MAME arcade"),
}

EMULATORS = {
    "NES":                   {"name": "FCEUX",      "exe": "fceux.exe"},
    "Super Nintendo (SNES)": {"name": "SNES9x",     "exe": "snes9x-x64.exe"},
    "Game Boy":              {"name": "mGBA",        "exe": "mGBA.exe"},
    "Game Boy Color":        {"name": "mGBA",        "exe": "mGBA.exe"},
    "Game Boy Advance":      {"name": "mGBA",        "exe": "mGBA.exe"},
    "Nintendo DS":           {"name": "DeSmuME",     "exe": "DeSmuME_0.9.13_x64.exe"},
    "Nintendo 64":           {"name": "Project64",   "exe": "Project64.exe"},
    "GameCube":              {"name": "Dolphin",     "exe": "Dolphin.exe"},
    "Wii":                   {"name": "Dolphin",     "exe": "Dolphin.exe"},
    "PlayStation 1":         {"name": "PCSX-R",      "exe": "pcsxr.exe"},
    "PlayStation 2":         {"name": "PCSX2",       "exe": "pcsx2.exe"},
    "PlayStation 3":         {"name": "RPCS3",       "exe": "rpcs3.exe"},
    "PSP":                   {"name": "PPSSPP",      "exe": "PPSSPPWindows64.exe"},
    "Sega Genesis":          {"name": "Gens/GS",     "exe": "gens.exe"},
    "Sega Saturn":           {"name": "Mednafen",    "exe": "mednafen.exe"},
    "Sega Dreamcast":        {"name": "Flycast",     "exe": "flycast.exe"},
    "Sega Game Gear":        {"name": "Gens/GS",     "exe": "gens.exe"},
    "Atari 2600":            {"name": "Stella",      "exe": "Stella.exe"},
    "Atari 7800":            {"name": "ProSystem",   "exe": "ProSystem.exe"},
    "Arcade (MAME)":         {"name": "MAME",        "exe": "mame64.exe"},
}

ROM_EXTENSIONS = {'.zip','.7z','.rar','.iso','.nes','.gba','.nds',
                  '.sfc','.smc','.z64','.n64','.gb','.gbc','.rvz',
                  '.chd','.cue','.bin','.gg','.md','.sms','.a26','.a78'}


class ROMScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        print("[ROMScraper] Motor Internet Archive inicializado.")

    def search(self, query, console_name="All"):
        """Busca ROMs no Internet Archive por nome e console."""
        print(f"\n[Busca] '{query}' em '{console_name}'...")
        results = []

        if console_name in ("All", None, "") or console_name.startswith("───"):
            # Busca genérica em todos os consoles
            results = self._search_ia(query, console_tag="")
        else:
            info = CONSOLES.get(console_name)
            if info:
                _, console_term = info
                results = self._search_ia(query, console_term=console_term, console_name=console_name)
            else:
                results = self._search_ia(query, console_tag="")

        print(f"[Busca] {len(results)} ROM(s) encontrada(s).")
        return results[:40]

    def browse(self, console_name):
        """Lista as ROMs mais populares de um console (sem filtro de nome)."""
        print(f"\n[Browse] Listando ROMs de '{console_name}'...")
        info = CONSOLES.get(console_name)
        if not info:
            return []
        _, console_term = info

        try:
            params = {
                "q": f'subject:({console_term} rom) AND mediatype:(software OR data)',
                "fl[]": ["identifier", "title", "description", "subject", "downloads"],
                "rows": 40,
                "page": 1,
                "output": "json",
                "sort[]": "downloads desc",
            }
            resp = self.session.get(IA_SEARCH_URL, params=params, timeout=15)
            resp.raise_for_status()
            docs = resp.json().get("response", {}).get("docs", [])
            print(f"[Browse] {len(docs)} itens encontrados para '{console_name}'.")

            results = []
            for doc in docs:
                identifier = doc.get("identifier", "")
                title = doc.get("title", identifier)
                clean_name = re.sub(r'\.[a-z0-9]{2,4}$', '', title, flags=re.I).strip()
                clean_name = re.sub(r'\s*[\(\[].+?[\)\]]', '', clean_name).strip()
                results.append({
                    "name": clean_name or title,
                    "full_title": title,
                    "identifier": identifier,
                    "url": f"https://archive.org/details/{identifier}",
                    "download_url": None,
                    "console": console_name,
                    "image": f"https://archive.org/services/img/{identifier}",
                    "downloads": doc.get("downloads", 0),
                    "full_filename": None,
                })
            return results

        except Exception as e:
            print(f"[Erro] Browse falhou: {e}")
            return []

    def _search_ia(self, query, console_term="", console_tag="", console_name=""):
        """Consulta a API de busca do Archive.org."""
        # Monta query combinando nome do jogo e console
        q_parts = [f'title:"{query}"', 'mediatype:(software OR data)']
        if console_term:
            q_parts.append(f'subject:({console_term} OR rom)')
        q_parts.append('subject:(rom OR roms OR game)')

        params = {
            "q": " AND ".join(q_parts),
            "fl[]": ["identifier", "title", "description", "subject", "downloads", "format"],
            "rows": 30,
            "page": 1,
            "output": "json",
            "sort[]": "downloads desc",
        }

        try:
            resp = self.session.get(IA_SEARCH_URL, params=params, timeout=15)
            resp.raise_for_status()
            docs = resp.json().get("response", {}).get("docs", [])
            print(f"[IA] {len(docs)} documento(s) encontrado(s).")

            results = []
            for doc in docs:
                identifier = doc.get("identifier", "")
                title = doc.get("title", identifier)
                # Limpa nome (remove extensão e tags)
                clean_name = re.sub(r'\.[a-z0-9]{2,4}$', '', title, flags=re.I).strip()
                clean_name = re.sub(r'\s*[\(\[].+?[\)\]]', '', clean_name).strip()

                results.append({
                    "name": clean_name or title,
                    "full_title": title,
                    "identifier": identifier,
                    "url": f"https://archive.org/details/{identifier}",
                    "download_url": None,  # Resolvido ao baixar
                    "console": console_name or self._guess_console(doc),
                    "image": f"https://archive.org/services/img/{identifier}",
                    "downloads": doc.get("downloads", 0),
                    "full_filename": None,
                })
            return results

        except Exception as e:
            print(f"[Erro] Busca IA falhou: {e}")
            return []

    def _guess_console(self, doc):
        """Tenta adivinhar o console pelas tags do item."""
        subjects = " ".join(doc.get("subject", [])).lower() if isinstance(doc.get("subject"), list) else str(doc.get("subject", "")).lower()
        if "nes" in subjects or "nintendo entertainment" in subjects: return "NES"
        if "snes" in subjects or "super nintendo" in subjects: return "Super Nintendo (SNES)"
        if "game boy advance" in subjects or "gba" in subjects: return "Game Boy Advance"
        if "game boy color" in subjects or "gbc" in subjects: return "Game Boy Color"
        if "game boy" in subjects: return "Game Boy"
        if "playstation 2" in subjects or "ps2" in subjects: return "PlayStation 2"
        if "playstation" in subjects or "psx" in subjects: return "PlayStation 1"
        if "psp" in subjects: return "PSP"
        if "nintendo 64" in subjects or "n64" in subjects: return "Nintendo 64"
        if "sega genesis" in subjects or "mega drive" in subjects: return "Sega Genesis"
        if "dreamcast" in subjects: return "Sega Dreamcast"
        return "ROM"

    def get_download_url(self, rom_data):
        """
        Resolve o link de download direto de um item do Archive.org.
        Busca os arquivos do item e retorna o mais relevante.
        """
        identifier = rom_data.get("identifier", "")
        if not identifier:
            return None

        print(f"[IA] Buscando arquivos de: {identifier}...")
        try:
            resp = self.session.get(f"{IA_DETAILS_URL}/{identifier}", timeout=15)
            resp.raise_for_status()
            files_raw = resp.json().get("files", {})

            # O IA pode retornar dict {nome: meta} ou lista [{name, ...}]
            if isinstance(files_raw, list):
                file_iter = [(f.get("name", ""), f) for f in files_raw]
            else:
                file_iter = files_raw.items()

            preferred_ext = ['.zip', '.7z', '.rar', '.iso', '.rvz', '.chd']
            best_file = None
            best_priority = 999

            for fname, fmeta in file_iter:
                ext = "." + fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
                if ext in ROM_EXTENSIONS:
                    priority = preferred_ext.index(ext) if ext in preferred_ext else 50
                    if priority < best_priority:
                        best_priority = priority
                        best_file = fname

            if best_file:
                url = f"{IA_DOWNLOAD_URL}/{identifier}/{urllib.parse.quote(best_file)}"
                print(f"[IA] Arquivo selecionado: {best_file}")
                return url, best_file

            print(f"[Aviso] Nenhum arquivo ROM encontrado em '{identifier}'.")
            return None, None

        except Exception as e:
            print(f"[Erro] Falha ao resolver download: {e}")
            return None, None
