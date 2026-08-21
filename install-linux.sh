#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
UV_VERSION="0.11.32"

if [[ ! -r /etc/os-release ]]; then
  printf 'Não foi possível identificar a distribuição Linux.\n' >&2
  exit 1
fi

# shellcheck disable=SC1091
source /etc/os-release
case "${ID:-}:${VERSION_ID:-}" in
  ubuntu:22.04|ubuntu:24.04|ubuntu:26.04|debian:12|debian:13) ;;
  *)
    printf 'Instalador disponível para Ubuntu 22.04/24.04/26.04 e Debian 12/13.\n' >&2
    exit 1
    ;;
esac

run_as_root() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    printf 'O sistema precisa do comando sudo para instalar bibliotecas do Chromium.\n' >&2
    exit 1
  fi
}

printf '%s\n' \
  'Instalação do Q.U.A.T.I.' \
  '' \
  "Serão baixados o gerenciador uv ${UV_VERSION} (se necessário), Python 3.12," \
  'as bibliotecas verificadas no uv.lock, as dependências do sistema e o Chromium.' \
  'O sistema poderá solicitar a senha administrativa para instalar bibliotecas do Chromium.' \
  ''
read -r -p 'Autoriza a instalação? [s/N] ' answer
case "${answer,,}" in
  s|sim|y|yes) ;;
  *) printf 'Instalação cancelada.\n'; exit 0 ;;
esac

for required_file in \
  "$PROJECT_ROOT/pyproject.toml" \
  "$PROJECT_ROOT/uv.lock" \
  "$PROJECT_ROOT/app.py" \
  "$PROJECT_ROOT/scripts/launch-linux.sh" \
  "$PROJECT_ROOT/src/quati/assets/quati-icon.png"; do
  if [[ ! -f "$required_file" ]]; then
    printf 'O download está incompleto: %s não foi encontrado. Extraia novamente todo o ZIP.\n' \
      "${required_file#"$PROJECT_ROOT/"}" >&2
    exit 1
  fi
done

AVAILABLE_KB="$(df -Pk "$PROJECT_ROOT" | awk 'NR==2 {print $4}')"
if [[ "$AVAILABLE_KB" =~ ^[0-9]+$ ]] && (( AVAILABLE_KB < 2097152 )); then
  printf 'Separe pelo menos 2 GB livres para Python, bibliotecas e Chromium.\n' >&2
  exit 1
fi

if [[ "${EUID:-$(id -u)}" -ne 0 ]] && ! command -v sudo >/dev/null 2>&1; then
  printf 'O sistema precisa do comando sudo para instalar bibliotecas do Chromium.\n' >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  printf 'Instalando o componente seguro de download...\n'
  run_as_root apt-get update
  run_as_root apt-get install -y ca-certificates curl
fi

UV_BIN="$(command -v uv 2>/dev/null || true)"
if [[ -z "$UV_BIN" ]]; then
  TEMP_DIR="$(mktemp -d)"
  trap 'rm -rf -- "$TEMP_DIR"' EXIT
  INSTALLER="$TEMP_DIR/install-uv.sh"
  UV_URL="https://astral.sh/uv/${UV_VERSION}/install.sh"

  curl --proto '=https' --tlsv1.2 -LsSf "$UV_URL" -o "$INSTALLER"
  UV_NO_MODIFY_PATH=1 sh "$INSTALLER"
  UV_BIN="$HOME/.local/bin/uv"
fi

if [[ ! -x "$UV_BIN" ]]; then
  printf 'O executável do uv não foi localizado.\n' >&2
  exit 1
fi

cd "$PROJECT_ROOT"
if [[ -r "$PROJECT_ROOT/data/quati.pid" ]]; then
  "$PROJECT_ROOT/scripts/stop-linux.sh"
fi
printf '1/4 Instalando Python 3.12...\n'
"$UV_BIN" python install 3.12

printf '2/4 Instalando as bibliotecas verificadas...\n'
"$UV_BIN" sync --python 3.12 --frozen

printf '3/4 Instalando Chromium e bibliotecas do sistema...\n'
"$UV_BIN" run playwright install --with-deps chromium

printf '4/4 Criando o atalho do aplicativo...\n'
chmod +x "$PROJECT_ROOT/scripts/launch-linux.sh" "$PROJECT_ROOT/scripts/stop-linux.sh"

BIN_DIR="$HOME/.local/bin"
APPLICATIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$BIN_DIR" "$APPLICATIONS_DIR"

LAUNCH_WRAPPER="$BIN_DIR/quati-launch"
STOP_WRAPPER="$BIN_DIR/quati-stop"
printf '#!/usr/bin/env bash\nexec %q\n' "$PROJECT_ROOT/scripts/launch-linux.sh" > "$LAUNCH_WRAPPER"
chmod 755 "$LAUNCH_WRAPPER"

ICON_PATH="$PROJECT_ROOT/src/quati/assets/quati-icon.png"
APP_ENTRY="$APPLICATIONS_DIR/quati.desktop"
STOP_ENTRY="$APPLICATIONS_DIR/quati-stop.desktop"
printf '%s\n' \
  '[Desktop Entry]' \
  'Type=Application' \
  'Name=Q.U.A.T.I.' \
  'Comment=Central local de vagas públicas' \
  "Exec=$LAUNCH_WRAPPER" \
  "Icon=$ICON_PATH" \
  'Terminal=false' \
  'Categories=Utility;' > "$APP_ENTRY"
chmod 644 "$APP_ENTRY"
rm -f -- "$STOP_WRAPPER" "$STOP_ENTRY"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi

printf '\nInstalação concluída. Abra Q.U.A.T.I. pelo menu de aplicativos. A porta local fecha quando todas as abas do app são fechadas.\n'
