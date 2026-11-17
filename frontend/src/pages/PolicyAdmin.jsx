import React, { useState, useEffect } from 'react';
import { ShieldAlert, CheckCircle, FileText, ArrowRight, RefreshCw, Plus, Check, History, Layers, AlertCircle, ShieldCheck, Edit, Save, Lock, Unlock } from 'lucide-react';
import { fetchActivePolicy, fetchPolicyVersions, uploadPolicyAmendment, activatePolicyVersion, fetchPolicyVersionDetail, updatePolicyParameters } from '../api';

export default function PolicyAdmin() {
  const [activePolicy, setActivePolicy] = useState(null);
  const [versions, setVersions] = useState([]);
  const [selectedVersion, setSelectedVersion] = useState(null);
  const [loading, setLoading] = useState(false);

  // Amendment upload form
  const [amendmentForm, setAmendmentForm] = useState({
    versionId: 'v5.1',
    name: 'Corvo Policy v5.1 Amendment',
    effectiveDate: '2026-12-01',
    amendmentText: 'Increase emergency PO threshold from 500,000 to 750,000 INR and increase RFQ threshold from 200,000 to 300,000 INR',
    createdBy: 'Head of Procurement',
  });
  const [draftResult, setDraftResult] = useState(null);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [activating, setActivating] = useState(false);

  // Admin write access toggle
  const [writeAccess, setWriteAccess] = useState(false);
  const [savingParams, setSavingParams] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const [active, vers] = await Promise.all([
        fetchActivePolicy(),
        fetchPolicyVersions()
      ]);
      setActivePolicy(active);
      setVersions(vers);
      if (active?.version_id) {
        const detail = await fetchPolicyVersionDetail(active.version_id);
        setSelectedVersion(detail);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSelectVersion = async (vid) => {
    try {
      const detail = await fetchPolicyVersionDetail(vid);
      setSelectedVersion(detail);
    } catch (err) {
      alert(err.message);
    }
  };

  const handleUploadAmendment = async (e) => {
    e.preventDefault();
    setUploadLoading(true);
    setDraftResult(null);
    try {
      const res = await uploadPolicyAmendment({
        version_id: amendmentForm.versionId,
        name: amendmentForm.name,
        effective_date: amendmentForm.effectiveDate,
        amendment_text: amendmentForm.amendmentText,
        created_by: amendmentForm.createdBy,
      });
      setDraftResult(res);
      await loadData();
      handleSelectVersion(res.version_id);
    } catch (err) {
      alert(err.message);
    } finally {
      setUploadLoading(false);
    }
  };

  const handleActivate = async (vid) => {
    if (!window.confirm(`Are you sure you want to activate policy version ${vid}? This will dynamically supersede the current active policy without restarting the server.`)) {
      return;
    }
    setActivating(true);
    try {
      await activatePolicyVersion(vid, 'CPO / Governance Committee', 'Approved through Policy Admin');
      alert(`Policy ${vid} is now ACTIVE!`);
      await loadData();
      handleSelectVersion(vid);
    } catch (err) {
      alert(err.message);
    } finally {
      setActivating(false);
    }
  };

  const saveParams = async () => {
    if (!selectedVersion || !selectedVersion.rules_definition) return;
    setSavingParams(true);
    try {
      const params = {};
      selectedVersion.rules_definition.parameters &&
        Object.entries(selectedVersion.rules_definition.parameters).forEach(([k, v]) => {
          const el = document.getElementById(`param-${k}`);
          if (el) params[k] = el.value === '' ? v : Number(el.value);
        });
      await updatePolicyParameters(selectedVersion.version_id, params, 'Policy Admin');
      await loadData();
      alert('Parameters updated and synced to decision rules.');
    } catch (err) {
      alert(err.message);
    } finally {
      setSavingParams(false);
    }
  };

  const formatValue = (val) => {
    if (val === null || val === undefined) return 'None';
    if (typeof val === 'object') {
      return JSON.stringify(val, null, 2);
    }
    if (typeof val === 'number') {
      return `₹${val.toLocaleString('en-IN')}`;
    }
    return String(val);
  };

  const formatParamKey = (k) => {
    if (!k) return '';
    return k
      .split('_')
      .map((w) => {
        const upper = w.toUpperCase();
        if (['PO', 'RFQ', 'RFP', 'INR', 'USD', 'CEO', 'CPO'].includes(upper)) return upper;
        return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
      })
      .join(' ');
  };

  const renderParamValue = (k, v) => {
    if (v === null || v === undefined) return 'None';
    if (typeof v === 'number') {
      if (/days$/.test(k)) return `${v} days`;
      if (/hours$/.test(k)) return `${v} hrs`;
      return `₹${v.toLocaleString('en-IN')}`;
    }
    return String(v);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6 overflow-hidden">
      {/* Header */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-800 flex items-center space-x-2">
            <ShieldAlert className="w-5 h-5 text-sky-600 flex-shrink-0" />
            <span>Policy-as-Data Administration & Amendment Control</span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Corvo Procurement policies are defined dynamically as structured data. Upload amendments, inspect diffs, and activate new rules without restarting code.
          </p>
        </div>

        {activePolicy && (
          <div className="flex items-center space-x-3 bg-emerald-50 border border-emerald-200 px-4 py-2 rounded-lg flex-shrink-0">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
            <div>
              <div className="text-[11px] text-emerald-800 font-semibold">Active Policy Engine</div>
              <div className="text-xs font-mono font-bold text-emerald-900">
                {activePolicy.version_id} ({activePolicy.name})
              </div>
            </div>
          </div>
        )}

        {/* Admin access toggle */}
        <div className="flex items-center space-x-2 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-lg flex-shrink-0">
          <span className="text-[10px] text-slate-500 font-medium">Admin Mode:</span>
          <button
            onClick={() => setWriteAccess(!writeAccess)}
            className={`px-2.5 py-1 rounded text-[10px] font-semibold transition-colors ${
              writeAccess
                ? 'bg-amber-100 text-amber-800 border border-amber-200'
                : 'bg-slate-200 text-slate-700 border border-slate-300'
            }`}
          >
            {writeAccess ? (
              <>
                <Lock className="w-3 h-3 mr-1" /> Write Access
              </>
            ) : (
              <>
                <Unlock className="w-3 h-3 mr-1" /> Read-Only
              </>
            )}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Col: Upload Amendment & Version History */}
        <div className="space-y-6 min-w-0">
          {/* Upload Amendment Form */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 text-xs">
            <h3 className="text-sm font-semibold text-slate-800 mb-3 flex items-center space-x-1.5">
              <Plus className="w-4 h-4 text-sky-600" />
              <span>Submit Policy Amendment</span>
            </h3>

            <form onSubmit={handleUploadAmendment} className="space-y-3">
              <div>
                <label className="block text-slate-600 font-semibold mb-1">New Version ID</label>
                <input
                  type="text"
                  value={amendmentForm.versionId}
                  onChange={(e) => setAmendmentForm({ ...amendmentForm, versionId: e.target.value })}
                  className="w-full border border-slate-300 rounded px-2.5 py-1.5 focus:ring-1 focus:ring-sky-500 font-mono"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-600 font-semibold mb-1">Policy Title</label>
                <input
                  type="text"
                  value={amendmentForm.name}
                  onChange={(e) => setAmendmentForm({ ...amendmentForm, name: e.target.value })}
                  className="w-full border border-slate-300 rounded px-2.5 py-1.5 focus:ring-1 focus:ring-sky-500"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-600 font-semibold mb-1">Effective Date</label>
                <input
                  type="date"
                  value={amendmentForm.effectiveDate}
                  onChange={(e) => setAmendmentForm({ ...amendmentForm, effectiveDate: e.target.value })}
                  className="w-full border border-slate-300 rounded px-2.5 py-1.5 focus:ring-1 focus:ring-sky-500"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-600 font-semibold mb-1">
                  Amendment Description (Natural Language or JSON)
                </label>
                <textarea
                  rows={4}
                  value={amendmentForm.amendmentText}
                  onChange={(e) => setAmendmentForm({ ...amendmentForm, amendmentText: e.target.value })}
                  placeholder="e.g. Increase emergency PO threshold to 750000 INR..."
                  className="w-full border border-slate-300 rounded px-2.5 py-1.5 focus:ring-1 focus:ring-sky-500 leading-relaxed font-sans"
                  required
                />
              </div>

              <button
                type="submit"
                disabled={uploadLoading}
                className="w-full bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white font-semibold py-2 rounded-lg flex items-center justify-center space-x-1.5 transition-colors shadow-sm"
              >
                {uploadLoading ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Analyzing Diff with LLM...</span>
                  </>
                ) : (
                  <span>Upload & Generate Diff</span>
                )}
              </button>
            </form>
          </div>

          {/* Policy Versions List with scroll container */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 text-xs">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-slate-800 flex items-center space-x-1.5">
                <History className="w-4 h-4 text-slate-600" />
                <span>Version History</span>
              </h3>
              <span className="text-[11px] text-slate-400 font-mono">({versions.length} versions)</span>
            </div>

            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {versions.map((v) => {
                const isSelected = selectedVersion?.version_id === v.version_id;
                return (
                  <div
                    key={v.version_id}
                    onClick={() => handleSelectVersion(v.version_id)}
                    className={`p-3 rounded-lg border cursor-pointer transition-all ${
                      isSelected
                        ? 'border-sky-500 bg-sky-50/50 shadow-sm'
                        : 'border-slate-200 hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-slate-800">{v.version_id}</span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          v.status === 'ACTIVE'
                            ? 'bg-emerald-100 text-emerald-800'
                            : v.status === 'DRAFT'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-slate-100 text-slate-500'
                        }`}
                      >
                        {v.status}
                      </span>
                    </div>
                    <div className="text-slate-600 mt-1 font-medium truncate">{v.name}</div>
                    <div className="text-slate-400 text-[10px] mt-1 font-mono">Effective: {v.effective_date}</div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right 2 Cols: Version Details, Diff Inspector & Dynamic Activation */}
        <div className="lg:col-span-2 space-y-6 min-w-0">
          {selectedVersion ? (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 space-y-6 text-xs min-w-0 overflow-hidden">
              {/* Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 gap-3">
                <div className="min-w-0">
                  <div className="flex items-center space-x-2">
                    <span className="text-base font-bold font-mono text-slate-900">
                      {selectedVersion.version_id}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        selectedVersion.status === 'ACTIVE'
                          ? 'bg-emerald-100 text-emerald-800'
                          : selectedVersion.status === 'DRAFT'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {selectedVersion.status}
                    </span>
                  </div>
                  <div className="text-slate-600 text-sm mt-0.5 font-medium truncate">{selectedVersion.name}</div>
                  <div className="text-slate-400 text-[11px] mt-0.5">
                    Parent: <span className="font-mono">{selectedVersion.parent_version_id || 'None (Base)'}</span> | Created By: {selectedVersion.created_by}
                  </div>
                  <div className="text-slate-600 text-[11px] mt-1 font-sans">
                    Status: <span className={`font-bold ${selectedVersion.status === 'ACTIVE' ? 'text-emerald-700' : 'text-slate-700'}`}>{selectedVersion.status}</span>
                    &bull; Effective: <span className="font-mono font-bold">{selectedVersion.effective_date}</span>
                    &bull; Approved By: <span className="font-bold">{selectedVersion.created_by}</span>
                  </div>
                </div>

                {selectedVersion.status !== 'ACTIVE' && (
                  <button
                    onClick={() => handleActivate(selectedVersion.version_id)}
                    disabled={activating}
                    className="bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-semibold px-4 py-2 rounded-lg flex items-center space-x-1.5 transition-colors shadow-sm flex-shrink-0"
                  >
                    <Check className="w-4 h-4" />
                    <span>{activating ? 'Activating...' : 'Approve & Activate'}</span>
                  </button>
                )}
              </div>

              {/* Formatted Diff Viewer */}
              {selectedVersion.diff && selectedVersion.diff.length > 0 ? (
                <div className="border border-slate-200 bg-white rounded-xl p-4 space-y-3">
                  <div className="font-semibold text-slate-800 flex items-center justify-between">
                    <span className="flex items-center space-x-1.5">
                      <Layers className="w-4 h-4 text-slate-600" />
                      <span>Structured Policy Changes Detected ({selectedVersion.diff.length})</span>
                    </span>
                    <span className="text-[11px] font-mono text-slate-500">
                      vs {selectedVersion.parent_version_id || 'v5.0'}
                    </span>
                  </div>

                  <div className="space-y-2.5 max-h-96 overflow-y-auto pr-1">
                    {selectedVersion.diff.map((d, idx) => (
                      <div key={idx} className="p-3 bg-white border border-slate-200 rounded-lg text-xs space-y-2 shadow-sm">
                        <div className="flex items-center space-x-2">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                              d.type === 'ADDED'
                                ? 'bg-emerald-100 text-emerald-800'
                                : d.type === 'REMOVED'
                                ? 'bg-rose-50 text-rose-700'
                                : 'bg-slate-100 text-slate-700'
                            }`}
                          >
                            {d.type}
                          </span>
                          <span className="font-mono font-bold text-slate-800 break-all">{d.path}</span>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
                          {/* Previous Value */}
                          {d.type === 'ADDED' ? (
                            <div className="p-2.5 bg-slate-50/50 border border-dashed border-slate-200 rounded text-slate-400 font-mono overflow-x-auto max-h-40 flex flex-col justify-center h-full">
                              <span className="text-[10px] uppercase font-bold text-slate-500 block font-sans mb-0.5 italic">
                                Previous Value:
                              </span>
                              <span className="text-[11px] italic">Not set in parent</span>
                            </div>
                          ) : d.type === 'REMOVED' ? (
                            <div className="p-2.5 bg-rose-50/60 border border-rose-200 rounded text-rose-700 font-mono overflow-x-auto max-h-40 line-through">
                              <span className="text-[10px] uppercase font-bold text-rose-600 block font-sans mb-0.5">
                                Previous Value:
                              </span>
                              <pre className="whitespace-pre-wrap break-all text-[11px]">
                                {formatValue(d.old_value)}
                              </pre>
                            </div>
                          ) : (
                            <div className="p-2.5 bg-slate-50 border border-slate-200 rounded text-slate-600 font-mono overflow-x-auto max-h-40">
                              <span className="text-[10px] uppercase font-bold text-slate-500 block font-sans mb-0.5">
                                Previous Value:
                              </span>
                              <pre className="whitespace-pre-wrap break-all text-[11px]">
                                {formatValue(d.old_value)}
                              </pre>
                            </div>
                          )}

                          {/* Updated Value */}
                          {d.type === 'REMOVED' ? (
                            <div className="p-2.5 bg-slate-50 border border-slate-200 rounded text-slate-400 font-mono overflow-x-auto max-h-40 flex flex-col justify-center h-full">
                              <span className="text-[10px] uppercase font-bold text-slate-500 block font-sans mb-0.5 italic">
                                Updated Value:
                              </span>
                              <span className="text-[11px] italic">Removed</span>
                            </div>
                          ) : (
                            <div className="p-2.5 bg-emerald-50/70 border border-emerald-200 rounded text-emerald-900 font-mono overflow-x-auto max-h-40">
                              <span className="text-[10px] uppercase font-bold text-emerald-700 block font-sans mb-0.5">
                                Updated Value:
                              </span>
                              <pre className="whitespace-pre-wrap break-all text-[11px]">
                                {formatValue(d.new_value)}
                              </pre>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : selectedVersion.parent_version_id ? (
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-slate-500 text-xs">
                  No structural rule differences detected against parent version.
                </div>
              ) : null}

              {/* Unified Policy Governance Card: Routing Flow + Operating Parameters */}
              <div className="border border-slate-200 rounded-xl overflow-hidden divide-y divide-slate-200">
                {/* Policy Routing Threshold Flow */}
                <div className="p-4 bg-slate-50/50">
                  <h4 className="font-semibold text-slate-800 text-xs mb-3 flex items-center space-x-1.5">
                    <ShieldCheck className="w-4 h-4 text-sky-600" />
                    <span>Decision Engine Threshold Architecture</span>
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="p-3 bg-emerald-50/70 border border-emerald-200 rounded-lg text-emerald-900">
                      <div className="font-semibold text-xs text-emerald-800 flex items-center justify-between">
                        <span>Direct Purchase Order (PO)</span>
                        <span className="text-[10px] bg-emerald-100 px-1.5 py-0.5 rounded font-mono font-bold">Auto-PO</span>
                      </div>
                      <ul className="text-[11px] text-emerald-800 mt-2 space-y-1">
                        <li>• <strong>Contract PO:</strong> Active contract with sufficient ceiling room</li>
                        <li>• <strong>Emergency PO:</strong> Urgency tagged, up to ₹{selectedVersion.rules_definition?.parameters?.emergency_po_threshold?.toLocaleString('en-IN') ?? '5,00,000'}</li>
                        <li>• <strong>Spot PO:</strong> Value &lt; ₹{selectedVersion.rules_definition?.parameters?.rfq_threshold?.toLocaleString('en-IN') ?? '2,00,000'} with 365d active history</li>
                      </ul>
                    </div>

                    <div className="p-3 bg-amber-50/70 border border-amber-200 rounded-lg text-amber-900">
                      <div className="font-semibold text-xs text-amber-800 flex items-center justify-between">
                        <span>Sourcing Request Escalation</span>
                        <span className="text-[10px] bg-amber-100 px-1.5 py-0.5 rounded font-mono font-bold">Sourcing</span>
                      </div>
                      <ul className="text-[11px] text-amber-800 mt-2 space-y-1">
                        <li>• <strong>RFQ (3 Quotes):</strong> Value ₹2L to ₹10L or ceiling depleted</li>
                        <li>• <strong>Formal RFP (5 Quotes):</strong> Value &ge; ₹10,00,000</li>
                        <li>• <strong>Capex & New Items:</strong> Equipment sourcing & custom items</li>
                      </ul>
                    </div>
                  </div>
                </div>

                {/* Operating Rule Parameters */}
                <div className="p-4 bg-white">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-semibold text-slate-800 text-xs">Operating Rule Parameters</h4>
                    {writeAccess && (
                      <button
                        onClick={saveParams}
                        disabled={savingParams}
                        className="flex items-center space-x-1 px-2.5 py-1 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white text-[10px] font-semibold rounded transition-colors"
                      >
                        {savingParams ? (
                          <Save className="w-3 h-3 animate-spin" />
                        ) : (
                          <Save className="w-3 h-3" />
                        )}
                        <span>Save & Sync Rules</span>
                      </button>
                    )}
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                    {selectedVersion?.rules_definition?.parameters &&
                      Object.entries(selectedVersion.rules_definition.parameters).map(([k, v]) => {
                        const isComplexSpan =
                          k === 'supplier_ranking_weights' || k === 'recency_buckets';
                        const colSpan = isComplexSpan ? 3 : 1;
                        return (
                          <div
                            key={k}
                            className={`p-2.5 border border-slate-200 rounded-lg min-w-0 ${
                              colSpan === 3 ? 'md:col-span-3' : colSpan === 2 ? 'md:col-span-2' : ''
                            }`}
                          >
                            <span className="text-[10px] text-slate-400 uppercase font-sans block truncate mb-0.5" title={k}>
                              {formatParamKey(k)}
                            </span>
                            <div className="mt-0.5">
                              {isComplexSpan && typeof v === 'object' && !Array.isArray(v) ? (
                                // Nested object (e.g. supplier_ranking_weights) → pill badges
                                <div className="flex flex-wrap gap-1.5">
                                  {Object.entries(v).map(([sk, sv]) => (
                                    <span
                                      key={sk}
                                      className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs"
                                    >
                                      <span className="text-slate-500 font-sans">{formatParamKey(sk)}</span>
                                      <span className="font-mono font-bold text-slate-800">
                                        {typeof sv === 'number' ? sv.toFixed(2) : String(sv)}
                                      </span>
                                    </span>
                                  ))}
                                </div>
                              ) : Array.isArray(v) ? (
                                // Array (e.g. recency_buckets) → inline pills
                                <div className="flex flex-wrap gap-1.5">
                                  {v.map((item, i) => (
                                    <span
                                      key={i}
                                      className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs"
                                    >
                                      {typeof item === 'object' && item !== null
                                        ? Object.entries(item).map(([ik, iv]) => `${formatParamKey(ik)}=${iv}`).join(', ')
                                        : String(item)}
                                    </span>
                                  ))}
                                </div>
                              ) : writeAccess ? (
                                <input
                                  id={`param-${k}`}
                                  defaultValue={v}
                                  className="w-full font-mono font-bold text-slate-800 text-xs block bg-slate-50 border border-sky-300 rounded px-2 py-1 focus:ring-1 focus:ring-sky-500 outline-none"
                                />
                              ) : (
                                <span className="font-mono font-bold text-slate-800 text-xs block truncate">
                                  {renderParamValue(k, v)}
                                </span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                  </div>
                  {!writeAccess && (
                    <p className="text-[10px] text-slate-400 mt-2 italic">
                      Switch to <strong>Write Access</strong> to edit operational rule parameters and thresholds.
                    </p>
                  )}
                </div>
              </div>

              {/* Polished Code / Rule Preview Panel */}
              <div className="rounded-xl overflow-hidden border border-slate-700 shadow-sm">
                <div className="bg-slate-800 px-4 py-2.5 text-xs font-mono text-slate-300 border-b border-slate-700 flex justify-between items-center">
                  <span className="font-semibold">
                    {selectedVersion.version_id} Rule Logic ({selectedVersion.status}){' '}
                    <span className="text-[10px] opacity-70">Read-Only AST</span>
                  </span>
                  <span className="text-[10px] text-slate-400 bg-slate-700/60 px-2 py-0.5 rounded">JSON DSL</span>
                </div>
                <pre className="bg-slate-900 text-slate-100 p-4 text-[11px] font-mono overflow-x-auto max-h-80 leading-relaxed">
                  {JSON.stringify(selectedVersion.rules_definition, null, 2)}
                </pre>
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-12 text-center text-slate-400 text-xs">
              Select a policy version to inspect rules and approval diffs.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
