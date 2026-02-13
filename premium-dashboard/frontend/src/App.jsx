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
   const [maxLength, setMaxLength] = useState(0);
   const [maxReach, setMaxReach] = useState(0);
   const [showWishlist, setShowWishlist] = useState(false);
   const [filters, setFilters] = useState({
      search: '',
      minPPS: 0,
      minLength: 0,
      minReach: 0,

      minAssetQuality: 0,  // NEW Filter
      requireCapex: false,
      requireOpex: false
   });
   const [isLoading, setIsLoading] = useState(true);
   const [disclaimerAccepted, setDisclaimerAccepted] = useState(false);
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
               center: [53.0, 4.5], // Focus on Netherlands, Belgium, Germany, UK
               zoom: 5,
               zoomControl: false,
               attributionControl: false
            });

            L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
               maxZoom: 19
            }).addTo(map.current);

            L.control.attribution({ position: 'bottomleft' }).addTo(map.current);

            // Clear selection when clicking empty map
            map.current.on('click', () => {
               console.log("Map background clicked. Clearing selection.");
               setSelectedTrack(null);
            });
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
      setIsLoading(true);
      try {
         const headers = { 'Authorization': `Bearer ${token}` };

         // 1. Fetch Tracks (Critical)
         let tracksData = [];
         try {
            const tracksRes = await fetch('/api/tracks', { headers });
            if (tracksRes.status === 401) { handleLogout(); return; }
            if (tracksRes.ok) {
               tracksData = await tracksRes.json();
               console.log(`FETCH: Loaded ${tracksData.length} tracks.`);
            } else {
               console.error("Failed to load tracks:", tracksRes.status);
            }
         } catch (e) {
            console.error("Error fetching tracks:", e);
         }

         // 2. Fetch Wishlist (Non-critical)
         let wishData = [];
         try {
            const wishRes = await fetch('/api/wishlist', { headers });
            if (wishRes.ok) wishData = await wishRes.json();
         } catch (e) {
            console.warn("Could not load wishlist:", e);
         }

         // 3. Fetch Shapes (Non-critical)
         let shapesData = { type: "FeatureCollection", features: [] };
         try {
            const shapesRes = await fetch('/api/tracks/shapes', { headers });
            if (shapesRes.ok) shapesData = await shapesRes.json();
         } catch (e) {
            console.warn("Could not load shapes:", e);
         }

         if (!Array.isArray(tracksData) || tracksData.length === 0) {
            console.warn("No tracks available to show.");
            setTracks([]);
         } else {
            setTracks(tracksData);
            setWishlist(Array.isArray(wishData) ? wishData : []);
            setShapes(shapesData);

            setMaxLength(Math.max(...tracksData.map(t => t.consolidated_track_length || 0), 1000));
            setMaxReach(Math.max(...tracksData.map(t => t.catchment_area_size || 0), 500));

            const filtered = tracksData.filter(t => {
               const matchesType = (activeFilters.indoor && t.is_indoor) ||
                  (activeFilters.outdoor && t.is_outdoor) ||
                  (activeFilters.sim && t.is_sim);
               const searchLower = filters.search.toLowerCase();
               const matchesSearch = !filters.search ||
                  t.Name?.toLowerCase().includes(searchLower) ||
                  t.City?.toLowerCase().includes(searchLower);
               const matchesMetrics = (t.disposable_income_pps >= filters.minPPS) &&
                  (t.consolidated_track_length >= filters.minLength) &&
                  (t.catchment_area_size >= filters.minReach);

               const matchesAssetQuality = !filters.minAssetQuality || (t.asset_quality_score && t.asset_quality_score >= filters.minAssetQuality);

               const matchesCapex = !filters.requireCapex || (t.sentiment_capex_score > 0.3);
               const matchesOpex = !filters.requireOpex || (t.sentiment_opex_score > 0.3);

               return matchesType && matchesSearch && matchesMetrics && matchesAssetQuality && matchesCapex && matchesOpex;
            });

            console.log(`FETCH: ${filtered.length} tracks matched filters. Adding markers...`);
            addMarkers(filtered);
         }
      } catch (err) {
         console.error("fetchData overall error:", err);
      } finally {
         setTimeout(() => setIsLoading(false), 1500);
      }
   };

   useEffect(() => {
      if (tracks.length > 0) {
         const filtered = tracks.filter(t => {
            const matchesType = (activeFilters.indoor && t.is_indoor) ||
               (activeFilters.outdoor && t.is_outdoor) ||
               (activeFilters.sim && t.is_sim);
            const searchLower = filters.search.toLowerCase();
            const matchesSearch = !filters.search ||
               (t.Name && t.Name.toLowerCase().includes(searchLower)) ||
               (t.City && t.City.toLowerCase().includes(searchLower));
            const matchesMetrics = (t.disposable_income_pps >= filters.minPPS) &&
               (t.consolidated_track_length >= filters.minLength) &&
               (t.catchment_area_size >= filters.minReach);

            const matchesAssetQuality = !filters.minAssetQuality || (t.asset_quality_score && t.asset_quality_score >= filters.minAssetQuality);

            const matchesCapex = !filters.requireCapex || (t.sentiment_capex_score > 0.3);
            const matchesOpex = !filters.requireOpex || (t.sentiment_opex_score > 0.3);

            return matchesType && matchesSearch && matchesMetrics && matchesAssetQuality && matchesCapex && matchesOpex;
         });
         console.log(`FILTER EFFECT: ${filtered.length} tracks matched. Refreshing markers...`);
         addMarkers(filtered);
      }
   }, [activeFilters, filters, tracks]);

   const addMarkers = (data) => {
      if (!map.current) {
         console.warn("addMarkers called but map.current is null");
         return;
      }

      markers.current.forEach(m => m.remove());
      markers.current = [];

      let addedCount = 0;
      data.forEach(track => {
         if (!track.Latitude || !track.Longitude) return;

         const isMultiTrack = track.is_indoor && track.is_outdoor;
         const isTrackSim = (track.is_indoor || track.is_outdoor) && track.is_sim;

         let color = '#A78BFA';
         if (isMultiTrack) color = '#FF6600';
         else if (isTrackSim) color = '#EC4899';
         else if (track.is_indoor) color = '#00A3FF';
         else if (track.is_outdoor) color = '#4ADE80';

         try {
            const marker = L.circleMarker([track.Latitude, track.Longitude], {
               radius: 6,
               fillColor: color,
               color: '#fff',
               weight: 2,
               opacity: 1,
               fillOpacity: 0.8
            })
               .addTo(map.current)
               .on('click', (e) => {
                  setSelectedTrack(track);
                  map.current.flyTo([track.Latitude, track.Longitude], 13, { duration: 1.5 });
                  L.DomEvent.stopPropagation(e);
               });

            markers.current.push(marker);
            addedCount++;
         } catch (e) {
            console.error("Error creating marker for track:", track.Name, e);
         }
      });
      console.log(`addMarkers: Successfully placed ${addedCount} markers.`);
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
                  color: '#FF6600',
                  weight: 5,
                  fillColor: '#FF6600',
                  fillOpacity: 0.4,
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

   const METRIC_INFO = {
      wealth: {
         meaning: "Net disposable income per inhabitant in Purchasing Power Standard (PPS).",
         importance: "Indicates local ability to spend on leisure and premium services. High wealth areas support higher ticket prices.",
         source: "Eurostat NUTS-3 (2023)"
      },
      length: {
         meaning: "Total distance of the racing circuit in meters.",
         importance: "Longer tracks support more karts simultaneously and attract professional/corporate event bookings.",
         source: "Official Track Website / OSM Geometry"
      },
      reach: {
         meaning: "The total geographical surface area reachable within a 30-minute drive-time in square kilometers (km²).",
         importance: "Reflects the geographic accessibility and the spatial footprint of the immediate local market available to the facility.",
         source: "OpenRouteService Matrix API"
      },
      strategicInsights: {
         meaning: "AI-powered analysis of customer reviews using the Gemini API to extract investment-relevant signals.",
         importance: "Identifies asset condition issues, operational strengths/weaknesses, and market positioning to inform acquisition decisions.",
         source: "Google Gemini AI Analysis"
      },
   };

   const InfoTooltip = ({ info, position = 'right' }) => (
      <div
         className="ml-1 text-slate-500 hover:text-mp-orange transition-colors cursor-help"
         onMouseEnter={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const tooltipWidth = 256; // w-64 = 16rem = 256px
            setActiveTooltip({
               info,
               x: position === 'left' ? rect.left - tooltipWidth - 10 : rect.right + 10,
               y: rect.top,
               position
            });
         }}
         onMouseLeave={() => setActiveTooltip(null)}
      >
         <span className="text-[10px] font-bold border border-slate-500 rounded-full w-3 h-3 flex items-center justify-center">i</span>
      </div>
   );

   const GlobalTooltip = () => {
      if (!activeTooltip) return null;
      return (
         <div
            className="fixed z-[9999] w-64 bg-slate-900/95 backdrop-blur-xl border border-white/20 p-4 rounded-xl shadow-2xl pointer-events-none animate-in fade-in zoom-in-95 duration-200"
            style={{ top: activeTooltip.y, left: activeTooltip.x }}
         >
            <div className="text-[10px] font-bold text-mp-orange uppercase tracking-widest mb-2">What it means</div>
            <div className="text-xs text-slate-300 leading-relaxed mb-3">{activeTooltip.info.meaning}</div>

            <div className="text-[10px] font-bold text-mp-orange uppercase tracking-widest mb-2">Investment Context</div>
            <div className="text-xs text-slate-300 leading-relaxed mb-3">{activeTooltip.info.importance}</div>

            <div className="pt-2 border-t border-white/10 flex justify-between items-center">
               <span className="text-[9px] text-slate-500 uppercase tracking-widest">Source</span>
               <span className="text-[9px] text-slate-400 italic">{activeTooltip.info.source}</span>
            </div>
         </div>
      );
   };



   const SliderFilter = ({ label, lowLabel, highLabel, value, max, onChange, unit = "", info }) => (
      <div className="space-y-2 pt-2">
         <div className="flex justify-between items-center mb-1">
            <div className="flex items-center">
               <label className="text-[11px] font-bold text-slate-300 uppercase tracking-widest">{label}</label>
               {info && <InfoTooltip info={info} />}
            </div>
            <span className="text-[10px] text-slate-500 font-mono italic">
               {value === 0 ? "Any" : `> ${value.toLocaleString()}${unit}`}
            </span>
         </div>
         <div className="flex justify-between items-end">
            <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">{lowLabel}</span>
            <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">{highLabel}</span>
         </div>
         <input
            type="range"
            min="0"
            max={max}
            value={value}
            onChange={(e) => onChange(parseInt(e.target.value))}
            className="premium-slider"
         />
      </div>
   );

   const MetricBox = ({ label, value, unit = "", progress, color = "bg-mp-orange", info }) => (
      <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-2 relative group">
         <div className="flex justify-between items-start">
            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{label}</div>
            {info && <InfoTooltip info={info} position="right" />}
         </div>
         <div className="text-xl font-bold">
            {value > 0 ? value.toLocaleString() : "N/A"} <span className="text-[10px] font-normal text-slate-400">{unit}</span>
         </div>
         <div className="flex space-x-1 mt-2">
            {[1, 2, 3, 4, 5].map(i => (
               <div
                  key={i}
                  className={`h-1 flex-1 rounded-full transition-all duration-500 ${progress >= i * 20 ? `${color} glow-step` : 'bg-white/10'}`}
               />
            ))}
         </div>
      </div>
   );

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

   const copyListAsMarkdown = () => {
      const pinnedTracks = tracks.filter(t => wishlist.includes(t.track_id));
      if (pinnedTracks.length === 0) return;

      let markdown = "# My Karting Wishlist\n\n";
      pinnedTracks.forEach(t => {
         const types = [t.is_indoor && "Indoor", t.is_outdoor && "Outdoor", t.is_sim && "SIM"].filter(Boolean).join(" | ");
         markdown += `## ${t.Name}\n`;
         markdown += `- **Location**: ${t.City}, ${t.Country}\n`;
         markdown += `- **Type**: ${types}\n`;
         markdown += `- **Track Length**: ${t.consolidated_track_length > 0 ? `${t.consolidated_track_length}m` : "N/A"}\n`;
         markdown += `- **Catchment Area**: ${t.catchment_area_size > 0 ? `${t.catchment_area_size}km²` : "N/A"}\n`;
         markdown += `- [Google Maps](${t["Maps URL"]})\n\n`;
      });

      navigator.clipboard.writeText(markdown);
      alert("Wishlist copied to clipboard as Markdown!");
   };

   const selectTrackFromWishlist = (track) => {
      setSelectedTrack(track);
      setShowWishlist(false);
      map.current.flyTo([track.Latitude, track.Longitude], 13, { duration: 1.5 });
   };

   // 1. DATA GLOSSARY


   const getInvestmentHypothesis = (track) => {
      const capex = track.sentiment_capex_score || 0;
      const opex = track.sentiment_opex_score || 0;
      const wealth = track.disposable_income_pps || 0;
      const quality = track.asset_quality_score || 0;

      let level = (wealth > 30000 && quality < 50) ? "HIGH CONVICTION" : "STRATEGIC POTENTIAL";
      let focus = "";
      let verdict = "";

      if (capex > 0.4) {
         focus = "Structural asset decay detected. Primary value unlock through CAPEX-led facility modernization.";
         verdict = `ACQUIRE FOR LOCATION. DEMOLISH FLEET. PIVOT TO CORPORATE HOSPITALITY. (High Failure Risk: ${Math.round(capex * 100)}%)`;
      } else if (opex > 0.4) {
         focus = "Operational inefficiency identified. Strategic management pivot required to capture premium market share.";
         verdict = "MANAGEMENT OVERHAUL REQUIRED. IMPLEMENT DYNAMIC PRICING. (Ops Efficiency: LOW)";
      } else if (wealth > 32000) {
         focus = "Market Arbitrage: High-wealth demographics served by stagnation. Potential for high-yield luxury karting pivot.";
         verdict = "PRIME ARBITRAGE OPPORTUNITY. RAISE TICKET PRICES 25%. TARGET LUXURY SEGMENT.";
      } else {
         focus = "Yield Optimization: Strong market fundamentals with minor friction. Ideal for rapid operational turnaround.";
         verdict = "STABLE CASH FLOW. OPTIMIZE UTILIZATION RATES. (Low Risk Entry)";
      }

      return { level, focus, verdict };
   };

   // Calculate effective confidence based on review count + AI assessment
   const getEffectiveConfidence = (track) => {
      const reviewCount = parseInt(track.review_count_12m) || parseInt(track['Review Velocity (12m)']) || 0;
      const aiConfidence = track.ai_confidence || 'low';

      // Insufficient data threshold (0-1 reviews)
      if (reviewCount <= 1) return 'insufficient';

      // Low sample size (2-4 reviews) always caps at low
      if (reviewCount <= 4) return 'low';

      // Medium sample (5-7): cap at medium
      if (reviewCount <= 7) {
         return aiConfidence === 'high' ? 'medium' : aiConfidence;
      }

      // High sample (8+): trust AI confidence
      return aiConfidence;
   };

   if (!isAuthenticated) {
      return (
         <div className="h-screen w-screen bg-mp-black flex items-center justify-center p-6 font-['Inter',sans-serif]">
            <div className="w-full max-w-md bg-glass backdrop-blur-3xl border border-white/10 rounded-3xl p-10 shadow-2xl">
               <div className="text-center mb-10">
                  <div className="flex justify-center mb-6">
                     <img src="/logo.png" className="h-20 object-contain filter drop-shadow-2xl" alt="MP One Logo" />
                  </div>
                  <h1 className="text-2xl font-black italic tracking-tighter text-white">MP ONE <span className="text-mp-orange italic">PORTAL</span></h1>
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
         {(isLoading || !disclaimerAccepted) && (
            <div className="preloader-overlay">
               <div className="flex flex-col items-center max-w-lg px-10 text-center">
                  <img src="/logo.png" className="h-24 object-contain mb-8" alt="MP One" />

                  {isLoading ? (
                     <div className="flex flex-col items-center">
                        <div className="w-12 h-12 border-4 border-mp-orange/20 border-t-mp-orange rounded-full animate-spin mb-4"></div>
                        <div className="text-[10px] font-black tracking-[0.4em] text-mp-orange uppercase">Initiating Data Feeds</div>
                     </div>
                  ) : (
                     <div className="space-y-8 animate-in fade-in zoom-in duration-500">
                        <div className="space-y-4">
                           <h2 className="text-xl font-black text-white italic tracking-tight">DATA DISCLAIMER</h2>
                           <p className="text-slate-400 text-sm leading-relaxed">
                              Data is collected from online sources, and may be partly incomplete or inaccurate.
                              The information provided is for intelligence purposes only.
                           </p>
                        </div>
                        <button
                           onClick={() => {
                              setDisclaimerAccepted(true);
                              // Critical: Leaflet needs to recalculate bounds after overlay removal
                              setTimeout(() => {
                                 if (map.current) {
                                    map.current.invalidateSize();
                                    console.log("Map size invalidated.");
                                 }
                              }, 100);
                           }}
                           className="bg-mp-orange text-white px-8 py-3 rounded-xl font-black text-[11px] tracking-widest uppercase hover:scale-105 transition-all shadow-lg shadow-mp-orange/30"
                        >
                           I understand, continue
                        </button>
                     </div>
                  )}
               </div>
            </div>
         )}

         {/* 1. TOP NAV */}
         <header className="h-16 px-6 flex items-center justify-between border-b border-white/10 z-[5000] bg-mp-black/80 backdrop-blur-lg relative">
            <div className="flex items-center space-x-4">
               <img src="/logo.png" className="h-8 object-contain" alt="MP One Logo" />
               <div className="h-6 w-[1px] bg-white/10 mx-2"></div>
               <h1 className="text-lg font-black italic tracking-tighter uppercase text-white">Market <span className="text-mp-orange">Intelligence</span></h1>
            </div>
            <div className="flex items-center space-x-6">
               <a
                  href="/report.pdf"
                  download
                  className="px-4 py-1.5 rounded-lg border border-white text-white text-xs font-bold hover:bg-white/10 transition-all flex items-center space-x-2"
               >
                  <span>DOWNLOAD REPORT</span>
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
               </a>
               <button
                  onClick={() => {
                     console.log("Wishlist Toggle Clicked:", !showWishlist);
                     setShowWishlist(!showWishlist);
                  }}
                  className={`text-sm font-medium transition-colors flex items-center space-x-2 ${showWishlist ? 'text-mp-orange' : 'hover:text-mp-orange'}`}
               >
                  <span>WISH LIST</span>
                  <span className="bg-mp-orange text-[10px] font-bold px-1.5 py-0.5 rounded-full text-white">{wishlist.length}</span>
               </button>
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
            <aside className="absolute top-6 left-6 w-72 z-[4000] max-h-[calc(100vh-3rem)] flex flex-col pointer-events-none">
               <div className="overflow-y-auto scrollbar-hide space-y-4 pointer-events-auto pb-4">
                  <div className="bg-glass border-premium p-5 rounded-2xl shadow-2xl space-y-6">
                     <div>
                        <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-mp-orange mb-4">MP ONE Intelligence</h3>
                        <div className="relative">
                           <input
                              type="text"
                              placeholder="Search Tracks or Cities..."
                              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-mp-orange/50 transition-all font-medium"
                              value={filters.search}
                              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                           />
                           <span className="absolute right-4 top-3.5 text-slate-600">🔍</span>
                        </div>
                     </div>

                     <div className="space-y-5">
                        <div className="pt-2">
                           <label className="text-[10px] font-black italic text-slate-400 uppercase tracking-widest block mb-4 border-b border-white/5 pb-2">Facility Profile</label>
                           <div className="grid grid-cols-3 gap-2 text-[10px]">
                              {[
                                 { label: 'Indoor', key: 'indoor', color: '#00A3FF' },
                                 { label: 'Outdoor', key: 'outdoor', color: '#4ADE80' },
                                 { label: 'SIM', key: 'sim', color: '#A78BFA' }
                              ].map(type => (
                                 <button
                                    key={type.key}
                                    onClick={() => setActiveFilters({ ...activeFilters, [type.key]: !activeFilters[type.key] })}
                                    className={`px-2 py-2 rounded-lg border transition-all duration-300 flex flex-col items-center justify-center space-y-1 ${activeFilters[type.key] ? 'bg-mp-orange/10 border-mp-orange/30 text-white shadow-lg shadow-mp-orange/5' : 'border-white/5 bg-transparent text-slate-600 hover:bg-white/5'}`}
                                 >
                                    <div className={`w-1.5 h-1.5 rounded-full`} style={{ backgroundColor: type.color }} />
                                    <span className="font-bold uppercase tracking-tighter">{type.label}</span>
                                 </button>
                              ))}
                           </div>
                        </div>

                        <div className="space-y-4 pt-2">
                           <label className="text-[10px] font-black italic text-slate-400 uppercase tracking-widest block border-b border-white/5 pb-2">Market Potential</label>
                           <SliderFilter
                              label="Wealth Index"
                              lowLabel="Low"
                              highLabel="High"
                              value={filters.minPPS}
                              max={40000}
                              unit=" PPS"
                              onChange={(v) => setFilters({ ...filters, minPPS: v })}
                              info={METRIC_INFO.wealth}
                           />

                           <SliderFilter
                              label="Track Length"
                              lowLabel="Short"
                              highLabel="Pro"
                              value={filters.minLength}
                              max={maxLength}
                              unit="m"
                              onChange={(v) => setFilters({ ...filters, minLength: v })}
                              info={METRIC_INFO.length}
                           />

                           <SliderFilter
                              label="Catchment Reach"
                              lowLabel="Local"
                              highLabel="Regional"
                              value={filters.minReach}
                              max={maxReach}
                              unit=" km²"
                              onChange={(v) => setFilters({ ...filters, minReach: v })}
                              info={METRIC_INFO.reach}
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


               </div>
            </aside>

            {/* RIGHT PANE: DETAIL */}
            <div className={`absolute top-0 right-0 h-full w-[400px] z-[6000] bg-mp-black border-l border-white/10 transform transition-transform duration-500 shadow-2xl ${selectedTrack ? 'translate-x-0' : 'translate-x-full'}`}>
               {selectedTrack && (
                  <div className="h-full flex flex-col">
                     {/* WRAPPED HEADER */}
                     <div className="p-8 pb-4 shrink-0">
                        <div className="flex justify-between items-start">
                           <div className="flex-1">
                              <h2 className="text-3xl font-black leading-tight tracking-tight text-white mb-1">{selectedTrack.Name}</h2>
                              <p className="text-sm font-medium text-slate-500">{selectedTrack.City}, {selectedTrack.Country}</p>
                           </div>
                           <div className="flex items-center space-x-3">
                              <button
                                 onClick={() => toggleWishlist(selectedTrack.track_id)}
                                 className={`w-10 h-10 rounded-full border flex items-center justify-center transition-all ${wishlist.includes(selectedTrack.track_id) ? 'bg-mp-orange border-mp-orange text-white shadow-lg shadow-mp-orange/30' : 'border-white/10 text-slate-500 hover:text-white'}`}
                              >
                                 <span className="text-lg">{wishlist.includes(selectedTrack.track_id) ? '★' : '☆'}</span>
                              </button>
                              <button onClick={() => setSelectedTrack(null)} className="text-slate-500 hover:text-white transition-colors text-xl">✕</button>
                           </div>
                        </div>

                        <div className="flex flex-wrap gap-2 mt-4">
                           {selectedTrack.is_outdoor && (
                              <div className="px-3 py-1 rounded-md bg-transparent border border-white/20 text-[10px] font-black text-white uppercase tracking-widest">Outdoor</div>
                           )}
                           {selectedTrack.is_indoor && (
                              <div className="px-3 py-1 rounded-md bg-transparent border border-white/20 text-[10px] font-black text-white uppercase tracking-widest">Indoor</div>
                           )}
                        </div>

                        <div className="flex space-x-3 mt-6">
                           <a
                              href={selectedTrack["Official Website"]}
                              target="_blank"
                              rel="noreferrer"
                              className="flex-1 bg-white/5 border border-white/10 rounded-xl py-3 flex items-center justify-center space-x-2 hover:bg-white/10 transition-all group"
                           >
                              <span className="text-[11px] font-black tracking-[0.15em] text-white">WEBSITE</span>
                              <span className="text-slate-500 group-hover:translate-x-1 transition-transform">→</span>
                           </a>
                           <a
                              href={selectedTrack["Maps URL"]}
                              target="_blank"
                              rel="noreferrer"
                              className="flex-1 bg-white/5 border border-white/10 rounded-xl py-3 flex items-center justify-center space-x-2 hover:bg-white/10 transition-all group"
                           >
                              <span className="text-[11px] font-black tracking-[0.15em] text-white">GOOGLE MAPS</span>
                              <span className="text-slate-500 group-hover:translate-x-1 transition-transform">→</span>
                           </a>
                        </div>
                     </div>

                     {/* SCROLLABLE BODY */}
                     <div className="flex-1 overflow-y-auto scrollbar-hide">
                        <div className="px-8 pb-8 space-y-8">
                           <div className="aspect-[16/10] w-full bg-slate-900 rounded-2xl overflow-hidden border border-white/10 shadow-2xl">
                              <img
                                 src={selectedTrack["Hero Image URL"]}
                                 className="w-full h-full object-cover grayscale-[0.2]"
                                 alt="Track"
                                 referrerPolicy="no-referrer"
                              />
                           </div>
                           {/* MOVED: Track Length */}
                           <div className="flex space-x-2">
                              {selectedTrack.is_indoor && (
                                 <div className="flex-1 bg-white/5 rounded-xl p-3 flex items-center justify-between border border-white/5">
                                    <span className="text-[9px] font-black text-white uppercase tracking-widest pl-1">Indoor</span>
                                    <span className="text-xs font-black text-white tracking-wide">{selectedTrack.consolidated_track_length}m</span>
                                 </div>
                              )}
                              {selectedTrack.is_outdoor && (
                                 <div className="flex-1 bg-white/5 rounded-xl p-3 flex items-center justify-between border border-white/5">
                                    <span className="text-[9px] font-black text-white uppercase tracking-widest pl-1">Outdoor</span>
                                    <span className="text-xs font-black text-white tracking-wide">{selectedTrack.consolidated_track_length}m</span>
                                 </div>
                              )}
                           </div>

                           {/* INVESTMENT PROFILE SECTION */}
                           <div className="space-y-6 pt-3 border-t border-white/10">

                              <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-5 space-y-5 shadow-inner">




                                 <div className="space-y-3">
                                    <div className="flex justify-between items-center">
                                       <div className="flex items-center">
                                          <span className="text-[11px] font-black text-slate-500 uppercase tracking-[0.2em]">Strategic Insight</span>
                                          <InfoTooltip info={METRIC_INFO.strategicInsights} position="left" />
                                       </div>
                                       <span className="text-[10px] text-slate-400">
                                          {selectedTrack.Average_Rating && selectedTrack.Average_Rating !== "N/A" && (
                                             <span className="mr-2">⭐ {parseFloat(selectedTrack.Average_Rating).toFixed(1)}</span>
                                          )}
                                       </span>
                                    </div>
                                    {(selectedTrack.review_count_12m > 0 || selectedTrack['Review Velocity (12m)'] > 0) && (
                                       <div className="text-xs text-slate-500 italic -mt-1">
                                          Based on {selectedTrack.review_count_12m || selectedTrack['Review Velocity (12m)']} reviews
                                       </div>
                                    )}
                                    <div className="bg-white/5 rounded-xl p-5 border border-white/5">
                                       {(() => {
                                          const getInsightIcon = (insight) => {
                                             if (insight.startsWith('Asset:')) return 'domain';
                                             if (insight.startsWith('Ops:')) return 'settings';
                                             if (insight.startsWith('Market:')) return 'trending_up';
                                             return 'circle';
                                          };
                                          const getIconColor = (insight) => {
                                             if (insight.startsWith('Asset:')) return 'text-blue-400';
                                             if (insight.startsWith('Ops:')) return 'text-amber-400';
                                             if (insight.startsWith('Market:')) return 'text-emerald-400';
                                             return 'text-slate-400';
                                          };
                                          const formatInsight = (insight) => {
                                             // Remove the prefix like "Asset: " to show just the verdict
                                             return insight.replace(/^(Asset|Ops|Market):\s*/, '');
                                          };
                                          const getInsightLabel = (insight) => {
                                             if (insight.startsWith('Asset:')) return 'ASSET';
                                             if (insight.startsWith('Ops:')) return 'OPERATIONS';
                                             if (insight.startsWith('Market:')) return 'MARKET FIT';
                                             return '';
                                          };
                                          try {
                                             const insights = selectedTrack.ai_insights ? JSON.parse(selectedTrack.ai_insights) : null;
                                             if (insights && Array.isArray(insights) && insights.length > 0) {
                                                return (
                                                   <>
                                                      <div className="space-y-5">
                                                         {insights.map((insight, i) => (
                                                            <div key={i} className="flex items-start gap-3">
                                                               <span className={`material-symbols-outlined text-xl flex-shrink-0 mt-0.5 ${getIconColor(insight)}`} style={{ fontVariationSettings: "'FILL' 1" }}>{getInsightIcon(insight)}</span>
                                                               <div className="flex-1">
                                                                  <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">{getInsightLabel(insight)}</div>
                                                                  <p className="text-sm text-slate-200 leading-relaxed font-medium">{formatInsight(insight)}</p>
                                                               </div>
                                                            </div>
                                                         ))}
                                                      </div>
                                                      {(() => {
                                                         const effectiveConf = getEffectiveConfidence(selectedTrack);
                                                         const confConfig = {
                                                            high: { icon: 'verified', color: 'text-green-400', label: 'High Confidence' },
                                                            medium: { icon: 'pending', color: 'text-yellow-400', label: 'Medium Confidence' },
                                                            low: { icon: 'error', color: 'text-red-400', label: 'Low Confidence' },
                                                            insufficient: { icon: 'help', color: 'text-slate-500', label: 'Insufficient Data' }
                                                         };
                                                         const conf = confConfig[effectiveConf] || confConfig.low;
                                                         return (
                                                            <div className="pt-4 mt-4 border-t border-white/10 flex items-center gap-2">
                                                               <span className={`material-symbols-outlined text-sm ${conf.color}`} style={{ fontVariationSettings: "'FILL' 1" }}>{conf.icon}</span>
                                                               <span className={`text-[10px] uppercase tracking-wider font-bold ${conf.color}`}>
                                                                  {conf.label}
                                                               </span>
                                                            </div>
                                                         );
                                                      })()}
                                                   </>
                                                );
                                             }
                                          } catch (e) { }
                                          // Fallback to old format
                                          return (
                                             <p className="text-sm leading-relaxed text-slate-300 italic font-medium">
                                                "{selectedTrack.problem_type_summary && selectedTrack.problem_type_summary.length > 20 ? selectedTrack.problem_type_summary : selectedTrack["Top Reviews Snippet"] || "No significant structural feedback detected in current dataset."}"
                                             </p>
                                          );
                                       })()}
                                    </div>
                                 </div>

                                 {selectedTrack.sentiment_detail_text && (
                                    <div className="pt-2">
                                       <div className="text-[9px] font-black text-slate-600 uppercase tracking-widest mb-2">Key Value Drivers</div>
                                       <div className="text-[10px] text-slate-400 leading-normal font-medium bg-white/2 p-3 rounded-lg border border-white/5">
                                          {selectedTrack.sentiment_detail_text}
                                       </div>
                                    </div>
                                 )}


                              </div>
                           </div>

                           <div className="space-y-4">
                              <h4 className="text-[11px] font-black text-slate-500 uppercase tracking-[0.2em]">Service Area</h4>
                              <div className="grid grid-cols-2 gap-3">
                                 <MetricBox
                                    label="Wealth Index"
                                    value={selectedTrack.disposable_income_pps}
                                    unit="PPS"
                                    progress={(selectedTrack.disposable_income_pps / 40000) * 100}
                                    info={METRIC_INFO.wealth}
                                 />
                                 <MetricBox
                                    label="Catchment Area"
                                    value={selectedTrack.catchment_area_size}
                                    unit="KM²"
                                    progress={(selectedTrack.catchment_area_size / 500) * 100}
                                    color="bg-blue-400"
                                    info={METRIC_INFO.reach}
                                 />
                              </div>
                           </div>




                        </div>
                     </div>
                  </div>
               )}
            </div>

            {/* WISHLIST OVERLAY */}
            <div className={`absolute top-0 right-0 h-full w-[450px] z-[6001] bg-mp-black border-l border-white/10 transform transition-transform duration-500 shadow-2xl flex flex-col ${showWishlist ? 'translate-x-0' : 'translate-x-full'}`}>
               <div className="p-8 pb-4 flex justify-between items-center">
                  <div className="flex items-center space-x-3">
                     <h2 className="text-2xl font-black text-white">MY <span className="text-mp-orange">WISHLIST</span></h2>
                     <span className="bg-white/10 px-2 py-0.5 rounded text-[10px] font-bold text-slate-400">{wishlist.length} ITEMS</span>
                  </div>
                  <div className="flex items-center space-x-4">
                     {wishlist.length > 0 && (
                        <button
                           onClick={copyListAsMarkdown}
                           className="text-[10px] font-bold text-mp-orange hover:text-white transition-colors flex items-center space-x-1 uppercase tracking-widest"
                        >
                           <span>Copy List</span>
                        </button>
                     )}
                     <button onClick={() => setShowWishlist(false)} className="text-slate-500 hover:text-white transition-colors text-xl">✕</button>
                  </div>
               </div>

               <div className="flex-1 overflow-y-auto px-8 pb-8 space-y-4">
                  {wishlist.length === 0 ? (
                     <div className="h-64 flex flex-col items-center justify-center text-slate-600 space-y-2">
                        <span className="text-4xl">☆</span>
                        <p className="text-xs font-medium uppercase tracking-widest">Your wishlist is empty</p>
                     </div>
                  ) : (
                     tracks.filter(t => wishlist.includes(t.track_id)).map(track => (
                        <div
                           key={track.track_id}
                           onClick={() => selectTrackFromWishlist(track)}
                           className="bg-white/5 border border-white/10 rounded-2xl p-4 flex space-x-4 cursor-pointer hover:bg-white/10 hover:border-mp-orange/30 transition-all group"
                        >
                           <div className="w-20 h-20 bg-slate-800 rounded-xl overflow-hidden flex-shrink-0">
                              <img
                                 src={track["Hero Image URL"]}
                                 className="w-full h-full object-cover grayscale group-hover:grayscale-0 transition-all duration-500"
                                 alt=""
                                 referrerPolicy="no-referrer"
                              />
                           </div>
                           <div className="flex-1 min-w-0">
                              <div className="flex justify-between items-start">
                                 <h3 className="text-sm font-bold text-white truncate pr-2">{track.Name}</h3>
                              </div>
                              <p className="text-[10px] text-slate-500 font-medium mb-2">{track.City}, {track.Country}</p>
                              <div className="flex flex-wrap gap-1">
                                 {track.is_outdoor && (
                                    <span className="text-[8px] font-black px-1.5 py-0.5 rounded bg-green-500/10 text-green-400 uppercase tracking-tighter border border-green-500/20">Outdoor</span>
                                 )}
                                 {track.is_indoor && (
                                    <span className="text-[8px] font-black px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 uppercase tracking-tighter border border-blue-500/20">Indoor</span>
                                 )}
                                 {track.is_sim && (
                                    <span className="text-[8px] font-black px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400 uppercase tracking-tighter border border-purple-500/20">SIM</span>
                                 )}
                              </div>
                           </div>
                           <div className="flex items-center text-slate-700 group-hover:text-mp-orange transition-colors text-xs">→</div>
                        </div>
                     ))
                  )}
               </div>
            </div>
         </div>
         {/* TOOLTIP OVERLAY */}
         <GlobalTooltip />
      </div>
   );
}

export default App;
