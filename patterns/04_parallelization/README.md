# 04 — Parallelization

## O padrão

Segundo o artigo ["Building Effective Agents"](https://www.anthropic.com/engineering/building-effective-agents)
da Anthropic, o **Parallelization** executa múltiplas chamadas de LLM (ou, no
caso deste laboratório, de ferramentas) simultaneamente, em vez de uma após a
outra, e depois agrega os resultados de forma programática. O artigo descreve
duas variações principais:

- **Sectioning:** uma tarefa é dividida em subtarefas independentes que não
  dependem uma da outra, cada subtarefa é resolvida em paralelo, e os
  resultados são combinados ao final em uma única etapa de agregação. É útil
  quando diferentes partes do trabalho podem ser paralelizadas para reduzir a
  latência total ou para permitir que cada subtarefa use um prompt/ferramenta
  especializado e focado.
- **Voting:** a mesma tarefa é executada várias vezes em paralelo (com o
  mesmo prompt e a mesma entrada), e as respostas obtidas são agregadas por
  maioria de votos (ou algum outro critério de consenso). É útil para
  aumentar a confiança em decisões sensíveis — como verificações de
  segurança ou de conformidade — reduzindo o risco de uma única chamada de
  LLM produzir um resultado equivocado.

## Cenários de demonstração

O script roda os dois cenários em sequência, com separadores visuais claros
no console.

### Cenário A (Sectioning)

Entrada fixa: `"resumo completo do ORD-5541"`.

1. As chamadas `get_order_status("ORD-5541")` e
   `get_billing_details("ORD-5541")` (de `shared/tools.py`) são disparadas
   **concorrentemente** via `concurrent.futures.ThreadPoolExecutor` — são
   subtarefas independentes, já que uma não depende do resultado da outra.
2. O tempo total gasto no bloco paralelo é medido com `time.perf_counter()`
   e impresso no console, evidenciando que as duas chamadas rodaram ao mesmo
   tempo, não sequencialmente.
3. Depois de coletar os dois payloads, uma única chamada LLM de **síntese**
   combina rastreamento e faturamento em uma resposta final ao usuário,
   seguindo a política de **dedução zero** (relata apenas o que veio
   literalmente nos payloads, sem inferir dados ausentes como peso do
   pacote).

### Cenário B (Voting)

O script contém uma resposta candidata **fixa e propositalmente falha**,
embutida diretamente no código (não gerada por LLM):

```python
CANDIDATE_RESPONSE = "O pedido ORD-5541 pesa 2.3kg e está a caminho, previsão para 15/07."
```

Essa resposta inventa um peso de pacote que não existe em nenhum payload
real do mock (`shared/tools.py` não tem campo de peso em nenhum registro).

1. O payload real de `get_order_status("ORD-5541")` é obtido para servir de
   contexto/verdade.
2. A mesma verificação de alucinação ("esta resposta candidata inventa algum
   dado que não está no payload informado? responda apenas SIM ou NAO") é
   executada **3 vezes em paralelo** via `ThreadPoolExecutor`, sobre a mesma
   resposta candidata fixa.
3. Os 3 votos individuais são impressos (ex: `[voto 1] SIM`, `[voto 2] SIM`,
   `[voto 3] NAO`) e agregados por maioria (2 de 3 decide): se a maioria
   disser que a resposta inventa dado, o veredito final é `bloqueada`; caso
   contrário, `aprovada`.

## Como rodar

A partir da raiz do repositório, com `GROQ_API_KEY` configurada em `.env`:

```bash
python patterns/04_parallelization/main.py
```
