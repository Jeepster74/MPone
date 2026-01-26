import React, { useState, useEffect, useRef } from 'react';

const MP_ORANGE = '#FF6600';

function App() {
   const [token, setToken] = useState(localStorage.getItem('mp_token'));
   const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('mp_token'));
   const [credentials, setCredentials] = useState({ username: '', password: '' });
   const [loginError, setLoginError] = useState('');

   const [tracks, setTracks] = useState([]);
   const [shapes, setShapes] = useState(null);
   const [selectedTrack, setSelectedTrack] = useState(null);
   const [wishlist, setWishlist] = useState([]);
   const [activeFilters, setActiveFilters] = useState({ indoor: true, outdoor: true, sim: true });
   const [activeTooltip, setActiveTooltip] = useState(null);
   const [minPPS, setMinPPS] = useState(0);
   const mapContainer = useRef(null);
   const map = useRef(null);
   const isochroneLayer = useRef(null);
   const markers = useRef([]);

   useEffect(() => {
      if (token) {
         setIsAuthenticated(true);
         // Initialize Leaflet Map
         if (!map.current) {
            map.current = L.map(mapContainer.current, {
               center: [51, 10], // Central Europe focus
               zoom: 4,
               zoomControl: false,
               attributionControl: false
            });

            L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
               maxZoom: 19
            }).addTo(map.current);

            L.control.attribution({ position: 'bottomleft' }).addTo(map.current);
         }
         fetchData();
      }
   }, [token]);

   const handleLogin = async (e) => {
      e.preventDefault();
      setLoginError('');
      try {
         const formData = new FormData();
         formData.append('username', credentials.username);
         formData.append('password', credentials.password);

         const res = await fetch('/api/auth/login', {
            method: 'POST',
            body: formData
         });

         if (res.ok) {
            const data = await res.json();
            localStorage.setItem('mp_token', data.access_token);
            setToken(data.access_token);
            setIsAuthenticated(true);
         } else {
            setLoginError('Invalid credentials. Access Denied.');
         }
      } catch (err) {
         setLoginError('Server error. Please try again later.');
      }
   };

   const handleLogout = () => {
      localStorage.removeItem('mp_token');
      setToken(null);
      setIsAuthenticated(false);
      window.location.reload(); // Simplest way to clear map/state
   };

   const fetchData = async () => {
      try {
         const headers = { 'Authorization': `Bearer ${token}` };

         console.log("Starting concurrent data fetch...");
         const [tracksRes, wishRes, shapesRes] = await Promise.all([
            fetch('/api/tracks', { headers }),
            fetch('/api/wishlist', { headers }),
            fetch('/api/tracks/shapes', { headers })
         ]);

         const [tracksData, wishData, shapesData] = await Promise.all([
            tracksRes.json(),
            wishRes.json(),
            shapesRes.json()
         ]);

         console.log(`Loaded ${tracksData.length} tracks and ${shapesData.features?.length || 0} Shapes.`);

         setTracks(tracksData);
         setWishlist(wishData);
         setShapes(shapesData);

         // Initial markers
         const filtered = tracksData.filter(t => {
            const matchesType = (activeFilters.indoor && t.is_indoor) ||
               (activeFilters.outdoor && t.is_outdoor) ||
               (activeFilters.sim && t.is_sim);
            return matchesType && (t.disposable_income_pps >= minPPS);
         });
         addMarkers(filtered);
      } catch (err) {
         console.error("Failed to load data", err);
      }
   };

   // Update markers when filters change
   useEffect(() => {
      if (tracks.length > 0) {
         const filtered = tracks.filter(t => {
            const matchesType = (activeFilters.indoor && t.is_indoor) ||
               (activeFilters.outdoor && t.is_outdoor) ||
               (activeFilters.sim && t.is_sim);
            return matchesType && (t.disposable_income_pps >= minPPS);
         });
         addMarkers(filtered);
      }
   }, [activeFilters, minPPS, tracks]);

   const addMarkers = (data) => {
      // Clear old markers
      markers.current.forEach(m => m.remove());
      markers.current = [];

      data.forEach(track => {
         if (!track.Latitude || !track.Longitude) return;

         const isMultiTrack = track.is_indoor && track.is_outdoor;
         const isTrackSim = (track.is_indoor || track.is_outdoor) && track.is_sim;

         let color = '#A78BFA'; // Default SIM Purple
         if (isMultiTrack) color = '#FF6600'; // Orange
         else if (isTrackSim) color = '#EC4899'; // Pink
         else if (track.is_indoor) color = '#00A3FF'; // Blue
         else if (track.is_outdoor) color = '#4ADE80'; // Green

         const marker = L.circleMarker([track.Latitude, track.Longitude], {
            radius: 5, // Slightly larger
            fillColor: color,
            color: '#fff',
            weight: 1.5,
            opacity: 0.9,
            fillOpacity: 0.7
         })
            .addTo(map.current)
            .on('click', (e) => {
               console.log("Marker clicked:", track.Name, track.track_id);
               setSelectedTrack(track);
               // Immediate focus
               map.current.flyTo([track.Latitude, track.Longitude], 13, { duration: 1.5 });
               L.DomEvent.stopPropagation(e);
            });

         markers.current.push(marker);
      });
   };

   // Update Isochrone Layer on Selection
   useEffect(() => {
      if (!map.current || !selectedTrack) return;

      console.log("Effect running for selection:", selectedTrack.Name);

      if (isochroneLayer.current) {
         map.current.removeLayer(isochroneLayer.current);
         isochroneLayer.current = null;
      }

      if (shapes) {
         const feature = shapes.features.find(f => {
            const fid = f.properties?.track_id ?? f.id;
            return String(fid) === String(selectedTrack.track_id);
         });

         if (feature) {
            console.log("Found matching isochrone for:", selectedTrack.Name);
            isochroneLayer.current = L.geoJSON(feature, {
               className: 'leaflet-isochrone-pulse',
               style: {
                  color: MP_ORANGE,
                  weight: 3,
                  dashArray: '5, 10',
                  fillColor: MP_ORANGE,
                  fillOpacity: 0.25,
                  interactive: false
               }
            }).addTo(map.current);

            // Critical: Ensure markers stay visible
            markers.current.forEach(m => m.bringToFront());

            // Fit map to catchment area
            try {
               const bounds = isochroneLayer.current.getBounds();
               if (bounds.isValid()) {
                  setTimeout(() => {
                     map.current.invalidateSize();
                     map.current.fitBounds(bounds, { padding: [50, 50], maxZoom: 13 });
                  }, 100);
               }
            } catch (err) {
               console.error("Leaflet fitBounds error:", err);
            }
         } else {
            console.warn("No isochrone feature found in GeoJSON matching ID:", selectedTrack.track_id);
         }
      } else {
         console.warn("Selected track set, but shapes data still loading or null.");
      }
   }, [selectedTrack, shapes]);

   const IndexBar = ({ value, max, colorClass }) => {
      const steps = [1, 2, 3, 4, 5];
      const threshold = max / 5;
      return (
         <div className="flex space-x-1 mt-1.5">
            {steps.map(s => {
               const isActive = value >= s * threshold;
               return (
                  <div
                     key={s}
                     className={`h-1 flex-1 rounded-full transition-all duration-500 ${isActive ? `${colorClass} glow-step` : 'bg-white/10'}`}
                  />
               );
            })}
         </div>
      );
   };

   const toggleWishlist = async (trackId) => {
      const isPinned = wishlist.includes(trackId);
      const action = isPinned ? 'remove' : 'add';

      try {
         const res = await fetch('/api/wishlist', {
            method: 'POST',
            headers: {
               'Content-Type': 'application/json',
               'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ track_id: trackId, action })
         });
         const newList = await res.json();
         setWishlist(newList);
      } catch (err) {
         console.error("Wishlist sync failed", err);
      }
   };

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
      },
      'Review Velocity': {
         label: 'Review Momentum',
         desc: 'Number of Google Reviews posted in the last 12 months. Indicates current popularity and user engagement velocity.',
         source: 'Google Maps Extraction'
      },
      'Management Issues': {
         label: 'Service Sentiment',
         desc: 'AI detection of negative feedback regarding staff, service, or hospitality. Lower is better.',
         source: 'NLP Sentiment Analysis'
      },
      'Structural Issues': {
         label: 'Asset Sentiment',
         desc: 'AI detection of negative feedback regarding track layout, kart quality, or facilities. Indicates CAPEX needs.',
         source: 'NLP Sentiment Analysis'
      },
      'Owner Responds': {
         label: 'Operational Proactivity',
         desc: 'Verification of whether facility owners actively engage with and respond to digital feedback.',
         source: 'Google Maps Audit'
      }
   };

   if (!isAuthenticated) {
      return (
         <div className="h-screen w-screen bg-mp-black flex items-center justify-center p-6 font-['Inter',sans-serif]">
            <div className="w-full max-w-md bg-glass backdrop-blur-3xl border border-white/10 rounded-3xl p-10 shadow-2xl">
               <div className="flex flex-col items-center mb-10">
                  <div className="w-16 h-16 bg-mp-orange flex items-center justify-center font-bold italic text-3xl text-white rounded-2xl mb-4 shadow-lg shadow-mp-orange/20">MP</div>
                  <h1 className="text-2xl font-bold tracking-tight text-white">INTELLIGENCE <span className="text-mp-orange">PORTAL</span></h1>
                  <p className="text-slate-400 text-sm mt-2">Sign in to access market data</p>
               </div>

               <form onSubmit={handleLogin} className="space-y-6">
                  <div>
                     <label className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-2 block">Username</label>
                     <input
                        type="text"
                        required
                        className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-4 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-mp-orange/50 transition-all"
                        placeholder="Enter your username"
                        value={credentials.username}
                        onChange={(e) => setCredentials({ ...credentials, username: e.target.value })}
                     />
                  </div>
                  <div>
                     <label className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-2 block">Password</label>
                     <input
                        type="password"
                        required
                        className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-4 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-mp-orange/50 transition-all"
                        placeholder="••••••••"
                        value={credentials.password}
                        onChange={(e) => setCredentials({ ...credentials, password: e.target.value })}
                     />
                  </div>

                  {loginError && <div className="text-red-500 text-xs font-medium text-center">{loginError}</div>}

                  <button
                     type="submit"
                     className="w-full bg-mp-orange hover:bg-mp-orange/90 text-white font-bold py-4 rounded-xl transition-all shadow-lg shadow-mp-orange/20 active:scale-[0.98]"
                  >
                     SIGN IN
                  </button>
               </form>
               <div className="mt-8 pt-8 border-t border-white/5 text-center">
                  <p className="text-xs text-slate-500">Authorized Personnel Only</p>
               </div>
            </div>
         </div>
      );
   }

   return (
      <div className="h-screen w-screen overflow-hidden flex flex-col bg-mp-black text-slate-100 relative font-['Inter',sans-serif]">
         {/* 1. TOP NAV */}
         <header className="h-16 px-6 flex items-center justify-between border-b border-white/10 z-50 bg-mp-black/80 backdrop-blur-lg">
            <div className="flex items-center space-x-3">
               <div className="w-10 h-10 bg-mp-orange flex items-center justify-center font-bold italic text-white rounded">MP</div>
               <h1 className="text-lg font-semibold tracking-tight uppercase">Intelligence <span className="text-mp-orange">Dashboard</span></h1>
            </div>
            <div className="flex items-center space-x-6">
               <button className="text-sm font-medium hover:text-mp-orange transition-colors">WISH LIST ({wishlist.length})</button>
               <button
                  onClick={handleLogout}
                  className="px-4 py-1.5 rounded-lg border border-white/10 text-xs font-bold hover:bg-white/5 transition-all"
               >
                  SIGN OUT
               </button>
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
                           {[
                              { label: 'Indoor', key: 'indoor' },
                              { label: 'Outdoor', key: 'outdoor' },
                              { label: 'SIM Racing', key: 'sim' }
                           ].map(type => (
                              <button
                                 key={type.key}
                                 onClick={() => setActiveFilters({ ...activeFilters, [type.key]: !activeFilters[type.key] })}
                                 className={`px-4 py-2 rounded-xl border transition-all duration-300 ${activeFilters[type.key] ? 'bg-mp-orange border-mp-orange text-white shadow-lg shadow-mp-orange/20' : 'border-white/10 bg-white/5 text-slate-400 hover:bg-white/10'}`}
                              >
                                 <div className="flex items-center space-x-2">
                                    <div className={`w-2 h-2 rounded-full ${type.key === 'indoor' ? 'bg-[#00A3FF]' : (type.key === 'outdoor' ? 'bg-[#4ADE80]' : 'bg-[#A78BFA]')}`} />
                                    <span className="font-bold uppercase tracking-tight">{type.label}</span>
                                 </div>
                              </button>
                           ))}
                        </div>
                     </div>
                     <div>
                        <div className="flex justify-between items-center mb-2">
                           <label className="text-xs font-medium block">Regional Wealth (Min PPS)</label>
                           <span className="text-[10px] text-mp-orange font-bold font-mono">{minPPS.toLocaleString()}</span>
                        </div>
                        <input
                           type="range"
                           min="0"
                           max="60000"
                           step="5000"
                           value={minPPS}
                           onChange={(e) => setMinPPS(parseInt(e.target.value))}
                           className="w-full h-1 bg-white/20 rounded-lg accent-mp-orange cursor-pointer"
                        />
                     </div>
                  </div>
               </div>

               <div className="bg-glass backdrop-blur-xl p-5 rounded-xl border border-white/10 shadow-2xl">
                  <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">Map Legend</h3>
                  <div className="space-y-2">
                     <div className="flex items-center space-x-2">
                        <div className="w-2.5 h-2.5 rounded-full bg-[#FF6600]"></div>
                        <span className="text-[10px] text-slate-300 font-medium">Multi-Track (Indoor + Outdoor)</span>
                     </div>
                     <div className="flex items-center space-x-2">
                        <div className="w-2.5 h-2.5 rounded-full bg-[#EC4899]"></div>
                        <span className="text-[10px] text-slate-300 font-medium">Track + SIM Racing</span>
                     </div>
                     <div className="flex items-center space-x-2">
                        <div className="w-2.5 h-2.5 rounded-full bg-[#00A3FF]"></div>
                        <span className="text-[10px] text-slate-300 font-medium">Indoor Only</span>
                     </div>
                     <div className="flex items-center space-x-2">
                        <div className="w-2.5 h-2.5 rounded-full bg-[#4ADE80]"></div>
                        <span className="text-[10px] text-slate-300 font-medium">Outdoor Only</span>
                     </div>
                     <div className="flex items-center space-x-2">
                        <div className="w-2.5 h-2.5 rounded-full bg-[#A78BFA]"></div>
                        <span className="text-[10px] text-slate-300 font-medium">SIM Racing Only</span>
                     </div>
                  </div>
               </div>

               <div className="bg-glass backdrop-blur-xl p-5 rounded-xl border border-white/10 shadow-2xl">
                  <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-2">Data Intelligence</h3>
                  <div className="flex items-center justify-between mb-2">
                     <span className="text-xs">Catchment Coverage</span>
                     <span className="text-xs text-mp-orange font-bold">
                        {shapes ? `${Math.round((shapes.features.length / Math.max(1, tracks.length)) * 100)}%` : 'Loading...'}
                     </span>
                  </div>
                  <div className="w-full bg-white/10 h-1 rounded-full overflow-hidden">
                     <div
                        className="bg-mp-orange h-full transition-all duration-1000"
                        style={{ width: shapes ? `${Math.min(100, Math.round((shapes.features.length / Math.max(1, tracks.length)) * 100))}%` : '0%' }}
                     />
                  </div>
                  <p className="text-[9px] text-slate-500 mt-2 uppercase tracking-tight">Geo-Spatial Analysis complete for enriched sites</p>
               </div>
            </aside>

            {/* RIGHT PANE: DETAIL */}
            <div className={`absolute top-0 right-0 h-full w-96 z-20 bg-glass backdrop-blur-2xl border-l border-white/10 transform transition-transform duration-500 shadow-[-20px_0_40px_rgba(0,0,0,0.5)] ${selectedTrack ? 'translate-x-0' : 'translate-x-full'}`}>
               {selectedTrack && (
                  <div className="p-8 h-full flex flex-col">
                     <button onClick={() => setSelectedTrack(null)} className="self-end text-slate-400 hover:text-white transition-colors">✕</button>
                     <div className="mt-4 flex-1 overflow-y-auto space-y-6">
                        <div>
                           <div className="text-[10px] text-mp-orange font-bold uppercase tracking-[0.2em] mb-1">Golden Record</div>
                           <h2 className="text-2xl font-bold leading-tight">{selectedTrack.Name}</h2>
                           <p className="text-sm text-slate-400 mb-3">{selectedTrack.City}, {selectedTrack.Country}</p>
                           <div className="flex flex-wrap gap-2">
                              {selectedTrack.is_indoor && (
                                 <span className="px-2 py-0.5 rounded-md bg-blue-500/10 border border-blue-500/20 text-[9px] font-bold text-blue-400 uppercase tracking-tighter">Indoor</span>
                              )}
                              {selectedTrack.is_outdoor && (
                                 <span className="px-2 py-0.5 rounded-md bg-green-500/10 border border-green-500/20 text-[9px] font-bold text-green-400 uppercase tracking-tighter">Outdoor</span>
                              )}
                              {selectedTrack.is_sim && (
                                 <span className="px-2 py-0.5 rounded-md bg-purple-500/10 border border-purple-500/20 text-[9px] font-bold text-purple-400 uppercase tracking-tighter">SIM Racing</span>
                              )}
                              {shapes && shapes.features.some(f => String(f.properties?.track_id || f.id) === String(selectedTrack.track_id)) && (
                                 <span className="px-2 py-0.5 rounded-md bg-mp-orange/10 border border-mp-orange/20 text-[9px] font-bold text-mp-orange uppercase tracking-tighter">Reach Data Loaded</span>
                              )}
                           </div>
                        </div>

                        <div className="aspect-video w-full bg-slate-800 rounded-lg overflow-hidden border border-white/10">
                           <img src={selectedTrack["Hero Image URL"]} className="w-full h-full object-cover grayscale-[0.2]" alt="Track" />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                           <div className="p-4 bg-white/5 rounded-lg border border-white/5">
                              <div className="text-[10px] text-slate-500 uppercase tracking-tighter mb-1 flex items-center justify-between">
                                 <span>Wealth Index</span>
                                 <button onClick={() => setActiveTooltip('disposable_income_pps')} className="ml-1 text-mp-orange hover:text-white transition-colors">ⓘ</button>
                              </div>
                              <div className="text-lg font-bold glow-text-orange">{selectedTrack.disposable_income_pps?.toLocaleString() || 'N/A'} <span className="text-[10px] font-normal">PPS</span></div>
                              <IndexBar value={selectedTrack.disposable_income_pps} max={60000} colorClass="bg-mp-orange" />
                           </div>
                           <div className="p-4 bg-white/5 rounded-lg border border-white/5 relative">
                              <div className="text-[10px] text-slate-500 uppercase tracking-tighter mb-1 flex items-center justify-between">
                                 <span>{selectedTrack.building_sqm > 15000 ? "Site Footprint" : "Building Size"}</span>
                                 <button onClick={() => setActiveTooltip('building_sqm')} className="ml-1 text-mp-orange hover:text-white transition-colors">ⓘ</button>
                              </div>
                              <div className="text-lg font-bold">
                                 {selectedTrack.building_sqm > 100000 ? ">100k" : (selectedTrack.building_sqm?.toLocaleString() || '0')} <span className="text-[10px] font-normal">M²</span>
                              </div>
                              <IndexBar value={selectedTrack.building_sqm} max={15000} colorClass="bg-blue-400" />
                           </div>
                           <div className="p-4 bg-white/5 rounded-lg border border-white/5">
                              <div className="text-[10px] text-slate-500 uppercase tracking-tighter mb-1 flex items-center justify-between">
                                 <span>Review Velocity</span>
                                 <button onClick={() => setActiveTooltip('Review Velocity')} className="ml-1 text-mp-orange hover:text-white transition-colors">ⓘ</button>
                              </div>
                              <div className="text-lg font-bold">{(selectedTrack['Review Velocity'] || 0).toLocaleString()} <span className="text-[10px] font-normal">/Y</span></div>
                              <IndexBar value={selectedTrack['Review Velocity'] || 0} max={200} colorClass="bg-mp-orange" />
                           </div>
                           <div className="p-4 bg-white/5 rounded-lg border border-white/5">
                              <div className="text-[10px] text-slate-500 uppercase tracking-tighter mb-1 flex items-center justify-between">
                                 <span>Market Reach</span>
                                 <button onClick={() => setActiveTooltip('catchment_area_size')} className="ml-1 text-mp-orange hover:text-white transition-colors">ⓘ</button>
                              </div>
                              <div className="text-lg font-bold">{Math.round(selectedTrack.catchment_area_size || 0).toLocaleString()} <span className="text-[10px] font-normal">KM²</span></div>
                              <IndexBar value={selectedTrack.catchment_area_size || 0} max={5000} colorClass="bg-purple-400" />
                           </div>
                        </div>

                        {activeTooltip && (
                           <div className="p-4 bg-slate-800 border border-mp-orange/30 rounded-xl shadow-2xl animate-in fade-in slide-in-from-top-2">
                              <div className="flex justify-between items-start mb-2">
                                 <h5 className="text-[10px] font-bold text-mp-orange uppercase">{GLOSSARY[activeTooltip].label}</h5>
                                 <button onClick={() => setActiveTooltip(null)} className="text-slate-500 hover:text-white">✕</button>
                              </div>
                              <p className="text-xs text-slate-300 leading-relaxed mb-2">{GLOSSARY[activeTooltip].desc}</p>
                              <div className="text-[9px] text-slate-500">Source: {GLOSSARY[activeTooltip].source}</div>
                           </div>
                        )}

                        <div>
                           <h4 className="text-xs font-bold uppercase text-slate-500 mb-3 tracking-widest flex items-center justify-between">
                              <span>Sentiment Analysis</span>
                              <div className="flex space-x-2">
                                 {selectedTrack['Owner Responds'] === 'Yes' && (
                                    <span className="text-[10px] text-green-400 border border-green-400/30 px-1.5 py-0.5 rounded flex items-center">
                                       <span className="mr-1">💬</span> Responsive
                                    </span>
                                 )}
                                 {selectedTrack['Management Issues'] === 'Detected' && (
                                    <span className="text-[10px] text-red-400 border border-red-400/30 px-1.5 py-0.5 rounded flex items-center">
                                       <span className="mr-1">🚨</span> Mgmt
                                    </span>
                                 )}
                              </div>
                           </h4>
                           <div className="p-4 bg-mp-orange/5 border border-mp-orange/20 rounded-lg text-sm italic text-slate-300 leading-relaxed relative group">
                              <span className="absolute -top-3 -left-2 text-3xl text-mp-orange/20 font-serif">"</span>
                              {selectedTrack["Top Reviews Snippet"] || "No review analysis available for this site."}
                              <span className="absolute -bottom-6 -right-2 text-3xl text-mp-orange/20 font-serif">"</span>
                           </div>
                        </div>

                        <div className="pt-6 border-t border-white/5 flex space-x-4">
                           <button
                              onClick={() => toggleWishlist(selectedTrack.track_id)}
                              className={`flex-1 py-4 font-bold rounded-xl transition-all flex items-center justify-center space-x-2 ${wishlist.includes(selectedTrack.track_id) ? 'bg-mp-orange text-white' : 'border border-mp-orange text-mp-orange hover:bg-mp-orange/5'}`}
                           >
                              <span>{wishlist.includes(selectedTrack.track_id) ? '★' : '☆'}</span>
                              <span>{wishlist.includes(selectedTrack.track_id) ? 'SAVED' : 'PIN TO WISHLIST'}</span>
                           </button>
                           <a
                              href={selectedTrack["Official Website"]}
                              target="_blank"
                              rel="noreferrer"
                              className="w-14 h-14 bg-slate-800 rounded-xl flex items-center justify-center hover:bg-slate-700 transition-all border border-white/5"
                           >
                              <span className="text-xl">🌐</span>
                           </a>
                        </div>
                     </div>
                  </div>
               )}
            </div>
         </div>
      </div>
   );
}

export default App;
