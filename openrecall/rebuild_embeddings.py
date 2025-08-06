# rebuild_embeddings.py

import numpy as np
from openrecall.database import get_all_entries
from openrecall.nlp import get_embedding
from sqlalchemy.orm import sessionmaker
from openrecall.database import engine, Entry
import sys
import os

# Adiciona o diretório do projeto ao sys.path
project_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'C:\temp\openrecall_env\Lib\site-packages\openrecall'))
sys.path.insert(0, project_path)

# Agora podes importar
from openrecall.database import get_all_entries
from openrecall.nlp import get_embedding
from sqlalchemy.orm import sessionmaker
from openrecall.database import engine, Entry

# Setup session
Session = sessionmaker(bind=engine)
session = Session()

print("Rebuilding embeddings for all entries...\n")

entries = session.query(Entry).all()
total = len(entries)

updated = 0
for i, entry in enumerate(entries):
    if not entry.text:
        print(f"Skipping entry {i} (no text)...")
        continue

    try:
        # Recalculate embedding
        emb = get_embedding(entry.text)

        # Store as binary buffer
        entry.embedding = emb.astype(np.float64).tobytes()
        updated += 1

        if i % 10 == 0 or i == total - 1:
            print(f"[{i+1}/{total}] Updated embedding for entry with timestamp {entry.timestamp}")

    except Exception as e:
        print(f"❌ Error updating entry {i} ({entry.timestamp}): {e}")

# Commit all updates
session.commit()
session.close()

print(f"\n✅ Done. {updated}/{total} entries updated successfully.")
