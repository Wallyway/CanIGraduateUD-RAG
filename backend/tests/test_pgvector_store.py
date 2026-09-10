import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Base, DocumentItem, DocumentChunk, VectorType
from app.services.vector_store import VectorStoreService, _cosine_distance


@pytest.fixture
def sqlite_test_db(monkeypatch):
    """Provides an isolated in-memory SQLite database for vector store testing."""
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    monkeypatch.setattr("app.db.session.engine", test_engine)
    monkeypatch.setattr("app.db.session.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.services.vector_store.engine", test_engine)
    monkeypatch.setattr("app.services.vector_store.SessionLocal", TestingSessionLocal)

    yield TestingSessionLocal

    Base.metadata.drop_all(bind=test_engine)


def test_cosine_distance_math():
    """Verifies that mathematical cosine distance calculations match expected geometry."""
    # Identical vectors -> cosine similarity = 1.0, distance = 0.0
    v1 = [1.0, 0.0, 0.0]
    assert abs(_cosine_distance(v1, v1)) < 1e-6

    # Orthogonal vectors -> cosine similarity = 0.0, distance = 1.0
    v2 = [0.0, 1.0, 0.0]
    assert abs(_cosine_distance(v1, v2) - 1.0) < 1e-6

    # Opposite vectors -> cosine similarity = -1.0, distance = 2.0
    v3 = [-1.0, 0.0, 0.0]
    assert abs(_cosine_distance(v1, v3) - 2.0) < 1e-6

    # Empty or mismatched vectors
    assert _cosine_distance([], [1.0]) == 1.0
    assert _cosine_distance([0.0, 0.0], [0.0, 0.0]) == 1.0


def test_vector_type_serialization():
    """Verifies that VectorType serializes and deserializes lists of floats cleanly."""
    vt = VectorType(dim=384)

    class MockDialect:
        name = "sqlite"

    # Process bind param
    data = [0.1, 0.2, 0.3]
    serialized = vt.process_bind_param(data, MockDialect())
    assert isinstance(serialized, str)
    assert "[0.1, 0.2, 0.3]" in serialized

    # Process result value
    deserialized = vt.process_result_value(serialized, MockDialect())
    assert isinstance(deserialized, list)
    assert len(deserialized) == 3
    assert abs(deserialized[0] - 0.1) < 1e-5


def test_vector_store_add_and_query(sqlite_test_db, monkeypatch):
    """Tests inserting chunks and querying them ordered by cosine similarity."""
    service = VectorStoreService()

    # Create parent document
    db = sqlite_test_db()
    doc = DocumentItem(
        title="Acuerdo de Grados",
        filename="acuerdo_038.pdf",
        file_path="/tmp/fake.pdf"
    )
    db.add(doc)
    db.commit()
    doc_id = doc.id
    db.close()

    # Mock embeddings to be deterministic
    def mock_get_embeddings(texts):
        res = []
        for t in texts:
            tl = t.lower()
            if "pasantia" in tl or "pasantía" in tl:
                vec = [1.0] + [0.0] * 1535
            elif "ingles" in tl or "inglés" in tl:
                vec = [0.0, 1.0] + [0.0] * 1534
            else:
                vec = [0.0] * 1536
            res.append(vec)
        return res

    monkeypatch.setattr("app.services.vector_store.llm_adapter.get_embeddings", mock_get_embeddings)

    chunks = [
        "Requisitos para la modalidad de pasantía institucional.",
        "Requisito de acreditación de nivel de inglés B2 para grado."
    ]
    metas = [
        {"document_id": doc_id, "article": "Artículo 10", "title": "Acuerdo de Grados"},
        {"document_id": doc_id, "article": "Artículo 25", "title": "Acuerdo de Grados"}
    ]
    ids = [f"chunk_{doc_id}_0", f"chunk_{doc_id}_1"]

    service.add_chunks(chunks, metas, ids)
    assert service.get_total_chunks() == 2

    # Query for pasantia -> chunk_0 should have distance ~0.0
    results_pasantia = service.query("informacion sobre pasantia", n_results=2)
    assert len(results_pasantia) == 2
    assert results_pasantia[0]["id"] == f"chunk_{doc_id}_0"
    assert "pasantía" in results_pasantia[0]["content"]
    assert results_pasantia[0]["distance"] < 0.1

    # Query for ingles -> chunk_1 should have distance ~0.0
    results_ingles = service.query("como certifico mi ingles", n_results=2)
    assert len(results_ingles) == 2
    assert results_ingles[0]["id"] == f"chunk_{doc_id}_1"
    assert "inglés" in results_ingles[0]["content"]


