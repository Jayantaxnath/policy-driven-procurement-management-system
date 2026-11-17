import React, { useEffect, useState } from 'react';
import { Bot, FileSpreadsheet, Briefcase, ShieldAlert, Award } from 'lucide-react';
import { fetchActivePolicy } from '../api';

export default function Navbar({ activeTab, setActiveTab }) {
  const [activePolicy, setActivePolicy] = useState(null);

  const loadPolicy = () => {
    fetchActivePolicy()
      .then(data => setActivePolicy(data))
      .catch(() => {});
  };

  useEffect(() => {
    loadPolicy();
    const interval = setInterval(loadPolicy, 10000);
    return () => clearInterval(interval);
  }, []);

  const navItems = [
    { id: 'chat', label: 'Chat Intake', icon: Bot },
    { id: 'batch', label: 'Batch Upload', icon: FileSpreadsheet },
    { id: 'buyers', label: 'Workspace', icon: Briefcase },
    { id: 'policy', label: 'Policy Admin', icon: ShieldAlert },
    { id: 'suppliers', label: 'Suppliers', icon: Award },
  ];

  return (
    <header className="bg-slate-900 text-white shadow-sm border-b border-slate-800 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <div className="flex items-center space-x-3">
            <div className="h-9 w-9 bg-gradient-to-tr from-sky-500 to-indigo-600 rounded-lg flex items-center justify-center font-bold text-white shadow-sm">
              C
            </div>
            <div>
              <div className="font-semibold text-sm sm:text-base tracking-wide flex items-center space-x-2">
                <span>CORVO ENGINEERING</span>
              </div>
              <div className="text-[11px] text-slate-400">
                Deterministic Policy-as-Data Engine
              </div>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="flex items-center space-x-1 overflow-x-auto py-1">
            {navItems.map(item => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-all whitespace-nowrap ${
                    isActive
                      ? 'bg-sky-600 text-white shadow-sm'
                      : 'text-slate-300 hover:text-white hover:bg-slate-800'
                  }`}
                >
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Active Policy Status Pill */}
          <div className="hidden lg:flex items-center space-x-2 bg-slate-800 text-slate-300 border border-slate-700 px-3 py-1 rounded-full text-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span className="text-slate-400">Active Policy:</span>
            <span className="font-mono text-emerald-300 font-semibold">
              {activePolicy ? activePolicy.version_id : 'v5.0'}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}
