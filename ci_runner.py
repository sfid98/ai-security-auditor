import sys
import os
from ingest import CodeIngestor
from security_audit import generate_audit_report

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687") 
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
REPO_PATH = os.getenv("SCAN_TARGET", ".")

def main():
    print("🚀 AVVIO AI SECURITY AUDITOR PIPELINE")
    
    try:
        print("--- PHASE 1: Ingestion ---")
        ingestor = CodeIngestor(NEO4J_URI, ("neo4j", NEO4J_PASSWORD))
        ingestor.ingest(REPO_PATH)
        ingestor.close()
    except Exception as e:
        print(f"❌ Errore critico in ingestion: {e}")
        sys.exit(1)

    print("--- PHASE 2: AI Analysis ---")

    has_vulnerabilities, report_text = generate_audit_report() 
    
    with open("audit_result.md", "w") as f:
        f.write(report_text)
    
    print(f"::set-output name=report::{report_text}")

    if has_vulnerabilities:
        print("🚨 VULNERABILITÀ CRITICHE RILEVATE!")
        sys.exit(1) 
    
    print("✅ Nessuna vulnerabilità critica rilevata.")
    sys.exit(0)

if __name__ == "__main__":
    main()
