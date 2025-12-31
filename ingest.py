import os
import ast
import dotenv
from neo4j import GraphDatabase
from langchain_ollama import OllamaEmbeddings 

dotenv.load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
AUTH = (os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD", "password_segreta"))
SOURCE_DIR = "./my_legacy_project" 
ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


embeddings_model = OllamaEmbeddings(
    model="nomic-embed-text", 
    base_url=ollama_url
)

class CodeIngestor:
    def __init__(self, uri, auth):
        self.driver = GraphDatabase.driver(uri, auth=auth)
        self._clear_db() 

    def close(self):
        self.driver.close()

    def _clear_db(self):
        print("Pulizia del database...")
        with self.driver.session() as session:
            session.run("DROP INDEX code_index IF EXISTS")
            session.run("MATCH (n) DETACH DELETE n")

    def ingest(self, directory):
        print(f"Scansiono la cartella: {directory}")
        functions_data = []
        
        EXCLUDE_DIRS = {'tests', 'venv', '.git', '__pycache__', 'docs'}

        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, directory)
                    
                    print(f"Processing: {rel_path}...")
                    
                    with open(file_path, "r", encoding="utf-8") as f:
                        try:
                            tree = ast.parse(f.read())
                            file_funcs = self._extract_functions(tree, rel_path)
                            functions_data.extend(file_funcs)
                        except Exception as e:
                            print(f"⚠️ Errore parsing {rel_path}: {e}")

        if not functions_data:
            print("Nessuna funzione trovata.")
            return

        print(f"Trovate {len(functions_data)} funzioni. Inizio Embedding e Caricamento...")
        

        texts_to_embed = [f["text_representation"] for f in functions_data]
        vectors = embeddings_model.embed_documents(texts_to_embed)
        
        for i, func in enumerate(functions_data):
            func["embedding"] = vectors[i]

        print("Salvataggio su Neo4j...")
        with self.driver.session() as session:
            for func in functions_data:
                session.run("""
                    MERGE (f:Function {name: $name, filename: $filename})
                    SET f.code = $code,
                        f.docstring = $docstring,
                        f.embedding = $embedding
                """, **func)
                
                for call in func["calls"]:
                    session.run("""
                        MATCH (caller:Function {name: $caller_name, filename: $filename})
                        MATCH (callee:Function {name: $callee_name})
                        MERGE (caller)-[:CALLS]->(callee)
                    """, caller_name=func["name"], filename=func["filename"], callee_name=call)
        
        self._create_vector_index()
        print("Ingestione completata!")

    def _extract_functions(self, tree, filename):
        funcs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                calls = [n.func.id for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
                code_segment = ast.unparse(node)
                text_rep = f"Function Name: {node.name}\nDocstring: {ast.get_docstring(node)}\nSource Code:\n{code_segment}"
                
                funcs.append({
                    "name": node.name,
                    "filename": filename,
                    "docstring": ast.get_docstring(node) or "",
                    "code": code_segment,
                    "calls": calls,
                    "text_representation": text_rep
                })
        return funcs

    def _create_vector_index(self):
        embedding_dim = 768 
        
        print(f"Creazione indice vettoriale (Dim: {embedding_dim})...")
        with self.driver.session() as session:
            session.run(f"""
                CREATE VECTOR INDEX code_index IF NOT EXISTS
                FOR (f:Function)
                ON (f.embedding)
                OPTIONS {{indexConfig: {{
                 `vector.dimensions`: {embedding_dim},
                 `vector.similarity_function`: 'cosine'
                }}}}
            """)

if __name__ == "__main__":
    
    ingestor = CodeIngestor(URI, AUTH)
    ingestor.ingest(SOURCE_DIR)
    ingestor.close()