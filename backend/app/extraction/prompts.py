"""
All LLM prompt templates for IPTE claim extraction.
Kept as separate, focused prompts — never one mega-prompt.
"""

PRODUCT_IDENTITY_PROMPT = """\
You are an industrial product data extraction system.

Given the following document header text, extract product identity information.

DOCUMENT TEXT:
{text}

Return ONLY valid JSON matching this schema (no markdown, no explanation):
{{
  "product_name": "string or null",
  "manufacturer": "string or null",
  "model_number": "string or null",
  "category": "string or null",
  "sku": "string or null"
}}

Rules:
- Extract only what is clearly stated in the text.
- Do not guess or fabricate values.
- If a field is not present, use null.
"""

ATTRIBUTE_EXTRACTION_PROMPT = """\
You are an industrial product specification extractor.

Extract technical attributes from this document section. Return ONLY claims that are directly supported by the text.

DOCUMENT SECTION (page {page}):
{text}

Extract these attribute types if present:
voltage, power, pressure, flow_rate, rotational_speed, weight, length, width, height, temperature_min, temperature_max, current, frequency

Return ONLY valid JSON array (no markdown, no explanation):
[
  {{
    "attribute": "attribute_name_from_list_above",
    "raw_value": "exact value as written",
    "raw_unit": "unit as written",
    "evidence_text": "exact verbatim sentence or phrase from the document that states this value",
    "page": {page},
    "confidence": 0.0_to_1.0
  }}
]

Rules:
- ONLY extract values explicitly stated in the text.
- evidence_text MUST be a verbatim excerpt from the text above.
- Do not infer or calculate values.
- If no attributes are found, return empty array [].
- Confidence: 0.95+ if clearly stated, 0.7-0.94 if implied, never below 0.5.
"""

ATTRIBUTE_EXTRACTION_CORRECTION_PROMPT = """\
The previous extraction attempt returned invalid JSON. Here is the validation error:
{error}

Original text was:
{text}

Please return ONLY valid JSON array. No markdown. No explanation. Just the JSON array starting with [ and ending with ].
"""
