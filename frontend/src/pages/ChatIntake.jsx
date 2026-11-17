import React, { useState } from 'react';

const stripMarkdown = (text) => {
  if (!text) return text;
  return String(text)
    .replace(/\*\*(.*?)\*\*/g, '$1')   // **bold** -> bold
    .replace(/\*(.*?)\*/g, '$1')        // *italic* -> italic
    .replace(/`(.*?)`/g, '$1');         // `code` -> code
};
import { Send, Bot, User, CheckCircle2, AlertCircle, Sparkles, Building, Calendar, Layers, Clock, ArrowRight, ShieldCheck, ArrowRightCircle } from 'lucide-react';
import { chatIntake, submitChatPR } from '../api';

export default function ChatIntake() {
  const [messages, setMessages] = useState([
    {
      sender: 'bot',
      text: "Hi! I'm your Corvo Procurement Assistant. You can tell me what you need in natural language (e.g., I need 20 units of ball bearings for Pune plant by next Friday), and I will evaluate it directly against Corvo Procurement Policy.",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentSlots, setCurrentSlots] = useState({});
  const [lastEvaluation, setLastEvaluation] = useState(null);
  const [submissionSuccess, setSubmissionSuccess] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSend = async (e) => {
    e?.preventDefault();
    if (!input.trim() || loading) return;

    const userText = input.trim();
    setInput('');
    setSubmissionSuccess(null);

    // Start fresh slots for a new topic once a previous evaluation is done,
    // so old item/plant/qty don't carry over into an unrelated request.
    if (lastEvaluation) {
      setCurrentSlots({});
    }

    // Add user message
    setMessages(prev => [
      ...prev,
      {
        sender: 'user',
        text: userText,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
    ]);

    setLoading(true);
    try {
      const res = await chatIntake(userText, currentSlots);
      setCurrentSlots(res.slots || {});

      // Add assistant response
      setMessages(prev => [
        ...prev,
        {
          sender: 'bot',
          text: res.message,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);

      if (res.status === 'EVALUATED' && res.evaluation) {
        setLastEvaluation(res.evaluation);
      }
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          sender: 'bot',
          text: `⚠️ Sorry, an error occurred while processing: ${err.message}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitPR = async () => {
    if (!lastEvaluation || !currentSlots.plant) return;
    setIsSubmitting(true);
    try {
      const payload = {
        item_code: lastEvaluation.resolved_item_code !== 'NEW' ? lastEvaluation.resolved_item_code : null,
        description: currentSlots.item_description || lastEvaluation.resolved_item_code || 'Procured Item',
        quantity: parseFloat(currentSlots.quantity) || 1,
        uom: currentSlots.uom || 'NOS',
        plant: currentSlots.plant,
        need_by_date: currentSlots.need_by_date || new Date().toISOString().split('T')[0],
        urgency: currentSlots.urgency || 'Normal',
        requester: 'Engineer (Chat Intake)',
        department: 'Operations',
        estimated_unit_price: currentSlots.estimated_unit_price || null
      };

      const res = await submitChatPR(payload);
      setSubmissionSuccess(res);
      setLastEvaluation(null);
      setCurrentSlots({});

      setMessages(prev => [
        ...prev,
        {
          sender: 'bot',
          text: stripMarkdown(`🎉 **Success!** Purchase Request **${res.pr_no}** has been registered in the system (Requirement ID: \`${res.requirement_id}\`). It is now accessible in the **Buyer Workspace**.`),
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } catch (err) {
      alert(`Submission failed: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const samplePrompts = [
    "20 ball bearings for Pune plant by Friday",
    "50 Pneumatic Cylinders for Chakan next week",
    "Emergency breakdown replacement ball bearings for Pune plant today",
    "Request custom CNC tooling quote"
  ];

  const hasItem = Boolean(currentSlots.item_code || currentSlots.item_description);
  const hasQty = Boolean(currentSlots.quantity && Number(currentSlots.quantity) > 0);
  const hasPlant = Boolean(currentSlots.plant);
  const isParamsComplete = hasItem && hasQty && hasPlant;

  return (
    <div className="max-w-7xl mx-auto px-4 py-4 grid grid-cols-1 lg:grid-cols-3 gap-6 overflow-hidden">
      {/* Left 2 Cols: Chat Thread Anchored to Viewport */}
      <div className="lg:col-span-2 flex flex-col h-[calc(100vh-100px)] min-h-[600px] bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden min-w-0">
        {/* Header */}
        <div className="bg-slate-50 border-b border-slate-200 px-5 py-3.5 flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-full bg-sky-100 flex items-center justify-center text-sky-600">
              <Bot className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-800">PR Intake Chat Agent</h2>
              <p className="text-[11px] text-slate-500">Natural language purchase requests with real-time policy evaluation</p>
            </div>
          </div>
          <button
            onClick={() => {
              setCurrentSlots({});
              setLastEvaluation(null);
              setSubmissionSuccess(null);
              setMessages([
                {
                  sender: 'bot',
                  text: "Hi! I'm your Corvo Procurement Assistant. You can tell me what you need in natural language (e.g., I need 20 units of ball bearings for Pune plant by next Friday), and I will evaluate it directly against Corvo Procurement Policy.",
                  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                }
              ]);
            }}
            className="text-xs text-slate-500 hover:text-slate-800 px-2.5 py-1 rounded border border-slate-200 hover:bg-slate-100 transition-colors"
          >
            New Chat
          </button>
        </div>

        {/* Message Thread */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`flex items-start space-x-3 ${m.sender === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}
            >
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-semibold ${m.sender === 'user'
                  ? 'bg-sky-600 text-white'
                  : 'bg-slate-100 text-slate-700 border border-slate-200'
                  }`}
              >
                {m.sender === 'user' ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5 text-sky-600" />}
              </div>
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-xs sm:text-sm leading-relaxed ${m.sender === 'user'
                  ? 'bg-sky-600 text-white shadow-sm'
                  : 'bg-slate-100 text-slate-800 border border-slate-200'
                  }`}
              >
                <div className="whitespace-pre-line">{m.text}</div>
                <div
                  className={`text-[10px] mt-1 text-right ${m.sender === 'user' ? 'text-sky-200' : 'text-slate-400'
                    }`}
                >
                  {m.timestamp}
                </div>
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex items-center space-x-2 text-slate-400 text-xs py-2">
              <Bot className="w-4 h-4 text-sky-500 animate-spin" />
              <span>Analyzing policy rules & checking supplier catalogs...</span>
            </div>
          )}
        </div>

        {/* Starter Prompt Chips — shown only before the first user message */}
        {!messages.some((m) => m.sender === 'user') && (
          <div className="px-4 py-2 bg-slate-50/80 border-t border-slate-100 flex items-center space-x-2 overflow-x-auto text-xs shrink-0">
            <span className="text-slate-400 font-medium flex items-center space-x-1 flex-shrink-0 text-[11px]">
              <Sparkles className="w-3.5 h-3.5 text-sky-500" />
              <span>Try:</span>
            </span>
            {samplePrompts.map((p, i) => (
              <button
                key={i}
                onClick={() => {
                  setInput(p);
                }}
                className="bg-white border border-slate-200 hover:border-sky-300 hover:bg-sky-50 text-slate-600 px-2.5 py-1 rounded-full whitespace-nowrap transition-colors text-[11px]"
              >
                {p}
              </button>
            ))}
          </div>
        )}

        {/* Sticky Chat Input Bar */}
        <form onSubmit={handleSend} className="p-3 bg-white border-t border-slate-200 flex items-center space-x-2 shrink-0">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your purchase request (e.g., 20 ball bearings for Pune plant by Friday)..."
            className="flex-1 border border-slate-300 rounded-lg px-3.5 py-2 text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white px-4 py-2 rounded-lg flex items-center space-x-1.5 font-medium text-xs sm:text-sm transition-colors shadow-sm shrink-0"
          >
            <span>Send</span>
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>
      </div>

      {/* Right Col: Slot Extraction Card & Live Policy Routing Verdict */}
      <div className="space-y-4 min-w-0">
        {/* Extracted Slots Card */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
          <div className="flex items-center justify-between pb-2.5 border-b border-slate-100">
            <h3 className="text-xs font-semibold text-slate-800 flex items-center space-x-2">
              <Layers className="w-4 h-4 text-sky-600" />
              <span>Extracted PR Parameters</span>
            </h3>
            <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-mono">
              Slots
            </span>
          </div>

          <div className="mt-3 space-y-2.5 text-xs">
            {/* Item */}
            <div className="flex items-start justify-between">
              <span className="text-slate-500 flex items-center space-x-1.5">
                <span className={`w-2 h-2 rounded-full border ${hasItem ? 'bg-sky-500 border-sky-500' : 'border-slate-300'}`}></span>
                <span>Item</span>
              </span>
              <span className="text-right">
                {currentSlots.item_code ? (
                  <span className="bg-sky-50 text-sky-700 px-2 py-0.5 rounded font-mono font-semibold">
                    {currentSlots.item_code}
                  </span>
                ) : currentSlots.item_description ? (
                  <span className="font-medium text-slate-800">{currentSlots.item_description}</span>
                ) : (
                  <span className="text-slate-400 italic">Not specified</span>
                )}
              </span>
            </div>

            {/* Quantity */}
            <div className="flex items-center justify-between">
              <span className="text-slate-500 flex items-center space-x-1.5">
                <span className={`w-2 h-2 rounded-full border ${hasQty ? 'bg-sky-500 border-sky-500' : 'border-slate-300'}`}></span>
                <span>Quantity</span>
              </span>
              <span>
                {currentSlots.quantity ? (
                  <span className="font-semibold text-slate-800">{currentSlots.quantity} {currentSlots.uom || 'NOS'}</span>
                ) : (
                  <span className="text-slate-400 italic">Not specified</span>
                )}
              </span>
            </div>

            {/* Plant */}
            <div className="flex items-center justify-between">
              <span className="text-slate-500 flex items-center space-x-1.5">
                <span className={`w-2 h-2 rounded-full border ${hasPlant ? 'bg-sky-500 border-sky-500' : 'border-slate-300'}`}></span>
                <span>Target Plant</span>
              </span>
              <span>
                {currentSlots.plant ? (
                  <span className="bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded font-mono font-semibold">
                    {currentSlots.plant === 'PUN1' ? 'Pune (PUN1)' : 'Chakan (CHK1)'}
                  </span>
                ) : (
                  <span className="text-slate-400 italic">Pending (PUN1 / CHK1)</span>
                )}
              </span>
            </div>

            {/* Need-by Date */}
            <div className="flex items-center justify-between">
              <span className="text-slate-500 flex items-center space-x-1.5">
                <span className={`w-2 h-2 rounded-full border ${currentSlots.need_by_date ? 'bg-sky-500 border-sky-500' : 'border-slate-300'}`}></span>
                <span>Need-By Date</span>
              </span>
              <span className="font-mono text-slate-800">
                {currentSlots.need_by_date || <span className="text-slate-400 italic font-sans">Default (+7 days)</span>}
              </span>
            </div>

            {/* Urgency */}
            <div className="flex items-center justify-between">
              <span className="text-slate-500 flex items-center space-x-1.5">
                <span className={`w-2 h-2 rounded-full border ${currentSlots.urgency ? 'bg-sky-500 border-sky-500' : 'border-slate-300'}`}></span>
                <span>Urgency</span>
              </span>
              <span>
                {currentSlots.urgency === 'Emergency' ? (
                  <span className="bg-red-50 text-red-700 px-2 py-0.5 rounded font-semibold text-[11px]">🚨 Emergency</span>
                ) : currentSlots.urgency === 'Urgent' ? (
                  <span className="bg-amber-50 text-amber-700 px-2 py-0.5 rounded font-semibold text-[11px]">⚡ Urgent</span>
                ) : (
                  <span className="text-slate-600">Normal</span>
                )}
              </span>
            </div>

            {/* Estimated Unit Price */}
            <div className="flex items-center justify-between">
              <span className="text-slate-500 flex items-center space-x-1.5">
                <span className={`w-2 h-2 rounded-full border ${currentSlots.estimated_unit_price ? 'bg-sky-500 border-sky-500' : 'border-slate-300'}`}></span>
                <span>Est. Unit Price</span>
              </span>
              <span className="font-mono text-slate-800">
                {currentSlots.estimated_unit_price ? (
                  <span>₹{Number(currentSlots.estimated_unit_price).toLocaleString('en-IN')}</span>
                ) : (
                  <span className="text-slate-400 italic font-sans">Not specified</span>
                )}
              </span>
            </div>
          </div>
        </div>

        {/* Live Policy Routing Verdict Card (Always visible to fill dead space) */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-slate-100">
            <h3 className="text-xs font-semibold text-slate-800 flex items-center space-x-1.5">
              <ShieldCheck className="w-4 h-4 text-sky-600" />
              <span>Policy Routing Verdict</span>
            </h3>
            <span className="text-[10px] font-mono text-slate-400">Policy v5.0</span>
          </div>

          {/* 3-Step Visual Routing Tracker */}
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">1. Parameters Extraction</span>
              <span className={`text-[11px] font-semibold ${isParamsComplete ? 'text-emerald-600' : 'text-slate-400'}`}>
                {isParamsComplete ? '✓ Complete' : 'In Progress'}
              </span>
            </div>

            <div className="flex items-center justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">2. Corvo Policy Engine</span>
              <span className={`text-[11px] font-semibold ${lastEvaluation ? 'text-emerald-600' : 'text-slate-400'}`}>
                {lastEvaluation ? '✓ Evaluated' : 'Waiting on parameters'}
              </span>
            </div>

            <div className="flex items-center justify-between py-1">
              <span className="text-slate-500">3. Decision Outcome</span>
              {lastEvaluation ? (
                <span
                  className={`text-[11px] px-2 py-0.5 rounded font-bold ${lastEvaluation.decision === 'PO'
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : 'bg-amber-50 text-amber-700 border border-amber-200'
                    }`}
                >
                  {lastEvaluation.decision === 'PO' ? 'Direct PO' : 'Sourcing Request'}
                </span>
              ) : (
                <span className="text-[11px] text-slate-400 italic">Pending</span>
              )}
            </div>
          </div>

          {/* Evaluation Details If Available */}
          {lastEvaluation ? (
            <div className="pt-2 border-t border-slate-100 space-y-2 text-xs">
              <div className="bg-slate-50 p-2 rounded text-[11px] text-slate-700 leading-relaxed">
                <span className="font-semibold block mb-0.5">Route: {lastEvaluation.route}</span>
                {lastEvaluation.reason}
              </div>

              {lastEvaluation.group_value_inr ? (
                <div className="flex justify-between text-xs py-1">
                  <span className="text-slate-500">Total Group Value:</span>
                  <span className="font-bold text-slate-900 font-mono">₹{lastEvaluation.group_value_inr.toLocaleString('en-IN')}</span>
                </div>
              ) : null}

              <button
                onClick={handleSubmitPR}
                disabled={isSubmitting}
                className="w-full mt-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-medium py-2 px-3 rounded-lg flex items-center justify-center space-x-1.5 text-xs shadow-sm transition-all"
              >
                <span>{isSubmitting ? 'Submitting PR...' : 'Submit to Buyer Workspace'}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <div className="pt-1 text-[11px] text-slate-400 text-center py-2 bg-slate-50/60 rounded">
              State your requirement to see live deterministic routing and policy justifications.
            </div>
          )}
        </div>

        {/* Submission Confirmation Card */}
        {submissionSuccess && (
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3.5 text-xs text-emerald-800 space-y-1">
            <div className="font-bold flex items-center space-x-1.5 text-xs text-emerald-900">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>PR Submitted Successfully</span>
            </div>
            <div>PR Number: <span className="font-mono font-semibold">{submissionSuccess.pr_no}</span></div>
            <div>Requirement ID: <span className="font-mono font-semibold">{submissionSuccess.requirement_id}</span></div>
            <div className="text-slate-600 text-[11px] pt-1">
              Available immediately in the <strong>Buyer Workspace</strong> for review.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
