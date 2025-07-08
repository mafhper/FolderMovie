from tmdbv3api import TMDb, Movie, TV
import os
import re
import requests
import shutil
import subprocess
import tempfile
import traceback
from subliminal import Video, download_best_subtitles, save_subtitles, ProviderPool

import socket
import argparse
import logging
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

# --- CONFIGURAÇÃO DE LOGGING E RICH ---
# Configurar o logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("movie_organizer.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# Configurar o console Rich com um tema personalizado
custom_theme = Theme({
    "info": "dim cyan",
    "warning": "magenta",
    "error": "bold red",
    "success": "bold green",
    "header": "bold white on blue",
    "phase": "bold yellow on #333333",
    "separator": "bold black on white"
})
console = Console(theme=custom_theme)
# Aumentar o timeout padrão para conexões de socket para evitar timeouts com a API do OpenSubtitles
socket.setdefaulttimeout(60)

# --- CONFIGURAÇÃO ---
# Substitua 'SUA_CHAVE_API_TMDB' pela sua sua chave de API real do TMDb
TMDB_API_KEY = 'SUA_CHAVE_API_TMDB'

# Credenciais do OpenSubtitles (necessário para baixar legendas de lá)
# Crie uma conta em opensubtitles.org e preencha com seu usuário e senha
OPENSUBTITLES_USERNAME = 'usuário'
OPENSUBTITLES_PASSWORD = 'senha'

# --- INICIALIZAÇÃO DA API TMDB ---
tmdb = TMDb()
tmdb.api_key = TMDB_API_KEY
tmdb.language = 'pt-BR'  # Define o idioma para português do Brasil (pode ser ajustado para o idioma detectado)

movie_api = Movie()
tv_api = TV()


def extract_title_from_filename(filename):
    """
    Tenta extrair o título do filme/série e detectar se é uma série de um nome de arquivo.
    Retorna (title, is_series).
    Exemplos:
    - "A.Mulher.no.Jardim.2025.1080p.BluRay.DUAL.5.1.mkv" -> ("A Mulher no Jardim", False)
    - "As.Marvels.2023.1080p.BluRay.EAC3.AAC.DUAL.5.1.mkv" -> ("As Marvels", False)
    - "Ironheart.S01E01.1080p.WEB-DL.DUAL.5.1.mkv" -> ("Ironheart", True)
    - "The.Mandalorian.S02E05.1080p.WEB.H264-FLX.mkv" -> ("The Mandalorian", True)
    """
    name_without_ext = os.path.splitext(filename)[0]

    # Regex para detectar padrões de série (S01E01, S1E1, etc.)
    series_pattern = re.compile(r'[sS]\d+[eE]\d+')
    is_series = bool(series_pattern.search(name_without_ext))

    if is_series:
        # Para séries, tentar extrair o nome antes do padrão SXXEXX
        match = re.search(r'^(.*?)[sS]\d+[eE]\d+', name_without_ext)
        if match:
            title = match.group(1).replace('.', ' ').strip()
        else:
            title = name_without_ext.replace('.', ' ').strip() # Fallback
    else:
        # Para filmes, remover o ano e o que vem depois
        match_year = re.search(r'\.\d{4}', name_without_ext)
        if match_year:
            name_without_ext = name_without_ext[:match_year.start()]
        title = name_without_ext.replace('.', ' ').strip()

    title = re.sub(r'\s+', ' ', title)
    return title, is_series


def download_image(image_url, save_path):
    try:
        response = requests.get(image_url, stream=True)
        response.raise_for_status()
        with open(save_path, 'wb') as out_file:
            shutil.copyfileobj(response.raw, out_file)
        return True
    except requests.exceptions.RequestException as e:
        print(f"Erro ao baixar a imagem: {e}")
        return False

