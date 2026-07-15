# 02 — Prompt Chaining

## O padrão

Segundo o artigo ["Building Effective Agents"](https://www.anthropic.com/engineering/building-effective-agents)
da Anthropic, o **Prompt Chaining** decompõe uma tarefa em uma sequência fixa
de etapas menores, onde a saída de uma etapa alimenta a entrada da próxima.
Cada chamada ao LLM fica focada em um único subproblema — o que tende a
produzir resultados mais precisos do que pedir tudo em uma única chamada —,
e o artigo destaca a possibilidade de inserir **gates programáticos** entre
as etapas: pontos de checagem em código puro (sem LLM) que validam o
progresso e podem interromper a cadeia antecipadamente caso algo esteja fora
do esperado, evitando desperdiçar chamadas subsequentes com uma entrada já
inválida.

## Cenário de demonstração

Este padrão implementa uma cadeia de 4 etapas para responder perguntas sobre
pedidos:

1. **Extração (LLM 1):** interpreta a mensagem livre do usuário e extrai o
   `order_id` mencionado, respondendo em JSON estruturado.
2. **Gate (código Python puro):** valida se o `order_id` extraído bate com o
   formato esperado `^ORD-\d+$`. Se não bater, a cadeia é **interrompida
   imediatamente**, antes de qualquer chamada de ferramenta.
3. **Tools:** com o `order_id` validado, chama `get_order_status` e
   `get_billing_details` (de `shared/tools.py`).
4. **Síntese (LLM 2):** combina os dois payloads retornados pelas ferramentas
   em uma resposta final ao usuário, seguindo uma política de **dedução
   zero** — relata apenas o que veio nos payloads, e diz explicitamente
   quando uma informação não está disponível, em vez de inferir ou inventar.

O script roda dois cenários fixos em sequência (sem loop interativo):

- **Cenário 1 (caminho feliz):** `"Qual o status e valor faturado do
  ORD-5541?"` — o `order_id` extraído (`ORD-5541`) passa no gate, as
  ferramentas são chamadas e a cadeia chega até a síntese final.
- **Cenário 2 (gate rejeitando):** `"meu pedido é 12345"` — a extração
  retorna `12345` (sem o prefixo `ORD-`), o gate rejeita esse valor por não
  bater com o padrão esperado, e a cadeia é interrompida **antes** de
  qualquer chamada de ferramenta.

Cada etapa é impressa no console de forma didática (ex:
`[etapa 1/4] extração -> ...`, `[gate] validação de formato -> ...`), com
separadores visuais entre os cenários.

## Como rodar

A partir da raiz do repositório, com `GROQ_API_KEY` configurada em `.env`:

```bash
python patterns/02_prompt_chaining/main.py
```
