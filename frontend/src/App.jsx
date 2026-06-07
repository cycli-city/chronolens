import { useState, useEffect, useCallback, Fragment } from "react";
import { useDropzone } from "react-dropzone";
import { motion, AnimatePresence } from "framer-motion";
import {
  Archive, Upload, Search, GitCompare, Layers,
  FileText, ArrowRight, Clock, Plus, Microscope, Network, LogOut
} from "lucide-react";
import { supabase } from "./supabase";
import {
  uploadDocument, getVersions, getStats,
  askQuestion, compareVersions, getTimeline,
  semanticDiff, causalGraph, listDocuments
} from "./api/client";

const DOC_TYPES = ["general", "contract", "policy", "regulation", "report", "memo"];

function loadKnownDocs() {
  try { return JSON.parse(localStorage.getItem("chronolens_docs") || "[]"); }
  catch { return []; }
}
function saveKnownDocs(docs) {
  localStorage.setItem("chronolens_docs", JSON.stringify(docs));
}

/* ─────────────────────────────────────────
   AUTH GATE
───────────────────────────────────────── */
function AuthGate({ onAuth }) {
  const [tab, setTab] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function handleLogin() {
    setBusy(true); setError(""); setSuccess("");
    const { data, error: err } = await supabase.auth.signInWithPassword({ email, password });
    setBusy(false);
    if (err) return setError(err.message);
    onAuth(data.user);
  }

  async function handleSignup() {
    setBusy(true); setError(""); setSuccess("");
    const { error: err } = await supabase.auth.signUp({ email, password });
    setBusy(false);
    if (err) return setError(err.message);
    setSuccess("Account created — check your email to confirm, then log in.");
    setTab("login");
  }

  function submit() { tab === "login" ? handleLogin() : handleSignup(); }

  return (
    <div className="auth-wrap">
      <motion.div
        className="auth-box"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="auth-logo">Chrono<span className="accent">Lens</span></div>
        <div className="auth-tagline">Reading documents across the dimension of time.</div>

        <div className="auth-tabs">
          <button className={`auth-tab ${tab === "login" ? "active" : ""}`} onClick={() => { setTab("login"); setError(""); setSuccess(""); }}>
            Sign In
          </button>
          <button className={`auth-tab ${tab === "signup" ? "active" : ""}`} onClick={() => { setTab("signup"); setError(""); setSuccess(""); }}>
            Create Account
          </button>
        </div>

        {error && <div className="auth-error">{error}</div>}
        {success && <div className="auth-success">{success}</div>}

        <div className="field">
          <label className="field-label">Email</label>
          <input className="input" type="email" placeholder="you@example.com"
            value={email} onChange={(e) => setEmail(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()} />
        </div>
        <div className="field">
          <label className="field-label">Password</label>
          <input className="input" type="password" placeholder="••••••••"
            value={password} onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()} />
        </div>

        <button className="btn btn-primary" onClick={submit} disabled={busy}>
          {busy ? <span className="spinner" /> : tab === "login" ? "Sign In" : "Create Account"}
        </button>

        <div className="auth-footer">
          {tab === "login" ? "No account?" : "Already have one?"}&nbsp;
          <span style={{ color: "var(--amber)", cursor: "pointer" }}
            onClick={() => { setTab(tab === "login" ? "signup" : "login"); setError(""); }}>
            {tab === "login" ? "Sign up free" : "Sign in"}
          </span>
        </div>
      </motion.div>
    </div>
  );
}

