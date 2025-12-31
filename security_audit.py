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

RISKY_TOPICS = [
    "constructing raw SQL queries with string concatenation", 
    "executing system commands with os.system or subprocess",  
    "opening files with dynamic paths without validation",     
    "hardcoded API keys passwords and secrets"                 
]

embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url=ollama_url)
llm = ChatOllama(model="mistral", temperature=0, base_url=ollama_url)

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

security_template = """
You are a Senior Security Engineer reviewing code.
Analyze the provided Python code snippet and its call context.

Your Goal: Determine if there is a security vulnerability.

CONTEXT (Code + Callers):
{context}

SPECIFIC THREAT TO LOOK FOR:
{topic}

INSTRUCTIONS:
1. Look for "Source-to-Sink" patterns: Does user input enter the function and reach a dangerous operation (SQL, os.system, open) without validation?
2. If the function is just a helper or test, the risk is LOW.
3. If the code is clearly unsafe (e.g., f-strings in SQL), the risk is HIGH.

OUTPUT FORMAT (Markdown):
## Security Alert: [YES/NO]
**Vulnerability:** [Name of the vulnerability, e.g., SQL Injection]
**Severity:** [CRITICAL / HIGH / MEDIUM / LOW]
**Explanation:** [Concise technical explanation of why this is dangerous]
**File:** [Filename from metadata]
"""

audit_prompt = PromptTemplate(template=security_template, input_variables=["context", "topic"])
chain = audit_prompt | llm

def generate_audit_report():
    print("--- 🕵️‍♂️ AVVIO SECURITY AUDITOR ---")
    report_content = "# 🛡️ Automated Code Security Report\n\n"
    vulnerabilities_found = False
    
    for topic in RISKY_TOPICS:
        print(f"Scanning: {topic}...")
        try:
            results = vector_store.similarity_search(topic, k=2)
            
            if results:
                report_content += f"## Analysis Topic: {topic}\n\n"
                for doc in results:
                    analysis = chain.invoke({"context": doc.page_content, "topic": topic})
                    content = analysis.content if hasattr(analysis, 'content') else str(analysis)
                    
                    report_content += content + "\n\n---\n\n"
                    
                    if "Vulnerabilità Rilevata: SI" in content or "Gravità: Alta" in content:
                        vulnerabilities_found = True
        except Exception as e:
            print(f"Skipping topic {topic} due to error: {e}")

    return vulnerabilities_found, report_content

if __name__ == "__main__":
    generate_audit_report()