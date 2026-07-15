"""Padrão: Orchestrator-Workers.

Uma chamada LLM orquestradora decompõe o pedido livre do usuário em uma
lista DINÂMICA de subtarefas (order_ids a investigar) — o número de
subtarefas não é fixo no código, depende do que o modelo encontrar no
texto de entrada. Cada subtarefa é delegada a uma chamada LLM "worker",
todas usando o MESMO prompt genérico parametrizado apenas pelo order_id.
Por fim, uma segunda chamada LLM orquestradora sintetiza os resumos de
todos os workers em uma resposta final única, tratando com transparência
qualquer worker que tenha falhado (ex: order_id inexistente) sem
interromper o processamento dos demais.

Este padrão não tem loop interativo: roda dois cenários fixos em sequência.

Executar (a partir da raiz do repositório):
    python patterns/05_orchestrator_workers/main.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.groq_client import MODEL, get_client  # noqa: E402
from shared.tools import get_order_status  # noqa: E402
from prompts import (  # noqa: E402
    ORCHESTRATOR_DECOMPOSE_SYSTEM_PROMPT,
    ORCHESTRATOR_SYNTHESIZE_SYSTEM_PROMPT,
    WORKER_SYSTEM_PROMPT,
)


def decompose(client, user_message: str) -> list[str]:
    """Chamada orquestradora 1 — identifica dinamicamente os order_ids mencionados.

    Retorna a lista de order_ids extraída do JSON estruturado. Se a resposta
    do modelo não for um JSON válido ou não tiver o formato esperado, retorna
    lista vazia (o script não deve quebrar por causa de uma resposta
    inesperada do orquestrador).
    """
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": ORCHESTRATOR_DECOMPOSE_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        print(f"  [erro] resposta de decomposição não é JSON válido: {raw!r}")
        return []

    order_ids = parsed.get("order_ids", [])
    if not isinstance(order_ids, list):
        return []
    return [str(order_id) for order_id in order_ids]


def run_worker(client, order_id: str) -> str:
    """Delega uma subtarefa a um worker: consulta o order_id e resume o resultado.

    Usa sempre o mesmo prompt genérico (WORKER_SYSTEM_PROMPT), variando só o
    order_id investigado. Se o pedido não existir, a própria ferramenta
    retorna um payload de erro, que o worker relata como falha específica
    deste item — sem lançar exceção nem interromper os demais workers.
    """
    payload = get_order_status(order_id)
    context = f"order_id a investigar: {order_id}\n\nPayload retornado por get_order_status:\n{payload}"

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": WORKER_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        temperature=0.0,
    )
    return response.choices[0].message.content or ""


def synthesize(client, user_message: str, worker_summaries: dict[str, str]) -> str:
    """Chamada orquestradora 2 — combina os resumos de todos os workers na resposta final."""
    summaries_block = "\n\n".join(
        f"Resumo do worker para {order_id}:\n{summary}"
        for order_id, summary in worker_summaries.items()
    )
    context = (
        f"Pergunta original do usuário: {user_message}\n\n"
        f"{summaries_block}"
    )
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": ORCHESTRATOR_SYNTHESIZE_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        temperature=0.0,
    )
    return response.choices[0].message.content or ""


def run_scenario(client, user_message: str) -> None:
    """Executa o fluxo completo orchestrator-workers para uma mensagem de usuário."""
    print(f"Entrada do usuário: {user_message!r}\n")

    # Etapa 1: orquestrador decompõe dinamicamente em subtarefas (order_ids)
    order_ids = decompose(client, user_message)
    print(f"[orquestrador] decompôs em: {order_ids}")

    if not order_ids:
        print(
            "\n[orquestrador] síntese final -> nenhum order_id identificado "
            "na mensagem; nada a delegar aos workers."
        )
        return

    # Etapa 2: delegação sequencial a um worker por order_id identificado
    worker_summaries: dict[str, str] = {}
    for order_id in order_ids:
        summary = run_worker(client, order_id)
        worker_summaries[order_id] = summary
        print(f"\n[worker {order_id}] -> {summary}")

    # Etapa 3: orquestrador sintetiza os resumos dos workers na resposta final
    answer = synthesize(client, user_message, worker_summaries)
    print(f"\n[orquestrador] síntese final -> {answer}")


def main() -> None:
    client = get_client()

    scenarios = [
        "Compare o status de entrega do ORD-5541 e do ORD-9902.",
        "Compare o ORD-5541 com o ORD-0000.",
    ]

    print(f"Padrão: Orchestrator-Workers (modelo: {MODEL})\n")

    for index, scenario in enumerate(scenarios, start=1):
        print("=" * 70)
        print(f"Cenário {index}/{len(scenarios)}")
        print("=" * 70)
        run_scenario(client, scenario)
        print()


if __name__ == "__main__":
    main()
