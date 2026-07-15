# Laboratório de Padrões de Agentes de IA

Laboratório de estudo e teste que implementa, no mesmo domínio (rastreamento
e faturamento de pedidos, baseado em `spec.md`), todos os padrões descritos
no artigo
[Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
da Anthropic, usando a API do Groq. Cada padrão vive em sua própria pasta
dentro de `patterns/`, é independente e executável isoladamente — o objetivo
é permitir comparar lado a lado como cada padrão resolveria o mesmo
problema.

O valor central que atravessa todos os padrões é o mesmo da spec original:
**proveniência estrita de dados** — o agente nunca deve afirmar algo que não
veio literalmente do payload de uma ferramenta.

## Padrões implementados

| Pasta | Padrão | O que demonstra |
| --- | --- | --- |
| [`patterns/01_augmented_llm/`](patterns/01_augmented_llm/) | Augmented LLM | LLM + tool calling nativo, sem workflow — o ponto de partida recomendado pelo artigo. CLI interativo. |
| [`patterns/02_prompt_chaining/`](patterns/02_prompt_chaining/) | Prompt Chaining | Decomposição em etapas sequenciais (extração → gate programático → tools → síntese) |
| [`patterns/03_routing/`](patterns/03_routing/) | Routing | Classificação prévia + prompts especializados por categoria |
| [`patterns/04_parallelization/`](patterns/04_parallelization/) | Parallelization | Sectioning (subtarefas fixas em paralelo) + Voting (consenso por maioria) |
| [`patterns/05_orchestrator_workers/`](patterns/05_orchestrator_workers/) | Orchestrator-Workers | Decomposição dinâmica (nº de subtarefas decidido em runtime) + delegação a workers |
| [`patterns/06_evaluator_optimizer/`](patterns/06_evaluator_optimizer/) | Evaluator-Optimizer | Loop gerador↔avaliador — guardrail automatizado da política anti-alucinação |

Cada pasta tem seu próprio `README.md` detalhando o padrão, o cenário de
demonstração e como rodar. `01_augmented_llm` é a implementação principal
(CLI interativo); as demais (`02` a `06`) rodam cenários fixos embutidos no
código, imprimindo cada etapa do padrão no console — pensadas para leitura e
teste rápido, não para uso interativo.

### Padrões do artigo fora de escopo deste laboratório

- **Retrieval / memória persistente** — nenhum padrão usa busca em base de
  conhecimento ou memória entre execuções; todo o estado vive em memória
  durante o processo.
- **Agente autônomo aberto (multi-turno, checkpoint humano)** — `01` tem um
  loop de tool-calling *dentro de um turno* com condição de parada, mas não
  planejamento aberto entre múltiplos turnos nem aprovação humana entre
  ações. Não fazia parte do escopo dos "5 padrões faltantes" priorizado para
  este laboratório.

## Estrutura do repositório

```
agent-patterns-lab/
├── spec.md                      # especificação original do agente
├── README.md                    # este arquivo — índice do laboratório
├── requirements.txt
├── .env                         # GROQ_API_KEY (não versionado)
├── docs/superpowers/specs/      # design docs do laboratório
├── shared/
│   ├── tools.py                 # get_order_status, get_billing_details, TOOL_DEFINITIONS, TOOL_REGISTRY
│   └── groq_client.py           # get_client(), MODEL — compartilhado por todos os padrões
└── patterns/
    ├── 01_augmented_llm/
    ├── 02_prompt_chaining/
    ├── 03_routing/
    ├── 04_parallelization/
    ├── 05_orchestrator_workers/
    └── 06_evaluator_optimizer/
```

### O que é compartilhado entre os padrões, e por quê

| Módulo | Compartilhado? | Motivo |
| --- | --- | --- |
| `shared/tools.py` | Sim | Mesmo domínio (rastreamento/faturamento) em todos os padrões — reimplementar seria duplicação pura, sem ganho didático. |
| `shared/groq_client.py` | Sim | Boilerplate de infraestrutura (`load_dotenv`, cliente Groq, resolução de `GROQ_MODEL`), sem lógica de domínio. |
| Prompts de sistema | Não — locais por pasta | Cada padrão exige uma estrutura de prompt estruturalmente diferente (um único prompt vs. classificador+especializados vs. gerador+avaliador vs. orquestrador+worker). Compartilhar obscureceria justamente a diferença que o laboratório existe para demonstrar. |

## Como rodar

```bash
pip install -r requirements.txt
python patterns/01_augmented_llm/main.py        # CLI interativo
python patterns/02_prompt_chaining/main.py      # cenário fixo
python patterns/03_routing/main.py              # cenário fixo
python patterns/04_parallelization/main.py      # cenário fixo
python patterns/05_orchestrator_workers/main.py # cenário fixo
python patterns/06_evaluator_optimizer/main.py  # cenário fixo
```

Sempre a partir da raiz do repositório. `GROQ_API_KEY` já está configurada em
`.env` (obtenha a sua em https://console.groq.com caso precise trocar).
`GROQ_MODEL` é opcional e sobrescreve o modelo padrão
(`llama-3.3-70b-versatile`).

### Nota técnica — Groq e `tool_choice`

A API do Groq retorna `400 BadRequestError` se `tools`/`tool_choice` forem
passados explicitamente como `None` em uma chamada sem ferramentas — omita
esses parâmetros completamente (não os passe como `None`) quando a chamada
não usa tool calling. Isso apareceu ao implementar o padrão `03_routing`
(rotas que não chamam nenhuma ferramenta) e vale para qualquer chamada nova
adicionada a este laboratório.

## Diretrizes do laboratório

- **Sem testes automatizados** — decisão explícita do projeto, para
  priorizar velocidade de desenvolvimento. Validação é manual/end-to-end,
  rodando cada `main.py` e inspecionando o output.
- **Toda a prosa em pt-BR** — comentários, docstrings, prints e READMEs.
  Nomes de função/variável/parâmetro seguem convenção de código em inglês
  (`order_id`, `get_order_status`, etc.).
- **Design doc** — o design completo deste laboratório (decisões de
  arquitetura, cenários por padrão, tratamento de erro) está em
  [`docs/superpowers/specs/2026-07-15-agent-patterns-lab-design.md`](docs/superpowers/specs/2026-07-15-agent-patterns-lab-design.md).
