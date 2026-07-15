# Design: Laboratório de padrões de agentes (Building Effective Agents)

Data: 2026-07-15
Status: Aprovado pelo usuário, aguardando plano de implementação

## Contexto

O repositório `ai-agent-v2` implementa hoje um único agente (spec.md) na raiz:
`agent.py` + `tools.py` + `system_prompt.py`, usando a API do Groq. Esse
agente corresponde ao padrão **Augmented LLM** do artigo
[Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
(LLM + tool use nativo, sem retrieval nem memória persistente).

Em conversa anterior, mapeamos todos os padrões do artigo contra o que existe
no repositório (ver tabela completa no histórico da conversa). Resultado:
Augmented LLM e ACI (Agent-Computer Interface) estão implementados; **Prompt
Chaining, Routing, Parallelization, Orchestrator-Workers e Evaluator-Optimizer
não existem**.

O usuário quer transformar o repositório em um laboratório onde cada padrão
do artigo tem sua própria pasta, executável isoladamente, para fins de estudo
e teste.

## Objetivo

Reorganizar o repositório em `patterns/`, uma pasta por padrão, reaproveitando
o domínio de rastreamento/faturamento de pedidos já existente (mesmas duas
tools: `get_order_status`, `get_billing_details`) em todos os padrões, para
permitir comparação direta de como cada padrão resolve o mesmo problema.

## Fora de escopo

- Testes automatizados (diretriz já estabelecida no projeto: priorizar
  velocidade de desenvolvimento nesta fase).
- Padrão "Agente autônomo" completo (multi-turno, checkpoint humano) — já
  parcialmente coberto por `01_augmented_llm` e não fazia parte do escopo
  aprovado ("todos os 5" padrões de workflow faltantes, não o padrão de
  agente aberto).
- Inicializar repositório git / commit automático — o projeto atualmente não
  é um repositório git; a spec será apenas salva em disco.

## Arquitetura

```
ai-agent-v2/
├── spec.md
├── README.md                    (índice do laboratório)
├── requirements.txt
├── .env / .gitignore
├── shared/
│   ├── tools.py                 (get_order_status, get_billing_details, TOOL_DEFINITIONS, TOOL_REGISTRY)
│   └── groq_client.py           (load_dotenv() + get_client() + MODEL padrão/env)
└── patterns/
    ├── 01_augmented_llm/
    │   ├── README.md
    │   ├── system_prompt.py
    │   └── main.py
    ├── 02_prompt_chaining/
    │   ├── README.md
    │   ├── prompts.py
    │   └── main.py
    ├── 03_routing/
    │   ├── README.md
    │   ├── prompts.py
    │   └── main.py
    ├── 04_parallelization/
    │   ├── README.md
    │   ├── prompts.py
    │   └── main.py
    ├── 05_orchestrator_workers/
    │   ├── README.md
    │   ├── prompts.py
    │   └── main.py
    └── 06_evaluator_optimizer/
        ├── README.md
        ├── prompts.py
        └── main.py
```

### Decisões de compartilhamento de módulos

| Módulo | Compartilhado? | Motivo |
| --- | --- | --- |
| `shared/tools.py` | Sim | Mesmo domínio em todos os padrões (decisão do usuário); reimplementar seria duplicação pura, sem ganho didático. |
| `shared/groq_client.py` | Sim | Boilerplate de infraestrutura (`load_dotenv`, instanciar `Groq()`, resolver `GROQ_MODEL`) sem lógica de domínio. |
| Prompts (`system_prompt.py` / `prompts.py`) | Não — local por pasta | Cada padrão exige uma estrutura de prompt estruturalmente diferente (um único prompt vs. classificador+especializados vs. gerador+avaliador vs. orquestrador+worker). Compartilhar obscureceria a diferença que o laboratório existe para demonstrar. |

### Modo de execução

- `patterns/01_augmented_llm/main.py` — **mantém o loop de chat interativo**
  atual (CLI com `input()`), pois é a implementação principal já validada
  manualmente ao longo do desenvolvimento.
- `patterns/02_..06_.../main.py` — **cenário fixo**: cada script roda um ou
  mais exemplos pré-definidos embutidos no código e imprime cada etapa do
  padrão no console (sem loop interativo), conforme decisão do usuário.

## Componentes por pasta

### `shared/tools.py`
Movido de `tools.py` (raiz) sem alterações de comportamento: mocks
`_TRACKING_DB`/`_BILLING_DB`, funções `get_order_status`/`get_billing_details`
com mensagens de erro acionáveis, `TOOL_DEFINITIONS` (JSON Schema) e
`TOOL_REGISTRY`.

### `shared/groq_client.py` (novo)
Função `get_client() -> Groq` que chama `load_dotenv()` e instancia o
cliente; constante `MODEL` resolvida de `GROQ_MODEL` com fallback para
`llama-3.3-70b-versatile`. Elimina a necessidade de repetir esse boilerplate
em 6 arquivos `main.py`.

### `patterns/01_augmented_llm/`
Conteúdo atual de `agent.py` + `system_prompt.py`, movidos e ajustados para
importar de `shared/`. Comportamento idêntico ao já validado (loop de chat,
`MAX_TOOL_ROUNDS`, logging de rounds, parsing seguro de argumentos).

### `patterns/02_prompt_chaining/`
**Cenário:** "Qual o status e valor faturado do ORD-5541?"
**Fluxo:**
1. Chamada LLM 1 (extração): extrai `order_id` da mensagem livre do usuário,
   retorna JSON estruturado `{"order_id": "..."}`.
2. **Gate programático** (código, não LLM): valida formato `ORD-\d+`. Se
   inválido, aborta a cadeia imediatamente com mensagem clara — não avança
   para as próximas etapas.
3. Chamadas às tools: `get_order_status` + `get_billing_details` com o
   `order_id` validado.
4. Chamada LLM 2 (síntese): combina os dois payloads em uma resposta final,
   respeitando a política de dedução zero (só relata o que veio nos
   payloads).

Também inclui um segundo cenário fixo com entrada como "meu pedido é 12345"
(sem o prefixo `ORD-`) — a etapa de extração retorna `"12345"`, o gate
rejeita por não bater com `ORD-\d+`, e a cadeia é interrompida antes de
qualquer chamada de tool.

### `patterns/03_routing/`
**Cenário:** 4 mensagens de entrada fixas, uma por categoria.
**Fluxo:**
1. Chamada LLM classificadora: decide a categoria — `rastreamento`,
   `faturamento`, `ambiguo` ou `fora_de_escopo`.
2. Roteamento programático (`if/elif` em código) para o prompt especializado
   correspondente:
   - `rastreamento` → prompt focado em status/localização, chama
     `get_order_status`.
   - `faturamento` → prompt focado em valores/impostos, chama
     `get_billing_details`.
   - `ambiguo` → prompt que pergunta ao usuário qual das duas opções deseja.
   - `fora_de_escopo` → prompt educado informando os limites do agente.

### `patterns/04_parallelization/`
**Cenário A (sectioning):** "resumo completo do ORD-5541" → dispara
`get_order_status` e `get_billing_details` **concorrentemente** via
`concurrent.futures.ThreadPoolExecutor`, agrega os dois resultados em uma
única resposta.

**Cenário B (voting):** o script contém uma resposta candidata **fixa e
propositalmente falha** embutida no código (ex: uma resposta que afirma o
peso do pacote sem essa informação existir no payload). Roda a mesma
verificação LLM ("esta resposta inventa algum dado não verificado pelo
payload?") **3 vezes em paralelo** sobre essa candidata fixa e decide por
maioria de votos (2 de 3) se a resposta deve ser bloqueada.

Ambos os cenários rodam no mesmo `main.py`, um após o outro, com prints
identificando qual é sectioning e qual é voting.

### `patterns/05_orchestrator_workers/`
**Cenário:** "Compare o status de entrega do ORD-5541 e do ORD-9902."
**Fluxo:**
1. Chamada LLM orquestradora: identifica dinamicamente quantos e quais
   `order_id` estão no pedido do usuário (não é um número fixo de seções,
   ao contrário do parallelization — decidido pelo conteúdo do input).
2. Para cada `order_id` identificado, delega a uma chamada "worker" (mesmo
   prompt genérico, parametrizado), que executa a tool correspondente e
   retorna o resultado verificado.
3. Chamada LLM orquestradora final: sintetiza a comparação entre os
   resultados dos workers.

Se um worker falhar (ex: pedido inexistente), o orquestrador reporta a
falha para aquele item específico sem interromper a comparação dos demais.

### `patterns/06_evaluator_optimizer/`
**Cenário:** pergunta armadilha (ex: "qual o peso do pacote do ORD-5541?").
**Fluxo:**
1. Chamada LLM geradora: produz uma resposta candidata a partir do payload
   real da tool.
2. Chamada LLM avaliadora: recebe a resposta candidata + o payload bruto e
   critica explicitamente contra os critérios da spec (a resposta inventou
   algum dado ausente do payload? deveria ter pedido esclarecimento e não
   pediu?). Retorna aprovação ou motivo de rejeição.
3. Se rejeitada, o feedback do avaliador é devolvido ao gerador, que produz
   nova tentativa. Loop até aprovar ou atingir `max_iterations` (3).
4. Se o limite for atingido sem aprovação, retorna a última tentativa **com
   aviso explícito** de que não foi totalmente validada (transparência, sem
   alegar sucesso silenciosamente).

Este é o padrão mais diretamente ligado ao valor central do projeto
(proveniência de dados): funciona como um guardrail automatizado para a
própria política anti-alucinação da spec.

## Tratamento de erros (visão geral)

Sem framework de exceptions customizado — cada pasta trata sua falha
característica de forma explícita e visível no output, nunca falhando
silenciosamente:

| Pasta | Falha tratada | Comportamento |
| --- | --- | --- |
| 02_prompt_chaining | `order_id` em formato inválido | Gate aborta a cadeia antes de chamar qualquer tool |
| 03_routing | Entrada não classificável | Cai na rota `ambiguo`, pede esclarecimento |
| 04_parallelization | Uma das chamadas paralelas falha/retorna erro de tool | Resultado parcial reportado, lacuna explicitada |
| 05_orchestrator_workers | Um worker falha (pedido inexistente) | Reporta falha só daquele item, demais seguem |
| 06_evaluator_optimizer | Limite de iterações atingido sem aprovação | Retorna última tentativa com aviso explícito de não-validação |

## Documentação

- `README.md` (raiz) vira índice do laboratório: visão geral do projeto,
  tabela padrão → pasta → status (já existia uma versão dessa tabela,
  produzida em conversa anterior), instruções de setup comuns
  (`requirements.txt`, `.env`).
- O conteúdo detalhado de "práticas de robustez" hoje no README raiz migra
  para `patterns/01_augmented_llm/README.md`, já que é específico da
  implementação daquele padrão.
- Cada pasta `02`–`06` ganha um `README.md` próprio explicando: o padrão
  segundo o artigo, o cenário de demonstração escolhido, e como rodar.

## Testes

Não serão criados testes automatizados nesta fase, conforme diretriz
estabelecida no início do projeto. Validação continua manual/end-to-end,
rodando cada `main.py` e inspecionando o output.
