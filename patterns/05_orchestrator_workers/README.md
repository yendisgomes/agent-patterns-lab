# 05 — Orchestrator-Workers

## O padrão

Segundo o artigo ["Building Effective Agents"](https://www.anthropic.com/engineering/building-effective-agents)
da Anthropic, no **Orchestrator-Workers** um LLM central (o orquestrador)
analisa a tarefa de entrada, a decompõe dinamicamente em subtarefas e delega
cada uma a um LLM "worker", para depois sintetizar os resultados em uma
resposta final. A diferença crucial em relação ao **Parallelization**
(padrão 04) é que lá o número e a natureza das subtarefas são fixos e
conhecidos de antemão no código (ex: sempre uma chamada de rastreamento +
uma de faturamento, disparadas em paralelo); aqui o **próprio orquestrador
decide, em tempo de execução e a partir do conteúdo do input**, quantas
subtarefas existem e quais são — o código não sabe de antemão se haverá
zero, um, dois ou dez workers a acionar. Essa flexibilidade é o que torna o
padrão adequado para tarefas complexas cujo formato não pode ser previsto
com precisão.

## Cenário de demonstração

Este padrão implementa um fluxo de 3 chamadas LLM (mais N chamadas de
worker, uma por subtarefa) para comparar pedidos:

1. **Orquestrador — decomposição (LLM):** lê o pedido livre do usuário e
   identifica dinamicamente quais `order_id`s foram mencionados, retornando
   uma lista estruturada em JSON (`{"order_ids": [...]}`). O tamanho dessa
   lista não é fixo no código — depende do que o modelo encontrar no texto.
2. **Workers (LLM, um por order_id):** para cada `order_id` identificado, uma
   chamada worker independente usa o MESMO prompt genérico (parametrizado
   apenas pelo `order_id`), chama `get_order_status` (de `shared/tools.py`)
   e produz um resumo verificado daquele pedido específico, seguindo uma
   política de **dedução zero** — nunca inventa dado ausente do payload. Os
   workers rodam sequencialmente (um loop simples); o foco didático aqui é a
   decomposição dinâmica, não a concorrência (já coberta pelo padrão 04).
3. **Orquestrador — síntese final (LLM):** recebe os resumos de todos os
   workers e produz a comparação/resposta final ao usuário. Se algum worker
   tiver sido delegado a um `order_id` inexistente, ele reporta a falha
   específica daquele item (usando a mensagem de erro que a própria
   ferramenta retorna) — essa falha NÃO interrompe o processamento dos
   demais workers, e a síntese final menciona explicitamente qual pedido não
   foi encontrado, ao lado dos resultados dos que foram.

O script roda dois cenários fixos em sequência (sem loop interativo):

- **Cenário 1 (caminho feliz):** `"Compare o status de entrega do ORD-5541 e
  do ORD-9902."` — o orquestrador identifica 2 order_ids, delega a 2
  workers (ambos com sucesso) e sintetiza uma comparação completa.
- **Cenário 2 (com falha parcial):** `"Compare o ORD-5541 com o ORD-0000."`
  — o orquestrador identifica 2 order_ids; o worker do ORD-5541 tem sucesso,
  o worker do ORD-0000 falha (pedido inexistente); a síntese final reflete
  essa falha parcial claramente, sem quebrar o fluxo.

Cada etapa é impressa no console com prefixos didáticos (ex:
`[orquestrador] decompôs em: [...]`, `[worker ORD-5541] -> ...`,
`[orquestrador] síntese final -> ...`), com separadores visuais entre os
dois cenários.

## Como rodar

A partir da raiz do repositório, com `GROQ_API_KEY` configurada em `.env`:

```bash
python patterns/05_orchestrator_workers/main.py
```
