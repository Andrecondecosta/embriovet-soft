#!/usr/bin/env python3
"""Script de teste para verificar configuração antes do deploy"""

import os
import sys

def verificar_arquivos():
    """Verifica se todos os arquivos necessários existem"""
    print("📁 Verificando arquivos...")
    
    arquivos_necessarios = [
        'app.py',
        'requirements_streamlit.txt',
        'render.yaml',
        'setup_database.py',
        'start.sh',
        '.streamlit/config.toml'
    ]
    
    faltando = []
    for arquivo in arquivos_necessarios:
        if os.path.exists(arquivo):
            print(f"  ✅ {arquivo}")
        else:
            print(f"  ❌ {arquivo} - FALTANDO")
            faltando.append(arquivo)
    
    if faltando:
        print(f"\n❌ Arquivos faltando: {', '.join(faltando)}")
        return False
    
    print("\n✅ Todos os arquivos necessários estão presentes")
    return True

def verificar_requirements():
    """Verifica se requirements.txt está correto"""
    print("\n📦 Verificando requirements...")
    
    try:
        with open('requirements_streamlit.txt', 'r') as f:
            conteudo = f.read()
        
        pacotes_necessarios = [
            'streamlit',
            'pandas',
            'psycopg2-binary',
            'bcrypt',
            'python-dotenv',
            'reportlab'
        ]
        
        faltando = []
        for pacote in pacotes_necessarios:
            if pacote in conteudo:
                print(f"  ✅ {pacote}")
            else:
                print(f"  ❌ {pacote} - FALTANDO")
                faltando.append(pacote)
        
        if faltando:
            print(f"\n⚠️ Pacotes faltando no requirements: {', '.join(faltando)}")
            return False
        
        print("\n✅ Requirements.txt está correto")
        return True
        
    except Exception as e:
        print(f"\n❌ Erro ao ler requirements: {e}")
        return False

def verificar_scripts_sql():
    """Verifica se scripts SQL existem"""
    print("\n🗄️ Verificando scripts SQL...")
    
    scripts = [
        'adicionar_campos_proprietarios.sql',
        'adicionar_constraint_nome_unico.sql',
        'adicionar_auditoria_stock.sql'
    ]
    
    existem = []
    for script in scripts:
        if os.path.exists(script):
            print(f"  ✅ {script}")
            existem.append(script)
        else:
            print(f"  ⚠️ {script} - Opcional")
    
    if existem:
        print(f"\n✅ {len(existem)} script(s) SQL encontrado(s)")
    
    return True

def verificar_permissoes():
    """Verifica permissões de execução"""
    print("\n🔐 Verificando permissões...")
    
    if os.path.exists('start.sh'):
        if os.access('start.sh', os.X_OK):
            print("  ✅ start.sh é executável")
            return True
        else:
            print("  ⚠️ start.sh não é executável")
            print("  Execute: chmod +x start.sh")
            return False
    
    return True

def verificar_render_yaml():
    """Verifica configuração do render.yaml"""
    print("\n⚙️ Verificando render.yaml...")
    
    try:
        with open('render.yaml', 'r') as f:
            conteudo = f.read()
        
        checks = {
            'services:': 'Definição de serviços',
            'type: pserv': 'PostgreSQL database',
            'type: web': 'Web service',
            'buildCommand:': 'Comando de build',
            'startCommand:': 'Comando de start',
            'DATABASE_URL': 'Variável DATABASE_URL'
        }
        
        for check, descricao in checks.items():
            if check in conteudo:
                print(f"  ✅ {descricao}")
            else:
                print(f"  ❌ {descricao} - FALTANDO")
        
        print("\n✅ render.yaml verificado")
        return True
        
    except Exception as e:
        print(f"\n❌ Erro ao ler render.yaml: {e}")
        return False

def main():
    print("="*60)
    print("🚀 VERIFICAÇÃO PRÉ-DEPLOY - EMBRIOVET")
    print("="*60)
    print()
    
    resultados = []
    
    resultados.append(verificar_arquivos())
    resultados.append(verificar_requirements())
    resultados.append(verificar_scripts_sql())
    resultados.append(verificar_permissoes())
    resultados.append(verificar_render_yaml())
    
    print()
    print("="*60)
    
    if all(resultados):
        print("✅ TUDO OK! Pronto para deploy no Render")
        print()
        print("📝 Próximos passos:")
        print("1. git add .")
        print("2. git commit -m 'Preparar para deploy'")
        print("3. git push origin main")
        print("4. Acessar Render → New → Blueprint")
        print("5. Conectar repositório")
        print()
        print("📖 Consulte DEPLOY_RENDER.md para instruções detalhadas")
        return 0
    else:
        print("❌ ERROS ENCONTRADOS! Corrija antes de fazer deploy")
        return 1

if __name__ == "__main__":
    sys.exit(main())
