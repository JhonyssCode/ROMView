# ROMView 🎮

Um navegador e gerenciador de downloads de ROMs retro para desktop. Com uma interface elegante, o ROMView se conecta à API pública do Internet Archive para buscar, exibir capas e fazer o download de jogos clássicos de vários consoles diretamente para o seu PC.

## ✨ Funcionalidades

- **Acervo Completo**: Utiliza o gigantesco acervo do Internet Archive (coleções No-Intro e Redump).
- **Download Direto**: Resolve links e baixa `.zip`, `.iso`, `.7z` e outros arquivos diretamente pelo app.
- **Interface Gamer**: Design dark mode premium usando PyQt5 e QSS.
- **Multiconsoles**: Suporte a dezenas de sistemas (NES, SNES, N64, GBA, PS1, PS2, Sega Genesis, MAME, etc).
- **Progresso Real**: Barra de progresso assíncrona integrada ao card de cada jogo.

## 🚀 Como instalar

1. **Pré-requisitos**:
   - [Python 3.9+](https://www.python.org/downloads/)

2. **Clone ou baixe este repositório**:
   ```bash
   git clone https://github.com/JhonyssCode/ROMView.git
   cd ROMView
   ```

3. **Instale as dependências Python**:
   ```bash
   pip install -r requirements.txt
   ```
   *(Dependências principais: `PyQt5`, `requests`, `beautifulsoup4`)*

## 🕹️ Como rodar

Basta executar o arquivo principal:

```bash
python main.py
```

1. Selecione um console na barra lateral esquerda (ex: `Game Boy Advance`).
2. O aplicativo listará as ROMs mais populares daquele console. Se preferir, digite o nome de um jogo na barra de busca superior.
3. Clique em "⬇ Baixar ROM" no card do jogo.
4. Escolha onde salvar no seu computador e acompanhe a barra de progresso.
5. Abra o arquivo no seu emulador favorito!

## ⚠️ Aviso Legal
Este projeto é uma ferramenta de busca que interage com o catálogo público do Internet Archive (archive.org). É sua responsabilidade garantir que você possui o direito legal de baixar e possuir as cópias de backup (ROMs) dos jogos pesquisados, de acordo com as leis de direitos autorais locais.
