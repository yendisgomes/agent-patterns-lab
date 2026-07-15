"""Conjunto de ferramentas simuladas (poka-yoke) conforme spec.md seção 3.

Cada ferramenta retorna APENAS os campos definidos em seu contrato de API. As
lacunas de dados são intencionais, para permitir validar a proveniência
estrita de dados do agente.
"""

import json

# Bancos mock — campos deliberadamente disjuntos entre rastreamento e faturamento.
_TRACKING_DB = {
    "ORD-5541": {
        "order_id": "ORD-5541",
        "status": "Em rota de entrega",
        "estimated_delivery": "2026-07-15",
        "last_location": "Centro de distribuição - Cajamar/SP",
    },
    "ORD-12345": {
        "order_id": "ORD-12345",
        "status": "Entregue",
        "estimated_delivery": "2026-07-10",
        "last_location": "Destinatário - São Paulo/SP",
    },
    "ORD-9902": {
        "order_id": "ORD-9902",
        "status": "Aguardando coleta",
        "estimated_delivery": "2026-07-20",
        "last_location": "Vendedor - Curitiba/PR",
    },
}

_BILLING_DB = {
    "ORD-5541": {
        "order_id": "ORD-5541",
        "invoice_id": "NF-88123",
        "total_billed": 349.90,
        "taxes": 41.99,
        "currency": "BRL",
        "payment_status": "paid",
    },
    "ORD-12345": {
        "order_id": "ORD-12345",
        "invoice_id": "NF-77001",
        "total_billed": 129.00,
        "taxes": 15.48,
        "currency": "BRL",
        "payment_status": "paid",
    },
}


def get_order_status(order_id: str) -> str:
    record = _TRACKING_DB.get(order_id)
    if record is None:
        return json.dumps(
            {
                "error": "order_not_found",
                "order_id": order_id,
                "message": (
                    f"Nenhum registro de rastreamento encontrado para '{order_id}'. "
                    "O identificador pode estar incorreto ou o pedido pode não "
                    "existir no sistema de logística. Confirme o código com o "
                    "usuário antes de tentar novamente — não reformule ou "
                    "adivinhe uma variação do id."
                ),
            },
            ensure_ascii=False,
        )
    return json.dumps(record, ensure_ascii=False)


def get_billing_details(order_id: str) -> str:
    record = _BILLING_DB.get(order_id)
    if record is None:
        return json.dumps(
            {
                "error": "invoice_not_found",
                "order_id": order_id,
                "message": (
                    f"Nenhuma nota fiscal/fatura encontrada para '{order_id}'. "
                    "Isso pode significar que o pedido ainda não foi faturado, "
                    "que o id está incorreto, ou que a compra não existe. Não "
                    "assuma que o pedido foi pago ou faturado — informe a "
                    "ausência de dados ao usuário e peça confirmação do código."
                ),
            },
            ensure_ascii=False,
        )
    return json.dumps(record, ensure_ascii=False)


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": (
                "Recupera o status de rastreamento de um pedido específico. "
                "AVISO: Esta ferramenta retorna apenas a localização do pacote e o "
                "status da entrega. Ela NÃO fornece detalhes de pagamento, preços, "
                "cupons aplicados ou peso físico da encomenda."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": (
                            "O identificador alfanumérico único do pedido "
                            "(ex: 'ORD-12345'). Proibido inventar se o usuário "
                            "não forneceu."
                        ),
                    }
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_billing_details",
            "description": (
                "Recupera os dados financeiros e de nota fiscal de um pedido "
                "concluído. AVISO: Esta ferramenta serve apenas para verificar "
                "impostos e o valor total faturado. Ela NÃO rastreia o andamento "
                "físico da entrega nem exibe descontos por itens individuais."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "Identificador do pedido (ex: 'ORD-12345').",
                    }
                },
                "required": ["order_id"],
            },
        },
    },
]

TOOL_REGISTRY = {
    "get_order_status": get_order_status,
    "get_billing_details": get_billing_details,
}
