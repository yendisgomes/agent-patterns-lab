"""Padrão: Evaluator-Optimizer.

Agente de Integridade de Integração de API (PoC) — implementação com Groq.

Duas chamadas de LLM em loop: um GERADOR produz uma resposta candidata para
a pergunta do usuário, e um AVALIADOR audita essa resposta contra o payload
bruto da ferramenta, aprovando ou reprovando com um motivo específico. Se
reprovada, o motivo vira feedback para uma nova tentativa do gerador — até
aprovar ou atingir o limite de iterações. Cenário fixo, sem loop interativo.

Executar (a partir da raiz do repositório):
    python patterns/06_evaluator_optimizer/main.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.groq_client import MODEL, get_client  # noqa: E402
from shared.tools import get_order_status  # noqa: E402
from prompts import (  # noqa: E402
    EVALUATOR_SYSTEM_PROMPT,
    GENERATOR_RETRY_USER_TEMPLATE,
    GENERATOR_SYSTEM_PROMPT,
)

MAX_ITERATIONS = 3

USER_QUESTION = "Qual o peso do pacote do meu pedido ORD-5541?"
ORDER_ID = "ORD-5541"


def generate_answer(client, question: str, payload: str, feedback: str | None) -> str:
    """Chama o LLM gerador e retorna a resposta candidata (texto livre)."""
    user_content = (
        f"Pergunta do usuário: {question}\n\nDados do pedido (payload JSON):\n{payload}"
    )

    messages = [
        {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    if feedback is not None:
        # Reaproveita o mesmo turno de usuário como histórico e anexa o
        # pedido de correção com o feedback do avaliador.
        messages.append({"role": "assistant", "content": feedback[1]})
        messages.append(
            {
                "role": "user",
                "content": GENERATOR_RETRY_USER_TEMPLATE.format(
                    previous_answer=feedback[1], feedback=feedback[0]
                ),
            }
        )

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.7,
    )
    return response.choices[0].message.content or ""


def evaluate_answer(client, question: str, payload: str, candidate: str) -> dict:
    """Chama o LLM avaliador e retorna o veredito estruturado em dict."""
    user_content = (
        f"Pergunta original do usuário: {question}\n\n"
        f"Payload JSON bruto retornado pela ferramenta:\n{payload}\n\n"
        f"Resposta candidata do gerador:\n{candidate}"
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": EVALUATOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or "{}"
    try:
        verdict = json.loads(raw)
    except json.JSONDecodeError:
        verdict = {"aprovado": False, "motivo": f"Resposta do avaliador não é JSON válido: {raw}"}

    verdict.setdefault("aprovado", False)
    verdict.setdefault("motivo", "Avaliador não forneceu motivo.")
    return verdict


def run_evaluator_optimizer(client, question: str, order_id: str) -> str:
    """Executa o loop gerador/avaliador e retorna a resposta final ao usuário."""
    payload = get_order_status(order_id)
    print(f"Payload bruto consultado ({order_id}):\n  {payload}\n")

    candidate = ""
    feedback: tuple[str, str] | None = None  # (motivo, resposta_anterior)

    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"--- Iteração {iteration}/{MAX_ITERATIONS} ---")

        candidate = generate_answer(client, question, payload, feedback)
        print(f"[gerador] Tentativa:\n  {candidate}\n")

        verdict = evaluate_answer(client, question, payload, candidate)
        aprovado = bool(verdict.get("aprovado"))
        motivo = str(verdict.get("motivo", ""))

        status = "APROVADO" if aprovado else "REJEITADO"
        print(f"[avaliador] Veredito: {status} — motivo: {motivo}\n")

        if aprovado:
            return candidate

        feedback = (motivo, candidate)

    aviso = (
        "[AVISO] Limite de "
        f"{MAX_ITERATIONS} iterações atingido sem aprovação do avaliador. "
        "A resposta abaixo NÃO foi validada e pode conter informações não "
        "confirmadas pelo payload — trate com cautela."
    )
    print(aviso)
    return f"{candidate}\n\n{aviso}"


def main() -> None:
    client = get_client()

    print(f"Padrão Evaluator-Optimizer (modelo: {MODEL})")
    print(f"Cenário fixo: \"{USER_QUESTION}\"\n")

    resposta_final = run_evaluator_optimizer(client, USER_QUESTION, ORDER_ID)

    print("=== Resposta final entregue ao usuário ===")
    print(resposta_final)


if __name__ == "__main__":
    main()