def test_vector_store_filtering_and_deletion(sqlite_test_db, monkeypatch):
    """Tests metadata filtering, article-level deletion, and document deletion."""
    service = VectorStoreService()

    db = sqlite_test_db()
    doc1 = DocumentItem(title="Doc 1", filename="doc1.pdf", file_path="/tmp/doc1.pdf")
    doc2 = DocumentItem(title="Doc 2", filename="doc2.pdf", file_path="/tmp/doc2.pdf")
    db.add_all([doc1, doc2])
    db.commit()
    d1_id, d2_id = doc1.id, doc2.id
    db.close()

    monkeypatch.setattr("app.services.vector_store.llm_adapter.get_embeddings", lambda texts: [[0.1] * 1536 for _ in texts])

    service.add_chunks(
        chunks=["Art 1 contenido", "Art 2 contenido"],
        metadatas=[{"document_id": d1_id, "article": "Artículo 1"}, {"document_id": d1_id, "article": "Artículo 2"}],
        ids=[f"chunk_{d1_id}_1", f"chunk_{d1_id}_2"]
    )
    service.add_chunks(
        chunks=["Doc 2 contenido"],
        metadatas=[{"document_id": d2_id, "article": "Artículo 5"}],
        ids=[f"chunk_{d2_id}_1"]
    )

    assert service.get_total_chunks() == 3

    # Query with filter_criteria for doc1
    filtered = service.query("consulta", n_results=5, filter_criteria={"document_id": d1_id})
    assert len(filtered) == 2
    assert all(r["metadata"]["document_id"] == d1_id for r in filtered)

    # Get chunks by document ID
    d1_chunks = service.get_chunks_by_document_id(d1_id)
    assert len(d1_chunks) == 2

    # Delete only Articulo 1
    deleted = service.delete_chunks_by_article(d1_id, ["Artículo 1"])
    assert f"chunk_{d1_id}_1" in deleted
    assert service.get_total_chunks() == 2

    # Delete doc2 completely
    service.delete_by_document_id(d2_id)
    assert service.get_total_chunks() == 1

    # Reset
    service.reset()
    assert service.get_total_chunks() == 0


def test_cascade_delete_from_parent_document(sqlite_test_db, monkeypatch):
    """Verifies that deleting a DocumentItem automatically cascades and deletes its DocumentChunks."""
    service = VectorStoreService()

    db = sqlite_test_db()
    doc = DocumentItem(title="Parent", filename="p.pdf", file_path="/tmp/p.pdf")
    db.add(doc)
    db.commit()
    doc_id = doc.id

    monkeypatch.setattr("app.services.vector_store.llm_adapter.get_embeddings", lambda texts: [[0.5] * 1536 for _ in texts])

    service.add_chunks(
        chunks=["Texto del hijo"],
        metadatas=[{"document_id": doc_id, "article": "Art 1"}],
        ids=[f"child_{doc_id}"]
    )
    assert service.get_total_chunks() == 1

    # Delete parent document from DB
    doc_to_delete = db.query(DocumentItem).filter(DocumentItem.id == doc_id).first()
    db.delete(doc_to_delete)
    db.commit()
    db.close()

    # The chunk must be cascade-deleted!
    assert service.get_total_chunks() == 0
