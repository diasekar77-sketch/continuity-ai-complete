from datetime import datetime, timezone

from app.rag import document_loader, text_splitter


def ingest_document(conn, store, filename: str, data: bytes, category: str | None = None) -> dict:
    text = document_loader.load_text(filename, data)
    chunks = text_splitter.split_policy(text)
    if not chunks:
        raise ValueError("No readable text found in the document")
    cur = conn.execute("INSERT INTO documents (filename, category, uploaded_at) VALUES (?,?,?)",
                       (filename, category, datetime.now(timezone.utc).isoformat(timespec="seconds")))
    doc_id = cur.lastrowid
    n = store.add_chunks(doc_id, filename, category or "", chunks)
    conn.execute("UPDATE documents SET chunk_count=? WHERE document_id=?", (n, doc_id))
    conn.commit()
    return {"document_id": doc_id, "filename": filename, "category": category, "chunks": n}


def list_documents(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM documents ORDER BY document_id DESC")]
