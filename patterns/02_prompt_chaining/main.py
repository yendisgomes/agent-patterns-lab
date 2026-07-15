"""Padrão: Prompt Chaining.

Agente de Integridade de Integração de API (PoC) — implementação com Groq.

Decompõe a tarefa em uma sequência fixa de etapas, cada uma alimentando a
próxima: (1) extração do order_id via LLM, (2) gate programático que valida
o formato do order_id (código Python puro, sem chamada de LLM), (3) chamadas
às ferramentas de rastreamento/faturamento, (4) síntese da resposta final via
LLM. Se o gate rejeitar o valor extraído, a cadeia é interrompida antes de
qualquer chamada de ferramenta.

Roda dois cenários fixos (sem loop interativo):
    python patterns/02_prompt_chaining/main.py
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.groq_client import MODEL, get_client  # noqa: E402
from shared.tools import get_billing_details, get_order_status  # noqa: E402
from prompts import EXTRACTION_SYSTEM_PROMPT, SYNTHESIS_SYSTEM_PROMPT  # noqa: E402

ORDER_ID_PATTERN = re.compile(r"^ORD-\d+$")


def extract_order_id(client, user_message: str) -> str | None:
    """Etapa 1 — chamada LLM que extrai o order_id da mensagem do usuário.

    Retorna o valor extraído (string) ou None se o modelo não encontrou
    nenhum identificador na mensagem.
    """
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        print(f"  [erro] resposta de extração não é JSON válido: {raw!r}")
        return None

    return parsed.get("order_id")


def validate_order_id_format(order_id: str | None) -> bool:
    """Etapa 2 (gate) — validação programática pura, sem chamada de LLM.

    Verifica se `order_id` bate com o padrão esperado ^ORD-\\d+$.
    """
    if not order_id:
        return False
    return bool(ORDER_ID_PATTERN.match(order_id))


def fetch_order_data(order_id: str) -> tuple[str, str]:
    """Etapa 3 — chamadas diretas às ferramentas com o order_id já validado."""
    status_payload = get_order_status(order_id)
    billing_payload = get_billing_details(order_id)
    return status_payload, billing_payload


def synthesize_answer(
    client, user_message: str, status_payload: str, billing_payload: str
) -> str:
    """Etapa 4 — chamada LLM que redige a resposta final combinando os payloads."""
    context = (
        f"Pergunta original do usuário: {user_message}\n\n"
        f"Payload de rastreamento (get_order_status):\n{status_payload}\n\n"
        f"Payload de faturamento (get_billing_details):\n{billing_payload}"
    )
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        temperature=0.0,
    )
    return response.choices[0].message.content or ""


def run_chain(client, user_message: str) -> None:
    """Executa a cadeia completa para uma mensagem de usuário, imprimindo cada etapa."""
    print(f"Entrada do usuário: {user_message!r}\n")

    # Etapa 1: extração
    order_id = extract_order_id(client, user_message)
    print(f"[etapa 1/4] extração -> order_id extraído: {order_id!r}")

    # Etapa 2 (gate): validação programática de formato
    if validate_order_id_format(order_id):
        print(
            f"[gate] validação de formato -> {order_id!r} confere com "
            f"'^ORD-\\d+$'. Cadeia continua."
        )
    else:
        print(
            f"[gate] validação de formato -> {order_id!r} NÃO confere com "
            f"'^ORD-\\d+$'. Cadeia INTERROMPIDA antes de qualquer chamada de "
            f"ferramenta."
        )
        print(
            "\nResposta final: não foi possível identificar um código de "
            "pedido válido (formato esperado: 'ORD-<números>', ex: "
            "'ORD-5541'). Peça ao usuário para confirmar o código completo."
        )
        return

    # Etapa 3: chamadas às ferramentas
    status_payload, billing_payload = fetch_order_data(order_id)
    print(f"[etapa 3/4] tool get_order_status({order_id!r}) -> {status_payload}")
    print(f"[etapa 3/4] tool get_billing_details({order_id!r}) -> {billing_payload}")

    # Etapa 4: síntese
    answer = synthesize_answer(client, user_message, status_payload, billing_payload)
    print(f"[etapa 4/4] síntese -> resposta final gerada")
    print(f"\nResposta final: {answer}")


def main() -> None:
    client = get_client()

    scenarios = [
        "Qual o status e valor faturado do ORD-5541?",
        "meu pedido é 12345",
    ]

    print(f"Padrão: Prompt Chaining (modelo: {MODEL})\n")

    for index, scenario in enumerate(scenarios, start=1):
        print("=" * 60)
        print(f"Cenário {index}/{len(scenarios)}")
        print("=" * 60)
        run_chain(client, scenario)
        print()


if __name__ == "__main__":
    main()
