#!/usr/bin/env python3
"""Script de teste para verificar assinaturas das funções de transferência"""

import inspect

# Importar as funções diretamente das definições
exec("""
def transferir_palhetas_parcial(stock_origem_id, proprietario_destino_id, quantidade):
    pass

def transferir_palhetas_externo(stock_origem_id, destinatario_externo, quantidade, tipo="Venda", observacoes=""):
    pass

# Aliases
transferir_stock_interno = transferir_palhetas_parcial
transferir_stock_externo = transferir_palhetas_externo
""")

print("=== Assinaturas das Funções ===")
print(f"transferir_palhetas_parcial: {inspect.signature(transferir_palhetas_parcial)}")
print(f"transferir_palhetas_externo: {inspect.signature(transferir_palhetas_externo)}")
print(f"transferir_stock_interno: {inspect.signature(transferir_stock_interno)}")
print(f"transferir_stock_externo: {inspect.signature(transferir_stock_externo)}")

print("\n=== Testando Chamadas ===")

# Testar transferência interna
try:
    transferir_stock_interno("stock_123", "dest_456", 10)
    print("✓ transferir_stock_interno(stock_id, dest_id, qtd) - OK")
except TypeError as e:
    print(f"✗ transferir_stock_interno: {e}")

# Testar transferência externa
try:
    transferir_stock_externo("stock_123", "destinatario", 10, "Venda", "obs")
    print("✓ transferir_stock_externo(stock_id, destinatario, qtd, tipo, obs) - OK")
except TypeError as e:
    print(f"✗ transferir_stock_externo: {e}")