/* ─────────────────────────────────────────
   MAIN APP
───────────────────────────────────────── */
export default function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [knownDocs, setKnownDocs] = useState(loadKnownDocs());
  const [activeDoc, setActiveDoc] = useState(null);
  const [versions, setVersions] = useState([]);
  const [stats, setStats] = useState({ total_chunks: 0 });
  const [mode, setMode] = useState("ask");

  // Check existing session on load
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
      setLoading(false);
    });
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });
    return () => subscription.unsubscribe();
  }, []);

  const refreshVersions = useCallback(async (docId) => {
    if (!docId) return;
    try {
      const data = await getVersions(docId);
      setVersions(data.versions || []);
    } catch { setVersions([]); }
  }, []);

  useEffect(() => {
    if (user) {
      getStats().then(setStats).catch(() => {});
      listDocuments()
        .then((data) => {
          if (data?.documents?.length) {
            setKnownDocs(data.documents);
            saveKnownDocs(data.documents);
          }
        })
        .catch(() => {});
    }
  }, [user]);

  useEffect(() => {
    if (activeDoc) refreshVersions(activeDoc);
  }, [activeDoc, refreshVersions]);

  function registerDoc(docId) {
    if (!knownDocs.includes(docId)) {
      const next = [...knownDocs, docId];
      setKnownDocs(next);
      saveKnownDocs(next);
    }
  }

  async function handleSignOut() {
    await supabase.auth.signOut();
    setUser(null);
    setActiveDoc(null);
    setVersions([]);
  }

  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long", year: "numeric", month: "long", day: "numeric"
  });

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <span className="spinner" style={{ width: 24, height: 24, borderWidth: 3 }} />
      </div>
    );
  }

  if (!user) return <AuthGate onAuth={setUser} />;

  return (
    <>
      <header className="masthead">
        <div className="masthead-toprule">
          <span>Temporal Document Intelligence</span>
          <span style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-faint)" }}>
              {user.email}
            </span>
            <button
              onClick={handleSignOut}
              style={{ background: "transparent", border: "none", color: "var(--ink-faint)", cursor: "pointer", display: "flex", alignItems: "center", gap: 4, fontFamily: "var(--font-mono)", fontSize: 11 }}
            >
              <LogOut size={12} /> Sign out
            </button>
          </span>
        </div>
        <motion.h1
          className="masthead-title"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          Chrono<span className="accent">Lens</span>
        </motion.h1>
        <div className="masthead-sub">
          <span className="masthead-tagline">Reading documents across the dimension of time.</span>
          <span className="masthead-stat">
            <b>{stats.total_chunks}</b> fragments archived &nbsp;·&nbsp; {today}
          </span>
        </div>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <div>
            <div className="section-label"><Archive size={13} /> The Archive</div>
            <div className="doc-list">
              {knownDocs.length === 0 && (
                <div className="doc-empty">No documents yet. Deposit one below.</div>
              )}
              {knownDocs.map((d) => (
                <button
                  key={d}
                  className={`doc-item ${activeDoc === d ? "active" : ""}`}
                  onClick={() => setActiveDoc(d)}
                >
                  <FileText size={14} />
                  <span className="doc-id">{d}</span>
                </button>
              ))}
            </div>
          </div>

          <UploadPanel
            activeDoc={activeDoc}
            onUploaded={(docId) => {
              registerDoc(docId);
              setActiveDoc(docId);
              refreshVersions(docId);
              getStats().then(setStats).catch(() => {});
            }}
          />
        </aside>

        <main className="workspace">
          {!activeDoc ? (
            <div className="empty-state">
              <div className="big">Select or deposit a document to begin.</div>
              <div>Every version you add becomes a point in time you can question, compare, and trace.</div>
            </div>
          ) : (
            <>
              <div className="timeline-wrap">
                <div className="section-label"><Clock size={13} /> Version Timeline · {activeDoc}</div>
                {versions.length === 0 ? (
                  <div className="doc-empty">No versions found for this document.</div>
                ) : (
                  <div className="timeline">
                    {versions.map((v, i) => (
                      <motion.div
                        key={v.version}
                        className="version-card"
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.08 }}
                      >
                        <div className="version-node" />
                        <div className="version-num">Version {v.version}</div>
                        <div className="version-date">{v.timestamp}</div>
                        <div className="version-name">{v.doc_name}</div>
                      </motion.div>
                    ))}
                  </div>
                )}
              </div>

              <div className="mode-tabs">
                <button className={`mode-tab ${mode === "ask" ? "active" : ""}`} onClick={() => setMode("ask")}>
                  <Search size={14} /> Interrogate
                </button>
                <button className={`mode-tab ${mode === "compare" ? "active" : ""}`} onClick={() => setMode("compare")}>
                  <GitCompare size={14} /> Compare
                </button>
                <button className={`mode-tab ${mode === "diff" ? "active" : ""}`} onClick={() => setMode("diff")}>
                  <Microscope size={14} /> Semantic Diff
                </button>
                <button className={`mode-tab ${mode === "evolve" ? "active" : ""}`} onClick={() => setMode("evolve")}>
                  <Layers size={14} /> Trace Evolution
                </button>
                <button className={`mode-tab ${mode === "graph" ? "active" : ""}`} onClick={() => setMode("graph")}>
                  <Network size={14} /> Causal Graph
                </button>
              </div>

              <AnimatePresence mode="wait">
                <motion.div
                  key={mode}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.25 }}
                >
                  {mode === "ask" && <AskPanel docId={activeDoc} />}
                  {mode === "compare" && <ComparePanel docId={activeDoc} versions={versions} />}
                  {mode === "diff" && <DiffPanel docId={activeDoc} versions={versions} />}
                  {mode === "evolve" && <EvolvePanel docId={activeDoc} />}
                  {mode === "graph" && <GraphPanel docId={activeDoc} />}
                </motion.div>
              </AnimatePresence>
            </>
          )}
        </main>
      </div>
    </>
  );
}

