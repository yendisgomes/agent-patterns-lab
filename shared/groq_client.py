"""Helper compartilhado de cliente Groq — usado por todas as pastas de patterns/.

Centraliza `load_dotenv()`, a resolução do modelo padrão e a criação do
cliente, evitando repetir esse boilerplate em cada padrão do laboratório.
"""

import os
import sys

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def get_client() -> Groq:
    """Retorna um cliente Groq configurado, ou encerra com mensagem clara."""
    if not os.environ.get("GROQ_API_KEY"):
        sys.exit("Defina a variável de ambiente GROQ_API_KEY antes de executar.")
    return Groq()
