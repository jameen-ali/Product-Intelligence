import React, { useEffect, useState, useCallback, useMemo, useRef } from "react";
import {
  LayoutDashboard, Layers, FileText, AlertTriangle,
  GitFork, CheckCircle2, ChevronRight, RefreshCw, Upload,
  Download, Eye, X, BarChart2, Package,
  ArrowRight, Cpu, Search, Filter, ShieldCheck, Database,
  FileCheck, ShieldAlert, Sparkles, Server, Info, ExternalLink, Globe, Link, Check,
  FileSpreadsheet, ScanLine
} from "lucide-react";
import {
  api, Product, AttributeData, Source, GraphData, ConflictData,
  ClaimItem, EvidenceItem
} from "./services/api";

type Tab = "dashboard" | "workspace" | "sources" | "conflicts" | "graph" | "processing" | "export";

const TRUST_CONFIG: Record<string, { icon: string; bg: string; text: string; border: string }> = {
  VERIFIED: { icon: "✓", bg: "bg-emerald-500/10", text: "text-emerald-400", border: "border-emerald-500/30" },
  INFERRED: { icon: "◆", bg: "bg-sky-500/10", text: "text-sky-400", border: "border-sky-500/30" },
  CONFLICT: { icon: "⚠", bg: "bg-amber-500/10", text: "text-amber-400", border: "border-amber-500/30" },
  UNKNOWN: { icon: "?", bg: "bg-slate-500/10", text: "text-slate-400", border: "border-slate-600/30" },
};

