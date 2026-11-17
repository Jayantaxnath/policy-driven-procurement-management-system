import React, { useState, useEffect } from 'react';
import { Briefcase, CheckCircle, AlertOctagon, Search, Filter, History, Eye, Check, X, Building, ArrowUpRight } from 'lucide-react';
import { fetchRequirements, fetchRequirementDetail, approveRequirement, overrideRequirement, fetchBuyerActions } from '../api';

export default function BuyerWorkspace() {
  const [requirements, setRequirements] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [selectedReq, setSelectedReq] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Filters
  const [plant, setPlant] = useState('');
  const [route, setRoute] = useState('');
  const [decision, setDecision] = useState('');
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('date');
  const [sortOrder, setSortOrder] = useState('desc');

  // Modals & Action State
  const [showOverrideModal, setShowOverrideModal] = useState(false);
  const [overrideForm, setOverrideForm] = useState({
    buyerId: 'Buyer John Doe',
    overrideReason: '',
    newRoute: 'SPOT_PO',
    newSupplierId: '',
  });
  const [actionError, setActionError] = useState(null);
  const [activeTab, setActiveTab] = useState('list'); // 'list' | 'audit'
  const [auditActions, setAuditActions] = useState([]);

  const loadRequirements = async () => {
    setLoading(true);
    try {
      const data = await fetchRequirements({
        plant: plant || undefined,
        route: route || undefined,
        decision: decision || undefined,
        search: search || undefined,
        sortBy,
        sortOrder,
        limit: 100
      });
      setRequirements(data.requirements || []);
      setTotal(data.total || 0);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadAudit = async () => {
    try {
      const data = await fetchBuyerActions();
      setAuditActions(data || []);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadRequirements();
  }, [plant, route, decision, search, sortBy, sortOrder]);

  const handleSelectRequirement = async (id) => {
    setDetailLoading(true);
    try {
      const detail = await fetchRequirementDetail(id);
      setSelectedReq(detail);
      setOverrideForm({
        buyerId: 'Buyer John Doe',
        overrideReason: '',
        newRoute: detail.route,
        newSupplierId: detail.supplier_id || '',
      });
    } catch (err) {
      alert(err.message);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleApprove = async (id) => {
    try {
      await approveRequirement(id, 'Buyer John Doe', 'Policy criteria verified and accepted');
      alert(`Requirement ${id} successfully approved!`);
      loadRequirements();
      if (selectedReq?.requirement_id === id) {
        handleSelectRequirement(id);
      }
    } catch (err) {
      alert(err.message);
    }
  };

  const handleOverrideSubmit = async (e) => {
    e.preventDefault();
    setActionError(null);
    if (!overrideForm.overrideReason || overrideForm.overrideReason.trim().length < 5) {
      setActionError('A mandatory, meaningful business reason (min 5 chars) is required to override.');
      return;
    }

    try {
      await overrideRequirement(selectedReq.requirement_id, {
        buyerId: overrideForm.buyerId,
        overrideReason: overrideForm.overrideReason,
        newRoute: overrideForm.newRoute,
        newSupplierId: overrideForm.newSupplierId || undefined,
      });
      alert(`Requirement ${selectedReq.requirement_id} successfully overridden.`);
      setShowOverrideModal(false);
      loadRequirements();
      handleSelectRequirement(selectedReq.requirement_id);
    } catch (err) {
      setActionError(err.message);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-800 flex items-center space-x-2">
            <Briefcase className="w-5 h-5 text-sky-600" />
            <span>Buyer Workspace & Approval Governance</span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Review clubbed procurement requirements, evaluate pricing waterfalls, approve decisions, or apply audited overrides.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => setActiveTab('list')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
              activeTab === 'list' ? 'bg-sky-600 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
          >
            Requirements ({total})
          </button>
          <button
            onClick={() => {
              setActiveTab('audit');
              loadAudit();
            }}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg flex items-center space-x-1.5 transition-colors ${
              activeTab === 'audit' ? 'bg-sky-600 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
          >
            <History className="w-3.5 h-3.5" />
            <span>Audit Trail</span>
          </button>
        </div>
      </div>

      {activeTab === 'list' ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left 2 Cols: Requirements Table */}
          <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden flex flex-col h-[700px] min-w-0">
            {/* Filter Bar */}
            <div className="p-3 border-b border-slate-200 bg-slate-50 flex items-center gap-1.5 flex-wrap md:flex-nowrap">
              {/* Search — far left */}
              <div className="relative shrink-0">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2 top-1.5" />
                <input
                  type="text"
                  placeholder="Search item or ID..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && loadRequirements()}
                  className="h-8 pl-7 pr-2 text-[10px] border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-sky-500 md:w-40 w-32"
                />
                {search && (
                  <button
                    onClick={() => { setSearch(''); loadRequirements(); }}
                    className="absolute right-2 top-1.5 text-slate-400 hover:text-red-500 p-1"
                  >
                    <X className="w-3 h-3" />
                  </button>
                )}
              </div>

              {/* Filters + Sort — pushed to far right */}
              <div className="flex-1 md:flex items-center gap-1 justify-end">
                {/* Filters */}
                <Filter className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                <select
                  value={plant}
                  onChange={(e) => setPlant(e.target.value)}
                  className="h-8 bg-white border border-slate-300 rounded px-1.5 py-0.5 text-[10px] text-slate-700 w-auto md:min-w-[60px] min-w-[48px]"
                >
                  <option value="">All Plants</option>
                  <option value="PUN1">Pune (PUN1)</option>
                  <option value="CHK1">Chakan (CHK1)</option>
                </select>
                <select
                  value={route}
                  onChange={(e) => setRoute(e.target.value)}
                  className="h-8 bg-white border border-slate-300 rounded px-1.5 py-0.5 text-[10px] text-slate-700 w-auto md:min-w-[72px] min-w-[60px]"
                >
                  <option value="">All Routes</option>
                  <option value="CONTRACT_PO">CONTRACT_PO</option>
                  <option value="SPOT_PO">SPOT_PO</option>
                  <option value="EMERGENCY_PO">EMERGENCY_PO</option>
                  <option value="RFQ">RFQ</option>
                  <option value="RFP">RFP</option>
                  <option value="CAPEX_SOURCING">CAPEX_SOURCING</option>
                  <option value="NEW_ITEM_SOURCING">NEW_ITEM_SOURCING</option>
                </select>
                <select
                  value={decision}
                  onChange={(e) => setDecision(e.target.value)}
                  className="h-8 bg-white border border-slate-300 rounded px-1.5 py-0.5 text-[10px] text-slate-700 w-auto md:min-w-[64px] min-w-[52px]"
                >
                  <option value="">All Decisions</option>
                  <option value="PO">PO Only</option>
                  <option value="SOURCING_REQUEST">Sourcing Only</option>
                </select>

                {/* Divider between filters and sort */}
                <div className="h-4 w-0.5 bg-slate-300 shrink-0 mx-1 hidden md:block" />

                {/* Sort — grouped tightly, far right */}
                <div className="flex items-center gap-0.5 shrink-0">
                  <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value)}
                    className="h-8 bg-white border border-slate-300 rounded px-1.5 py-0.5 text-[10px] text-slate-700 w-auto md:min-w-[56px] min-w-[44px]"
                  >
                    <option value="date">Date</option>
                    <option value="value">Value</option>
                  </select>
                  <span className="text-[9px] text-slate-400 hidden md:inline">/</span>
                  <select
                    value={sortOrder}
                    onChange={(e) => setSortOrder(e.target.value)}
                    className="h-8 bg-white border border-slate-300 rounded px-1.5 py-0.5 text-[10px] text-slate-700 w-auto md:min-w-[40px] min-w-[36px]"
                  >
                    <option value="desc">Desc</option>
                    <option value="asc">Asc</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Table Container */}
            <div className="flex-1 overflow-y-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-100 text-slate-600 uppercase font-semibold border-b border-slate-200 sticky top-0">
                  <tr>
                    <th className="px-4 py-3">Requirement ID</th>
                    <th className="px-4 py-3">Resolved Item</th>
                    <th className="px-4 py-3">Plant</th>
                    <th className="px-4 py-3 text-center">Submitted</th>
                    <th className="px-4 py-3">Route</th>
                    <th className="px-4 py-3 text-right">Value (₹)</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-center">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-mono">
                  {requirements.map((req) => {
                    const isSelected = selectedReq?.requirement_id === req.requirement_id;
                    return (
                      <tr
                        key={req.requirement_id}
                        onClick={() => handleSelectRequirement(req.requirement_id)}
                        className={`cursor-pointer transition-colors ${
                          isSelected ? 'border-l-4 border-l-sky-600 bg-sky-50/60 font-semibold' : 'hover:bg-slate-50 border-l-4 border-l-transparent'
                        }`}
                      >
                        <td className="px-4 py-2.5 text-slate-800">{req.requirement_id}</td>
                        <td className="px-4 py-2.5 text-sky-700">
                          {req.resolved_item_code || 'NEW'}
                        </td>
                        <td className="px-4 py-2.5 text-slate-600 font-sans text-[11px]">
                          {req.plant || '-'}
                        </td>
                        <td className="px-4 py-2.5 text-center text-slate-500 text-[10px] font-sans">
                          {req.submitted_at ? new Date(req.submitted_at).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '-'}
                        </td>
                        <td className="px-4 py-2.5 text-slate-700">{req.route}</td>
                        <td className="px-4 py-2.5 text-right font-bold text-slate-900 tabular-nums">
                          {req.group_value_inr ? `₹${req.group_value_inr.toLocaleString('en-IN')}` : '-'}
                        </td>
                        <td className="px-4 py-2.5 font-sans">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                              req.buyer_status === 'APPROVED'
                                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                : req.buyer_status === 'OVERRIDDEN'
                                ? 'bg-amber-50 text-amber-700 border-amber-200'
                                : 'bg-slate-50 text-slate-600 border-slate-200'
                            }`}
                          >
                            {req.buyer_status}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-center font-sans">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleSelectRequirement(req.requirement_id);
                            }}
                            className="text-sky-600 hover:text-sky-800 p-1"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                  {requirements.length === 0 && !loading && (
                    <tr>
                      <td colSpan={7} className="text-center py-10 text-slate-400 font-sans text-xs">
                        No requirements found. Process a batch CSV or raise a PR via Chat Intake.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Right Col: Detail Drawer */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 overflow-y-auto h-[700px] min-w-0">
            {selectedReq ? (
              <div className="space-y-5 text-xs">
                {/* Header */}
                <div className="border-b border-slate-100 pb-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] text-slate-400 font-mono">REQ ID</span>
                    <span
                      className={`px-2 py-0.5 rounded font-bold ${
                        selectedReq.decision === 'PO' ? 'bg-emerald-100 text-emerald-800' : 'bg-indigo-100 text-indigo-800'
                      }`}
                    >
                      {selectedReq.decision}
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-slate-800 font-mono mt-1">
                    {selectedReq.requirement_id}
                  </h3>
                  <p className="text-xs text-slate-500 mt-0.5 font-sans">
                    {selectedReq.resolved_item_code} - {selectedReq.item_description || 'Custom Requirement'}
                  </p>
                </div>

                {/* Key Metrics */}
                <div className="grid grid-cols-2 gap-2 bg-slate-50 p-3 rounded-lg">
                  <div>
                    <span className="text-slate-400 block text-[10px]">ROUTE</span>
                    <span className="font-bold text-slate-800 font-mono">{selectedReq.route}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px]">VALUATION</span>
                    <span className="font-bold text-emerald-600">
                      ₹{selectedReq.group_value_inr ? selectedReq.group_value_inr.toLocaleString('en-IN') : '0.00'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px]">UNIT PRICE</span>
                    <span className="font-semibold text-slate-700">
                      ₹{selectedReq.unit_price ? selectedReq.unit_price.toFixed(2) : 'TBD'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px]">PRICE SOURCE</span>
                    <span className="font-mono text-slate-700">{selectedReq.price_source || 'WATERFALL'}</span>
                  </div>
                </div>

                {/* Selected / Suggested Suppliers */}
                {selectedReq.supplier_id && (
                  <div className="border border-slate-200 rounded-lg p-3">
                    <div className="text-[11px] font-semibold text-slate-700 mb-1">Assigned Supplier:</div>
                    <div className="font-bold text-slate-800">
                      {selectedReq.supplier_name || selectedReq.supplier_id} ({selectedReq.supplier_id})
                    </div>
                  </div>
                )}

                {selectedReq.suggested_suppliers?.length > 0 && (
                  <div>
                    <div className="text-[11px] font-semibold text-slate-700 mb-2">Suggested Suppliers (Ranked):</div>
                    <div className="space-y-1.5">
                      {selectedReq.suggested_suppliers.map((s, i) => (
                        <div key={i} className="p-2 border border-slate-200 rounded bg-slate-50 flex items-center justify-between">
                          <div>
                            <span className="font-semibold text-slate-800">{s.name || s.supplier_id}</span>
                            <span className="text-slate-400 ml-1">({s.supplier_id})</span>
                            {s.city && <div className="text-[10px] text-slate-500">{s.city}</div>}
                          </div>
                          {s.on_time_pct && (
                            <div className="text-right text-[10px]">
                              <span className="text-emerald-700 font-semibold">{s.on_time_pct}% on-time</span>
                              <div className="text-slate-500">★ {s.quality_rating}</div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Policy Justification */}
                <div>
                  <div className="text-[11px] font-semibold text-slate-700 mb-1">Policy Rationale:</div>
                  <p className="bg-slate-50 p-2.5 rounded border border-slate-200 text-slate-600 text-[11px] leading-relaxed">
                    {selectedReq.reason}
                  </p>
                </div>

                {/* Clubbed PR Lines */}
                {selectedReq.clubbed_pr_lines?.length > 0 && (
                  <div>
                    <div className="text-[11px] font-semibold text-slate-700 mb-1">
                      Clubbed PR Lines ({selectedReq.clubbed_pr_lines.length}):
                    </div>
                    <div className="space-y-1.5 max-h-36 overflow-y-auto">
                      {selectedReq.clubbed_pr_lines.map((l, i) => (
                        <div key={i} className="p-2 bg-slate-50 rounded border border-slate-100 flex justify-between font-mono text-[11px]">
                          <span>{l.pr_no}/{l.pr_line}</span>
                          <span className="font-bold text-slate-700">{l.quantity} {l.uom}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Action Controls */}
                <div className="pt-3 border-t border-slate-200 flex space-x-2">
                  <button
                    onClick={() => handleApprove(selectedReq.requirement_id)}
                    className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2 rounded-lg flex items-center justify-center space-x-1.5 transition-colors shadow-sm"
                  >
                    <Check className="w-4 h-4" />
                    <span>Approve Decision</span>
                  </button>
                  <button
                    onClick={() => setShowOverrideModal(true)}
                    className="border border-slate-300 text-slate-700 hover:bg-slate-50 font-medium py-2 px-3 rounded-lg flex items-center justify-center space-x-1.5 transition-colors"
                  >
                    <AlertOctagon className="w-4 h-4 text-slate-500" />
                    <span>Override</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-slate-400 text-xs text-center p-6">
                <Briefcase className="w-8 h-8 text-slate-300 mb-2" />
                <span>Select any requirement from the list to view its valuation trace, clubbed lines, and execute buyer actions.</span>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Audit Trail Tab */
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h3 className="text-sm font-semibold text-slate-800 mb-4">Buyer Action Governance Log</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3">Requirement</th>
                  <th className="px-4 py-3">Action</th>
                  <th className="px-4 py-3">Buyer</th>
                  <th className="px-4 py-3">Route Changes</th>
                  <th className="px-4 py-3">Override Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono">
                {auditActions.map((a, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="px-4 py-2.5 text-slate-500 font-sans">{a.performed_at}</td>
                    <td className="px-4 py-2.5 text-slate-800 font-bold">{a.requirement_id}</td>
                    <td className="px-4 py-2.5 font-sans">
                      <span
                        className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                          a.action === 'APPROVED' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {a.action}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-slate-700 font-sans">{a.buyer_id}</td>
                    <td className="px-4 py-2.5 text-slate-600">
                      {a.previous_route !== a.new_route ? `${a.previous_route} → ${a.new_route}` : a.new_route}
                    </td>
                    <td className="px-4 py-2.5 text-slate-800 font-sans">{a.override_reason || '-'}</td>
                  </tr>
                ))}
                {auditActions.length === 0 && (
                  <tr>
                    <td colSpan={6} className="text-center py-6 text-slate-400 font-sans">
                      No buyer actions recorded yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Override Modal */}
      {showOverrideModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-md w-full p-6 text-xs space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="text-sm font-bold text-slate-800 flex items-center space-x-1.5">
                <AlertOctagon className="w-4 h-4 text-amber-600" />
                <span>Override Policy Decision</span>
              </h3>
              <button onClick={() => setShowOverrideModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleOverrideSubmit} className="space-y-3">
              <div>
                <label className="block text-slate-600 font-semibold mb-1">Buyer Name / ID</label>
                <input
                  type="text"
                  value={overrideForm.buyerId}
                  onChange={(e) => setOverrideForm({ ...overrideForm, buyerId: e.target.value })}
                  className="w-full border border-slate-300 rounded px-3 py-1.5 focus:ring-1 focus:ring-sky-500"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-600 font-semibold mb-1">New Route</label>
                <select
                  value={overrideForm.newRoute}
                  onChange={(e) => setOverrideForm({ ...overrideForm, newRoute: e.target.value })}
                  className="w-full border border-slate-300 rounded px-3 py-1.5 focus:ring-1 focus:ring-sky-500"
                >
                  <option value="CONTRACT_PO">CONTRACT_PO</option>
                  <option value="SPOT_PO">SPOT_PO</option>
                  <option value="EMERGENCY_PO">EMERGENCY_PO</option>
                  <option value="RFQ">RFQ</option>
                  <option value="RFP">RFP</option>
                  <option value="CAPEX_SOURCING">CAPEX_SOURCING</option>
                  <option value="NEW_ITEM_SOURCING">NEW_ITEM_SOURCING</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-600 font-semibold mb-1">New Supplier ID (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. S001"
                  value={overrideForm.newSupplierId}
                  onChange={(e) => setOverrideForm({ ...overrideForm, newSupplierId: e.target.value })}
                  className="w-full border border-slate-300 rounded px-3 py-1.5 focus:ring-1 focus:ring-sky-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-slate-600 font-semibold mb-1">
                  Mandatory Business Justification <span className="text-red-500">*</span>
                </label>
                <textarea
                  rows={3}
                  placeholder="Explain why this policy override is necessary (minimum 5 characters)..."
                  value={overrideForm.overrideReason}
                  onChange={(e) => setOverrideForm({ ...overrideForm, overrideReason: e.target.value })}
                  className="w-full border border-slate-300 rounded px-3 py-1.5 focus:ring-1 focus:ring-sky-500"
                  required
                />
              </div>

              {actionError && (
                <div className="p-2 bg-red-50 text-red-700 rounded border border-red-200 text-[11px]">
                  {actionError}
                </div>
              )}

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowOverrideModal(false)}
                  className="px-3 py-1.5 rounded border border-slate-300 text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded bg-amber-600 hover:bg-amber-700 text-white font-semibold"
                >
                  Confirm Override
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
