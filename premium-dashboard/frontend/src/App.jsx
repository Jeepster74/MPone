import React, { useState, useEffect, useRef } from 'react';

const MP_ORANGE = '#FF6600';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [selectedTrack, setSelectedTrack] = useState(null);
  const [wishlist, setWishlist] = useState([]);
  const mapContainer = useRef(null);
  const map = useRef(null);

  // 1. DATA GLOSSARY
  const GLOSSARY = {
    'disposable_income_pps': {
      label: 'Regional Wealth Index',
      desc: 'Net disposable income per inhabitant in Purchasing Power Standard (PPS). Reflects consumer spending power.',
      source: 'Eurostat 2023'
    },
    'catchment_area_size': {
      label: '30-Min Drive-Time Reach',
      desc: 'The geographical area (km²) reachable within 30 minutes by car. Larger areas indicate better road connectivity.',
      source: 'OpenRouteService API'
    },
    'building_sqm': {
      label: 'Facility Footprint',
      desc: 'The physical size of the building polygon measured in square meters. Used to verify indoor scale.',
      source: 'OpenStreetMap Polygons'
    }
  };

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col bg-mp-black text-slate-100 relative">
      {/* 1. TOP NAV */}
      <header className="h-16 px-6 flex items-center justify-between border-b border-white/10 z-50 bg-mp-black/80 backdrop-blur-lg">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 bg-mp-orange flex items-center justify-center font-bold italic text-white rounded">MP</div>
          <h1 className="text-lg font-semibold tracking-tight uppercase">Intelligence <span className="text-mp-orange">Dashboard</span></h1>
        </div>
        <div className="flex items-center space-x-6">
           <button className="text-sm font-medium hover:text-mp-orange transition-colors">WISH LIST ({wishlist.length})</button>
           <div className="w-8 h-8 rounded-full bg-slate-700 border border-white/20"></div>
        </div>
      </header>

      {/* 2. MAP (Background) */}
      <div className="flex-1 relative">
         <div ref={mapContainer} className="absolute inset-0 z-0 bg-slate-900" />
         
         {/* LEFT SIDEBAR: FILTERS */}
         <aside className="absolute top-6 left-6 w-72 z-10 space-y-4">
            <div className="bg-glass backdrop-blur-xl p-5 rounded-xl border border-white/10 shadow-2xl">
               <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">Market Filters</h3>
               <div className="space-y-4">
                  <div>
                    <label className="text-xs font-medium block mb-2">Facility Type</label>
                    <div className="flex flex-wrap gap-2 text-xs">
                       <button className="px-3 py-1.5 rounded-full bg-mp-orange text-white">Indoor</button>
                       <button className="px-3 py-1.5 rounded-full border border-white/20 hover:bg-white/5">Outdoor</button>
                       <button className="px-3 py-1.5 rounded-full border border-white/20 hover:bg-white/5">SIM Racing</button>
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-medium block mb-2">Regional Wealth (Min PPS)</label>
                    <input type="range" className="w-full h-1 bg-white/20 rounded-lg accent-mp-orange" />
                  </div>
               </div>
            </div>

            <div className="bg-glass backdrop-blur-xl p-5 rounded-xl border border-white/10 shadow-2xl">
               <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-2">Enrichment Status</h3>
               <div className="flex items-center justify-between">
                  <span className="text-xs">Catchment Reach</span>
                  <span className="text-xs text-mp-orange animate-pulse">Running... (25%)</span>
               </div>
            </div>
         </aside>

         {/* RIGHT PANE: DETAIL */}
         <div className={`absolute top-0 right-0 h-full w-96 z-20 bg-glass backdrop-blur-2xl border-l border-white/10 transform transition-transform duration-500 shadow-[-20px_0_40px_rgba(0,0,0,0.5)] ${selectedTrack ? 'translate-x-0' : 'translate-x-full'}`}>
             {selectedTrack && (
                <div className="p-8 h-full flex flex-col">
                   <button onClick={() => setSelectedTrack(null)} className="self-end text-slate-400 hover:text-white">✕</button>
                   <div className="mt-4 flex-1 overflow-y-auto space-y-6">
                      <div>
                        <div className="text-[10px] text-mp-orange font-bold uppercase tracking-[0.2em] mb-1">Golden Record</div>
                        <h2 className="text-2xl font-bold leading-tight">{selectedTrack.Name}</h2>
                        <p className="text-sm text-slate-400">{selectedTrack.City}, {selectedTrack.Country}</p>
                      </div>

                      <div className="aspect-video w-full bg-slate-800 rounded-lg overflow-hidden border border-white/10">
                         <img src={selectedTrack["Hero Image URL"]} className="w-full h-full object-cover grayscale-[0.2]" alt="Track" />
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                         <div className="p-4 bg-white/5 rounded-lg border border-white/5">
                            <div className="text-[10px] text-slate-500 uppercase tracking-tighter mb-1 flex items-center">
                                Wealth Index <span className="ml-1 cursor-help">ⓘ</span>
                            </div>
                            <div className="text-lg font-bold">{selectedTrack.disposable_income_pps.toLocaleString()} <span className="text-[10px] font-normal">PPS</span></div>
                         </div>
                         <div className="p-4 bg-white/5 rounded-lg border border-white/5">
                            <div className="text-[10px] text-slate-500 uppercase tracking-tighter mb-1">
                                Building Size 
                            </div>
                            <div className="text-lg font-bold">{selectedTrack.building_sqm.toLocaleString()} <span className="text-[10px] font-normal">M²</span></div>
                         </div>
                      </div>

                      <div>
                        <h4 className="text-xs font-bold uppercase text-slate-500 mb-3 tracking-widest">Sentiment Analysis</h4>
                        <div className="p-4 bg-mp-orange/5 border border-mp-orange/20 rounded-lg text-sm italic text-slate-300 leading-relaxed">
                           "{selectedTrack["Top Reviews Snippet"]}"
                        </div>
                      </div>

                      <button className="w-full py-4 mt-auto bg-mp-orange text-white font-bold rounded-lg hover:brightness-110 transition-all flex items-center justify-center space-x-2">
                         <span>☆</span> <span>SAVE TO WISH LIST</span>
                      </button>
                   </div>
                </div>
             )}
         </div>
      </div>
    </div>
  );
}

export default App;
