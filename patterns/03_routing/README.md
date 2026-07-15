# 03 — Routing

Segundo o artigo ["Building Effective Agents"](https://www.anthropic.com/engineering/building-effective-agents)
da Anthropic, o padrão **Routing** classifica um input em uma categoria e
direciona esse input para uma tarefa especializada subsequente, permitindo
usar prompts, ferramentas e até modelos otimizados para cada tipo de
requisição, em vez de tentar resolver casos muito diferentes com um único
prompt genérico "faz tudo". Neste laboratório, uma primeira chamada LLM atua
como classificador (retornando apenas o rótulo da categoria) e o
direcionamento em si é feito por código Python comum (`if`/`elif`) — sem
nenhuma chamada LLM adicional para decidir o caminho — que escolhe qual
prompt especializado será usado na chamada seguinte.

## Fluxo

1. **Classificador:** uma chamada ao LLM recebe a mensagem do usuário e
   responde com exatamente uma palavra entre `rastreamento`, `faturamento`,
   `ambiguo` ou `fora_de_escopo`. A resposta é normalizada
   (`.strip().lower()`) e validada contra esse conjunto; se o modelo
   responder algo fora do esperado, o script nunca quebra — faz fallback
   para `ambiguo`.
2. **Roteamento programático:** com base na categoria, o código Python
   decide qual prompt especializado usar:
   - `rastreamento` → prompt focado em status/localização, chama a
     ferramenta `get_order_status`.
   - `faturamento` → prompt focado em valores/impostos, chama a ferramenta
     `get_billing_details`.
   - `ambiguo` → prompt que pergunta ao usuário se ele quer Rastreamento ou
     Faturamento (não chama nenhuma ferramenta).
   - `fora_de_escopo` → prompt que informa educadamente que o agente só
     lida com pedidos/rastreamento/faturamento (não chama nenhuma
     ferramenta).

## Cenários de demonstração

O script `main.py` roda 4 cenários fixos em sequência (sem loop
interativo):

1. `"Qual o status do pedido ORD-5541?"` → categoria esperada:
   `rastreamento`.
2. `"Quanto foi cobrado no pedido ORD-12345?"` → categoria esperada:
   `faturamento`.
3. `"Me dá informação sobre o pedido ORD-9902"` → categoria esperada:
   `ambiguo` (não há palavra-chave de status/entrega nem de valor/pagamento
   na mensagem).
4. `"Vocês vendem tênis de corrida?"` → categoria esperada:
   `fora_de_escopo`.

Para cada cenário, o script imprime a categoria decidida pelo classificador
e a resposta final produzida pela rota especializada correspondente.

## Como rodar

A partir da raiz do repositório:

```bash
python patterns/03_routing/main.py
```

Requer `GROQ_API_KEY` configurada em `.env` na raiz do repositório (já
tratado pelo helper `shared/groq_client.py`).
