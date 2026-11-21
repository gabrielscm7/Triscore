#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="${1:-$HOME/Desktop}"
TARGET="$DESKTOP_DIR/Triscore.desktop"

mkdir -p "$DESKTOP_DIR"
cat > "$TARGET" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Triscore
Comment=Gestão de Tempos e Classificação Esportiva
Exec=$APP_DIR/TriScore.sh
Icon=$APP_DIR/app/static/img/logo.png
Path=$APP_DIR
Terminal=true
Categories=Office;Sports;
StartupNotify=true
EOF

chmod +x "$TARGET"
if command -v gio >/dev/null 2>&1; then
  gio set "$TARGET" metadata::trusted true 2>/dev/null || true
fi

echo "Atalho criado em: $TARGET"
echo "Se o GNOME pedir, clique com o botao direito no atalho e escolha 'Allow Launching'."
