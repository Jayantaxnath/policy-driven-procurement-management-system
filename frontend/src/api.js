/**
 * Corvo Procurement API Client
 */
const BASE_URL = import.meta.env.VITE_API_URL || '/api';

export async function fetchHealth() {
  const res = await fetch('/health');
  return res.json();
}

// Batch
export async function uploadBatch(file, policyVersion = null) {
  const formData = new FormData();
  formData.append('file', file);
  if (policyVersion) {
    formData.append('policy_version', policyVersion);
  }
  const res = await fetch(`${BASE_URL}/process-batch`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to process batch CSV');
  }
  return res.json();
}

export function getExportUrl(runId) {
  return `${BASE_URL}/runs/${runId}/export`;
}

export function getPreferredSuppliersExportUrl(asOfDate = '2026-11-01') {
  return `${BASE_URL}/preferred-suppliers?as_of_date=${asOfDate}`;
}

// Requirements & Buyers
export async function fetchRequirements({ runId, plant, route, decision, search, sortBy = 'date', sortOrder = 'desc', limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (runId) params.append('run_id', runId);
  if (plant) params.append('plant', plant);
  if (route) params.append('route', route);
  if (decision) params.append('decision', decision);
  if (search) params.append('search', search);
  params.append('sort_by', sortBy);
  params.append('sort_order', sortOrder);
  params.append('limit', limit);
  params.append('offset', offset);

  const res = await fetch(`${BASE_URL}/requirements?${params.toString()}`);
  return res.json();
}

export async function fetchRequirementDetail(id) {
  const res = await fetch(`${BASE_URL}/requirements/${id}`);
  if (!res.ok) throw new Error('Requirement not found');
  return res.json();
}

export async function approveRequirement(id, buyerId, notes = '') {
  const res = await fetch(`${BASE_URL}/requirements/${id}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ buyer_id: buyerId, notes }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Approval failed');
  }
  return res.json();
}

export async function overrideRequirement(id, { buyerId, overrideReason, newRoute, newSupplierId, newDecision }) {
  const res = await fetch(`${BASE_URL}/requirements/${id}/override`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      buyer_id: buyerId,
      override_reason: overrideReason,
      new_route: newRoute,
      new_supplier_id: newSupplierId,
      new_decision: newDecision,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Override failed');
  }
  return res.json();
}

export async function fetchBuyerActions() {
  const res = await fetch(`${BASE_URL}/buyers/actions`);
  return res.json();
}

// Policy
export async function fetchActivePolicy() {
  const res = await fetch(`${BASE_URL}/policy/active`);
  return res.json();
}

export async function fetchPolicyVersions() {
  const res = await fetch(`${BASE_URL}/policy/versions`);
  return res.json();
}

export async function fetchPolicyVersionDetail(versionId) {
  const res = await fetch(`${BASE_URL}/policy/${versionId}`);
  return res.json();
}

export async function uploadPolicyAmendment(payload) {
  const res = await fetch(`${BASE_URL}/policy/upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to upload amendment');
  }
  return res.json();
}

export async function activatePolicyVersion(versionId, actor, notes = '') {
  const res = await fetch(`${BASE_URL}/policy/${versionId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ actor, notes }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Activation failed');
  }
  return res.json();
}

export async function updatePolicyParameters(versionId, params, actor) {
  const res = await fetch(`${BASE_URL}/policy/${versionId}/parameters`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ actor, parameters: params }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to update parameters');
  }
  return res.json();
}

// Chat
export async function chatIntake(message, currentSlots = {}) {
  const res = await fetch(`${BASE_URL}/chat/pr-intake`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, current_slots: currentSlots }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Chat intake failed');
  }
  return res.json();
}

export async function submitChatPR(payload) {
  const res = await fetch(`${BASE_URL}/chat/submit-pr`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to submit PR');
  }
  return res.json();
}
