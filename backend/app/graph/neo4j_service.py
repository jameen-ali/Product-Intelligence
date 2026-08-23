"""
Graph service — writes and reads the Product Truth Graph in Neo4j.
All nodes and relationships follow the architecture-specified schema.
"""
import logging
from typing import Optional
from uuid import UUID

from app.core.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)

def _safe_str(v) -> Optional[str]:
    return str(v) if v is not None else None


def create_product_node(product_id: UUID, name: str, model_number: Optional[str] = None,
                        manufacturer: Optional[str] = None, category: Optional[str] = None) -> bool:
    query = """
    MERGE (p:Product {id: $id})
    SET p.name = $name,
        p.model_number = $model_number,
        p.manufacturer = $manufacturer,
        p.category = $category
    RETURN p.id
    """
    try:
        neo4j_client.execute_query(query, {
            "id": _safe_str(product_id),
            "name": name,
            "model_number": model_number,
            "manufacturer": manufacturer,
            "category": category,
        })
        return True
    except Exception as e:
        logger.error(f"Neo4j: create_product_node failed: {e}")
        return False


def delete_product_graph(product_id: UUID) -> bool:
    """
    Remove Product node and all connected provenance nodes (Attribute, Claim, Evidence, Document, Source)
    belonging to this product from Neo4j graph.
    """
    query = """
    MATCH (p:Product {id: $id})
    OPTIONAL MATCH (p)-[*0..4]-(n)
    DETACH DELETE p, n
    """
    try:
        neo4j_client.execute_query(query, {"id": _safe_str(product_id)})
        logger.info(f"Neo4j graph deleted for product {product_id}")
        return True
    except Exception as e:
        logger.error(f"Neo4j delete_product_graph failed: {e}")
        return False


def create_source_node(source_id: UUID, product_id: UUID, source_type: str,
                       name: str, authority_rank: int = 5) -> bool:
    query = """
    MERGE (s:Source {id: $id})
    SET s.type = $type, s.name = $name, s.authority_rank = $authority_rank
    WITH s
    OPTIONAL MATCH (p:Product {id: $product_id})
    FOREACH (_ IN CASE WHEN p IS NOT NULL THEN [1] ELSE [] END | MERGE (p)-[:FROM_SOURCE]->(s))
    RETURN s.id
    """
    try:
        neo4j_client.execute_query(query, {
            "id": _safe_str(source_id),
            "product_id": _safe_str(product_id),
            "type": source_type,
            "name": name,
            "authority_rank": authority_rank,
        })
        return True
    except Exception as e:
        logger.error(f"Neo4j: create_source_node failed: {e}")
        return False


def create_document_node(document_id: UUID, source_id: UUID, filename: str,
                         page_count: int, file_hash: str) -> bool:
    query = """
    MERGE (d:Document {id: $id})
    SET d.filename = $filename, d.page_count = $page_count, d.file_hash = $file_hash
    WITH d
    OPTIONAL MATCH (s:Source {id: $source_id})
    FOREACH (_ IN CASE WHEN s IS NOT NULL THEN [1] ELSE [] END | MERGE (d)-[:FROM_SOURCE]->(s))
    RETURN d.id
    """
    try:
        neo4j_client.execute_query(query, {
            "id": _safe_str(document_id),
            "source_id": _safe_str(source_id),
            "filename": filename,
            "page_count": page_count,
            "file_hash": file_hash,
        })
        return True
    except Exception as e:
        logger.error(f"Neo4j: create_document_node failed: {e}")
        return False


def create_attribute_node(attribute_id: UUID, name: str, display_name: str,
                          unit_type: Optional[str] = None) -> bool:
    query = """
    MERGE (a:Attribute {id: $id})
    SET a.name = $name, a.display_name = $display_name, a.unit_type = $unit_type
    RETURN a.id
    """
    try:
        neo4j_client.execute_query(query, {
            "id": _safe_str(attribute_id),
            "name": name,
            "display_name": display_name,
            "unit_type": unit_type,
        })
        return True
    except Exception as e:
        logger.error(f"Neo4j: create_attribute_node failed: {e}")
        return False


def link_product_has_attribute(product_id: UUID, attribute_id: UUID) -> bool:
    query = """
    MATCH (p:Product {id: $product_id})
    MATCH (a:Attribute {id: $attribute_id})
    MERGE (p)-[:HAS_ATTRIBUTE]->(a)
    RETURN a.id
    """
    try:
        neo4j_client.execute_query(query, {
            "product_id": _safe_str(product_id),
            "attribute_id": _safe_str(attribute_id),
        })
        return True
    except Exception as e:
        logger.error(f"Neo4j: link_product_has_attribute failed: {e}")
        return False


