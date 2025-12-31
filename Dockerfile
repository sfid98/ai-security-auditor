# Usa Python leggero
FROM python:3.10-slim

# Variabili d'ambiente per evitare file .pyc
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Installa dipendenze sistema (git serve a volte per alcune lib)
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Copia e installa requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il codice sorgente del tool
COPY ingest.py security_audit.py ci_runner.py ./

# Cartella dove monteremo il codice da analizzare
RUN mkdir /target_code

# Quando il container parte, esegue questo script
ENTRYPOINT ["python", "ci_runner.py"]
