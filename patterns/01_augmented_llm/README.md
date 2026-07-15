# 01 — Augmented LLM

Implementação da especificação (`spec.md`) usando a API do Groq: um assistente
de logística e gestão de pedidos que prioriza **proveniência estrita de
dados** sobre completude da resposta. O agente prefere dizer "não sei" ou
pedir esclarecimento a arriscar uma alucinação.

## O padrão

O **Augmented LLM** é o bloco de construção mais simples do artigo
[Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents):
uma única chamada de LLM aumentada com tools (e, potencialmente, retrieval e
memória — não usados aqui), sem workflow de múltiplas etapas orquestradas em
código. Este padrão é o que o artigo recomenda como ponto de partida — "comece
simples" — e é por isso que ele é o padrão principal deste laboratório, não
apenas mais um exemplo.

## Sumário

- [Arquitetura](#arquitetura)
- [Fluxo de execução](#fluxo-de-execução)
- [Práticas de robustez implementadas](#práticas-de-robustez-implementadas)
- [Como rodar](#como-rodar)
- [Cenários de validação](#cenários-de-validação)
- [Limitações conhecidas](#limitações-conhecidas)

---

## Arquitetura

Chamada direta ao SDK do Groq com um loop de tool calling nativo — sem
framework de orquestração. Não há múltiplos agentes, roteador ou pipeline de
workflow; a complexidade fica só onde o problema exige.

| Arquivo | Responsabilidade |
| --- | --- |
| `main.py` | Loop de chat via CLI + loop de resolução de tool calls (multi-round) |
| `system_prompt.py` | Prompt de sistema: identidade, protocolo de raciocínio, regras anti-alucinação, tratamento de erro |
| `../../shared/tools.py` | Definições JSON Schema das ferramentas + implementações mock (compartilhado com todo o laboratório) |
| `../../shared/groq_client.py` | Cliente Groq + resolução de modelo (compartilhado com todo o laboratório) |

### Ferramentas simuladas (`shared/tools.py`)

Duas ferramentas com contratos de API **deliberadamente estreitos** (design
poka-yoke — à prova de erro por construção, não por instrução):

- **`get_order_status(order_id)`** — status de rastreamento e localização.
  NÃO retorna dados de pagamento, preço, cupom ou peso.
- **`get_billing_details(order_id)`** — dados fiscais e valor faturado. NÃO
  retorna andamento da entrega nem descontos por item.

Os bancos mock (`_TRACKING_DB` e `_BILLING_DB`) têm **campos e chaves
propositalmente disjuntos**: `ORD-9902` existe só em rastreamento (sem
faturamento), e nenhum registro tem campo de peso. Isso existe para exercitar
o comportamento de lacuna de dados descrito abaixo. Essas mesmas tools mock
são reaproveitadas por todos os outros padrões do laboratório (`patterns/02`
a `patterns/06`), para permitir comparar como cada padrão resolve o mesmo
problema.

---

## Fluxo de execução

```
Usuário digita mensagem
        │
        ▼
messages.append({role: user, content: ...})
        │
        ▼
┌───────────────────────────────────────────┐
│  run_turn() — loop de até MAX_TOOL_ROUNDS  │
│                                             │
│  1. Chama client.chat.completions.create   │
│     (model, messages, tools, tool_choice=  │
│     "auto", temperature=0.0)               │
│                                             │
│  2. Sem tool_calls?                        │
│     → anexa resposta final e retorna       │
│                                             │
│  3. Com tool_calls?                        │
│     → anexa a mensagem do assistant        │
│       (preservando os tool_calls)          │
│     → para cada tool_call:                 │
│         - faz parse seguro do JSON de args │
│         - despacha via TOOL_REGISTRY       │
│         - loga "[round N/M] tool(args)     │
│           -> resultado" no console         │
│         - anexa tool_result com o          │
│           tool_call_id correspondente      │
│     → volta ao passo 1 com o histórico     │
│       atualizado                           │
└───────────────────────────────────────────┘
        │
        ▼
Se o limite de rounds for atingido sem resposta final:
  → loga aviso com as ferramentas já consultadas
  → retorna mensagem explícita de limite ao usuário
        │
        ▼
Resposta impressa no CLI
```

Cada turno reenvia o histórico completo (a API é *stateless*), incluindo o
bloco `<thinking>` e os `tool_calls`/`tool_results` de rounds anteriores
dentro do mesmo turno.

---

## Práticas de robustez implementadas

Esta seção documenta explicitamente **o que foi feito e por quê** para tornar
o agente confiável, seguindo tanto a especificação quanto princípios de
design de agentes de produção.

### 1. Protocolo "pense antes de agir" (`system_prompt.py`)

Todo turno é obrigado a abrir com um bloco `<thinking>` estruturado em 4
passos antes de qualquer chamada de ferramenta ou resposta:

1. **Objetivo do usuário** — qual é o pedido literal?
2. **Compatibilidade da ferramenta** — qual ferramenta atende exatamente a
   isso, sem forçar seu propósito?
3. **Auditoria de parâmetros** — os valores exigidos pelo schema existem de
   fato, ou algum está sendo assumido/adivinhado?
4. **Verificação de dados pós-execução** — o payload retornado realmente
   contém o que o usuário pediu?

Isso torna o raciocínio do modelo **auditável** — o console mostra o processo
de decisão completo, não só o resultado.

### 2. Suposição de mundo fechado / política de dedução zero

O agente é instruído a tratar como inexistente qualquer dado que não veio
literalmente no payload JSON da ferramenta na sessão atual. Ele é
explicitamente proibido de inferir, deduzir ou aproximar valores ausentes
(ex: peso a partir de status de entrega). Isso é reforçado com um exemplo
concreto no próprio prompt.

### 3. Proibição de parâmetros especulativos

O agente nunca pode inventar ou preencher automaticamente um parâmetro
obrigatório ausente (ex: assumir `order_id = "1"`). Se faltar um parâmetro,
a instrução é **não chamar a ferramenta** e pedir o dado ao usuário.

### 4. Desambiguação de pedidos vagos

Quando o pedido do usuário pode mapear para mais de uma ferramenta (ex:
"informações da compra"), o agente é instruído a perguntar explicitamente se
o interesse é rastreamento ou faturamento, em vez de escolher arbitrariamente.

### 5. Design poka-yoke das ferramentas (ACI — Agent-Computer Interface)

Cada `description` de ferramenta documenta explicitamente **o que ela NÃO
retorna**, não só o que retorna. Isso reduz a chance de o modelo assumir
dados adjacentes que a API simplesmente não fornece — o limite fica embutido
na interface, não depende só de o modelo lembrar de uma regra genérica.

### 6. Mensagens de erro acionáveis das ferramentas

Quando um `order_id` não é encontrado, a ferramenta não retorna só um código
de erro — retorna um campo `"message"` em linguagem natural instruindo o
modelo a **confirmar o código com o usuário e nunca adivinhar uma variação
do id**. Isso foi validado end-to-end: ao consultar um pedido inexistente, o
agente chama a ferramenta, recebe o erro estruturado e pede confirmação do
código em vez de inventar dados ou tentar outro id por conta própria.

### 7. Limite de rounds de tool calling (proteção contra loop)

`MAX_TOOL_ROUNDS = 5` limita quantas idas e voltas de tool calling ocorrem
em um único turno. Se o limite for atingido, o agente não falha
silenciosamente: loga um aviso no console e retorna ao usuário uma mensagem
explícita informando quais ferramentas já foram consultadas antes de pedir
para reformular o pedido.

### 8. Parsing seguro de argumentos de tool call

Os argumentos de cada `tool_call` (JSON bruto vindo do modelo) são
decodificados com `try/except json.JSONDecodeError`, e chamadas de ferramenta
com assinatura incompatível são capturadas com `try/except TypeError` —
evitando que uma tool call malformada derrube o processo.

### 9. Determinismo (`temperature=0.0`)

O agente roda com `temperature=0.0` para minimizar variância de resposta em
casos que exigem aderência estrita ao protocolo (parâmetros ausentes, gaps de
dados, desambiguação) — comportamento mais previsível e testável.

### 10. Transparência operacional (logging)

Cada chamada de ferramenta é logada no console no formato
`[round N/M] nome(args) -> resultado`, permitindo auditar exatamente quais
dados o modelo usou para compor a resposta final — inclusive quando o
resultado é um erro.

### 11. Segredos fora do código-fonte

A chave `GROQ_API_KEY` fica em `.env` na raiz do repositório (carregado via
`python-dotenv` em `shared/groq_client.py`), listado em `.gitignore` para
nunca ser versionado. O programa falha imediatamente e com mensagem clara
(`sys.exit(...)`) se a chave não estiver definida, em vez de deixar a
primeira chamada de API falhar de forma opaca.

---

## Como rodar

A partir da raiz do repositório:

```bash
pip install -r requirements.txt
python patterns/01_augmented_llm/main.py
```

A chave `GROQ_API_KEY` já está configurada em `.env` na raiz (obtenha a sua
em https://console.groq.com caso precise trocar). Variável opcional
`GROQ_MODEL` sobrescreve o modelo padrão (`llama-3.3-70b-versatile`).

## Cenários de validação (dados mock)

- `ORD-5541`, `ORD-12345` — existem em rastreamento e faturamento
- `ORD-9902` — existe apenas em rastreamento (lacuna de faturamento)
- "Qual o peso do pacote do ORD-5541?" — payload sem campo de peso → agente
  deve declarar a limitação em vez de inventar
- "Onde está meu pedido?" — sem `order_id` → agente deve pedir o código, não
  adivinhar
- "Me dá informações da compra ORD-12345" — pedido ambíguo → agente deve
  perguntar Rastreamento vs Faturamento
- "Qual o status do pedido ORD-0000?" (inexistente) → agente deve chamar a
  ferramenta, receber o erro estruturado e pedir confirmação do código

Todos os cenários acima foram testados manualmente ponta a ponta contra a API
real do Groq durante o desenvolvimento.

## Limitações conhecidas

- **Sem testes automatizados** — por decisão explícita, para priorizar
  velocidade de desenvolvimento nesta fase de PoC/laboratório. A validação
  até aqui foi manual/end-to-end.
- **Sem checkpoint de supervisão humana** — aceitável neste escopo porque as
  ferramentas são somente leitura (sem efeitos colaterais); seria necessário
  antes de expor ações que alterem estado.
- **Variação de comportamento entre modelos** — o system prompt foi escrito
  com exemplos no estilo Claude (spec original), mas roda sobre
  `llama-3.3-70b-versatile` via Groq. Em alguns casos observados, o modelo
  responde a uma lacuna de dados (ex: peso do pacote) sem chamar a ferramenta
  primeiro — funcionalmente correto (não alucina), mas menos completo que o
  trace de referência da spec, que sempre consulta a ferramenta antes de
  declarar a lacuna.
- **Sessão em memória** — o histórico de conversa existe apenas durante a
  execução do processo; não há persistência entre execuções do CLI.