def create_claim_node(claim_id: UUID, attribute_id: UUID, raw_value: str,
                      raw_unit: Optional[str], normalized_value: Optional[float],
                      normalized_unit: Optional[str], status: str,
                      extraction_confidence: float) -> bool:
    query = """
    MERGE (c:Claim {id: $id})
    SET c.raw_value = $raw_value, c.raw_unit = $raw_unit,
        c.normalized_value = $normalized_value, c.normalized_unit = $normalized_unit,
        c.status = $status, c.extraction_confidence = $extraction_confidence
    WITH c
    OPTIONAL MATCH (a:Attribute {id: $attribute_id})
    FOREACH (_ IN CASE WHEN a IS NOT NULL THEN [1] ELSE [] END | MERGE (a)-[:HAS_CLAIM]->(c))
    RETURN c.id
    """
    try:
        neo4j_client.execute_query(query, {
            "id": _safe_str(claim_id),
            "attribute_id": _safe_str(attribute_id),
            "raw_value": raw_value,
            "raw_unit": raw_unit,
            "normalized_value": normalized_value,
            "normalized_unit": normalized_unit,
            "status": status,
            "extraction_confidence": extraction_confidence,
        })
        return True
    except Exception as e:
        logger.error(f"Neo4j: create_claim_node failed: {e}")
        return False


def create_evidence_node(evidence_id: UUID, claim_id: UUID, document_id: UUID,
                         text_snippet: str, page_number: int,
                         section_header: Optional[str] = None) -> bool:
    query = """
    MERGE (e:Evidence {id: $id})
    SET e.text_snippet = $text_snippet, e.page_number = $page_number,
        e.section_header = $section_header
    WITH e
    OPTIONAL MATCH (c:Claim {id: $claim_id})
    FOREACH (_ IN CASE WHEN c IS NOT NULL THEN [1] ELSE [] END | MERGE (c)-[:SUPPORTED_BY]->(e))
    WITH e
    OPTIONAL MATCH (d:Document {id: $document_id})
    FOREACH (_ IN CASE WHEN d IS NOT NULL THEN [1] ELSE [] END | MERGE (e)-[:EXTRACTED_FROM]->(d))
    RETURN e.id
    """
    try:
        neo4j_client.execute_query(query, {
            "id": _safe_str(evidence_id),
            "claim_id": _safe_str(claim_id),
            "document_id": _safe_str(document_id),
            "text_snippet": text_snippet[:500],
            "page_number": page_number,
            "section_header": section_header,
        })
        return True
    except Exception as e:
        logger.error(f"Neo4j: create_evidence_node failed: {e}")
        return False


def get_product_graph(product_id: UUID) -> dict:
    """
    Return the full Product Truth Graph for a given product_id.
    Traverses: Product -> Attribute -> Claim -> Evidence -> Document -> Source
    """
    query = """
    MATCH (p:Product {id: $product_id})
    OPTIONAL MATCH (p)-[:HAS_ATTRIBUTE]->(a:Attribute)
    OPTIONAL MATCH (a)-[:HAS_CLAIM]->(c:Claim)
    OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(e:Evidence)
    OPTIONAL MATCH (e)-[:EXTRACTED_FROM]->(d:Document)
    OPTIONAL MATCH (d)-[:FROM_SOURCE]->(s:Source)
    RETURN p, a, c, e, d, s
    """
    try:
        records = neo4j_client.execute_query(query, {"product_id": _safe_str(product_id)})

        nodes = {}
        edges = []

        def _add_node(n, label):
            if n is None:
                return None
            nid = n.get("id")
            if nid and nid not in nodes:
                nodes[nid] = {"id": nid, "label": label, "properties": dict(n)}
            return nid

        for row in records:
            pid = _add_node(row.get("p"), "Product")
            aid = _add_node(row.get("a"), "Attribute")
            cid = _add_node(row.get("c"), "Claim")
            eid = _add_node(row.get("e"), "Evidence")
            did = _add_node(row.get("d"), "Document")
            sid = _add_node(row.get("s"), "Source")

            if pid and aid:
                edges.append({"from": pid, "to": aid, "type": "HAS_ATTRIBUTE"})
            if aid and cid:
                edges.append({"from": aid, "to": cid, "type": "HAS_CLAIM"})
            if cid and eid:
                edges.append({"from": cid, "to": eid, "type": "SUPPORTED_BY"})
            if eid and did:
                edges.append({"from": eid, "to": did, "type": "EXTRACTED_FROM"})
            if did and sid:
                edges.append({"from": did, "to": sid, "type": "FROM_SOURCE"})

        return {"nodes": list(nodes.values()), "edges": edges}
    except Exception as e:
        logger.error(f"Neo4j: get_product_graph failed: {e}")
        return {"nodes": [], "edges": [], "error": str(e)}
