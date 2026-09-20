"""
Autenticación con la cuenta de YouTube (una sola vez). Genera token.json, que las subidas
automáticas reutilizarán sin pedir permiso de nuevo (hasta que caduque el token de refresco).

Uso:
    python autenticar_youtube.py

Imprime la URL de autorización en vez de abrir un navegador (para poder completarla
mediante automatización de navegador). Tras dar permiso, la redirección a localhost
la captura este mismo script automáticamente.
"""
import sys
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

BASE = Path(__file__).parent.parent
CLIENT_SECRET = BASE / "client_secret.json"
TOKEN_PATH = BASE / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def main():
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=8765, open_browser=False, prompt="consent")
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    print(f"Token guardado en: {TOKEN_PATH}")


if __name__ == "__main__":
    main()
