// Uniqueness Constraints for IPTE Graph Nodes

CREATE CONSTRAINT product_id_unique IF NOT EXISTS
FOR (p:Product) REQUIRE p.id IS UNIQUE;

CREATE CONSTRAINT source_id_unique IF NOT EXISTS
FOR (s:Source) REQUIRE s.id IS UNIQUE;

CREATE CONSTRAINT document_id_unique IF NOT EXISTS
FOR (d:Document) REQUIRE d.id IS UNIQUE;

CREATE CONSTRAINT attribute_id_unique IF NOT EXISTS
FOR (a:Attribute) REQUIRE a.id IS UNIQUE;

CREATE CONSTRAINT claim_id_unique IF NOT EXISTS
FOR (c:Claim) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT evidence_id_unique IF NOT EXISTS
FOR (e:Evidence) REQUIRE e.id IS UNIQUE;

CREATE CONSTRAINT decision_id_unique IF NOT EXISTS
FOR (dec:Decision) REQUIRE dec.id IS UNIQUE;

CREATE CONSTRAINT review_id_unique IF NOT EXISTS
FOR (r:Review) REQUIRE r.id IS UNIQUE;

CREATE CONSTRAINT version_id_unique IF NOT EXISTS
FOR (pv:ProductVersion) REQUIRE pv.id IS UNIQUE;

CREATE CONSTRAINT change_id_unique IF NOT EXISTS
FOR (ch:Change) REQUIRE ch.id IS UNIQUE;

CREATE CONSTRAINT asset_id_unique IF NOT EXISTS
FOR (ast:Asset) REQUIRE ast.id IS UNIQUE;
