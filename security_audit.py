import os
import dotenv
from langchain_community.vectorstores import Neo4jVector
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_classic.prompts import PromptTemplate

# Setup
dotenv.load_dotenv()
URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
AUTH = (os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD", "password_segreta"))
ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# 1. Definizione dei "Sink" (Concetti pericolosi da cercare)
RISKY_TOPICS = [
    "SQL execution database query raw sql",  # SQL Injection
    "subprocess system call os.system exec eval", # Command Injection
    "password secret key token credential hardcoded", # Hardcoded Secrets
    "flask request args form input", # Unsanitized Input handling
]

# 2. Configurazione LLM e Vector Store (Locale)
embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url=ollama_url)
llm = ChatOllama(model="mistral", temperature=0, base_url=ollama_url)

# Query GraphRAG specializzata per la sicurezza
# Cerca chi chiama la funzione vulnerabile per capire se è esposta
security_retrieval_query = """
RETURN
    "Function Name: " + node.name + "\\n" +
    "File: " + node.filename + "\\n" +
    "Code snippet: " + substring(node.code, 0, 300) + "...\\n" +
    "CONTEXT - Callers (Who uses this?): " + 
    reduce(s = "", caller IN [(node)<-[:CALLS]-(c) | c.name] | s + caller + ", ")
    AS text,
    score,
    {source: node.filename} AS metadata
"""

vector_store = Neo4jVector.from_existing_graph(
    embedding=embeddings,
    url=URI,
    username=AUTH[0],
    password=AUTH[1],
    index_name="code_index",
    node_label="Function",
    text_node_properties=["name", "docstring", "code"],
    embedding_node_property="embedding",
    retrieval_query=security_retrieval_query
)

# 3. Il Prompt "Security Engineer"
security_template = """
Sei un esperto Cyber Security Auditor. Analizza il seguente frammento di codice Python e il suo contesto di chiamata (Callers).

OBIETTIVO:
Identifica se esiste una VULNERABILITÀ DI SICUREZZA reale (es. SQL Injection, Command Injection, Hardcoded Secrets).

REGOLE:
1. Se il codice usa variabili in query SQL/System Command senza sanitizzazione, è un rischio ALTO.
2. Se i "Callers" suggeriscono che la funzione è interna (es. usata solo da test o utils), il rischio è BASSO.
3. Se i "Callers" suggeriscono che la funzione è esposta (es. API, Views, Controller), il rischio è CRITICO.

CONTESTO CODICE:
{context}

DOMANDA SPECIFICA:
Analizza questo codice cercando potenziali vulnerabilità relative a: {topic}.

OUTPUT FORMAT (Markdown):
## Vulnerabilità Rilevata: [SI/NO]
**Tipo:** [es. SQL Injection / Safe]
**Gravità:** [Alta/Media/Bassa]
**Analisi:** [Spiegazione tecnica breve del perché è pericoloso o perché è sicuro]
**File:** [Nome File]
"""

audit_prompt = PromptTemplate(template=security_template, input_variables=["context", "topic"])
chain = audit_prompt | llm

def generate_audit_report():
    print("--- 🕵️‍♂️ AVVIO SECURITY AUDITOR ---")
    report_content = "# 🛡️ Automated Code Security Report\n\n"
    vulnerabilities_found = False
    
    for topic in RISKY_TOPICS:
        print(f"Scanning: {topic}...")
        # Nota: assicurati che vector_store sia inizializzato globalmente o passato qui
        try:
            results = vector_store.similarity_search(topic, k=2)
            
            if results:
                report_content += f"## Analysis Topic: {topic}\n\n"
                for doc in results:
                    analysis = chain.invoke({"context": doc.page_content, "topic": topic})
                    content = analysis.content if hasattr(analysis, 'content') else str(analysis)
                    
                    report_content += content + "\n\n---\n\n"
                    
                    # Logica semplice: se l'LLM scrive "Vulnerabilità Rilevata: SI" o "RISK: HIGH"
                    # impostiamo il flag a True. (Puoi renderlo più robusto con JSON output)
                    if "Vulnerabilità Rilevata: SI" in content or "Gravità: Alta" in content:
                        vulnerabilities_found = True
        except Exception as e:
            print(f"Skipping topic {topic} due to error: {e}")

    return vulnerabilities_found, report_content

if __name__ == "__main__":
    generate_audit_report()