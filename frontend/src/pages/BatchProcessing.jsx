import React, { useState } from 'react';
import { Upload, FileSpreadsheet, Download, CheckCircle, AlertTriangle, Filter, Search, RefreshCw, ChevronRight } from 'lucide-react';
import { uploadBatch, getExportUrl } from '../api';

export default function BatchProcessing() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Filters
  const [decisionFilter, setDecisionFilter] = useState('ALL');
  const [routeFilter, setRouteFilter] = useState('ALL');
  const [search, setSearch] = useState('');

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const data = await uploadBatch(file);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Filter decisions
  const filteredDecisions = (result?.decisions || []).filter(d => {
    if (decisionFilter !== 'ALL' && d.decision !== decisionFilter) return false;
    if (routeFilter !== 'ALL' && d.route !== routeFilter) return false;
    if (search.trim()) {
      const s = search.toLowerCase();
      const matchPr = String(d.pr_no || '').toLowerCase().includes(s);
      const matchItem = String(d.resolved_item_code || '').toLowerCase().includes(s);
      const matchGroup = String(d.group_id || '').toLowerCase().includes(s);
      if (!matchPr && !matchItem && !matchGroup) return false;
    }
    return true;
  });

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {/* Upload Banner & Header */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-800 flex items-center space-x-2">
              <FileSpreadsheet className="w-5 h-5 text-sky-600" />
              <span>Bulk PR Batch Processing</span>
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Upload multi-line PR CSV batches to run automated anti-splitting, 3-step valuation, contract ledger checks, and Section 4 decisioning.
            </p>
          </div>

          {result && (
            <a
              href={getExportUrl(result.run_id)}
              download={`decisions_${result.run_id}.csv`}
              className="inline-flex items-center space-x-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2.5 rounded-lg shadow-sm transition-all"
            >
              <Download className="w-4 h-4" />
              <span>Download Decisions CSV (Section 4)</span>
            </a>
          )}
        </div>

        {/* Drag & Drop Upload Form */}
        <div className="mt-5 border-2 border-dashed border-slate-300 rounded-xl py-10 px-6 text-center hover:border-sky-500 transition-colors bg-slate-50/50">
          <input
            type="file"
            id="batchFile"
            accept=".csv"
            onChange={handleFileChange}
            className="hidden"
          />
          <label htmlFor="batchFile" className="cursor-pointer flex flex-col items-center">
            <div className="w-12 h-12 rounded-full bg-sky-50 text-sky-600 flex items-center justify-center mb-3">
              <Upload className="w-6 h-6" />
            </div>
            <span className="text-sm font-semibold text-slate-700">
              {file ? file.name : 'Click to select or drag and drop a PR batch CSV'}
            </span>
            <span className="text-xs text-slate-400 mt-1">
              Supports standard Corvo PR Batch schema with automated Section 4 policy routing
            </span>
          </label>

          {file && (
            <div className="mt-4 flex items-center justify-center space-x-3">
              <span className="text-xs font-mono bg-sky-100 text-sky-800 px-3 py-1 rounded-full">
                {file.name} ({(file.size / 1024).toFixed(1)} KB)
              </span>
              <button
                onClick={handleUpload}
                disabled={loading}
                className="bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white text-xs font-semibold px-5 py-2 rounded-lg shadow-sm transition-all flex items-center space-x-1.5"
              >
                {loading ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Executing Policy Engine...</span>
                  </>
                ) : (
                  <span>Process Batch</span>
                )}
              </button>
            </div>
          )}
        </div>

        {/* Static CSV Format & Routing Guide */}
        <div className="mt-6 pt-5 border-t border-slate-200 text-xs">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-4">
            <span className="font-semibold text-slate-700 text-xs">Expected CSV Columns:</span>
            <div className="flex flex-wrap gap-1.5 font-mono text-[11px]">
              {['pr_no', 'pr_line', 'created_at', 'plant', 'item_code', 'quantity', 'need_by_date', 'urgency'].map((col) => (
                <span key={col} className="bg-slate-100 text-slate-600 px-2 py-0.5 rounded border border-slate-200">
                  {col}
                </span>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
            <div className="p-3 bg-emerald-50/70 border border-emerald-200 rounded-lg text-emerald-900">
              <div className="font-semibold text-xs flex items-center space-x-1.5 text-emerald-800">
                <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
                <span>Auto-PO Path (Direct Purchase Order)</span>
              </div>
              <p className="text-[11px] text-emerald-700 mt-1 leading-relaxed">
                Applies when active contract exists with available ceiling, or emergency under ₹5L, or spot buy under ₹2L with 365-day active history.
              </p>
            </div>

            <div className="p-3 bg-amber-50/70 border border-amber-200 rounded-lg text-amber-900">
              <div className="font-semibold text-xs flex items-center space-x-1.5 text-amber-800">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                <span>Sourcing Queue (RFQ / RFP / Capex)</span>
              </div>
              <p className="text-[11px] text-amber-700 mt-1 leading-relaxed">
                Triggered when ceiling depleted, contract supplier blocked, value ₹2L–₹10L (RFQ), value &ge; ₹10L (RFP), or uncataloged/Capex items.
              </p>
            </div>
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Execution Metrics Summary Cards */}
      {result && result.stats && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
          <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
            <div className="text-xs text-slate-500 font-medium">Total Lines</div>
            <div className="text-2xl font-bold text-slate-800 mt-1">{result.stats.total_lines}</div>
            <div className="text-[11px] text-slate-400 mt-0.5">Input PR lines</div>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
            <div className="text-xs text-slate-500 font-medium">Requirements</div>
            <div className="text-2xl font-bold text-sky-600 mt-1">{result.stats.total_requirements}</div>
            <div className="text-[11px] text-slate-400 mt-0.5">Clubbed groups</div>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
            <div className="text-xs text-slate-500 font-medium">POs Generated</div>
            <div className="text-2xl font-bold text-emerald-600 mt-1">{result.stats.total_pos}</div>
            <div className="text-[11px] text-slate-400 mt-0.5">Consolidated POs</div>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
            <div className="text-xs text-slate-500 font-medium">Sourcing Requests</div>
            <div className="text-2xl font-bold text-indigo-600 mt-1">{result.stats.total_sourcing}</div>
            <div className="text-[11px] text-slate-400 mt-0.5">RFQ / RFP / Capex</div>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
            <div className="text-xs text-slate-500 font-medium">Not Processed</div>
            <div className="text-2xl font-bold text-amber-600 mt-1">{result.stats.total_not_processed}</div>
            <div className="text-[11px] text-slate-400 mt-0.5">Qty &le; 0 or Invalid Plant</div>
          </div>
        </div>
      )}

      {/* Decisions Output Table */}
      {result && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          {/* Table Header & Controls */}
          <div className="p-4 border-b border-slate-200 bg-slate-50 flex flex-col md:flex-row items-center justify-between gap-3">
            <div className="flex items-center space-x-2 text-xs">
              <Filter className="w-4 h-4 text-slate-400" />
              <span className="font-semibold text-slate-700">Filter Decisions:</span>
              <select
                value={decisionFilter}
                onChange={(e) => setDecisionFilter(e.target.value)}
                className="bg-white border border-slate-300 rounded px-2.5 py-1 text-xs text-slate-700"
              >
                <option value="ALL">All Decisions</option>
                <option value="PO">PO Only</option>
                <option value="SOURCING_REQUEST">Sourcing Requests Only</option>
                <option value="NOT_PROCESSED">Not Processed</option>
              </select>

              <select
                value={routeFilter}
                onChange={(e) => setRouteFilter(e.target.value)}
                className="bg-white border border-slate-300 rounded px-2.5 py-1 text-xs text-slate-700"
              >
                <option value="ALL">All Routes</option>
                <option value="CONTRACT_PO">CONTRACT_PO</option>
                <option value="SPOT_PO">SPOT_PO</option>
                <option value="EMERGENCY_PO">EMERGENCY_PO</option>
                <option value="RFQ">RFQ</option>
                <option value="RFP">RFP</option>
                <option value="CAPEX_SOURCING">CAPEX_SOURCING</option>
                <option value="NEW_ITEM_SOURCING">NEW_ITEM_SOURCING</option>
              </select>
            </div>

            <div className="relative w-full md:w-64">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search PR, item, or group..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-sky-500"
              />
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-100 text-slate-600 font-semibold uppercase tracking-wider border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">PR / Line</th>
                  <th className="px-4 py-3">Resolved Item</th>
                  <th className="px-4 py-3">Group ID</th>
                  <th className="px-4 py-3">PO ID</th>
                  <th className="px-4 py-3">Decision</th>
                  <th className="px-4 py-3">Route</th>
                  <th className="px-4 py-3">Supplier</th>
                  <th className="px-4 py-3 text-right">Unit Rate (₹)</th>
                  <th className="px-4 py-3 text-right">Value (₹)</th>
                  <th className="px-4 py-3">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono">
                {filteredDecisions.slice(0, 100).map((row, idx) => (
                  <tr key={idx} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-2.5 text-slate-800 font-medium">
                      {row.pr_no}/{row.pr_line}
                    </td>
                    <td className="px-4 py-2.5 text-sky-700">
                      {row.resolved_item_code}
                    </td>
                    <td className="px-4 py-2.5 text-slate-500 font-sans text-[11px]">
                      {row.group_id}
                    </td>
                    <td className="px-4 py-2.5 text-slate-700 font-bold">
                      {row.po_id || '-'}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold font-sans border ${
                          row.decision === 'PO'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : row.decision === 'SOURCING_REQUEST'
                            ? 'bg-amber-50 text-amber-700 border-amber-200'
                            : 'bg-slate-50 text-slate-600 border-slate-200'
                        }`}
                      >
                        {row.decision}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-slate-700">
                      {row.route}
                    </td>
                    <td className="px-4 py-2.5 text-slate-800 font-bold">
                      {row.supplier_id || (row.suggested_supplier_ids ? `Sug: ${row.suggested_supplier_ids}` : '-')}
                    </td>
                    <td className="px-4 py-2.5 text-right text-slate-700 tabular-nums">
                      {row.unit_price ? row.unit_price.toFixed(2) : '-'}
                    </td>
                    <td className="px-4 py-2.5 text-right font-bold text-slate-900 tabular-nums">
                      {row.group_value_inr ? row.group_value_inr.toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '0.00'}
                    </td>
                    <td className="px-4 py-2.5 text-slate-600 font-sans text-[11px] max-w-xs truncate" title={row.reason}>
                      {row.reason}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="p-3 bg-slate-50 border-t border-slate-200 text-xs text-slate-500 flex justify-between">
            <span>Showing {Math.min(filteredDecisions.length, 100)} of {filteredDecisions.length} decision rows</span>
            <span>Policy Version: <strong className="font-mono">{result.policy_version}</strong></span>
          </div>
        </div>
      )}
    </div>
  );
}
