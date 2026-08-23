const API_BASE_URL = 'http://localhost:8000';

export interface ComponentHealth {
  status: string;
  details?: Record<string, any>;
  error?: string;
}

export interface HealthResponse {
  status: string;
  application: string;
  timestamp: string;
  services: Record<string, ComponentHealth>;
}

export interface Product {
  id: string;
  name: string;
  manufacturer?: string;
  model_number?: string;
  category?: string;
  description?: string;
  created_at: string;
}

export interface EvidenceItem {
  evidence_id: string;
  text_snippet: string;
  page_number?: number;
  section_header?: string;
  content_type: string;
}

export interface ClaimItem {
  claim_id: string;
  raw_value: string;
  original_unit?: string;
  normalized_value?: number;
  normalized_unit?: string;
  extraction_confidence: number;
  status: string;
  location_reference?: string;
  source?: { id: string; name: string; type: string; authority_rank?: number };
  document?: { id: string; filename?: string };
  evidence: EvidenceItem[];
}

export interface AttributeData {
  attribute_id: string;
  name: string;
  display_name: string;
  unit_type?: string;
  default_unit?: string;
  trust_status: string;
  confidence?: number;
  confidence_breakdown?: Record<string, number>;
  decision_reason?: string;
  canonical_value?: string;
  claims: ClaimItem[];
}

export interface Source {
  id: string;
  product_id: string;
  type: string;
  name: string;
  authority_rank: number;
  url_or_path?: string;
  created_at: string;
}

export interface GraphData {
  nodes: Array<{ id: string; label: string; properties: Record<string, any> }>;
  edges: Array<{ from: string; to: string; type: string }>;
}

export interface ConflictGroup {
  normalized_value: string;
  claims: ClaimItem[];
  source_count: number;
  best_authority: number;
}

export interface ConflictData {
  attribute_name: string;
  attribute_display_name: string;
  attribute_id: string;
  groups: ConflictGroup[];
}

export interface ConflictsResponse {
  product_id: string;
  conflict_count: number;
  conflicts: ConflictData[];
}

export interface ReviewAction {
  reviewer_id?: string;
  notes?: string;
}

export interface ReviewResponse {
  review_id: string;
  claim_id: string;
  action: string;
  reviewer_id: string;
  message: string;
}

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, options);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

async function fetchBlob(path: string): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(`${API_BASE_URL}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const disposition = res.headers.get('Content-Disposition') || '';
  const match = disposition.match(/filename=(.+)/);
  const filename = match ? match[1] : 'export';
  return { blob: await res.blob(), filename };
}

export const api = {
  health: () => fetchJSON<HealthResponse>('/health'),

  products: {
    list: () => fetchJSON<Product[]>('/products'),
    get: (id: string) => fetchJSON<Product>(`/products/${id}`),
    create: (data: Partial<Product>) => fetchJSON<Product>('/products', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
    sources: (id: string) => fetchJSON<Source[]>(`/products/${id}/sources`),
    addSource: (id: string, data: Partial<Source>) =>
      fetchJSON<Source>(`/products/${id}/sources`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...data, product_id: id }),
      }),
    attributes: (id: string) => fetchJSON<{ attributes: AttributeData[] }>(`/products/${id}/attributes`),
    claims: (id: string) => fetchJSON<any[]>(`/products/${id}/claims`),
    evidence: (id: string) => fetchJSON<{ evidence: any[] }>(`/products/${id}/evidence`),
    graph: (id: string) => fetchJSON<GraphData>(`/products/${id}/graph`),
  },

  conflicts: {
    forProduct: (id: string) => fetchJSON<ConflictsResponse>(`/conflicts/products/${id}`),
  },

  reviews: {
    approve: (claimId: string, action?: ReviewAction) =>
      fetchJSON<ReviewResponse>(`/reviews/claims/${claimId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(action || {}),
      }),
    reject: (claimId: string, action?: ReviewAction) =>
      fetchJSON<ReviewResponse>(`/reviews/claims/${claimId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(action || {}),
      }),
    markUnknown: (claimId: string, action?: ReviewAction) =>
      fetchJSON<ReviewResponse>(`/reviews/claims/${claimId}/mark-unknown`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(action || {}),
      }),
    forProduct: (id: string) => fetchJSON<any>(`/reviews/products/${id}`),
  },

  exports: {
    json: (id: string) => fetchBlob(`/exports/products/${id}/json`),
    csv: (id: string) => fetchBlob(`/exports/products/${id}/csv`),
  },

  processing: {
    processPDF: (productId: string, sourceId: string, file: File) => {
      const fd = new FormData();
      fd.append('source_id', sourceId);
      fd.append('file', file);
      return fetchJSON<any>(`/processing/products/${productId}/process`, {
        method: 'POST',
        body: fd,
      });
    },
    processURL: (productId: string, sourceId: string, url: string) => {
      return fetchJSON<any>(`/processing/products/${productId}/process-url`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_id: sourceId, url }),
      });
    },
    processExcel: (productId: string, sourceId: string, file: File) => {
      const fd = new FormData();
      fd.append('source_id', sourceId);
      fd.append('file', file);
      return fetchJSON<any>(`/processing/products/${productId}/process-excel`, {
        method: 'POST',
        body: fd,
      });
    },
    processImage: (productId: string, sourceId: string, file: File) => {
      const fd = new FormData();
      fd.append('source_id', sourceId);
      fd.append('file', file);
      return fetchJSON<any>(`/processing/products/${productId}/process-image`, {
        method: 'POST',
        body: fd,
      });
    },
  },
};


