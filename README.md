# FolderMovie Organizer

Este script Python ajuda a organizar sua biblioteca de filmes, buscando metadados de filmes no The Movie Database (TMDb) e aplicando-os diretamente aos seus arquivos de vídeo (MP4 e MKV).

## Funcionalidades Atuais

- Extração inteligente do título do filme/série a partir do nome do arquivo, incluindo detecção de padrões de série (S01E01).
- Busca automática de informações de filmes e séries no TMDb (título, data de lançamento).
    - Prioriza a busca em português do Brasil (`pt-BR`) e, se não houver resultados, tenta em inglês (`en-US`).
- Seleção automática do filme/série mais provável com base nos resultados da busca.
- Resumo das correspondências encontradas e confirmação do usuário antes da aplicação dos metadados.
- Aplicação de metadados (título, data de lançamento) a arquivos MP4 usando `ffmpeg`.
- Aplicação de metadados (título, data de lançamento) a arquivos MKV usando `mkvpropedit`.
- Criação de arquivos de backup (`.bak`) antes de modificar os arquivos originais.
- Download e aplicação de capa (poster) para os arquivos de vídeo.
- Download de legendas em português do Brasil (`pt-BR`) usando `subliminal` e credenciais do OpenSubtitles.

## Próximas Funcionalidades (Em Desenvolvimento)

- Internacionalização da aplicação (suporte a múltiplos idiomas para a interface).
- Aprimoramento da interface do usuário no terminal.

## Requisitos

- Python 3.x
- `ffmpeg` (para arquivos MP4 e `ffprobe` para detecção de idioma de áudio)
- `mkvtoolnix` (que inclui `mkvpropedit`, para arquivos MKV)
- Chave de API do TMDb

## Instalação

1.  **Clone o repositório (ou baixe os arquivos):**

    ```bash
    git clone <URL_DO_SEU_REPOSITORIO>
    cd MovieOrganizer
    ```

2.  **Crie e ative um ambiente virtual (recomendado):**

    ```bash
    python3 -m venv venv
    source venv/bin/activate  # No Linux/macOS
    # venv\Scripts\activate  # No Windows
    ```

3.  **Instale as dependências Python:**

    ```bash
    pip install tmdbv3api requests subliminal
    ```

4.  **Instale `ffmpeg` e `mkvtoolnix`:**

    Certifique-se de ter `ffmpeg` e `mkvtoolnix` instalados em seu sistema e acessíveis via PATH. Você pode encontrá-los nos gerenciadores de pacotes da sua distribuição (ex: `sudo apt install ffmpeg mkvtoolnix` no Debian/Ubuntu) ou em seus sites oficiais.

## Configuração

1.  **Obtenha uma chave de API do TMDb:**
    - Vá para [The Movie Database (TMDb)](https://www.themoviedb.org/)
    - Crie uma conta (se ainda não tiver uma).
    - Vá para as configurações da sua conta -> API.
    - Solicite uma nova chave de API de desenvolvedor.

2.  **Obtenha credenciais do OpenSubtitles:**
    - Vá para [OpenSubtitles.org](https://www.opensubtitles.org/)
    - Crie uma conta (se ainda não tiver uma).

3.  **Atualize o arquivo `movie_organizer.py`:**

    Abra `movie_organizer.py` e substitua `'SUA_CHAVE_API_TMDB'` pela sua chave de API real do TMDb.

    ```python
    TMDB_API_KEY = 'SUA_CHAVE_API_TMDB'
    ```

    Preencha também suas credenciais do OpenSubtitles:

    ```python
    OPENSUBTITLES_USERNAME = 'SEU_USUARIO_OPENSUBTITLES'
    OPENSUBTITLES_PASSWORD = 'SUA_SENHA_OPENSUBTITLES'
    ```

## Como Usar

1.  **Execute o script, passando o diretório dos filmes como argumento:**

    ```bash
    python movie_organizer.py /caminho/para/seus/filmes
    ```

2.  O script irá processar cada arquivo, sugerir uma correspondência do TMDb e, ao final, apresentar um resumo para sua confirmação antes de aplicar os metadados.

## Acessibilidade Global e Menu de Contexto (Linux)

Para usar o `movie_organizer.py` de qualquer diretório e integrá-lo ao menu de contexto do seu gerenciador de arquivos (ex: Nautilus, Nemo, Dolphin), siga os passos abaixo:

### 1. Tornar o Script Executável e Acessível Globalmente

1.  **Torne o script executável:**
    ```bash
    chmod +x movie_organizer.py
    ```
2.  **Mova o script para um diretório no seu PATH:**
    ```bash
    sudo mv movie_organizer.py /usr/local/bin/movie-organizer
    ```
    (Você pode escolher outro nome, como `movie-organizer`, para facilitar a digitação.)

Agora você pode executar o script de qualquer lugar no terminal, passando o caminho do diretório como argumento:
```bash
movie-organizer /home/usuario/Videos/MeusFilmes
```

### 2. Integrar ao Menu de Contexto (Exemplo para GNOME/Cinnamon - Nautilus/Nemo)

Para adicionar uma opção "Organizar Filmes" ao clicar com o botão direito em uma pasta:

1.  **Crie um arquivo `.desktop` para a ação personalizada:**
    ```bash
    nano ~/.local/share/file-manager/actions/movie-organizer.desktop
    ```
    (Se a pasta `file-manager/actions` não existir, crie-a: `mkdir -p ~/.local/share/file-manager/actions`)

2.  **Cole o seguinte conteúdo no arquivo `movie-organizer.desktop`:**
    ```ini
    [Desktop Entry]
    Type=Action
    ToolbarLabel=Organizar Filmes
    Name=Organizar Filmes com TMDb
    Profiles=profile-using-item-selection;
    Icon=video-x-generic

    [X-Action-Profile profile-using-item-selection]
    MimeTypes=inode/directory;
    Selection=any
    Exec=gnome-terminal -- bash -c "movie-organizer %f; echo 'Pressione Enter para fechar...'; read -n 1"
    # Ou para Nemo (Cinnamon):
    # Exec=nemo-terminal -- bash -c "movie-organizer %f; echo 'Pressione Enter para fechar...'; read -n 1"
    # Ou para um terminal genérico (pode variar):
    # Exec=xterm -e "movie-organizer %f; echo 'Pressione Enter para fechar...'; read -n 1"
    ```
    *   `Exec`: Este comando abre um terminal, executa o `movie-organizer` com o diretório selecionado (`%f`) e mantém o terminal aberto até você pressionar Enter. Ajuste `gnome-terminal` para o seu emulador de terminal preferido (`konsole`, `xterm`, `terminator`, etc.).

3.  **Salve e feche o arquivo.**

4.  **Reinicie seu gerenciador de arquivos** ou faça logoff e login novamente para que a nova opção apareça.

Agora, ao clicar com o botão direito em qualquer pasta no seu gerenciador de arquivos, você verá a opção "Organizar Filmes com TMDb". Selecionar esta opção executará o script no diretório escolhido.
