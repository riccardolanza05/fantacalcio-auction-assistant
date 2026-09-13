"""
Autenticazione minimale per il server d'asta.

Il server ascolta su 0.0.0.0 per farsi raggiungere dal telefono sulla WiFi
di casa: senza password chiunque sulla stessa rete potrebbe aprire la pagina
e vedere le tue stime. Con la password serve fare login una volta per
dispositivo; il token viene salvato sul telefono e resta valido finche' il
server e' acceso, quindi non lo ridigiti durante l'asta.

Nota onesta sui limiti: il traffico e' in HTTP in chiaro sulla rete locale,
quindi questo protegge dalla curiosita' degli altri sulla stessa WiFi, non
da un attacco vero. Per l'uso previsto (un'asta tra amici) e' adeguato; non
riusare questa password altrove.

La password NON ha un default nel codice: va impostata con la variabile
d'ambiente ASTA_PASSWORD prima di avviare il server, es.

    ASTA_PASSWORD="una-password-tua" python app.py
"""
import hmac
import os
import secrets

PASSWORD = os.environ.get("ASTA_PASSWORD")
if not PASSWORD:
    raise RuntimeError(
        "Variabile d'ambiente ASTA_PASSWORD non impostata. "
        "Avvia il server con: ASTA_PASSWORD=\"una-password-tua\" python app.py"
    )

# token di sessione validi, in memoria: si azzerano al riavvio del server
_tokens: set[str] = set()


def verifica_password(candidata: str) -> bool:
    """Confronto a tempo costante, per non perdere tempo con timing attack."""
    if not candidata:
        return False
    return hmac.compare_digest(str(candidata), PASSWORD)


def nuovo_token() -> str:
    token = secrets.token_urlsafe(32)
    _tokens.add(token)
    return token


def token_valido(token: str | None) -> bool:
    if not token:
        return False
    return token in _tokens


def revoca_tutti():
    _tokens.clear()
