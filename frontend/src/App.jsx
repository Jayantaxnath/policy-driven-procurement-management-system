import React, { useState, Component, useEffect } from 'react';
import Navbar from './components/Navbar';
import ChatIntake from './pages/ChatIntake';
import BatchProcessing from './pages/BatchProcessing';
import BuyerWorkspace from './pages/BuyerWorkspace';
import PolicyAdmin from './pages/PolicyAdmin';
import SupplierExplorer from './pages/SupplierExplorer';
import { fetchActivePolicy } from './api';

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="max-w-xl mx-auto my-12 p-6 bg-white border border-red-200 rounded-xl shadow-sm text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-red-100 text-red-600 mx-auto flex items-center justify-center font-bold text-xl">
            !
          </div>
          <h2 className="text-base font-bold text-slate-800">Something went wrong rendering this view</h2>
          <p className="text-xs text-red-600 bg-red-50 p-3 rounded font-mono break-all">
            {this.state.error?.toString()}
          </p>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.reload();
            }}
            className="px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white rounded-lg text-xs font-semibold"
          >
            Reload Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}


export default function App() {
  const [activeTab, setActiveTab] = useState('chat');
  const [activePolicyVersion, setActivePolicyVersion] = useState('v5.0');

  useEffect(() => {
    fetchActivePolicy().then((p) => setActivePolicyVersion(p?.version_id || 'v5.0')).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <div className="sticky top-0 z-50 shrink-0">
        <Navbar
          activeTab={activeTab}
          setActiveTab={setActiveTab}
        />
      </div>

      <main className="flex-1 pb-12">
        <ErrorBoundary>
          {/* Pages stay mounted (hidden when inactive) so tab switches preserve
               form/chat/workspace state. A full page refresh remounts everything fresh. */}
          <div className={activeTab === 'chat' ? '' : 'hidden'}>
            <ChatIntake />
          </div>
          <div className={activeTab === 'batch' ? '' : 'hidden'}>
            <BatchProcessing />
          </div>
          <div className={activeTab === 'buyers' ? '' : 'hidden'}>
            <BuyerWorkspace />
          </div>
          <div className={activeTab === 'policy' ? '' : 'hidden'}>
            <PolicyAdmin />
          </div>
          <div className={activeTab === 'suppliers' ? '' : 'hidden'}>
            <SupplierExplorer />
          </div>
        </ErrorBoundary>
      </main>

      <footer className="bg-white border-t border-slate-200 py-4 text-center text-xs text-slate-400">
        Corvo Engineering Autonomous Procurement System &bull;
        Policy {activePolicyVersion} Deterministic Engine &bull;
        Built for Cantill.ai
      </footer>
    </div>
  );
}


// export default function App() {
//   const [activeTab, setActiveTab] = useState('chat');

//   return (
//     <div className="min-h-screen bg-slate-50 flex flex-col">
//       <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />
      
//       <main className="flex-1 pb-12">
//         <ErrorBoundary>
//           {activeTab === 'chat' && <ChatIntake />}
//           {activeTab === 'batch' && <BatchProcessing />}
//           {activeTab === 'buyers' && <BuyerWorkspace />}
//           {activeTab === 'policy' && <PolicyAdmin />}
//           {activeTab === 'suppliers' && <SupplierExplorer />}
//         </ErrorBoundary>
//       </main>

//       <footer className="bg-white border-t border-slate-200 py-4 text-center text-xs text-slate-400">
//         Corvo Engineering Autonomous Procurement System &bull; Policy v5.0 Deterministic Engine &bull; Built for Cantill.ai
//       </footer>
//     </div>
//   );
// }