function TrustBadge({ status }: { status: string }) {
  const cfg = TRUST_CONFIG[status] || TRUST_CONFIG.UNKNOWN;
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold border ${cfg.bg} ${cfg.text} ${cfg.border}`}>
      <span className="text-[10px] font-bold">{cfg.icon}</span>
      <span>{status}</span>
    </span>
  );
}

function ConfidenceMeter({ score, breakdown }: { score?: number; breakdown?: Record<string, number> }) {
  const [open, setOpen] = useState(false);
  if (score == null) return null;
  const pct = Math.round(score * 100);
  const barColor = pct >= 80 ? "bg-emerald-500" : pct >= 60 ? "bg-sky-500" : pct >= 40 ? "bg-amber-500" : "bg-rose-500";
  const textColor = barColor.replace("bg-", "text-");
  return (
    <div className="relative inline-block">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 px-2 py-1 rounded hover:bg-slate-800/80 transition-colors"
        title="Click to view confidence factors"
      >
        <div className="w-16 h-1.5 bg-slate-800 rounded-full overflow-hidden">
          <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
        </div>
        <span className={`text-xs font-mono font-bold ${textColor}`}>{pct}%</span>
        <BarChart2 className="w-3 h-3 text-slate-500" />
      </button>
      {open && breakdown && (
        <div className="absolute z-50 top-8 right-0 w-64 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl p-3.5 space-y-2 text-left">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Confidence Breakdown</span>
            <span className="text-xs font-mono font-bold text-sky-400">{pct}% overall</span>
          </div>
          {Object.entries(breakdown).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between text-xs">
              <span className="text-slate-400 capitalize">{k.replace(/_/g, " ")}</span>
              <div className="flex items-center gap-2">
                <div className="w-14 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-sky-500 rounded-full" style={{ width: `${Math.round(v * 100)}%` }} />
                </div>
                <span className="text-slate-300 font-mono text-[10px] w-7 text-right">{Math.round(v * 100)}%</span>
              </div>
            </div>
          ))}
          <button
            onClick={() => setOpen(false)}
            className="w-full text-[10px] text-slate-500 hover:text-slate-300 mt-1 text-right block"
          >
            Close ✕
          </button>
        </div>
      )}
    </div>
  );
}

function EvidenceDrawer({ attr, onClose }: { attr: AttributeData; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-slate-950 border-l border-slate-800 flex flex-col h-full shadow-2xl overflow-hidden animate-in slide-in-from-right duration-200">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/60">
          <div>
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-sky-400" />
              <h3 className="text-lg font-bold text-white">{attr.display_name}</h3>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">Evidence Inspector — Complete Provenance Chain</p>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Canonical Value</div>
            <div className="text-2xl font-bold font-mono text-white">{attr.canonical_value || "—"}</div>
            <div className="flex items-center gap-4 pt-1">
              <TrustBadge status={attr.trust_status} />
              {attr.confidence != null && <ConfidenceMeter score={attr.confidence} breakdown={attr.confidence_breakdown} />}
            </div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-400 uppercase tracking-wider">
              <Info className="w-4 h-4 text-sky-400" /> Why This Value?
            </div>
            <p className="text-sm text-slate-300 leading-relaxed font-sans">{attr.decision_reason || "Reasoning determined by source authority and agreement."}</p>
          </div>

          <div>
            <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">
              Extracted Claims &amp; Evidence ({attr.claims.length})
            </div>
            <div className="space-y-4">
              {attr.claims.map((claim, idx) => (
                <div key={claim.claim_id || idx} className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-950/40">
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-slate-500 font-mono">Claim #{idx + 1}</span>
                      <span className="text-sm font-mono text-sky-400 font-bold">{claim.raw_value} {claim.original_unit || ""}</span>
                      {claim.normalized_value != null && (
                        <div className="flex items-center gap-1.5 text-xs font-mono text-emerald-400">
                          <ArrowRight className="w-3 h-3 text-slate-600" />
                          <span>{claim.normalized_value} {claim.normalized_unit || ""}</span>
                        </div>
                      )}
                    </div>
                    <TrustBadge status={claim.status} />
                  </div>
                  <div className="p-4 space-y-3">
                    {claim.source && (
                      <div className="bg-slate-950 rounded-lg p-3 text-xs border border-slate-800/60">
                        <div className="text-[10px] text-slate-500 uppercase font-semibold mb-1">Source Document</div>
                        <div className="flex items-center justify-between">
                          <span className="text-slate-200 font-medium">{claim.source.name}</span>
                          <span className="px-2 py-0.5 bg-slate-800 text-slate-400 rounded text-[10px] uppercase font-bold">{claim.source.type}</span>
                        </div>
                      </div>
                    )}
                    {claim.evidence && claim.evidence.length > 0 ? (
                      claim.evidence.map(ev => (
                        <div key={ev.evidence_id} className="border-l-2 border-sky-500/60 pl-3 py-1 bg-slate-950/30 rounded-r-lg">
                          <div className="flex items-center gap-2 text-[11px] text-sky-400 mb-1 font-medium">
                            <FileText className="w-3.5 h-3.5" />
                            {ev.page_number ? `Page ${ev.page_number}` : "Document"}
                            {ev.section_header ? ` · ${ev.section_header}` : ""}
                          </div>
                          <blockquote className="text-xs text-slate-300 italic leading-relaxed font-mono">"{ev.text_snippet}"</blockquote>
                        </div>
                      ))
                    ) : (
                      <p className="text-xs text-slate-500 italic">No verbatim text snippet recorded.</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function AttributeTruthTable({ attrs }: { attrs: AttributeData[] }) {
  const [selected, setSelected] = useState<AttributeData | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const filteredAttrs = useMemo(() => {
    return attrs.filter(attr => {
      const matchesSearch = attr.display_name.toLowerCase().includes(search.toLowerCase()) ||
                            attr.name.toLowerCase().includes(search.toLowerCase()) ||
                            (attr.canonical_value || "").toLowerCase().includes(search.toLowerCase());
      const matchesStatus = statusFilter === "ALL" || attr.trust_status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [attrs, search, statusFilter]);

  return (
    <>
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-sky-400" />
            <h3 className="text-sm font-bold text-white">Attribute Truth Table</h3>
            <span className="text-xs text-slate-500 ml-2">({filteredAttrs.length} of {attrs.length} attributes)</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Filter attributes..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500 w-48"
              />
            </div>
            <select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-sky-500"
            >
              <option value="ALL">All Statuses</option>
              <option value="VERIFIED">Verified</option>
              <option value="INFERRED">Inferred</option>
              <option value="CONFLICT">Conflict</option>
              <option value="UNKNOWN">Unknown</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-[1fr_160px_140px_110px_130px_48px] border-b border-slate-800 bg-slate-950/60 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
          <div className="px-4 py-2.5">Attribute</div>
          <div className="px-4 py-2.5">Canonical Value</div>
          <div className="px-4 py-2.5">Original Extract</div>
          <div className="px-4 py-2.5">Status</div>
          <div className="px-4 py-2.5">Confidence</div>
          <div className="px-4 py-2.5 text-center">Inspect</div>
        </div>

        <div className="divide-y divide-slate-800/50">
          {filteredAttrs.length === 0 ? (
            <div className="p-8 text-center text-slate-500 text-xs">No matching attributes found.</div>
          ) : (
            filteredAttrs.map(attr => {
              const best = attr.claims[0];
              return (
                <div
                  key={attr.attribute_id}
                  className="grid grid-cols-[1fr_160px_140px_110px_130px_48px] hover:bg-slate-800/40 transition-colors cursor-pointer text-xs items-center"
                  onClick={() => setSelected(attr)}
                >
                  <div className="px-4 py-3 font-semibold text-slate-200">{attr.display_name}</div>
                  <div className="px-4 py-3 font-mono text-white font-bold">{attr.canonical_value || (best ? `${best.raw_value} ${best.original_unit || ""}` : "—")}</div>
                  <div className="px-4 py-3 font-mono text-slate-400">{best ? `${best.raw_value} ${best.original_unit || ""}` : "—"}</div>
                  <div className="px-4 py-3"><TrustBadge status={attr.trust_status} /></div>
                  <div className="px-4 py-3"><ConfidenceMeter score={attr.confidence} breakdown={attr.confidence_breakdown} /></div>
                  <div className="px-4 py-3 flex items-center justify-center">
                    <button
                      onClick={e => { e.stopPropagation(); setSelected(attr); }}
                      className="p-1.5 rounded hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
                      title="Inspect evidence"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
      {selected && <EvidenceDrawer attr={selected} onClose={() => setSelected(null)} />}
    </>
  );
}

function ProductWorkspace({ productId }: { productId: string }) {
  const [product, setProduct] = useState<Product | null>(null);
  const [attrs, setAttrs] = useState<AttributeData[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [processResult, setProcessResult] = useState<any>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [p, a, s] = await Promise.all([
        api.products.get(productId),
        api.products.attributes(productId),
        api.products.sources(productId),
      ]);
      setProduct(p); setAttrs(a.attributes); setSources(s);
    } catch(e: any) {
      setError(e.message || "Failed to load product truth workspace.");
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => { load(); }, [load]);

  const handleProcessPDF = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files?.length || !sources.length) return;
    setProcessing(true);
    try {
      const formData = new FormData();
      formData.append("source_id", sources[0].id);
      formData.append("file", files[0]);
      const result = await api.processing.processPDF(productId, sources[0].id, files[0]);
      setProcessResult(result);
      await load();
    } catch(err: any) {
      setError(`Document processing failed: ${err.message}`);
    } finally {
      setProcessing(false);
    }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64 bg-slate-900 border border-slate-800 rounded-xl p-8">
      <div className="text-center space-y-3">
        <div className="w-8 h-8 border-2 border-sky-500 border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-sm font-medium text-slate-300">Loading Product Truth Workspace...</p>
      </div>
    </div>
  );

  if (error) return (
    <div className="bg-rose-500/10 border border-rose-500/20 rounded-xl p-6 text-center space-y-3">
      <AlertTriangle className="w-8 h-8 text-rose-400 mx-auto" />
      <p className="text-sm text-rose-300 font-medium">{error}</p>
      <button onClick={load} className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-xs text-white rounded-lg transition-colors font-medium">
        Retry Request
      </button>
    </div>
  );

  const conflictCount = attrs.filter(a => a.trust_status === "CONFLICT").length;
  const verifiedCount = attrs.filter(a => a.trust_status === "VERIFIED").length;
  const inferredCount = attrs.filter(a => a.trust_status === "INFERRED").length;
  const unknownCount = attrs.filter(a => a.trust_status === "UNKNOWN").length;
  const avgConf = attrs.length ? Math.round(attrs.reduce((s, a) => s + (a.confidence || 0), 0) / attrs.length * 100) : 0;

  return (
    <div className="space-y-5">
      <URLIngestionModal productId={productId} onComplete={load} />
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <Package className="w-6 h-6 text-sky-400" />
              <h2 className="text-2xl font-bold text-white tracking-tight">{product?.name}</h2>
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-400 mt-1">
              {product?.manufacturer && <span>Manufacturer: <strong className="text-slate-200">{product.manufacturer}</strong></span>}
              {product?.category && <span>Category: <strong className="text-slate-200">{product.category}</strong></span>}
            </div>
            {product?.model_number && (
              <div className="mt-2.5 inline-flex items-center gap-1.5 px-2.5 py-1 bg-sky-500/10 border border-sky-500/20 rounded-md text-xs font-mono text-sky-400 font-bold">
                <Cpu className="w-3.5 h-3.5" /> Model: {product.model_number}
              </div>
            )}
            <div className="mt-4 flex items-center gap-2.5 text-xs flex-wrap">
              <span className="px-3 py-1 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">✓ {verifiedCount} Verified</span>
              <span className="px-3 py-1 rounded-md bg-sky-500/10 text-sky-400 border border-sky-500/20 font-semibold">◆ {inferredCount} Inferred</span>
              {conflictCount > 0 && <span className="px-3 py-1 rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/20 font-semibold">⚠ {conflictCount} Conflicts</span>}
              {unknownCount > 0 && <span className="px-3 py-1 rounded-md bg-slate-500/10 text-slate-400 border border-slate-700 font-semibold">? {unknownCount} Unknown</span>}
              <span className="px-3 py-1 rounded-md bg-slate-800 text-slate-400 border border-slate-700 font-medium">{sources.length} Ingestion Source{sources.length !== 1 ? "s" : ""}</span>
            </div>
          </div>
          <div className="text-right flex flex-col items-end">
            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Truth Engine Quality Score</div>
            <div className="text-3xl font-bold font-mono text-white">{avgConf}%</div>
            <div className="text-xs text-slate-500">Average Confidence Score</div>
            <button onClick={load} className="mt-3 p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors" title="Refresh Product Truth">
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {processResult && !processing && (
        <div className="bg-emerald-900/10 border border-emerald-700/30 rounded-xl p-4">
          <div className="text-emerald-400 font-bold text-sm mb-3 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" /> Ingestion Pipeline Complete
          </div>
          <div className="grid grid-cols-4 gap-3 text-xs">
            {[
              { l: "Parsed Blocks", v: processResult.result?.blocks_parsed },
              { l: "Claims Extracted", v: processResult.result?.claims_extracted },
              { l: "Qdrant Index", v: processResult.result?.qdrant_indexed },
              { l: "Neo4j Nodes", v: processResult.result?.neo4j_nodes },
            ].map(({ l, v }) => (
              <div key={l} className="bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-center">
                <div className="text-xl font-bold font-mono text-emerald-400">{v ?? 0}</div>
                <div className="text-slate-500">{l}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {sources.length > 0 && attrs.length === 0 && !processing && (
        <div className="bg-slate-900 border border-dashed border-slate-700 rounded-xl p-10 text-center">
          <Upload className="w-10 h-10 text-sky-400 mx-auto mb-3" />
          <h4 className="text-base font-bold text-white mb-1">Ingest PDF Document</h4>
          <p className="text-slate-400 text-xs mb-4 max-w-md mx-auto">
            Docling Layout Parsing → Rule &amp; LLM Extraction → Deterministic Normalization → Provenance Graph
          </p>
          <label className="cursor-pointer inline-flex items-center gap-2 px-5 py-2.5 bg-sky-600 hover:bg-sky-500 text-white text-sm rounded-lg transition-colors font-medium shadow-md">
            <Upload className="w-4 h-4" /> Upload Technical Datasheet (PDF)
            <input type="file" accept=".pdf" className="hidden" onChange={handleProcessPDF} />
          </label>
        </div>
      )}

      {attrs.length > 0 && (
        <div className="flex items-center justify-between bg-slate-900 border border-slate-800 rounded-xl p-3.5">
          <div className="flex items-center gap-3">
            <label className="cursor-pointer inline-flex items-center gap-2 px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs rounded-lg transition-colors border border-slate-700 font-medium">
              <Upload className="w-3.5 h-3.5 text-sky-400" /> {processing ? "Running Ingestion..." : "Ingest Additional Source Document (PDF)"}
              <input type="file" accept=".pdf" className="hidden" onChange={handleProcessPDF} disabled={processing} />
            </label>
            <span className="text-xs text-slate-500">Cross-referencing multiple sources triggers conflict detection</span>
          </div>
          {processing && (
            <div className="flex items-center gap-2 text-xs font-mono text-sky-400">
              <div className="w-3 h-3 border-2 border-sky-400 border-t-transparent rounded-full animate-spin" /> Processing...
            </div>
          )}
        </div>
      )}

      {attrs.length > 0 && <AttributeTruthTable attrs={attrs} />}
    </div>
  );
}


function URLIngestionModal({ productId, onComplete }: { productId: string; onComplete: () => void }) {
  const [url, setUrl] = useState("");
  const [validating, setValidating] = useState(false);
  const [validated, setValidated] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [currentStage, setCurrentStage] = useState("IDLE");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);

  const handleValidate = () => {
    setValidationError(null);
    if (!url || (!url.startsWith("http://") && !url.startsWith("https://"))) {
      setValidationError("URL must start with http:// or https://");
      setValidated(false);
      return;
    }
    const lower = url.toLowerCase();
    if (lower.includes("localhost") || lower.includes("127.0.0.1") || lower.includes("0.0.0.0")) {
      setValidationError("Access to private/local host is forbidden for security reasons");
      setValidated(false);
      return;
    }
    setValidating(true);
    setTimeout(() => {
      setValidating(false);
      setValidated(true);
    }, 400);
  };

  const handleProcessURL = async () => {
    if (!url || !validated) return;
    setProcessing(true);
    setErrorMsg(null);
    setCurrentStage("FETCHING WEBPAGE (Crawl4AI)...");

    try {
      // 1. Create or get URL source
      const source = await api.products.addSource(productId, {
        type: "url",
        name: "Website Specification Page",
        authority_rank: 3,
        url_or_path: url,
      });

      setCurrentStage("PARSING BLOCKS & TABLES...");
      await new Promise(r => setTimeout(r, 400));

      setCurrentStage("EXTRACTING ATTRIBUTE CLAIMS...");
      await new Promise(r => setTimeout(r, 400));

      setCurrentStage("NORMALIZING & VALIDATING...");
      const res = await api.processing.processURL(productId, source.id, url);

      setCurrentStage("BUILDING TRUTH GRAPH & VECTOR INDEX...");
      await new Promise(r => setTimeout(r, 300));

      setResult(res.result);
      onComplete();
    } catch (e: any) {
      setErrorMsg(e.message || "Unable to process this webpage.");
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <Globe className="w-5 h-5 text-sky-400" />
          <h4 className="text-sm font-bold text-white">Ingest Website URL (Crawl4AI)</h4>
        </div>
        <span className="text-[10px] px-2 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 rounded font-bold">CRAWL4AI ACTIVE</span>
      </div>

      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <input
            type="url"
            value={url}
            onChange={e => { setUrl(e.target.value); setValidated(false); setValidationError(null); }}
            placeholder="https://manufacturer.com/product/specifications"
            disabled={processing}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 font-mono"
          />
        </div>
        <button
          onClick={handleValidate}
          disabled={validating || processing || !url}
          className="px-4 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 text-xs font-bold rounded-lg transition-colors border border-slate-700 whitespace-nowrap"
        >
          {validating ? "Validating..." : "Validate URL"}
        </button>
      </div>

      {validationError && (
        <div className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-lg p-2.5 font-medium">
          ⚠️ {validationError}
        </div>
      )}

      {validated && !validationError && (
        <div className="bg-slate-950 border border-sky-500/30 rounded-lg p-3.5 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400 font-bold">Source Preview:</span>
            <span className="text-emerald-400 font-bold font-mono">✓ URL Validated</span>
          </div>
          <div className="text-xs font-mono text-slate-200 truncate">{url}</div>
          <div className="flex items-center gap-4 text-[11px] text-slate-400 pt-1">
            <span>Type: <strong className="text-slate-300">Website</strong></span>
            <span>Authority Rank: <strong className="text-sky-400">#3 (Official Web Spec)</strong></span>
          </div>
          <button
            onClick={handleProcessURL}
            disabled={processing}
            className="w-full mt-2 py-2.5 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-xs font-bold rounded-lg transition-colors shadow-md flex items-center justify-center gap-2"
          >
            {processing ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>{currentStage}</span>
              </>
            ) : (
              <>
                <Globe className="w-4 h-4" /> Process Website Source (Crawl4AI)
              </>
            )}
          </button>
        </div>
      )}

      {errorMsg && (
        <div className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-lg p-3 space-y-1">
          <div className="font-bold">Unable to process this webpage.</div>
          <div className="text-slate-300 font-mono text-[11px]">{errorMsg}</div>
        </div>
      )}

      {result && (
        <div className="bg-emerald-950/20 border border-emerald-500/30 rounded-lg p-3 text-xs space-y-2">
          <div className="text-emerald-400 font-bold flex items-center gap-1.5">
            <CheckCircle2 className="w-4 h-4" /> URL Ingestion Complete
          </div>
          <div className="grid grid-cols-4 gap-2 text-center pt-1 font-mono text-[11px]">
            <div className="bg-slate-950 p-2 rounded border border-slate-800">
              <div className="text-emerald-400 font-bold">{result.blocks_parsed}</div>
              <div className="text-slate-500 text-[10px]">Blocks</div>
            </div>
            <div className="bg-slate-950 p-2 rounded border border-slate-800">
              <div className="text-emerald-400 font-bold">{result.claims_extracted}</div>
              <div className="text-slate-500 text-[10px]">Claims</div>
            </div>
            <div className="bg-slate-950 p-2 rounded border border-slate-800">
              <div className="text-emerald-400 font-bold">{result.qdrant_indexed}</div>
              <div className="text-slate-500 text-[10px]">Vector</div>
            </div>
            <div className="bg-slate-950 p-2 rounded border border-slate-800">
              <div className="text-emerald-400 font-bold">{result.neo4j_nodes}</div>
              <div className="text-slate-500 text-[10px]">Graph</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


function ExcelIngestionModal({ productId, onComplete }: { productId: string; onComplete: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [processing, setProcessing] = useState(false);
  const [currentStage, setCurrentStage] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [validationWarning, setValidationWarning] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const STAGES = [
    "READING WORKBOOK...", "MAPPING COLUMN HEADERS...", "EXTRACTING ATTRIBUTE ROWS...",
    "CREATING CLAIMS...", "NORMALIZING UNITS...", "BUILDING TRUTH GRAPH...",
  ];

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null;
    setFile(f); setResult(null); setErrorMsg(null); setValidationWarning(null);
    if (f) {
      const ext = f.name.split('.').pop()?.toLowerCase() ?? '';
      if (!['csv', 'xlsx', 'xlsm', 'xls'].includes(ext))
        setValidationWarning(`Unsupported: .${ext} — use .csv, .xlsx, or .xlsm`);
      else if (f.size > 50 * 1024 * 1024)
        setValidationWarning('File too large (max 50MB)');
    }
  };

  const handleProcess = async () => {
    if (!file || validationWarning) return;
    setProcessing(true); setErrorMsg(null);
    try {
      const source = await api.products.addSource(productId, {
        type: 'excel',
        name: file.name.endsWith('.csv') ? 'CSV Catalog' : 'Excel Catalog',
        authority_rank: 6,
        url_or_path: file.name,
      });
      for (const stage of STAGES) { setCurrentStage(stage); await new Promise(r => setTimeout(r, 280)); }
      const res = await api.processing.processExcel(productId, source.id, file);
      setCurrentStage('COMPLETED'); setResult(res.result); onComplete();
    } catch (e: any) {
      setErrorMsg(e.message || 'Excel ingestion failed.');
    } finally { setProcessing(false); }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <FileSpreadsheet className="w-5 h-5 text-emerald-400" />
          <h4 className="text-sm font-bold text-white">Ingest Excel / CSV Catalog</h4>
        </div>
        <span className="text-[10px] px-2 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 rounded font-bold">PANDAS ACTIVE</span>
      </div>
      <div
        className="border-2 border-dashed border-slate-700 hover:border-emerald-500/50 rounded-xl p-6 text-center cursor-pointer transition-colors group"
        onClick={() => fileInputRef.current?.click()}
      >
        <input ref={fileInputRef} type="file" accept=".csv,.xlsx,.xlsm,.xls" className="hidden" onChange={handleFileChange} disabled={processing} />
        {file ? (
          <div className="space-y-1">
            <div className="text-sm font-bold text-emerald-400">📊 {file.name}</div>
            <div className="text-xs text-slate-400">{(file.size / 1024).toFixed(1)} KB · Click to change</div>
          </div>
        ) : (
          <div className="space-y-2">
            <FileSpreadsheet className="w-8 h-8 text-slate-600 mx-auto group-hover:text-emerald-500 transition-colors" />
            <div className="text-xs text-slate-400">Drop or click · <strong className="text-slate-300">.csv .xlsx .xlsm</strong></div>
          </div>
        )}
      </div>
      {validationWarning && <div className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-lg p-2.5">⚠️ {validationWarning}</div>}
      {file && !validationWarning && !result && (
        <button onClick={handleProcess} disabled={processing}
          className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-2">
          {processing
            ? <><div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" /><span>{currentStage}</span></>
            : <><FileSpreadsheet className="w-4 h-4" /> Process Catalog (pandas)</>}
        </button>
      )}
      {errorMsg && <div className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-lg p-3"><div className="font-bold">Ingestion Failed</div><div className="text-slate-300 font-mono text-[11px] mt-1">{errorMsg}</div></div>}
      {result && (
        <div className="bg-emerald-950/20 border border-emerald-500/30 rounded-lg p-3 text-xs space-y-2">
          <div className="text-emerald-400 font-bold flex items-center gap-1.5"><CheckCircle2 className="w-4 h-4" /> Excel Ingestion Complete</div>
          {result.validation_messages?.length > 0 && <div className="text-amber-400 text-[11px]">{result.validation_messages.map((m: string, i: number) => <div key={i}>⚠ {m}</div>)}</div>}
          <div className="grid grid-cols-4 gap-2 text-center pt-1 font-mono text-[11px]">
            {[['rows_parsed','Rows'],['claims_extracted','Claims'],['qdrant_indexed','Vector'],['neo4j_nodes','Graph']].map(([k,label]) => (
              <div key={k} className="bg-slate-950 p-2 rounded border border-slate-800"><div className="text-emerald-400 font-bold">{result[k]??0}</div><div className="text-slate-500 text-[10px]">{label}</div></div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


function ImageIngestionModal({ productId, onComplete }: { productId: string; onComplete: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [processing, setProcessing] = useState(false);
  const [currentStage, setCurrentStage] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [validationWarning, setValidationWarning] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const STAGES = [
    "LOADING IMAGE...", "RUNNING PaddleOCR...", "READING NAMEPLATE TEXT...",
    "EXTRACTING ATTRIBUTES...", "NORMALIZING UNITS...", "BUILDING TRUTH GRAPH...",
  ];

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null;
    setFile(f); setResult(null); setErrorMsg(null); setValidationWarning(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    if (f) {
      const ext = f.name.split('.').pop()?.toLowerCase() ?? '';
      if (!['png', 'jpg', 'jpeg', 'webp'].includes(ext))
        setValidationWarning(`Unsupported: .${ext} — use .png .jpg .jpeg .webp`);
      else if (f.size > 20 * 1024 * 1024)
        setValidationWarning('Image too large (max 20MB)');
      else
        setPreviewUrl(URL.createObjectURL(f));
    }
  };

  const handleProcess = async () => {
    if (!file || validationWarning) return;
    setProcessing(true); setErrorMsg(null);
    try {
      const source = await api.products.addSource(productId, {
        type: 'image',
        name: 'Industrial Nameplate',
        authority_rank: 4,
        url_or_path: file.name,
      });
      for (const stage of STAGES) { setCurrentStage(stage); await new Promise(r => setTimeout(r, 350)); }
      const res = await api.processing.processImage(productId, source.id, file);
      setCurrentStage('COMPLETED'); setResult(res.result); onComplete();
    } catch (e: any) {
      setErrorMsg(e.message || 'Image OCR ingestion failed.');
    } finally { setProcessing(false); }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <ScanLine className="w-5 h-5 text-violet-400" />
          <h4 className="text-sm font-bold text-white">Ingest Nameplate Image (PaddleOCR)</h4>
        </div>
        <span className="text-[10px] px-2 py-0.5 bg-violet-500/10 text-violet-400 border border-violet-500/30 rounded font-bold">OCR ACTIVE</span>
      </div>
      <div
        className="border-2 border-dashed border-slate-700 hover:border-violet-500/50 rounded-xl p-6 text-center cursor-pointer transition-colors group"
        onClick={() => fileInputRef.current?.click()}
      >
        <input ref={fileInputRef} type="file" accept=".png,.jpg,.jpeg,.webp" className="hidden" onChange={handleFileChange} disabled={processing} />
        {previewUrl ? (
          <div className="space-y-2">
            <img src={previewUrl} alt="Nameplate preview" className="max-h-32 mx-auto rounded-lg border border-slate-700 object-contain" />
            <div className="text-xs text-slate-400">{file?.name} · {((file?.size ?? 0)/1024).toFixed(1)} KB · Click to change</div>
          </div>
        ) : (
          <div className="space-y-2">
            <ScanLine className="w-8 h-8 text-slate-600 mx-auto group-hover:text-violet-500 transition-colors" />
            <div className="text-xs text-slate-400">Drop or click · <strong className="text-slate-300">.png .jpg .jpeg .webp</strong></div>
          </div>
        )}
      </div>
      {validationWarning && <div className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-lg p-2.5">⚠️ {validationWarning}</div>}
      {file && !validationWarning && !result && (
        <button onClick={handleProcess} disabled={processing}
          className="w-full py-2.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-2">
          {processing
            ? <><div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" /><span>{currentStage}</span></>
            : <><ScanLine className="w-4 h-4" /> Run Nameplate OCR (PaddleOCR)</>}
        </button>
      )}
      {errorMsg && <div className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-lg p-3"><div className="font-bold">OCR Failed</div><div className="text-slate-300 font-mono text-[11px] mt-1">{errorMsg}</div></div>}
      {result && (
        <div className="bg-violet-950/20 border border-violet-500/30 rounded-lg p-3 text-xs space-y-2">
          <div className="text-violet-400 font-bold flex items-center gap-1.5"><CheckCircle2 className="w-4 h-4" /> OCR Ingestion Complete</div>
          <div className="grid grid-cols-4 gap-2 text-center pt-1 font-mono text-[11px]">
            {[['ocr_regions','Regions'],['claims_extracted','Claims'],['qdrant_indexed','Vector'],['neo4j_nodes','Graph']].map(([k,label]) => (
              <div key={k} className="bg-slate-950 p-2 rounded border border-slate-800"><div className="text-violet-400 font-bold">{result[k]??0}</div><div className="text-slate-500 text-[10px]">{label}</div></div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


function SourceManager({ productId }: { productId: string }) {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);

  const AUTHORITY_LABELS: Record<number, { label: string; color: string }> = {
    1: { label: "Manufacturer Technical Datasheet", color: "text-emerald-400" },
    2: { label: "Manufacturer Installation Manual", color: "text-emerald-300" },
    3: { label: "Official Web Specification", color: "text-sky-400" },
    4: { label: "Product Label / Nameplate", color: "text-sky-300" },
    5: { label: "Certified Inspection Report", color: "text-amber-400" },
    6: { label: "Authorized Distributor Listing", color: "text-amber-300" },
    7: { label: "Supplier Specification Sheet", color: "text-orange-400" },
    8: { label: "Third-Party Data Catalog", color: "text-slate-400" },
  };

  useEffect(() => {
    if (!productId) return;
    api.products.sources(productId).then(s => setSources(s)).finally(() => setLoading(false));
  }, [productId]);

  if (loading) return <div className="p-8 text-center text-slate-500 text-sm">Loading source provenance data...</div>;

  const reloadSources = () => api.products.sources(productId).then(s => setSources(s));

  return (
    <div className="space-y-5">
      <URLIngestionModal productId={productId} onComplete={reloadSources} />
      <ExcelIngestionModal productId={productId} onComplete={reloadSources} />
      <ImageIngestionModal productId={productId} onComplete={reloadSources} />
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-white">Attached Data Sources</h3>
            <p className="text-xs text-slate-400 mt-0.5">Ingestion documents and authority ranking ladder</p>
          </div>
          <span className="text-xs text-slate-500 font-mono">{sources.length} document source{sources.length !== 1 ? "s" : ""}</span>
        </div>
        {sources.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-sm">No sources attached yet to this product.</div>
        ) : (
          <div className="divide-y divide-slate-800/50">
            {sources.map(source => {
              const auth = AUTHORITY_LABELS[source.authority_rank] || { label: "Supplier Document", color: "text-slate-400" };
              const authScore = [1.00, 0.92, 0.80, 0.70, 0.65, 0.50, 0.40, 0.25][source.authority_rank - 1] || 0.40;
              return (
                <div key={source.id} className="px-5 py-4 flex items-center justify-between flex-wrap gap-4">
                  <div className="flex items-center gap-3.5">
                    <div className="w-10 h-10 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300">
                      <FileText className="w-5 h-5 text-sky-400" />
                    </div>
                    <div>
                      <div className="text-sm font-bold text-white">{source.name}</div>
                      <div className={`text-xs font-medium ${auth.color}`}>{auth.label}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-6 text-right">
                    <div>
                      <div className="text-[10px] text-slate-500 font-bold uppercase">Authority Score</div>
                      <div className="text-sm font-bold font-mono text-white">{Math.round(authScore * 100)}%</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-slate-500 font-bold uppercase">Rank</div>
                      <div className="text-sm font-bold font-mono text-slate-300">#{source.authority_rank}</div>
                    </div>
                    <span className="text-[10px] px-2.5 py-1 bg-slate-800 border border-slate-700 rounded-md capitalize font-bold text-slate-300">
                      {source.type}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-800">
          <h3 className="text-sm font-bold text-white">Ingestion Modality Matrix</h3>
          <p className="text-xs text-slate-400 mt-0.5">Supported document formats &amp; pipeline state</p>
        </div>
        <div className="grid grid-cols-2 divide-x divide-y divide-slate-800/50">
          {[
            { t: "PDF Technical Datasheet", e: true, d: "Docling layout-aware parsing with page, table, and header tracking." },
            { t: "URL Specification Page", e: true, d: "Crawl4AI webpage fetcher with structural table & text extraction." },
            { t: "Excel / CSV Catalog", e: true, d: "pandas + openpyxl column-mapped structured attribute ingestion with sheet/row provenance." },
            { t: "Image / Nameplate OCR", e: true, d: "PaddleOCR with bounding box and confidence-separated provenance." },
          ].map(({ t, e, d }) => (
            <div key={t} className="p-5 flex items-start gap-3">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-bold text-slate-200">{t}</span>
                  {e ? (
                    <span className="text-[10px] px-2 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 rounded font-bold">ACTIVE</span>
                  ) : (
                    <span className="text-[10px] px-2 py-0.5 bg-slate-800 text-slate-500 border border-slate-700 rounded font-semibold">COMING SOON</span>
                  )}
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">{d}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ConflictWorkspace({ productId }: { productId: string }) {
  const [conflicts, setConflicts] = useState<ConflictData[]>([]);
  const [loading, setLoading] = useState(true);
  const [reviewing, setReviewing] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, string>>({});

  const loadConflicts = useCallback(() => {
    if (!productId) return;
    setLoading(true);
    api.conflicts.forProduct(productId)
      .then(r => setConflicts(r.conflicts))
      .catch(() => setConflicts([]))
      .finally(() => setLoading(false));
  }, [productId]);

  useEffect(() => { loadConflicts(); }, [loadConflicts]);

  const handleReview = async (claimId: string, action: string) => {
    setReviewing(claimId);
    try {
      let r: any;
      if (action === "approve") r = await api.reviews.approve(claimId);
      else if (action === "reject") r = await api.reviews.reject(claimId);
      else r = await api.reviews.markUnknown(claimId);
      setResults(prev => ({ ...prev, [claimId]: r.message }));
      await loadConflicts();
    } catch (e: any) {
      setResults(prev => ({ ...prev, [claimId]: "Unable to save review decision. Please try again." }));
    } finally {
      setReviewing(null);
    }
  };

  if (loading) return <div className="p-8 text-center text-slate-500 text-sm">Detecting conflicting attribute values...</div>;

  if (conflicts.length === 0) return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-10 text-center space-y-3">
      <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto" />
      <h4 className="text-base font-bold text-white">No Unresolved Conflicts Detected</h4>
      <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
        All extracted values currently agree across available sources, or conflicts have been resolved by human review.
      </p>
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl">
        <AlertTriangle className="w-6 h-6 text-amber-400 flex-shrink-0" />
        <div>
          <div className="text-sm font-bold text-amber-400">{conflicts.length} Attribute Conflict{conflicts.length !== 1 ? "s" : ""} Requiring Review</div>
          <div className="text-xs text-slate-300 mt-0.5">Competing normalized values detected from different ingestion sources. Human decision is persisted to PostgreSQL database.</div>
        </div>
      </div>

      {conflicts.map(conflict => (
        <div key={conflict.attribute_id} className="bg-slate-900 border border-amber-500/30 rounded-xl overflow-hidden shadow-sm">
          <div className="px-6 py-4 border-b border-slate-800 bg-amber-500/5 flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-3">
              <ShieldAlert className="w-5 h-5 text-amber-400" />
              <span className="text-xs font-bold text-amber-400 uppercase tracking-wider">CONFLICT</span>
              <h3 className="text-base font-bold text-white">{conflict.attribute_display_name}</h3>
            </div>
            <span className="text-xs text-slate-400 font-mono">{conflict.groups.length} Competing Value Groups</span>
          </div>

          <div className="p-6">
            <div className={`grid gap-6 ${conflict.groups.length === 2 ? "grid-cols-2" : "grid-cols-1"}`}>
              {conflict.groups.map((group, gi) => (
                <div
                  key={gi}
                  className={`bg-slate-950 border rounded-xl p-5 space-y-4 ${gi === 0 ? "border-sky-500/40" : "border-slate-800"}`}
                >
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <span className="text-xs font-bold text-slate-400 uppercase">Candidate Value {String.fromCharCode(65 + gi)}</span>
                    <span className="text-xs text-slate-500">Authority Rank #{group.best_authority}</span>
                  </div>

                  <div className="text-3xl font-bold font-mono text-white">{group.normalized_value}</div>
                  <div className="text-xs text-slate-400">Supported by {group.source_count} document source{group.source_count !== 1 ? "s" : ""}</div>

                  {(group.claims as any[]).slice(0, 1).map((claim: any) => (
                    <div key={claim.claim_id} className="space-y-3 pt-2">
                      {(claim.evidence as any[])?.slice(0, 1).map((ev: any) => (
                        <div key={ev.evidence_id} className="border-l-2 border-amber-500/60 pl-3 py-1 bg-slate-900/50 rounded-r">
                          <div className="text-[10px] text-amber-400 font-semibold mb-1">
                            {ev.page_number ? `Page ${ev.page_number}` : "Document"} {ev.section_header ? ` · ${ev.section_header}` : ""}
                          </div>
                          <blockquote className="text-xs text-slate-300 italic font-mono leading-relaxed">"{ev.text_snippet}"</blockquote>
                        </div>
                      ))}
                      {claim.source && (
                        <div className="text-xs text-slate-400 font-medium flex items-center gap-1.5">
                          <FileText className="w-3.5 h-3.5 text-slate-500" /> Source: {claim.source.name}
                        </div>
                      )}

                      {results[claim.claim_id] ? (
                        <div className={`mt-3 text-xs rounded-lg p-2.5 font-medium border ${results[claim.claim_id].includes("Unable") ? "bg-rose-500/10 text-rose-400 border-rose-500/20" : "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"}`}>
                          {results[claim.claim_id].includes("Unable") ? "✕ " : "✓ "}{results[claim.claim_id]}
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 pt-2">
                          <button
                            onClick={() => handleReview(claim.claim_id, "approve")}
                            disabled={!!reviewing}
                            className="flex-1 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold rounded-lg transition-colors"
                          >
                            {reviewing === claim.claim_id ? "Saving..." : "APPROVE"}
                          </button>
                          <button
                            onClick={() => handleReview(claim.claim_id, "reject")}
                            disabled={!!reviewing}
                            className="flex-1 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-300 text-xs font-bold rounded-lg transition-colors border border-slate-700"
                          >
                            {reviewing === claim.claim_id ? "Saving..." : "REJECT"}
                          </button>
                          <button
                            onClick={() => handleReview(claim.claim_id, "unknown")}
                            disabled={!!reviewing}
                            className="py-2 px-3 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-slate-400 text-xs font-bold rounded-lg transition-colors border border-slate-800"
                          >
                            {reviewing === claim.claim_id ? "Saving..." : "MARK UNKNOWN"}
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function TruthGraph({ productId }: { productId: string }) {
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!productId) return;
    api.products.graph(productId).then(g => setGraph(g)).catch(e => setError(e.message)).finally(() => setLoading(false));
  }, [productId]);

  if (loading) return <div className="p-8 text-center text-slate-500 text-sm">Querying Neo4j provenance graph...</div>;
  if (error) return (
    <div className="bg-rose-500/10 border border-rose-500/20 rounded-xl p-6 text-center text-rose-400 text-sm font-medium">
      Neo4j Graph query failed: {error}
    </div>
  );

  if (!graph || graph.nodes.length === 0) return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-10 text-center space-y-2">
      <GitFork className="w-10 h-10 text-slate-600 mx-auto mb-2" />
      <p className="text-slate-400 text-sm font-medium">No Graph Provenance Nodes</p>
      <p className="text-xs text-slate-500">Run the ingestion pipeline to populate Neo4j nodes.</p>
    </div>
  );

  const byLabel: Record<string, typeof graph.nodes> = {};
  for (const n of graph.nodes) {
    byLabel[n.label] = byLabel[n.label] || [];
    byLabel[n.label].push(n);
  }
  const LABEL_ORDER = ["Product", "Attribute", "Claim", "Evidence", "Document", "Source"];
  const COLORS: Record<string, { bg: string; border: string; text: string }> = {
    Product: { bg: "bg-sky-500/10", border: "border-sky-500/40", text: "text-sky-400" },
    Attribute: { bg: "bg-purple-500/10", border: "border-purple-500/40", text: "text-purple-400" },
    Claim: { bg: "bg-emerald-500/10", border: "border-emerald-500/40", text: "text-emerald-400" },
    Evidence: { bg: "bg-amber-500/10", border: "border-amber-500/40", text: "text-amber-400" },
    Document: { bg: "bg-orange-500/10", border: "border-orange-500/40", text: "text-orange-400" },
    Source: { bg: "bg-rose-500/10", border: "border-rose-500/40", text: "text-rose-400" },
  };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-6 gap-3">
        {LABEL_ORDER.map(label => {
          const nodes = byLabel[label] || [];
          const c = COLORS[label];
          return (
            <div key={label} className={`${c.bg} border ${c.border} rounded-xl p-3.5 text-center`}>
              <div className={`text-2xl font-bold font-mono ${c.text}`}>{nodes.length}</div>
              <div className="text-xs font-semibold text-slate-400 mt-0.5">{label}s</div>
            </div>
          );
        })}
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
        <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">
          Neo4j Provenance Chain ({graph.nodes.length} Nodes, {graph.edges.length} Relationships)
        </div>
        <div className="flex items-center flex-wrap gap-2 text-xs">
          {LABEL_ORDER.map((label, i) => {
            const c = COLORS[label];
            const rels = ["", "HAS_ATTRIBUTE", "HAS_CLAIM", "SUPPORTED_BY", "EXTRACTED_FROM", "FROM_SOURCE"];
            return (
              <React.Fragment key={label}>
                {i > 0 && <span className="text-[10px] font-mono text-slate-500 px-1">{rels[i]} →</span>}
                <span className={`px-2.5 py-1 ${c.bg} ${c.border} border rounded-md ${c.text} font-bold`}>{label}</span>
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {LABEL_ORDER.filter(l => (byLabel[l] || []).length > 0).map(label => {
        const nodes = byLabel[label] || [];
        const c = COLORS[label];
        return (
          <div key={label} className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-3.5 border-b border-slate-800">
              <span className={`text-xs font-bold ${c.text} ${c.bg} border ${c.border} px-2.5 py-0.5 rounded-md`}>{label} Nodes</span>
              <span className="text-xs text-slate-500 font-mono">({nodes.length})</span>
            </div>
            <div className="divide-y divide-slate-800/50">
              {nodes.slice(0, 5).map(node => (
                <div key={node.id} className="px-5 py-3 flex items-start gap-4 text-xs">
                  <span className="font-mono text-[10px] text-slate-500 flex-shrink-0 mt-0.5">{node.id.slice(0, 8)}...</span>
                  <div className="flex-1 min-w-0 flex items-center flex-wrap gap-x-4 gap-y-1">
                    {Object.entries(node.properties).slice(0, 4).map(([k, v]) => (
                      <span key={k} className="text-slate-400">
                        <span className="text-slate-500 font-semibold">{k}:</span> <span className="text-slate-200 font-mono">{String(v).slice(0, 60)}</span>
                      </span>
                    ))}
                  </div>
                </div>
              ))}
              {nodes.length > 5 && <div className="px-5 py-2 text-xs text-slate-500 italic">+{nodes.length - 5} more nodes in Neo4j graph</div>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ExportPanel({ productId }: { productId: string }) {
  const [attrs, setAttrs] = useState<AttributeData[]>([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState<string | null>(null);
  const [exportMsg, setExportMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!productId) return;
    api.products.attributes(productId).then(r => setAttrs(r.attributes)).finally(() => setLoading(false));
  }, [productId]);

  const handleExport = async (fmt: "json" | "csv") => {
    setExporting(fmt);
    setExportMsg(null);
    try {
      const { blob, filename } = fmt === "json" ? await api.exports.json(productId) : await api.exports.csv(productId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url);
      setExportMsg(`✓ ${fmt.toUpperCase()} exported successfully`);
    } catch (e: any) {
      setExportMsg(`Export Error: ${e.message}`);
    } finally {
      setExporting(null);
    }
  };

  if (loading) return <div className="p-8 text-center text-slate-500 text-sm">Preparing export preview...</div>;

  const verified = attrs.filter(a => a.trust_status === "VERIFIED").length;
  const conflictsCount = attrs.filter(a => a.trust_status === "CONFLICT").length;
  const avgConf = attrs.length ? Math.round(attrs.reduce((s, a) => s + (a.confidence || 0), 0) / attrs.length * 100) : 0;

  return (
    <div className="space-y-6">
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-5">
        <div>
          <h3 className="text-base font-bold text-white">Commerce-Ready Export</h3>
          <p className="text-xs text-slate-400 mt-0.5">Download product truth records formatted for enterprise PIM and ERP systems.</p>
        </div>

        <div className="grid grid-cols-4 gap-4">
          {[
            { l: "Total Attributes", v: attrs.length, c: "text-white" },
            { l: "Verified", v: verified, c: "text-emerald-400" },
            { l: "Conflicts", v: conflictsCount, c: "text-amber-400" },
            { l: "Quality Confidence", v: `${avgConf}%`, c: "text-sky-400" },
          ].map(({ l, v, c }) => (
            <div key={l} className="bg-slate-950 border border-slate-800 rounded-xl p-4 text-center">
              <div className={`text-2xl font-bold font-mono ${c}`}>{v}</div>
              <div className="text-xs text-slate-500 mt-1">{l}</div>
            </div>
          ))}
        </div>

        {conflictsCount > 0 && (
          <div className="flex items-start gap-3 p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl text-xs text-amber-300">
            <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">{conflictsCount} unresolved conflict{conflictsCount !== 1 ? "s" : ""}</span> present in export payload. Conflict flags and competing values will be included in JSON/CSV export.
            </div>
          </div>
        )}

        <div className="flex gap-4 pt-2">
          <button
            onClick={() => handleExport("json")}
            disabled={!!exporting || attrs.length === 0}
            className="flex items-center gap-2 px-5 py-2.5 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-sm rounded-lg transition-colors font-bold shadow-md"
          >
            <Download className="w-4 h-4" /> {exporting === "json" ? "Generating JSON..." : "Download Export (JSON)"}
          </button>
          <button
            onClick={() => handleExport("csv")}
            disabled={!!exporting || attrs.length === 0}
            className="flex items-center gap-2 px-5 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 disabled:opacity-50 text-slate-200 text-sm rounded-lg transition-colors font-bold"
          >
            <Download className="w-4 h-4" /> {exporting === "csv" ? "Generating CSV..." : "Download Export (CSV)"}
          </button>
        </div>

        {exportMsg && (
          <div className={`text-xs px-4 py-2.5 rounded-lg font-medium ${exportMsg.startsWith("✓") ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-rose-500/10 text-rose-400 border border-rose-500/20"}`}>
            {exportMsg}
          </div>
        )}
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-800">
          <h3 className="text-sm font-bold text-white">Export Preview</h3>
        </div>
        <div className="divide-y divide-slate-800/50">
          {attrs.slice(0, 5).map(attr => (
            <div key={attr.attribute_id} className="px-5 py-3 flex items-center justify-between text-xs">
              <div className="flex items-center gap-3">
                <TrustBadge status={attr.trust_status} />
                <span className="text-slate-200 font-semibold">{attr.display_name}</span>
              </div>
              <div className="flex items-center gap-4">
                <span className="font-mono text-white font-bold">{attr.canonical_value || "—"}</span>
                {attr.confidence != null && <span className="text-slate-500 font-mono">{Math.round(attr.confidence * 100)}%</span>}
              </div>
            </div>
          ))}
          {attrs.length > 5 && <div className="px-5 py-2 text-xs text-slate-500">+{attrs.length - 5} more attributes in payload</div>}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("dashboard");
  const [health, setHealth] = useState<any>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);
  const [newProductName, setNewProductName] = useState("");
  const [creating, setCreating] = useState(false);

  const loadHealth = useCallback(async () => {
    try {
      setHealthLoading(true);
      const data = await api.health();
      setHealth(data);
    } catch {
      setHealth(null);
    } finally {
      setHealthLoading(false);
    }
  }, []);

  const loadProducts = useCallback(async () => {
    try {
      const ps = await api.products.list();
      setProducts(ps);
      if (ps.length > 0 && !selectedProductId) {
        setSelectedProductId(ps[0].id);
      }
    } catch {}
  }, [selectedProductId]);

  useEffect(() => {
    loadHealth();
    loadProducts();
    const interval = setInterval(loadHealth, 30000);
    return () => clearInterval(interval);
  }, [loadHealth, loadProducts]);

  const handleCreateProduct = async () => {
    const nameStr = newProductName.trim();
    if (!nameStr) return;
    setCreating(true);
    try {
      const payload: Partial<Product> = { name: nameStr };
      const parts = nameStr.split(" ");
      const lastPart = parts[parts.length - 1];
      if (/^[A-Za-z0-9-]+$/.test(lastPart) && /\d/.test(lastPart)) {
        payload.model_number = lastPart;
      }
      if (nameStr.toLowerCase().includes("motor")) {
        payload.category = "Electric Motor";
      } else if (nameStr.toLowerCase().includes("pump")) {
        payload.category = "Hydraulic Pump";
      } else if (nameStr.toLowerCase().includes("gearbox")) {
        payload.category = "Industrial Gearbox";
      }
      const p = await api.products.create(payload);
      await api.products.addSource(p.id, { type: "datasheet", name: "Manufacturer Datasheet", authority_rank: 1 });
      await loadProducts();
      setSelectedProductId(p.id);
      setActiveTab("workspace");
      setNewProductName("");
    } catch (e) {
      console.error(e);
    } finally {
      setCreating(false);
    }
  };

  const svcStatus = (svc: string) => health?.services?.[svc]?.status;

  const navItems: { id: Tab; label: string; icon: React.ElementType }[] = [
    { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
    { id: "workspace", label: "Workspace", icon: Layers },
    { id: "sources", label: "Sources", icon: FileText },
    { id: "conflicts", label: "Conflicts", icon: AlertTriangle },
    { id: "graph", label: "Truth Graph", icon: GitFork },
    { id: "processing", label: "Processing", icon: Cpu },
    { id: "export", label: "Export", icon: Download },
  ];

  const needsProduct = ["workspace", "sources", "conflicts", "graph", "export"].includes(activeTab) && !selectedProductId;

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 font-sans overflow-hidden">
      <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col flex-shrink-0">
        <div className="flex items-center gap-3 px-5 py-5 border-b border-slate-800">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-sky-500 to-sky-700 flex items-center justify-center font-black text-white text-xs shadow-md">
            IPTE
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-tight">Product Truth</h1>
            <p className="text-[10px] text-sky-400 font-semibold tracking-wide uppercase">Industrial SaaS Platform</p>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {navItems.map(({ id, label, icon: Icon }) => {
            const isActive = activeTab === id;
            return (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-semibold transition-all ${
                  isActive
                    ? "bg-sky-600/20 text-sky-400 border border-sky-500/30 shadow-sm"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                }`}
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                <span>{label}</span>
              </button>
            );
          })}
        </nav>

        <div className="p-4 border-t border-slate-800">
          <div className="bg-slate-950 rounded-xl border border-slate-800 p-3.5 space-y-2.5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">System Status</span>
              <button onClick={loadHealth} className="text-[10px] text-sky-400 hover:underline" title="Refresh health">
                ↻
              </button>
            </div>
            {["postgresql", "neo4j", "qdrant", "ollama"].map(svc => {
              const status = svcStatus(svc);
              const isOk = status === "healthy";
              const isWarn = status === "unhealthy";
              return (
                <div key={svc} className="flex items-center justify-between">
                  <span className="text-[11px] text-slate-400 capitalize font-medium">{svc}</span>
                  <div className="flex items-center gap-1.5">
                    <div className={`w-1.5 h-1.5 rounded-full ${isOk ? "bg-emerald-400" : isWarn ? "bg-rose-400" : "bg-amber-400"}`} />
                    <span className={`text-[10px] font-mono font-bold uppercase ${isOk ? "text-emerald-400" : isWarn ? "text-rose-400" : "text-amber-400"}`}>
                      {healthLoading ? "..." : status || "OK"}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </aside>

      <main className="flex-1 flex flex-col overflow-hidden bg-slate-950">
        <header className="h-14 border-b border-slate-800 bg-slate-900/60 px-6 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-bold text-white capitalize tracking-wide">
              {navItems.find(n => n.id === activeTab)?.label}
            </h2>
            {selectedProductId && products.find(p => p.id === selectedProductId) && (
              <>
                <ChevronRight className="w-4 h-4 text-slate-600" />
                <span className="text-xs text-sky-400 font-bold font-mono">
                  {products.find(p => p.id === selectedProductId)?.name}
                </span>
              </>
            )}
          </div>
          <div className="flex items-center gap-3">
            <span className="px-3 py-1 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> ENGINE ACTIVE
            </span>
          </div>
        </header>

        <div className="flex-1 overflow-auto p-6">
          {activeTab === "dashboard" && (
            <div className="space-y-6">
              <div className="grid grid-cols-4 gap-4">
                {[
                  { l: "Registered Products", v: products.length, c: "text-sky-400", sub: "Catalog Entities" },
                  { l: "Ingestion Pipeline", v: "ACTIVE", c: "text-emerald-400", sub: "Docling + LLM" },
                  { l: "Neo4j Provenance", v: svcStatus("neo4j") === "healthy" ? "HEALTHY" : "OFFLINE", c: svcStatus("neo4j") === "healthy" ? "text-emerald-400" : "text-amber-400", sub: "Graph Driver" },
                  { l: "Qdrant Vector DB", v: svcStatus("qdrant") === "healthy" ? "HEALTHY" : "OFFLINE", c: svcStatus("qdrant") === "healthy" ? "text-emerald-400" : "text-amber-400", sub: "Semantic Index" },
                ].map(({ l, v, c, sub }) => (
                  <div key={l} className="p-5 bg-slate-900 border border-slate-800 rounded-xl shadow-sm space-y-1">
                    <div className="text-xs font-semibold text-slate-400">{l}</div>
                    <div className={`text-2xl font-bold font-mono ${c}`}>{v}</div>
                    <div className="text-[10px] text-slate-500">{sub}</div>
                  </div>
                ))}
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-3 shadow-sm">
                <h3 className="text-sm font-bold text-white">Create Product Workspace</h3>
                <p className="text-xs text-slate-400">Initialize a new product identity to ingest datasheets and cross-reference truth attributes.</p>
                <div className="flex gap-3 pt-1">
                  <input
                    type="text"
                    placeholder="e.g. Industrial Electric Motor EM-750"
                    value={newProductName}
                    onChange={e => setNewProductName(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && handleCreateProduct()}
                    className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"
                  />
                  <button
                    onClick={handleCreateProduct}
                    disabled={creating || !newProductName.trim()}
                    className="px-5 py-2.5 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-sm font-bold rounded-lg transition-colors shadow-md"
                  >
                    {creating ? "Creating..." : "Create Product"}
                  </button>
                </div>
              </div>

              {products.length > 0 && (
                <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
                  <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
                    <h3 className="text-sm font-bold text-white">Product Catalog Workspaces</h3>
                    <span className="text-xs text-slate-500 font-mono">{products.length} Products</span>
                  </div>
                  <div className="divide-y divide-slate-800">
                    {products.map(p => (
                      <button
                        key={p.id}
                        className={`w-full flex items-center justify-between px-5 py-4 hover:bg-slate-800/50 transition-colors text-left ${selectedProductId === p.id ? "bg-slate-800/30" : ""}`}
                        onClick={() => {
                          setSelectedProductId(p.id);
                          setActiveTab("workspace");
                        }}
                      >
                        <div className="flex items-center gap-3">
                          <Package className="w-5 h-5 text-sky-400" />
                          <div>
                            <div className="text-sm font-bold text-white">{p.name}</div>
                            <div className="text-xs text-slate-400 flex items-center gap-2 mt-0.5">
                              {p.model_number && <span className="font-mono text-sky-400">Model: {p.model_number}</span>}
                              {p.manufacturer && <span>· {p.manufacturer}</span>}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-3 text-xs text-slate-400">
                          <span>Open Workspace</span>
                          <ChevronRight className="w-4 h-4 text-slate-500" />
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {needsProduct && (
            <div className="flex flex-col items-center justify-center h-64 gap-3 text-slate-500 bg-slate-900 border border-slate-800 rounded-xl p-8">
              <Layers className="w-10 h-10 text-slate-600" />
              <p className="text-sm text-slate-300 font-medium">Select a product workspace from the Dashboard to continue</p>
              <button onClick={() => setActiveTab("dashboard")} className="text-sky-400 text-xs font-bold hover:underline">
                Go to Dashboard
              </button>
            </div>
          )}

          {activeTab === "workspace" && selectedProductId && <ProductWorkspace productId={selectedProductId} />}
          {activeTab === "sources" && selectedProductId && <SourceManager productId={selectedProductId} />}
          {activeTab === "conflicts" && selectedProductId && <ConflictWorkspace productId={selectedProductId} />}
          {activeTab === "graph" && selectedProductId && <TruthGraph productId={selectedProductId} />}
          {activeTab === "export" && selectedProductId && <ExportPanel productId={selectedProductId} />}

          {activeTab === "processing" && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-5">
              <div>
                <h3 className="text-base font-bold text-white">Truth Engine Pipeline Stages</h3>
                <p className="text-xs text-slate-400 mt-0.5">8-stage deterministic and LLM-assisted verification workflow</p>
              </div>

              <div className="space-y-4">
                {[
                  { s: "INGESTING", d: "File validated, SHA-256 hash computed, duplicate document check executed." },
                  { s: "PARSING", d: "Docling layout-aware PDF parsing — text blocks, tables, headings with page references." },
                  { s: "EXTRACTING", d: "Rule-based + LLM claim extraction — values stored strictly as claims, never direct truth." },
                  { s: "NORMALIZING", d: "Deterministic unit conversion (5 HP → 3.73 kW, 7500 W → 7.5 kW, bar → psi)." },
                  { s: "VALIDATING", d: "Dimensional compatibility and schema validation per attribute definition." },
                  { s: "BUILDING TRUTH", d: "Cross-source claim comparison, conflict detection, deterministic confidence scoring." },
                  { s: "PERSISTING", d: "PostgreSQL (operational) + Qdrant (semantic index) + Neo4j (provenance graph)." },
                  { s: "COMPLETED", d: "Attributes, evidence, and provenance graph nodes available via REST API." },
                ].map(({ s, d }, i) => (
                  <div key={s} className="flex items-start gap-4 bg-slate-950 border border-slate-800 rounded-xl p-4">
                    <div className="w-7 h-7 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center justify-center flex-shrink-0 text-xs font-bold font-mono">
                      {i + 1}
                    </div>
                    <div>
                      <div className="text-xs font-bold text-slate-200">{s}</div>
                      <div className="text-xs text-slate-400 mt-1 leading-relaxed">{d}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
