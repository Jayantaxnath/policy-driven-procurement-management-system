import React, { useState } from 'react';
import { Award, Download, Calendar, Search, Star, Clock, CheckCircle } from 'lucide-react';
import { getPreferredSuppliersExportUrl } from '../api';

export default function SupplierExplorer() {
  const [asOfDate, setAsOfDate] = useState('2026-11-01');
  const [search, setSearch] = useState('');

  // Sample catalog highlights
  const catalogSamples = [
    {
      itemCode: 'ITM-1048',
      desc: 'Precision Linear Guide Way (20mm)',
      category: 'Pneumatics & Hydraulics',
      standardPrice: 12500,
      suppliers: [
        { rank: 1, id: 'S025', name: 'Apex Automation', price: 11450.00, onTime: 96, quality: 4.8 },
        { rank: 2, id: 'S027', name: 'Motion Tech Components', price: 11800.00, onTime: 92, quality: 4.6 },
        { rank: 3, id: 'S029', name: 'Linear Systems India', price: 12100.00, onTime: 94, quality: 4.4 },
      ]
    },
    {
      itemCode: 'ITM-1036',
      desc: 'High Pressure Hydraulic Hose Assembly',
      category: 'Fluid Handling',
      standardPrice: 3400,
      suppliers: [
        { rank: 1, id: 'S023', name: 'Hydrax Hydraulics', price: 3150.00, onTime: 98, quality: 4.9 },
        { rank: 2, id: 'S022', name: 'Fluidline Systems', price: 3200.00, onTime: 94, quality: 4.7 },
        { rank: 3, id: 'S024', name: 'Janatics Dealer Chakan', price: 3350.00, onTime: 91, quality: 4.5 },
      ]
    },
    {
      itemCode: 'ITM-1016',
      desc: 'Polyurethane Timing Belt T10-1500',
      category: 'Power Transmission',
      standardPrice: 1850,
      suppliers: [
        { rank: 1, id: 'S014', name: 'Mahalaxmi Industrial', price: 1720.00, onTime: 95, quality: 4.7 },
        { rank: 2, id: 'S013', name: 'Western Belting Corp', price: 1750.00, onTime: 93, quality: 4.6 },
        { rank: 3, id: 'S016', name: 'Standard Drives', price: 1800.00, onTime: 90, quality: 4.3 },
      ]
    },
    {
      itemCode: 'ITM-1001',
      desc: 'Deep Groove Ball Bearing 6205-2RS',
      category: 'Mechanical',
      standardPrice: 6500,
      suppliers: [
        { rank: 1, id: 'S001', name: 'Bhosari Steel Traders', price: 6340.39, onTime: 97, quality: 4.9 },
        { rank: 2, id: 'S002', name: 'Precision Bearings Pune', price: 6420.00, onTime: 95, quality: 4.7 },
        { rank: 3, id: 'S003', name: 'Industrial Spares Corp', price: 6500.00, onTime: 91, quality: 4.4 },
      ]
    }
  ];

  const filtered = catalogSamples.filter(i => {
    if (!search.trim()) return true;
    const s = search.toLowerCase();
    return i.itemCode.toLowerCase().includes(s) || i.desc.toLowerCase().includes(s) || i.category.toLowerCase().includes(s);
  });

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-800 flex items-center space-x-2">
            <Award className="w-5 h-5 text-amber-500" />
            <span>Preferred Supplier Ranking Explorer</span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Corvo Clause 6.4 multi-factor supplier ranking evaluated as of target date. Ranks suppliers by price reference, on-time delivery %, and quality score.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-1.5 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-lg text-xs">
            <Calendar className="w-4 h-4 text-slate-400" />
            <span className="text-slate-500 font-medium">As of Date:</span>
            <input
              type="date"
              value={asOfDate}
              onChange={(e) => setAsOfDate(e.target.value)}
              className="bg-transparent font-mono text-slate-800 font-semibold focus:outline-none"
            />
          </div>

          <a
            href={getPreferredSuppliersExportUrl(asOfDate)}
            download={`preferred_suppliers_${asOfDate}.csv`}
            className="inline-flex items-center space-x-1.5 bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-sm transition-all"
          >
            <Download className="w-4 h-4" />
            <span>Export All (CSV)</span>
          </a>
        </div>
      </div>

      {/* Search Bar */}
      <div className="relative max-w-md">
        <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
        <input
          type="text"
          placeholder="Search catalog item code or description..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-9 pr-4 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-sky-500 bg-white shadow-sm"
        />
      </div>

      {/* Grid of Items */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {filtered.map((item) => {
          const isAutoPo = item.itemCode === 'ITM-1001' || item.itemCode === 'ITM-1048';
          return (
            <div key={item.itemCode} className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-4">
              <div className="flex items-start justify-between pb-3 border-b border-slate-100">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-mono font-bold bg-sky-50 text-sky-700 px-2 py-0.5 rounded">
                      {item.itemCode}
                    </span>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                        isAutoPo
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : 'bg-amber-50 text-amber-700 border-amber-200'
                      }`}
                    >
                      {isAutoPo ? 'Auto-PO Ready' : 'Sourcing Required'}
                    </span>
                  </div>
                  <h3 className="text-sm font-bold text-slate-800 mt-1.5">{item.desc}</h3>
                  <span className="text-[11px] text-slate-400">{item.category}</span>
                </div>
                <div className="text-right">
                  <span className="text-[10px] text-slate-400 block">STANDARD PRICE</span>
                  <span className="font-semibold text-slate-700 text-xs tabular-nums">
                    ₹{item.standardPrice.toLocaleString('en-IN')}
                  </span>
                </div>
              </div>

              {/* Top 3 Suppliers */}
              <div className="space-y-2">
                {item.suppliers.map((sup) => {
                  const isTop = sup.rank === 1;
                  return (
                    <div
                      key={sup.rank}
                      className={`p-3 rounded-lg border flex items-center justify-between text-xs transition-colors ${
                        isTop
                          ? 'border-emerald-200 bg-emerald-50/60 shadow-xs'
                          : 'border-slate-200 bg-slate-50/60'
                      }`}
                    >
                      <div className="flex items-center space-x-3">
                        <div
                          className={`w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs ${
                            isTop
                              ? 'bg-emerald-600 text-white'
                              : 'bg-slate-200 text-slate-700'
                          }`}
                        >
                          {sup.rank}
                        </div>
                        <div>
                          <div className="font-semibold text-slate-800">
                            {sup.name} <span className="font-mono text-slate-400">({sup.id})</span>
                            {isTop && (
                              <span className="ml-1.5 text-[10px] font-semibold text-emerald-700 bg-emerald-100/60 px-1.5 py-0.2 rounded">
                                Preferred
                              </span>
                            )}
                          </div>
                          <div className="flex items-center space-x-3 text-[10px] text-slate-500 mt-0.5">
                            <span className="flex items-center space-x-1">
                              <Clock className="w-3 h-3 text-slate-400" />
                              <span>{sup.onTime}% on-time</span>
                            </span>
                            <span className="flex items-center space-x-1">
                              <Star className="w-3 h-3 text-amber-500 fill-amber-500" />
                              <span>{sup.quality} rating</span>
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="text-right">
                        <span className="font-bold text-slate-900 font-mono tabular-nums">
                          ₹{sup.price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </span>
                        <span className="text-[10px] text-slate-400 block">Ref Rate</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
