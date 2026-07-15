"""Padrão: Parallelization.

Agente de Integridade de Integração de API (PoC) — implementação com Groq.

O artigo "Building Effective Agents" descreve duas variações deste padrão:
Sectioning (quebrar uma tarefa em subtarefas independentes, executá-las em
paralelo e depois combinar os resultados) e Voting (rodar a mesma tarefa
várias vezes em paralelo e agregar as respostas por maioria, para aumentar a
confiança do resultado). Este script demonstra as duas, em cenários fixos e
sequenciais (sem loop interativo), usando `concurrent.futures.ThreadPoolExecutor`
para a concorrência real.

Executar (a partir da raiz do repositório):
    python patterns/04_parallelization/main.py
"""

import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.groq_client import MODEL, get_client  # noqa: E402
from shared.tools import get_billing_details, get_order_status  # noqa: E402
from prompts import SYNTHESIS_SYSTEM_PROMPT, VERIFICATION_SYSTEM_PROMPT  # noqa: E402

ORDER_ID = "ORD-5541"

# Resposta candidata FIXA e propositalmente falha (não gerada por LLM): ela
# inventa um peso de pacote que não existe em nenhum payload real do mock.
CANDIDATE_RESPONSE = (
    "O pedido ORD-5541 pesa 2.3kg e está a caminho, previsão para 15/07."
)

VOTE_ROUNDS = 3


def run_sectioning_scenario(client) -> None:
    """Cenário A — Sectioning: duas consultas independentes em paralelo, \
    seguidas de uma única síntese final."""
    print("=" * 70)
    print("Cenário A (Sectioning)")
    print("=" * 70)
    user_message = f"resumo completo do {ORDER_ID}"
    print(f"Entrada do usuário: {user_message!r}\n")

    # Duas subtarefas independentes: rastreamento e faturamento não dependem
    # uma da outra, então são disparadas concorrentemente no mesmo executor.
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as executor:
        status_future = executor.submit(get_order_status, ORDER_ID)
        billing_future = executor.submit(get_billing_details, ORDER_ID)
        status_payload = status_future.result()
        billing_payload = billing_future.result()
    elapsed = time.perf_counter() - start

    print(f"[paralelo] get_order_status({ORDER_ID!r}) -> {status_payload}")
    print(f"[paralelo] get_billing_details({ORDER_ID!r}) -> {billing_payload}")
    print(f"[paralelo] tempo total das duas chamadas concorrentes: {elapsed:.3f}s\n")

    # Etapa de síntese: uma única chamada LLM combina os dois payloads.
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
    answer = response.choices[0].message.content or ""
    print(f"Resposta final (síntese): {answer}\n")


def verify_candidate(client, real_payload: str, vote_number: int) -> str:
    """Executa uma rodada de verificação de alucinação e imprime o voto."""
    context = (
        f"Payload real (get_order_status):\n{real_payload}\n\n"
        f"Resposta candidata a verificar:\n{CANDIDATE_RESPONSE}"
    )
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": VERIFICATION_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        temperature=0.0,
    )
    raw = (response.choices[0].message.content or "").strip().upper()
    vote = "SIM" if "SIM" in raw else "NAO"
    print(f"  [voto {vote_number}] {vote}")
    return vote


def run_voting_scenario(client) -> None:
    """Cenário B — Voting: a mesma verificação roda 3x em paralelo sobre uma \
    resposta candidata fixa, e o veredito é decidido por maioria."""
    print("=" * 70)
    print("Cenário B (Voting)")
    print("=" * 70)
    print(f"Resposta candidata (fixa, embutida no código): {CANDIDATE_RESPONSE!r}\n")

    real_payload = get_order_status(ORDER_ID)
    print(f"Payload real de referência -> {real_payload}\n")

    print(f"Rodando {VOTE_ROUNDS} verificações em paralelo...")
    with ThreadPoolExecutor(max_workers=VOTE_ROUNDS) as executor:
        futures = [
            executor.submit(verify_candidate, client, real_payload, i)
            for i in range(1, VOTE_ROUNDS + 1)
        ]
        votes = [future.result() for future in futures]

    counts = Counter(votes)
    sim_count = counts["SIM"]
    nao_count = counts["NAO"]
    print(f"\nContagem de votos -> SIM: {sim_count} | NAO: {nao_count}")

    veredito = "bloqueada" if sim_count > nao_count else "aprovada"
    if veredito == "bloqueada":
        print(
            f"Veredito final: {veredito} — maioria dos votos identificou dado "
            "inventado (alucinação) na resposta candidata."
        )
    else:
        print(
            f"Veredito final: {veredito} — maioria dos votos não identificou "
            "dado inventado na resposta candidata."
        )
    print()


def main() -> None:
    client = get_client()

    print(f"Padrão: Parallelization (modelo: {MODEL})\n")

    run_sectioning_scenario(client)
    run_voting_scenario(client)


if __name__ == "__main__":
    main()
