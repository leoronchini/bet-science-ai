"""Erros fatais de IA — quota/indisponibilidade encerram a aplicacao."""


class AIUnavailableError(RuntimeError):
    """Modelo de IA inacessivel (quota excedida, chave invalida, servico fora).

    Propagada ate o main, que encerra a aplicacao (mesma politica do
    health check de inicializacao).
    """


_FATAL_MARKERS = (
    "429",
    "quota",
    "rate-limit",
    "rate limit",
    "resource_exhausted",
    "resource exhausted",
    "api key not valid",
    "api_key_invalid",
    "permission_denied",
    "503",
    "service unavailable",
)


def is_fatal_ai_error(exc: Exception) -> bool:
    """True se a excecao indica que o modelo esta indisponivel (nao vale retry)."""
    text = str(exc).lower()
    return any(marker in text for marker in _FATAL_MARKERS)
