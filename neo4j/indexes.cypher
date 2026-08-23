// Indexes for fast lookup

CREATE INDEX claim_status_idx IF NOT EXISTS
FOR (c:Claim) ON (c.status);

CREATE INDEX source_type_idx IF NOT EXISTS
FOR (s:Source) ON (s.type);

CREATE INDEX product_model_idx IF NOT EXISTS
FOR (p:Product) ON (p.model_number);

CREATE INDEX attribute_name_idx IF NOT EXISTS
FOR (a:Attribute) ON (a.name);

CREATE INDEX decision_status_idx IF NOT EXISTS
FOR (dec:Decision) ON (dec.trust_status);
