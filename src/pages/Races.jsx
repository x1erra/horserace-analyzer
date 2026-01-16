import { Link } from 'react-router-dom';
import { useState, useEffect } from 'react';
import axios from 'axios';
import RaceCard from '../components/RaceCard';

export default function Races() {
    const [activeTab, setActiveTab] = useState('today'); // 'today' or 'past'
    const [selectedTrack, setSelectedTrack] = useState('All'); // Changed default to 'All'

    // Default to current date YYYY-MM-DD
    const getTodayDate = () => {
        const today = new Date();
        const year = today.getFullYear();
        const month = String(today.getMonth() + 1).padStart(2, '0');
        const day = String(today.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    };

    const [selectedDate, setSelectedDate] = useState(getTodayDate());
    const [allRaces, setAllRaces] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [hasSearched, setHasSearched] = useState(false);

    // Pagination State
    const [currentPage, setCurrentPage] = useState(1);
    const [itemsPerPage, setItemsPerPage] = useState(30);

    // Metadata for filters
    const [availableTracks, setAvailableTracks] = useState([{ name: 'All Tracks', code: 'All' }]);
    const [availableDates, setAvailableDates] = useState(['All Dates']);
    const [metaLoading, setMetaLoading] = useState(true);

    // Fetch filter metadata on mount
    useEffect(() => {
        const fetchMetadata = async () => {
            try {
                const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';
                const response = await axios.get(`${baseUrl}/api/filter-options`);

                if (response.data) {
                    setAvailableTracks([{ name: 'All Tracks', code: 'All' }, ...response.data.tracks]);
                    setAvailableDates(['All Dates', ...response.data.dates]);
                }
            } catch (err) {
                console.error("Error fetching filter options:", err);
            } finally {
                setMetaLoading(false);
            }
        };
        fetchMetadata();
    }, []);

    // Reset pagination when filters or data change
    useEffect(() => {
        setCurrentPage(1);
    }, [activeTab, selectedTrack, selectedDate, allRaces]);

    // Reset state when tab changes
    const handleTabChange = (tab) => {
        setActiveTab(tab);
        setSelectedTrack('All');
        // Keep selectedDate as today even when switching tabs, or reset to All Dates?
        // User requested default is current date. Let's keep it as today or reset to today.
        // If switching to Past, probably want to start with today (or All?).
        // Let's reset to today to be safe and consistent with "default". 
        // Or if the user changed it, maybe keep it? Detailed req: "default dropdown date is the current date".
        // I will reset it to today when tab changes to ensure fresh start, or keep current implementation if it's cleaner.
        // The previous code reset it to 'All Dates'. I'll reset to today.
        if (tab === 'past') {
            setSelectedDate(getTodayDate());
        }
        setAllRaces([]);
        setHasSearched(false);
        setError(null);
    };

    const handleSearch = async () => {
        try {
            setLoading(true);
            setHasSearched(true);
            setError(null);
            // Reset to page 1 on new search (handled by useEffect dependency on allRaces, but explicit here doesn't hurt)
            setCurrentPage(1);

            const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';
            const endpoint = activeTab === 'today'
                ? `${baseUrl}/api/todays-races`
                : `${baseUrl}/api/past-races`;

            const params = {};

            if (activeTab === 'today') {
                // Dashboard filter logic style
                if (selectedTrack !== 'All') params.track = selectedTrack;
            } else {
                // Past races logic
                // If pagination is client side, we might want to fetch more or 'All' from backend?
                // User said "lets not start with everything by default because it's a hefty load".
                // But if we paginate client side, we MUST fetch everything first.
                // UNLESS we implement server-side pagination.
                // user said "control over how many results they load at once".
                // backend param `limit` exists.
                // However, the `Claims` page implementation was client-side pagination on a fetched list (limited by 200 in that case).
                // `params.limit = 100` was there before.
                // If I want to fetch "everything" for client side pagination, I might strictly need to remove limit or increase it.
                // BUT user said "lets not start with everything by default ... hefty load".
                // This implies they might WANT server side pagination or just a limit?
                // "lets give the user control over how many results they load at once" -> usually means "Items per page".
                // "lets not start with everything by default" -> implies initial fetch shouldn't be massive.
                // If I keep `params.limit = 100` (or make it larger like 300) and paginate that, it fits "hefty load" concern.
                // Let's bump it to 500 to get a good chunk of data, then paginate client side. 
                // Truly "hefty" data usually warrants server-side pagination. 
                // Given the context of "Claims" page which did client side, I will stick to client side but maybe increase the fetch limit slightly to ensure we get a good day's worth.
                // For "today", we fetch all. For "past", we filter by date or track.

                params.limit = 500; // Increased from 100 to allow more date range coverage if needed, but still limited.
                if (selectedTrack !== 'All') params.track = selectedTrack;
                if (selectedDate !== 'All Dates') {
                    params.start_date = selectedDate;
                    params.end_date = selectedDate;
                }
            }

            // Add cache buster
            params._t = Date.now();

            const response = await axios.get(endpoint, { params });
            const raceData = response.data.races || [];
            setAllRaces(raceData);

        } catch (err) {
            console.error("Error fetching races:", err);
            setError("Failed to load race data. Is the backend running?");
        } finally {
            setLoading(false);
        }
    };

    // Calculate Pagination
    const indexOfLastItem = currentPage * itemsPerPage;
    const indexOfFirstItem = indexOfLastItem - itemsPerPage;
    const currentItems = allRaces.slice(indexOfFirstItem, indexOfLastItem);
    const totalPages = Math.ceil(allRaces.length / itemsPerPage);

    const paginate = (pageNumber) => setCurrentPage(pageNumber);

    if (metaLoading) {
        return (
            <div className="text-white text-center p-20">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500"></div>
                <p className="mt-4">Loading options...</p>
            </div>
        );
    }

    return (
        <div className="space-y-8">
            <h3 className="text-3xl font-bold text-white">All Races</h3>
            <p className="text-sm text-gray-400 mb-4">Browse upcoming races and historical results.</p>

            {/* Tab selector */}
            <div className="flex gap-4 border-b border-purple-900/50">
                <button
                    onClick={() => handleTabChange('today')}
                    className={`px-6 py-3 font-medium transition ${activeTab === 'today'
                        ? 'text-purple-400 border-b-2 border-purple-400'
                        : 'text-gray-400 hover:text-white'
                        }`}
                >
                    Today's Races
                </button>
                <button
                    onClick={() => handleTabChange('past')}
                    className={`px-6 py-3 font-medium transition ${activeTab === 'past'
                        ? 'text-purple-400 border-b-2 border-purple-400'
                        : 'text-gray-400 hover:text-white'
                        }`}
                >
                    Past Races
                </button>
            </div>

            {/* Filter bar */}
            <div className="bg-black/50 p-4 rounded-xl border border-purple-900/20 flex flex-col md:flex-row gap-4 items-end">
                <div className="flex-1 w-full grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label className="block text-xs font-semibold text-gray-500 mb-1 ml-1 uppercase">Track</label>
                        <select
                            value={selectedTrack}
                            onChange={(e) => setSelectedTrack(e.target.value)}
                            className="w-full bg-black border border-gray-800 text-white px-4 py-2.5 rounded-lg focus:outline-none focus:border-purple-600 transition"
                        >
                            {availableTracks.map(track => (
                                <option key={track.code} value={track.code}>{track.name}</option>
                            ))}
                        </select>
                    </div>

                    {activeTab === 'past' && (
                        <div>
                            <label className="block text-xs font-semibold text-gray-500 mb-1 ml-1 uppercase">Date</label>
                            <select
                                value={selectedDate}
                                onChange={(e) => setSelectedDate(e.target.value)}
                                className="w-full bg-black border border-gray-800 text-white px-4 py-2.5 rounded-lg focus:outline-none focus:border-purple-600 transition"
                            >
                                <option value="All Dates">All Dates</option>
                                {availableDates.filter(d => d !== 'All Dates').map(date => (
                                    <option key={date} value={date}>{date}</option>
                                ))}
                            </select>
                        </div>
                    )}
                </div>

                <button
                    onClick={handleSearch}
                    disabled={loading}
                    className="w-full md:w-auto bg-black border border-purple-600 hover:bg-purple-900/20 hover:border-purple-500 disabled:opacity-50 text-white px-8 py-2.5 rounded-lg transition font-bold flex items-center justify-center gap-2 h-[42px] shadow-[0_0_15px_rgba(147,51,234,0.3)]"
                >
                    {loading ? (
                        <>
                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                            Loading...
                        </>
                    ) : (
                        <>
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                            Search
                        </>
                    )}
                </button>
            </div>

            {error && <div className="text-red-400 text-center p-4 bg-red-900/20 rounded-lg">{error}</div>}

            {/* Results */}
            {loading ? (
                <div className="text-center p-20">
                    <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500"></div>
                    <p className="mt-4 text-gray-400">Loading races...</p>
                </div>
            ) : !hasSearched ? (
                <div className="text-center p-20 bg-black rounded-xl border border-purple-900/30 border-dashed">
                    <p className="text-gray-500">Select filters and click Search to view races</p>
                </div>
            ) : (
                <>
                    {/* Results count */}
                    <p className="text-sm text-gray-400 mb-4">
                        Found {allRaces.length} {activeTab === 'today' ? "today's" : 'past'} races
                    </p>

                    {/* Grid of race cards */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-fadeIn">
                        {currentItems.length === 0 ? (
                            <div className="col-span-full text-center p-12 bg-black rounded-xl border border-purple-900/50">
                                <p className="text-gray-400 mb-4">
                                    {activeTab === 'today'
                                        ? "No races found matching your criteria."
                                        : "No past races found matching your criteria."}
                                </p>
                            </div>
                        ) : (
                            currentItems.map((race, index) => (
                                <RaceCard key={race.race_key || `${race.track_code}-${race.race_number}-${index}`} race={race} />
                            ))
                        )}
                    </div>

                    {/* Pagination Controls */}
                    {allRaces.length > 0 && (
                        <div className="mt-8 px-4 py-3 border border-purple-900/50 bg-black rounded-xl flex flex-col sm:flex-row items-center justify-between gap-4">
                            <div className="flex items-center text-sm text-gray-400">
                                <span>Show</span>
                                <select
                                    value={itemsPerPage}
                                    onChange={(e) => {
                                        setItemsPerPage(Number(e.target.value));
                                        setCurrentPage(1);
                                    }}
                                    className="mx-2 bg-black border border-purple-900/50 text-white text-xs rounded px-2 py-1 focus:outline-none focus:border-purple-500"
                                >
                                    <option value={15} className="bg-black">15</option>
                                    <option value={30} className="bg-black">30</option>
                                    <option value={50} className="bg-black">50</option>
                                    <option value={100} className="bg-black">100</option>
                                </select>
                                <span>results per page</span>
                            </div>

                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => paginate(currentPage - 1)}
                                    disabled={currentPage === 1}
                                    className={`px-3 py-1 rounded text-sm font-medium transition ${currentPage === 1
                                        ? 'bg-gray-800 text-gray-600 cursor-not-allowed'
                                        : 'bg-purple-900/30 text-purple-200 hover:bg-purple-900/50'
                                        }`}
                                >
                                    Previous
                                </button>

                                <span className="text-sm text-gray-400">
                                    Page <span className="font-medium text-white">{currentPage}</span> of <span className="font-medium text-white">{totalPages}</span>
                                </span>

                                <button
                                    onClick={() => paginate(currentPage + 1)}
                                    disabled={currentPage === totalPages}
                                    className={`px-3 py-1 rounded text-sm font-medium transition ${currentPage === totalPages
                                        ? 'bg-gray-800 text-gray-600 cursor-not-allowed'
                                        : 'bg-purple-900/30 text-purple-200 hover:bg-purple-900/50'
                                        }`}
                                >
                                    Next
                                </button>
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
