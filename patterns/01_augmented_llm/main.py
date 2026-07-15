"""Padrão: Augmented LLM.

Agente de Integridade de Integração de API (PoC) — implementação com Groq.

Loop de chat via CLI com tool calling nativo contra o conjunto de ferramentas
simuladas de e-commerce/entrega. É o único padrão do laboratório com loop
interativo — os demais (02-06) rodam cenários fixos.

Executar (a partir da raiz do repositório):
    python patterns/01_augmented_llm/main.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.groq_client import MODEL, get_client  # noqa: E402
from shared.tools import TOOL_DEFINITIONS, TOOL_REGISTRY  # noqa: E402
from system_prompt import SYSTEM_PROMPT  # noqa: E402

MAX_TOOL_ROUNDS = 5


def run_turn(client, messages: list) -> str:
    """Executa um turno do usuário, resolvendo chamadas de ferramenta até o modelo responder."""
    tools_called: list[str] = []

    for round_number in range(1, MAX_TOOL_ROUNDS + 1):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            temperature=0.0,
        )
        message = response.choices[0].message

        if not message.tool_calls:
            messages.append({"role": "assistant", "content": message.content})
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

            tools_called.append(name)
            print(
                f"  [round {round_number}/{MAX_TOOL_ROUNDS}] {name}"
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

    called_summary = ", ".join(tools_called) if tools_called else "nenhuma"
    print(
        f"  [aviso] limite de {MAX_TOOL_ROUNDS} rounds de tool-calling atingido. "
        f"Ferramentas chamadas nesta interação: {called_summary}."
    )
    return (
        f"Não consegui concluir a solicitação dentro do limite de "
        f"{MAX_TOOL_ROUNDS} chamadas de ferramenta. Ferramentas consultadas: "
        f"{called_summary}. Por favor, reformule o pedido ou tente novamente."
    )


def main() -> None:
    client = get_client()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    print(f"Agente de Logística e Pedidos (modelo: {MODEL})")
    print("Digite sua mensagem ('sair' para encerrar).\n")

    while True:
        try:
            user_input = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in {"sair", "exit", "quit"}:
            break

        messages.append({"role": "user", "content": user_input})
        answer = run_turn(client, messages)
        print(f"\nAgente: {answer}\n")


if __name__ == "__main__":
    main()
