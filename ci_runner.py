import sys
import os
from ingest import CodeIngestor
from security_audit import generate_audit_report

# Configurazioni da Env Vars (Standard in CI/CD)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687") # 'neo4j' è l'hostname del servizio nel container
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
REPO_PATH = os.getenv("SCAN_TARGET", ".")

def main():
    print("🚀 AVVIO AI SECURITY AUDITOR PIPELINE")
    
    # 1. Ingestione
    try:
        print("--- PHASE 1: Ingestion ---")
        ingestor = CodeIngestor(NEO4J_URI, ("neo4j", NEO4J_PASSWORD))
        ingestor.ingest(REPO_PATH)
        ingestor.close()
    except Exception as e:
        print(f"❌ Errore critico in ingestion: {e}")
        sys.exit(1)

    # 2. Audit
    print("--- PHASE 2: AI Analysis ---")
    # Modifica la tua funzione generate_audit_report per restituire un booleano (True se ci sono rischi)
    # e il testo del report invece di scrivere solo su file.
    has_vulnerabilities, report_text = generate_audit_report() 
    
    # 3. Output per GitHub Actions (o salvataggio artefatto)
    with open("audit_result.md", "w") as f:
        f.write(report_text)
    
    # Stampa un delimitatore speciale per GitHub Actions (se vuoi settare output)
    print(f"::set-output name=report::{report_text}")

    if has_vulnerabilities:
        print("🚨 VULNERABILITÀ CRITICHE RILEVATE!")
        # In un ambiente "soft" potresti uscire con 0 per non bloccare, 
        # ma per un "Quality Gate" serio si esce con 1.
        sys.exit(1) 
    
    print("✅ Nessuna vulnerabilità critica rilevata.")
    sys.exit(0)

if __name__ == "__main__":
    main()
