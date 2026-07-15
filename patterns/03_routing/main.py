"""Padrão: Routing.

Uma chamada LLM classifica a mensagem do usuário em uma de quatro
categorias (rastreamento, faturamento, ambiguo, fora_de_escopo). O
roteamento em si é feito por código Python puro (if/elif) — sem nenhuma
chamada LLM adicional para decidir o caminho — direcionando para um prompt
especializado por categoria. Cada rota especializada usa a(s) ferramenta(s)
relevante(s) ou responde diretamente, conforme o caso.

Este padrão não tem loop interativo: roda 4 cenários fixos em sequência.

Executar (a partir da raiz do repositório):
    python patterns/03_routing/main.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.groq_client import MODEL, get_client  # noqa: E402
from shared.tools import TOOL_DEFINITIONS, TOOL_REGISTRY  # noqa: E402
from prompts import (  # noqa: E402
    AMBIGUOUS_SYSTEM_PROMPT,
    BILLING_SYSTEM_PROMPT,
    CATEGORIES,
    CLASSIFIER_SYSTEM_PROMPT,
    OUT_OF_SCOPE_SYSTEM_PROMPT,
    TRACKING_SYSTEM_PROMPT,
)

MAX_TOOL_ROUNDS = 5

SCENARIOS = [
    "Qual o status do pedido ORD-5541?",
    "Quanto foi cobrado no pedido ORD-12345?",
    "Me dá informação sobre o pedido ORD-9902",
    "Vocês vendem tênis de corrida?",
]


def classify(client, user_input: str) -> str:
    """Chama o LLM classificador e normaliza/valida a categoria retornada.

    Se a resposta do modelo não bater exatamente com uma das categorias
    esperadas, faz fallback para "ambiguo" — o script nunca deve quebrar
    por causa de uma resposta inesperada do classificador.
    """
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ],
        temperature=0.0,
    )
    raw = (response.choices[0].message.content or "").strip().lower()

    for category in CATEGORIES:
        if category in raw:
            return category

    return "ambiguo"


def run_specialized_route(client, system_prompt: str, user_input: str, use_tools: bool) -> str:
    """Executa a rota especializada, resolvendo tool calls quando aplicável."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input},
    ]

    for round_number in range(1, MAX_TOOL_ROUNDS + 1):
        kwargs = {"model": MODEL, "messages": messages, "temperature": 0.0}
        if use_tools:
            kwargs["tools"] = TOOL_DEFINITIONS
            kwargs["tool_choice"] = "auto"

        response = client.chat.completions.create(**kwargs)
        message = response.choices[0].message

        if not message.tool_calls:
            return message.content or ""

        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ],
            }
        )

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            handler = TOOL_REGISTRY.get(name)
            if handler is None:
                result = json.dumps({"error": f"unknown_tool: {name}"})
            else:
                try:
                    result = handler(**args)
                except TypeError as exc:
                    result = json.dumps({"error": f"invalid_arguments: {exc}"})

            print(
                f"    [round {round_number}/{MAX_TOOL_ROUNDS}] {name}"
                f"({tool_call.function.arguments}) -> {result}"
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": result,
                }
            )

    return (
        f"Não consegui concluir a solicitação dentro do limite de "
        f"{MAX_TOOL_ROUNDS} chamadas de ferramenta."
    )


def route(client, category: str, user_input: str) -> str:
    """Roteamento programático (if/elif em Python puro, sem chamada LLM extra)."""
    if category == "rastreamento":
        return run_specialized_route(client, TRACKING_SYSTEM_PROMPT, user_input, use_tools=True)
    elif category == "faturamento":
        return run_specialized_route(client, BILLING_SYSTEM_PROMPT, user_input, use_tools=True)
    elif category == "ambiguo":
        return run_specialized_route(client, AMBIGUOUS_SYSTEM_PROMPT, user_input, use_tools=False)
    else:  # fora_de_escopo (e qualquer fallback inesperado)
        return run_specialized_route(client, OUT_OF_SCOPE_SYSTEM_PROMPT, user_input, use_tools=False)


def main() -> None:
    client = get_client()

    print(f"Padrão Routing (modelo: {MODEL})")
    print(f"Rodando {len(SCENARIOS)} cenários fixos em sequência.\n")

    for index, user_input in enumerate(SCENARIOS, start=1):
        print("=" * 70)
        category = classify(client, user_input)
        print(f'[cenário {index}] entrada: "{user_input}" -> categoria: {category}')

        answer = route(client, category, user_input)
        print(f"\nResposta: {answer}\n")

    print("=" * 70)


if __name__ == "__main__":
    main()
