"""
Script utilitário para verificar as credenciais Basic Auth do InvGate.
Uso: python get_token.py
"""
from services.invgate import _get_auth, INVGATE_ENV

if __name__ == "__main__":
    print(f"Credenciais InvGate [{INVGATE_ENV}]...\n")
    auth = _get_auth()
    print(f"Username: {auth.username}")
    print(f"API Key:  {auth.password[:8]}...")