def get_safe_title(selected_item):
    """
    Retorna o título seguro de um objeto de filme/série do TMDb, tratando casos onde
    o atributo pode ser um método ou não existir, ou se o item for uma string.
    """
    try:
        if isinstance(selected_item, str):
            return selected_item

        # Tentar 'title' primeiro
        if hasattr(selected_item, 'title'):
            title_attr = selected_item.title
            if callable(title_attr):
                try:
                    title_value = title_attr()
                    if isinstance(title_value, str):
                        return title_value
                except Exception:
                    pass # Ignorar se a chamada do método do TMDb falhar
            elif isinstance(title_attr, str):
                return title_attr

        # Em seguida, tentar 'name'
        if hasattr(selected_item, 'name'):
            name_attr = selected_item.name
            if callable(name_attr):
                try:
                    name_value = name_attr()
                    if isinstance(name_value, str):
                        return name_value
                except Exception:
                    pass # Ignorar se a chamada do método do TMDb falhar
            elif isinstance(name_attr, str):
                return name_attr

        return "Título Desconhecido"
    except Exception:
        return "Título Desconhecido (Erro)"

def get_audio_language(file_path):
    """
    Usa ffprobe para obter o idioma da primeira trilha de áudio de um arquivo de vídeo.
    Retorna o código do idioma (ex: 'eng', 'por') ou None se não for encontrado.
    """
    cmd = [
        'ffprobe', '-v', '0', '-select_streams', 'a',
        '-show_entries', 'stream=index:stream_tags=language',
        '-of', 'compact=p=0:nk=1',
        file_path
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        output_lines = result.stdout.strip().split('\n')
        if output_lines:
            # Pega a primeira linha e extrai o idioma (formato: index|language)
            first_audio_track = output_lines[0]
            if '|' in first_audio_track:
                lang = first_audio_track.split('|')[1]
                return lang.strip()
        return None
    except subprocess.CalledProcessError as e:
        print(f"Erro ao executar ffprobe: {e.stderr}")
        return None
    except Exception as e:
        print(f"Erro inesperado ao obter idioma do áudio: {e}")
        return None

def has_embedded_subtitle(file_path, lang_code='por'):
    """
    Usa ffprobe para verificar se um arquivo de vídeo possui uma trilha de legenda embutida
    no idioma especificado.
    Retorna True se encontrar, False caso contrário.
    """
    cmd = [
        'ffprobe', '-v', '0', '-select_streams', 's',
        '-show_entries', 'stream=index:stream_tags=language',
        '-of', 'compact=p=0:nk=1',
        file_path
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        output_lines = result.stdout.strip().split('\n')
        for line in output_lines:
            if '|' in line:
                lang = line.split('|')[1]
                if lang.strip() == lang_code:
                    return True
        return False
    except subprocess.CalledProcessError as e:
        print(f"Erro ao executar ffprobe para legendas: {e.stderr}")
        return False
    except Exception as e:
        print(f"Erro inesperado ao verificar legendas embutidas: {e}")
        return False

def download_and_save_subtitle(video_path, item_title, release_year):
    print(f"Buscando legendas para '{item_title}' ({release_year})...")
    try:
        # Criar um objeto Video para o subliminal, com metadados para busca mais precisa
        video = Video.fromname(os.path.basename(video_path))
        video.title = item_title
        video.year = release_year

        # Usar a função de alto nível do subliminal para baixar as legendas
        subtitles = download_best_subtitles(
            videos=[video],
            languages={'por'},
            providers=['opensubtitles'],
            provider_configs={
                'opensubtitles': {
                    'username': OPENSUBTITLES_USERNAME,
                    'password': OPENSUBTITLES_PASSWORD
                }
            }
        )

        if subtitles and subtitles.get(video):
            # Salvar a legenda na mesma pasta do vídeo
            save_subtitles(video, subtitles[video])
            print(f"Legenda baixada e salva para '{item_title}'.")
            return True
        else:
            print(f"Nenhuma legenda em português do Brasil encontrada para '{item_title}'.")
            return False
    except Exception as e:
        print(f"Erro ao baixar legenda: {e}")
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Organiza arquivos de vídeo buscando metadados no TMDb.")
    parser.add_argument('directory', type=str, help="Caminho para o diretório contendo os arquivos de vídeo.")
    args = parser.parse_args()

    movie_directory = args.directory

    if not os.path.isdir(movie_directory):
        log.error(f"Erro: O diretório especificado não existe: [bold red]{movie_directory}[/bold red]")
        console.print(f"[error]Erro: O diretório especificado não existe: {movie_directory}[/error]")
        return

    console.print(Panel("[bold green]Processamento Concluído![/bold green]\nVerifique seus arquivos organizados.", title="[bold white on green]Sucesso![/bold white on green]", style="success", expand=False))

    files_to_process = []

    console.print(Panel("[bold yellow]Fase 1: Análise e Busca de Metadados[/bold yellow]\nVerificando arquivos de vídeo e buscando informações no TMDb.", title="[bold white on yellow]Início do Processamento[/bold white on yellow]", style="phase", expand=False))

    files_to_process = []

    for filename in os.listdir(movie_directory):
        if '_processed' in filename:
            log.info(f"Arquivo '{filename}' já processado, pulando.")
            continue
        file_path = os.path.join(movie_directory, filename)
        if filename.lower().endswith(('.mkv', '.mp4', '.avi', '.mov')):
            console.print(f"\n[separator]-- Processando arquivo: [bold blue]{filename}[/bold blue] --[/separator]")
            extracted_title, is_series = extract_title_from_filename(filename)
            log.info(f"Título extraído: '{extracted_title}' (Tipo: {"Série" if is_series else "Filme"})")
            console.print(f"  [info]Título extraído:[/info] [bold cyan]'{extracted_title}'[/bold cyan] ([info]Tipo:[/info] {"Série" if is_series else "Filme"})")

            search_results_pt_br = []
            search_results_en_us = []
            selected_item = None

            # Tentar buscar em pt-BR primeiro
            tmdb.language = 'pt-BR'
            log.info(f"Buscando '{extracted_title}' no TMDb (idioma: pt-BR)...")
            if is_series:
                search_results_pt_br = tv_api.search(extracted_title)
            else:
                search_results_pt_br = movie_api.search(extracted_title)

            if search_results_pt_br and not isinstance(search_results_pt_br, str):
                selected_item = list(search_results_pt_br)[0] # Seleciona o primeiro resultado automaticamente
                log.info(f"Resultado encontrado em pt-BR: {get_safe_title(selected_item)}")
            else:
                # Se não encontrou em pt-BR, tentar em en-US
                log.warning(f"Nenhum resultado em pt-BR para '{extracted_title}'. Tentando em en-US...")
                console.print(f"  [warning]Nenhum resultado em pt-BR para '{extracted_title}'. Tentando em en-US...[/warning]")
                tmdb.language = 'en-US'
                if is_series:
                    search_results_en_us = tv_api.search(extracted_title)
                else:
                    search_results_en_us = movie_api.search(extracted_title)
                
                if search_results_en_us and not isinstance(search_results_en_us, str):
                    selected_item = list(search_results_en_us)[0]
                    log.info(f"Resultado encontrado em en-US: {get_safe_title(selected_item)}")
                else:
                    log.warning(f"Nenhum resultado em en-US para '{extracted_title}'.")

            # Resetar o idioma para pt-BR para as próximas operações
            tmdb.language = 'pt-BR'

            if selected_item and hasattr(selected_item, 'id'):
                console.print(f"  [success]Sugestão automática:[/success] [bold green]{get_safe_title(selected_item)}[/bold green]")
                files_to_process.append((file_path, selected_item, is_series))
            else:
                log.error(f"Nenhum resultado encontrado para '{extracted_title}'. Pulando este arquivo.")
                console.print(f"  [error]Nenhum resultado encontrado para '{extracted_title}'. Pulando este arquivo.[/error]")
            console.print("[separator]----------------------------------------[/separator]")

    print("\n" + "-" * 50)
    print("  FASE 1.5: CONFIRMAÇÃO  ")
    print("  Verifique as correlações antes de aplicar os metadados")
    print("-" * 50 + "\n")
    if not files_to_process:
        print("Nenhum arquivo de vídeo encontrado ou selecionado para processamento.")
        return

    while True:
        confirm = input("Confirmar e aplicar metadados aos arquivos listados? (s/n): ").lower()
        if confirm == 's':
            break
        elif confirm == 'n':
            print("Operação cancelada pelo usuário.")
            return
        else:
            print("Resposta inválida. Por favor, digite 's' para sim ou 'n' para não.")

    print("\n" + "-" * 50)
    print("  FASE 2: APLICAÇÃO DE METADADOS  ")
    print("  Aplicando metadados e baixando legendas  ")
    print("-" * 50 + "\n")

    for file_path, selected_item, is_series in files_to_process:
        filename = os.path.basename(file_path)
        print(f"  Processando metadados para: {filename}")

        # --- Baixar a capa ---
        cover_url = f"https://image.tmdb.org/t/p/original{selected_item.poster_path}" if selected_item.poster_path else None
        temp_cover_path = None

        if cover_url:
            temp_cover_path = os.path.join(tempfile.gettempdir(), f"cover_{selected_item.id}.jpg")
            print(f"Baixando capa para: {temp_cover_path}")
            if not download_image(cover_url, temp_cover_path):
                temp_cover_path = None # Falha ao baixar

        output_filename = f"{os.path.splitext(filename)[0]}_processed{os.path.splitext(filename)[1]}"
        output_file_path = os.path.join(movie_directory, output_filename)

        # --- Aplicar metadados ---
        if filename.lower().endswith('.mp4'):
            print("Aplicando metadados (MP4 com ffmpeg)...")
            # Obter detalhes completos do filme para mais metadados
            full_item_details = None
            if is_series:
                full_item_details = tv_api.details(selected_item.id)
            else:
                full_item_details = movie_api.details(selected_item.id)

            # Extrair metadados adicionais
            release_date = full_item_details.release_date if hasattr(full_item_details, 'release_date') else (
                full_item_details.first_air_date if hasattr(full_item_details, 'first_air_date') else ''
            )
            genres = ', '.join([g.name for g in full_item_details.genres]) if hasattr(full_item_details,
                                                                                       'genres') else ''

            cmd = [
                'ffmpeg', '-i', file_path,
            ]
            # Adicionar capa se existir
            if temp_cover_path:
                cmd.extend(['-i', temp_cover_path, '-map', '0', '-map', '1'])
            
            cmd.extend([
                '-c', 'copy',
                '-metadata', f'title={get_safe_title(selected_item)}',
                '-metadata', f'date={release_date}',
            ])

            if temp_cover_path:
                cmd.extend(['-c:v:1', 'mjpeg', '-disposition:v:1', 'attached_pic'])

            cmd.append(output_file_path)

            print(f"Comando ffmpeg: {' '.join(cmd)}")
            try:
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                print(f"Stdout ffmpeg: {result.stdout}")
                print(f"Metadados aplicados com sucesso em: {output_filename}")
                # Substituir o arquivo original pelo processado
                original_file_backup_path = file_path + '.bak'
                try:
                    os.rename(file_path, original_file_backup_path)
                    os.rename(output_file_path, file_path)
                    print(f"Arquivo original renomeado para backup: {original_file_backup_path}")
                    print(f"Arquivo processado renomeado para: {filename}")
                except OSError as e:
                    print(f"Erro ao substituir o arquivo: {e}")
            except subprocess.CalledProcessError as e:
                print(f"Erro ao aplicar metadados com ffmpeg: {e.stderr}")
                print(f"Comando falhou: {e.cmd}")
                print(f"Código de retorno: {e.returncode}")
                print(f"Stdout do erro: {e.stdout}")
                print(f"Stderr do erro: {e.stderr}")
                print(f"Pulando processamento de metadados para {filename} devido ao erro do ffmpeg.")
                continue # Skip to the next file in files_to_process

            # Baixar legendas após aplicar metadados
            audio_lang = get_audio_language(file_path)
            if audio_lang == 'por':
                print(f"Idioma de áudio detectado como Português ('por'). Pulando download de legendas para {filename}.")
            elif has_embedded_subtitle(file_path, 'por'):
                print(f"Legenda em Português (por) já embutida. Pulando download de legendas para {filename}.")
            else:
                item_title = get_safe_title(selected_item)
                item_release_year = int(release_date.split('-')[0]) if release_date else None
                if item_release_year:
                    download_and_save_subtitle(file_path, item_title, item_release_year)

        elif filename.lower().endswith('.mkv'):
            print("Aplicando metadados (MKV com ffmpeg)...")
            # Obter detalhes completos do filme para mais metadados
            full_item_details = None
            if is_series:
                full_item_details = tv_api.details(selected_item.id)
            else:
                full_item_details = movie_api.details(selected_item.id)

            # Extrair metadados adicionais
            release_date = full_item_details.release_date if hasattr(full_item_details, 'release_date') else (
                full_item_details.first_air_date if hasattr(full_item_details, 'first_air_date') else ''
            )
            genres = ', '.join([g.name for g in full_item_details.genres]) if hasattr(full_item_details,
                                                                                       'genres') else ''

            cmd = [
                'ffmpeg', '-i', file_path,
            ]
            # Adicionar capa se existir
            if temp_cover_path:
                cmd.extend(['-i', temp_cover_path, '-map', '0', '-map', '1'])
            
            cmd.extend([
                '-c', 'copy',
                '-metadata', f'title={get_safe_title(selected_item)}',
                '-metadata', f'date={release_date}',
            ])

            if temp_cover_path:
                cmd.extend(['-c:v:1', 'mjpeg', '-disposition:v:1', 'attached_pic'])

            cmd.append(output_file_path)

            print(f"Comando ffmpeg: {' '.join(cmd)}")
            try:
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                print(f"Stdout ffmpeg: {result.stdout}")
                print(f"Metadados aplicados com sucesso em: {output_filename}")
                # Substituir o arquivo original pelo processado
                original_file_backup_path = file_path + '.bak'
                try:
                    os.rename(file_path, original_file_backup_path)
                    os.rename(output_file_path, file_path)
                    print(f"Arquivo original renomeado para backup: {original_file_backup_path}")
                    print(f"Arquivo processado renomeado para: {filename}")
                except OSError as e:
                    print(f"Erro ao substituir o arquivo: {e}")
            except subprocess.CalledProcessError as e:
                print(f"Erro ao aplicar metadados com ffmpeg: {e.stderr}")
                print(f"Comando falhou: {e.cmd}")
                print(f"Código de retorno: {e.returncode}")
                print(f"Stdout do erro: {e.stdout}")
                print(f"Stderr do erro: {e.stderr}")
                print(f"Pulando processamento de metadados para {filename} devido ao erro do ffmpeg.")
                continue # Skip to the next file in files_to_process

            # Baixar legendas após aplicar metadados
            audio_lang = get_audio_language(file_path)
            if audio_lang == 'por':
                print(f"Idioma de áudio detectado como Português ('por'). Pulando download de legendas para {filename}.")
            elif has_embedded_subtitle(file_path, 'por'):
                print(f"Legenda em Português (por) já embutida. Pulando download de legendas para {filename}.")
            else:
                item_title = get_safe_title(selected_item)
                item_release_year = int(release_date.split('-')[0]) if release_date else None
                if item_release_year:
                    download_and_save_subtitle(file_path, item_title, item_release_year)

        else:
            print("Formato de arquivo não suportado para aplicação de metadados (apenas MP4 e MKV).")

        # --- Limpar arquivo temporário ---
        if temp_cover_path and os.path.exists(temp_cover_path):
            os.remove(temp_cover_path)
            print(f"Arquivo temporário removido: {temp_cover_path}")


if __name__ == "__main__":
    main()
