# 06 — Evaluator-Optimizer

Segundo o artigo ["Building Effective Agents"](https://www.anthropic.com/engineering/building-effective-agents)
da Anthropic, o padrão Evaluator-Optimizer usa duas chamadas de LLM em loop:
uma que **gera** uma resposta candidata e outra que **avalia** essa resposta
segundo critérios explícitos, devolvendo um veredito e um feedback acionável;
se reprovada, o feedback alimenta uma nova tentativa do gerador, e o ciclo se
repete até a resposta ser aprovada ou um limite de iterações ser atingido. É
o padrão mais indicado quando existe um critério de avaliação claro e
verificável, e quando iterações sucessivas de refinamento produzem ganhos
reais de qualidade — como acontece na revisão de tradução, na crítica
literária, ou (como aqui) na auditoria de veracidade de uma resposta.

## Por que este é o padrão mais ligado ao valor central do projeto

O valor central deste laboratório é a **proveniência estrita de dados**: o
agente nunca deve afirmar algo que não veio literalmente do payload de uma
ferramenta. Nos padrões anteriores, essa disciplina depende inteiramente do
prompt de sistema de um único LLM conseguir segui-la corretamente. O
Evaluator-Optimizer transforma essa política em um **guardrail
automatizado e independente**: mesmo que o gerador alucine ou invente um
dado ausente, um segundo LLM — instruído especificamente com os critérios
anti-alucinação da spec original — audita a resposta contra o payload bruto
antes que ela chegue ao usuário, e força uma correção quando necessário. É a
aplicação mais direta do princípio "confie, mas verifique" à política que
mais importa neste projeto.

## Cenário de demonstração

Pergunta armadilha fixa, sem loop interativo:

> "Qual o peso do pacote do meu pedido ORD-5541?"

O payload real de `get_order_status("ORD-5541")` traz apenas `status`,
`estimated_delivery` e `last_location` — **não há campo de peso**. O fluxo:

1. Consulta `get_order_status("ORD-5541")` e obtém o payload bruto.
2. **Gerador** (prompt propositalmente simples e permissivo, sem a rigidez
   anti-alucinação do padrão 01): recebe a pergunta e o payload, produz uma
   resposta candidata. Por ser mais "ingênuo", ele tem uma chance real de
   inventar um peso estimado na primeira tentativa.
3. **Avaliador** (prompt rigoroso, com os critérios de mundo fechado da
   spec): recebe a pergunta, o payload bruto e a resposta candidata, e
   retorna um JSON estruturado `{"aprovado": bool, "motivo": str}`.
4. Se `aprovado` for `false`, o `motivo` do avaliador vira feedback para uma
   nova chamada do gerador, que tenta corrigir o problema apontado. O loop
   se repete até aprovação ou até `max_iterations = 3`.
5. Se o limite for atingido sem aprovação, a última tentativa é devolvida
   junto com um **aviso explícito** de que ela não foi validada — o script
   nunca alega sucesso silenciosamente.
6. Cada iteração é impressa por completo: a tentativa do gerador e o
   veredito do avaliador (aprovado/rejeitado + motivo).

Em execuções reais contra a API do Groq, é comum ver a primeira tentativa do
gerador inventar uma faixa de peso estimada (ex: "aproximadamente 1,2 kg")
e ser rejeitada pelo avaliador com um motivo específico; a segunda tentativa
então reconhece explicitamente a ausência do dado no payload e é aprovada.

## Como rodar

A partir da raiz do repositório:

```bash
python patterns/06_evaluator_optimizer/main.py
```

Requer `GROQ_API_KEY` configurada em `.env` na raiz (já provisionada neste
repositório).