/* ---------- Upload Panel ---------- */
function UploadPanel({ activeDoc, onUploaded }) {
  const [file, setFile] = useState(null);
  const [docId, setDocId] = useState("");
  const [version, setVersion] = useState(1);
  const [timestamp, setTimestamp] = useState("");
  const [docName, setDocName] = useState("");
  const [docType, setDocType] = useState("general");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { if (activeDoc) setDocId(activeDoc); }, [activeDoc]);

  const onDrop = useCallback((accepted) => {
    if (accepted[0]) {
      setFile(accepted[0]);
      if (!docName) setDocName(accepted[0].name.replace(/\.[^.]+$/, ""));
    }
  }, [docName]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
    },
    maxFiles: 1,
  });

  async function submit() {
    setError("");
    if (!file) return setError("Attach a PDF or DOCX file.");
    if (!docId.trim()) return setError("Document ID required.");
    if (!timestamp) return setError("Date required.");
    if (!docName.trim()) return setError("Document name required.");

    const fd = new FormData();
    fd.append("file", file);
    fd.append("document_id", docId.trim());
    fd.append("version", String(version));
    fd.append("timestamp", timestamp);
    fd.append("doc_name", docName.trim());
    fd.append("doc_type", docType);

    setBusy(true);
    try {
      await uploadDocument(fd);
      onUploaded(docId.trim());
      setFile(null);
      setDocName("");
      setVersion((v) => Number(v) + 1);
    } catch (e) {
      setError(e.message || "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="section-label"><Upload size={13} /> Deposit a Version</div>

      <div {...getRootProps()} className={`dropzone ${isDragActive ? "active" : ""}`}>
        <input {...getInputProps()} />
        <div className="dropzone-icon"><FileText size={22} /></div>
        <div className="dropzone-text">
          {isDragActive ? "Release to attach" : "Drag a PDF/DOCX or click"}
        </div>
        {file && <div className="dropzone-file">{file.name}</div>}
      </div>

      <div className="field">
        <label className="field-label">Document ID</label>
        <input className="input" placeholder="e.g. vendor_agreement"
          value={docId} onChange={(e) => setDocId(e.target.value)} />
      </div>

      <div className="row-2">
        <div className="field">
          <label className="field-label">Version</label>
          <input className="input" type="number" min={1}
            value={version} onChange={(e) => setVersion(e.target.value)} />
        </div>
        <div className="field">
          <label className="field-label">Date</label>
          <input className="input" type="date"
            value={timestamp} onChange={(e) => setTimestamp(e.target.value)} />
        </div>
      </div>

      <div className="field">
        <label className="field-label">Name</label>
        <input className="input" placeholder="Display name"
          value={docName} onChange={(e) => setDocName(e.target.value)} />
      </div>

      <div className="field">
        <label className="field-label">Type</label>
        <select className="select" value={docType} onChange={(e) => setDocType(e.target.value)}>
          {DOC_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      <button className="btn btn-primary" onClick={submit} disabled={busy}>
        {busy ? <span className="spinner" /> : <><Plus size={14} /> Archive Version</>}
      </button>

      {error && <div className="error-bar">{error}</div>}
    </div>
  );
}

/* ---------- Ask Panel ---------- */
function AskPanel({ docId }) {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function ask() {
    if (!question.trim()) return;
    setBusy(true); setError(""); setResult(null);
    try {
      const data = await askQuestion(docId, question.trim());
      setResult(data);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  return (
    <div>
      <p className="panel-intro">
        Ask anything of this document. ChronoLens retrieves the most relevant fragments and answers with citations to the exact version and date.
      </p>
      <div className="field">
        <input className="input" placeholder="What obligations does this document define?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask()} />
      </div>
      <button className="btn btn-primary" style={{ width: "auto", paddingLeft: 32, paddingRight: 32 }}
        onClick={ask} disabled={busy}>
        {busy ? <span className="spinner" /> : <><Search size={14} /> Interrogate</>}
      </button>

      {error && <div className="error-bar">{error}</div>}

      {result && (
        <div className="result">
          <div className="result-head"><FileText size={12} /> Answer</div>
          <div className="result-body">{result.answer}</div>
          {result.sources?.length > 0 && (
            <div className="sources">
              {result.sources.map((s, i) => (
                <span key={i} className="source-chip">
                  v<b>{s.version}</b> · {s.timestamp}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ---------- Compare Panel ---------- */
function ComparePanel({ docId, versions }) {
  const [va, setVa] = useState("");
  const [vb, setVb] = useState("");
  const [aspect, setAspect] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (versions.length >= 2) {
      setVa(String(versions[0].version));
      setVb(String(versions[versions.length - 1].version));
    }
  }, [versions]);

  async function run() {
    setError(""); setResult(null);
    if (va === vb) return setError("Choose two different versions.");
    setBusy(true);
    try {
      const data = await compareVersions(docId, Number(va), Number(vb), aspect.trim());
      setResult(data);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  if (versions.length < 2) {
    return <p className="panel-intro">Upload at least two versions of this document to compare them across time.</p>;
  }

  return (
    <div>
      <p className="panel-intro">
        Place two versions side by side. ChronoLens identifies what was added, removed, modified — and flags changes that carry risk.
      </p>
      <div className="compare-selects">
        <div className="field">
          <label className="field-label">From Version</label>
          <select className="select" value={va} onChange={(e) => setVa(e.target.value)}>
            {versions.map((v) => <option key={v.version} value={v.version}>v{v.version} · {v.timestamp}</option>)}
          </select>
        </div>
        <span className="compare-arrow"><ArrowRight size={20} /></span>
        <div className="field">
          <label className="field-label">To Version</label>
          <select className="select" value={vb} onChange={(e) => setVb(e.target.value)}>
            {versions.map((v) => <option key={v.version} value={v.version}>v{v.version} · {v.timestamp}</option>)}
          </select>
        </div>
        <div className="field" style={{ flex: 1, minWidth: 200 }}>
          <label className="field-label">Focus (optional)</label>
          <input className="input" placeholder="e.g. payment terms, liability"
            value={aspect} onChange={(e) => setAspect(e.target.value)} />
        </div>
      </div>
      <button className="btn btn-primary" style={{ width: "auto", paddingLeft: 32, paddingRight: 32 }}
        onClick={run} disabled={busy}>
        {busy ? <span className="spinner" /> : <><GitCompare size={14} /> Compare Versions</>}
      </button>

      {error && <div className="error-bar">{error}</div>}

      {result && (
        <div className="result">
          <div className="result-head">
            <GitCompare size={12} /> v{result.version_a} → v{result.version_b} · {result.aspect}
          </div>
          <div className="result-body">{result.analysis}</div>
        </div>
      )}
    </div>
  );
}

/* ---------- Evolve Panel ---------- */
function EvolvePanel({ docId }) {
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run() {
    setBusy(true); setError(""); setResult(null);
    try {
      const data = await getTimeline(docId);
      setResult(data);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  return (
    <div>
      <p className="panel-intro">
        Trace the entire life of this document. ChronoLens reads every version in sequence and narrates how — and why — it evolved.
      </p>
      <button className="btn btn-primary" style={{ width: "auto", paddingLeft: 32, paddingRight: 32 }}
        onClick={run} disabled={busy}>
        {busy ? <span className="spinner" /> : <><Layers size={14} /> Generate Timeline</>}
      </button>

      {error && <div className="error-bar">{error}</div>}

      {result && (
        <div className="result">
          <div className="result-head"><Layers size={12} /> Evolution · {result.total_versions || 0} versions</div>
          <div className="result-body">
            {result.timeline_narrative || result.message}
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------- Semantic Diff Panel ---------- */
function DiffPanel({ docId, versions }) {
  const [va, setVa] = useState("");
  const [vb, setVb] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (versions.length >= 2) {
      setVa(String(versions[0].version));
      setVb(String(versions[versions.length - 1].version));
    }
  }, [versions]);

  async function run() {
    setError(""); setResult(null);
    if (va === vb) return setError("Choose two different versions.");
    setBusy(true);
    try {
      const data = await semanticDiff(docId, Number(va), Number(vb));
      setResult(data);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  if (versions.length < 2) {
    return <p className="panel-intro">Upload at least two versions to run a semantic diff.</p>;
  }

  const s = result?.summary;
  const visible = result?.changes?.filter((c) => c.type !== "unchanged") || [];

  return (
    <div>
      <p className="panel-intro">
        A precise, embedding-level diff. Rather than asking an AI to eyeball changes, ChronoLens aligns every fragment by meaning, classifies each as added, removed, or modified — then explains only what truly changed.
      </p>
      <div className="compare-selects">
        <div className="field">
          <label className="field-label">From Version</label>
          <select className="select" value={va} onChange={(e) => setVa(e.target.value)}>
            {versions.map((v) => <option key={v.version} value={v.version}>v{v.version} · {v.timestamp}</option>)}
          </select>
        </div>
        <span className="compare-arrow"><ArrowRight size={20} /></span>
        <div className="field">
          <label className="field-label">To Version</label>
          <select className="select" value={vb} onChange={(e) => setVb(e.target.value)}>
            {versions.map((v) => <option key={v.version} value={v.version}>v{v.version} · {v.timestamp}</option>)}
          </select>
        </div>
      </div>
      <button className="btn btn-primary" style={{ width: "auto", paddingLeft: 32, paddingRight: 32 }}
        onClick={run} disabled={busy}>
        {busy ? <span className="spinner" /> : <><Microscope size={14} /> Run Semantic Diff</>}
      </button>

      {error && <div className="error-bar">{error}</div>}

      {s && (
        <>
          <div className="diff-summary">
            <span className="diff-stat added">+{s.added} added</span>
            <span className="diff-stat removed">−{s.removed} removed</span>
            <span className="diff-stat modified">~{s.modified} modified</span>
            <span className="diff-stat unchanged">={s.unchanged} unchanged</span>
            <span className="diff-ratio">{Math.round(s.change_ratio * 100)}% changed</span>
          </div>
          <div className="diff-bar">
            <span className="seg added" style={{ flex: s.added || 0 }} />
            <span className="seg modified" style={{ flex: s.modified || 0 }} />
            <span className="seg removed" style={{ flex: s.removed || 0 }} />
            <span className="seg unchanged" style={{ flex: s.unchanged || 0 }} />
          </div>

          <div className="changes">
            {visible.length === 0 && (
              <div className="doc-empty">No substantive changes detected between these versions.</div>
            )}
            {visible.map((c, i) => (
              <div key={i} className={`change-block ${c.type}`}>
                <div className="change-tag">
                  {c.type}{c.similarity != null ? ` · similarity ${c.similarity}` : ""}
                </div>
                {c.type === "modified" ? (
                  <>
                    {c.explanation && <div className="diff-explain">{c.explanation}</div>}
                    <div className="diff-cols">
                      <div className="diff-col">
                        <div className="diff-col-label">Before · v{result.version_a}</div>
                        <div className="change-text">{c.before}</div>
                      </div>
                      <div className="diff-col">
                        <div className="diff-col-label">After · v{result.version_b}</div>
                        <div className="change-text">{c.after}</div>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="change-text">{c.text}</div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/* ---------- Causal Graph Panel ---------- */
function GraphPanel({ docId }) {
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run() {
    setBusy(true); setError(""); setResult(null);
    try {
      const data = await causalGraph(docId);
      setResult(data);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  return (
    <div>
      <p className="panel-intro">
        The crown jewel. ChronoLens chains its semantic diff across every consecutive version, then reasons over the whole timeline to infer <em>why</em> each change likely happened — with a confidence rating.
      </p>
      <button className="btn btn-primary" style={{ width: "auto", paddingLeft: 32, paddingRight: 32 }}
        onClick={run} disabled={busy}>
        {busy ? <span className="spinner" /> : <><Network size={14} /> Build Causal Graph</>}
      </button>

      {error && <div className="error-bar">{error}</div>}

      {result && (
        <div className="causal-graph">
          {result.nodes.map((node, i) => {
            const edge = result.edges.find((e) => e.from_version === node.version);
            const isLast = i === result.nodes.length - 1;
            const mag = edge?.change_magnitude || 0;

            const lineStyle = {
              "--thick": mag > 0.5 ? "5px" : mag > 0.2 ? "3px" : "2px",
              "--col": mag > 0.5 ? "var(--amber)" : mag > 0.2 ? "var(--copper)" : "var(--rule-bright)",
              "--glow": mag > 0.5 ? "0 0 12px rgba(212,154,63,0.5)" : "none",
            };

            return (
              <Fragment key={node.version}>
                <motion.div
                  className={`cg-row node ${isLast ? "latest" : ""}`}
                  initial={{ opacity: 0, x: -16 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.15 }}
                >
                  <div className="cg-spine">
                    <div className="cg-circle">{node.version}</div>
                  </div>
                  <div className="cg-card">
                    <div className="cg-card-ver">Version {node.version}</div>
                    <div className="cg-card-date">{node.timestamp}</div>
                    <div className="cg-card-name">{node.doc_name}</div>
                  </div>
                </motion.div>

                {edge && (
                  <motion.div
                    className="cg-row edge"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.15 + 0.08 }}
                  >
                    <div className="cg-spine">
                      <div className="cg-line" style={lineStyle} />
                    </div>
                    <div className={`cg-edge-card ${edge.confidence}`}>
                      <div className="cg-cause">↳ {edge.inferred_cause}</div>
                      {edge.correlated_events?.length > 0 && (
                        <div className="cg-evidence">
                          {edge.correlated_events.map((ev, ei) => (
                            <div key={ei} className="cg-ev-item">
                              <span className="cg-ev-date">{ev.event_date}</span>
                              <span className="cg-ev-title">{ev.title}</span>
                              <span className="cg-ev-score">
                                {ev.days_before_change}d prior · sem={ev.semantic_score.toFixed(2)}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                      <div className="cg-edge-meta">
                        <span className={`cg-conf ${edge.confidence}`}>
                          {edge.confidence} confidence
                        </span>
                        <div className="cg-counts">
                          {edge.summary.added > 0 && <span className="cnt added">+{edge.summary.added}</span>}
                          {edge.summary.removed > 0 && <span className="cnt removed">−{edge.summary.removed}</span>}
                          {edge.summary.modified > 0 && <span className="cnt modified">~{edge.summary.modified}</span>}
                        </div>
                        <div className="cg-mag">
                          <div className="cg-mag-bar">
                            <div className="cg-mag-fill" style={{ width: `${Math.round(mag * 100)}%` }} />
                          </div>
                          <span className="cg-mag-num">{Math.round(mag * 100)}%</span>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}
              </Fragment>
            );
          })}
        </div>
      )}
    </div>
  );
}