import { useParams, useNavigate, Link, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';
import axios from 'axios';

const getPostColor = (number) => {
    const num = parseInt(number);
    if (isNaN(num)) return { bg: '#374151', text: '#FFFFFF' };

    switch (num) {
        case 1: return { bg: '#EF4444', text: '#FFFFFF' }; // Red
        case 2: return { bg: '#FFFFFF', text: '#000000' }; // White
        case 3: return { bg: '#3B82F6', text: '#FFFFFF' }; // Blue
        case 4: return { bg: '#EAB308', text: '#000000' }; // Yellow
        case 5: return { bg: '#22C55E', text: '#FFFFFF' }; // Green
        case 6: return { bg: '#000000', text: '#FACC15' }; // Black with Yellow text
        case 7: return { bg: '#F97316', text: '#000000' }; // Orange with Black text
        case 8: return { bg: '#EC4899', text: '#000000' }; // Pink with Black text
        case 9: return { bg: '#06B6D4', text: '#000000' }; // Turquoise with Black text
        case 10: return { bg: '#A855F7', text: '#FFFFFF' }; // Purple
        case 11: return { bg: '#9CA3AF', text: '#FFFFFF' }; // Grey
        case 12: return { bg: '#84CC16', text: '#000000' }; // Lime with Black text
        case 13: return { bg: '#78350F', text: '#FFFFFF' }; // Brown
        case 14: return { bg: '#831843', text: '#FFFFFF' }; // Maroon
        case 15: return { bg: '#C3B091', text: '#000000' }; // Khaki (Corrected)
        case 16: return { bg: '#60A5FA', text: '#FFFFFF' }; // Copen Blue
        case 17: return { bg: '#1E3A8A', text: '#FFFFFF' }; // Navy
        case 18: return { bg: '#14532D', text: '#FFFFFF' }; // Forest Green
        case 19: return { bg: '#0EA5E9', text: '#FFFFFF' }; // Moonstone
        case 20: return { bg: '#D946EF', text: '#FFFFFF' }; // Fuschia
        default: return { bg: '#374151', text: '#FFFFFF' };
    }
};

export default function RaceDetails() {
    const { id } = useParams(); // This is the race_key
    const navigate = useNavigate();
    const location = useLocation();
    const cameFromChanges = location.state?.from === 'changes';
    const [raceData, setRaceData] = useState(null);
    const [raceChanges, setRaceChanges] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchRaceDetails = async () => {
            try {
                setLoading(true);
                // Scroll to top when race changes
                window.scrollTo(0, 0);

                const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';
                // Use the key from params. The backend endpoint expects race_key.
                const response = await axios.get(`${baseUrl}/api/race-details/${id}`);
                setRaceData(response.data);

                // Also fetch changes for this race
                const raceId = response.data.race?.id;
                if (raceId) {
                    try {
                        const changesRes = await axios.get(`${baseUrl}/api/race/${raceId}/changes`);
                        setRaceChanges(changesRes.data.changes || []);
                    } catch (e) {
                        console.log('No changes data available');
                    }
                }

                setError(null);
            } catch (err) {
                console.error("Error fetching race details:", err);
                setError("Failed to load race details.");
            } finally {
                setLoading(false);
            }
        };
        fetchRaceDetails();
    }, [id]);

    if (loading) {
        return (
            <div className="text-white text-center p-20 min-h-[50vh] flex flex-col justify-center items-center">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500"></div>
                <p className="mt-4">Loading details...</p>
            </div>
        );
    }

    if (error) return <div className="text-red-400 text-center p-20">{error}</div>;
    if (!raceData || !raceData.race) return <div className="text-gray-400 text-center p-20">Race not found.</div>;

    const { race, entries, exotic_payouts, claims, navigation } = raceData;
    const isUpcoming = race.race_status === 'upcoming';
    const isCompleted = race.race_status === 'completed';

    // Deduplicate entries by horse name and ensure valid data
    const uniqueEntries = entries.reduce((acc, current) => {
        const existingIndex = acc.findIndex(item => item.horse_name === current.horse_name);
        if (existingIndex > -1) {
            // Keep the one with more data (e.g., finish_position)
            if (current.finish_position && !acc[existingIndex].finish_position) {
                acc[existingIndex] = current;
            }
        } else {
            acc.push(current);
        }
        return acc;
    }, []);

    // Sort entries: Limit logic moved here for safety
    const sortedEntries = uniqueEntries.sort((a, b) => {
        if (isCompleted && a.finish_position && b.finish_position) {
            return a.finish_position - b.finish_position;
        }
        // Handle cases where finish_position might be null in a completed race (e.g. DNF) - push to bottom
        if (isCompleted && a.finish_position && !b.finish_position) return -1;
        if (isCompleted && !a.finish_position && b.finish_position) return 1;

        return parseInt(a.program_number || 999) - parseInt(b.program_number || 999);
    });

    const raceConditions = [
        { detail: 'Track', value: race.track_name },
        { detail: 'Location', value: race.location || 'N/A' },
        { detail: 'Date', value: race.race_date },
        { detail: 'Post Time', value: race.post_time || 'TBD' },
        { detail: 'Race Number', value: race.race_number },
        { detail: 'Surface', value: race.surface || 'N/A' },
        { detail: 'Distance', value: race.distance || 'N/A' },
        { detail: 'Race Type', value: race.race_type || 'N/A' },
        { detail: 'Purse', value: race.purse || 'N/A' },
        { detail: 'Status', value: race.race_status },
        { detail: 'Data Source', value: race.data_source === 'drf' ? 'DRF Upload' : 'Equibase' },
    ];

    if (isCompleted && race.final_time) {
        raceConditions.push({ detail: 'Final Time', value: race.final_time });
    }

    return (
        <div className="space-y-6 md:space-y-8 pb-20 md:pb-0">
            {/* Header / Navigation Section */}
            <div className="flex flex-col gap-4">
                {/* Top Navigation Bar */}
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                    {cameFromChanges ? (
                        <Link
                            to="/changes"
                            className="flex items-center gap-2 bg-black border border-purple-900/50 hover:bg-purple-900/20 text-purple-300 hover:text-white px-4 py-2 rounded-lg transition group text-sm font-medium"
                        >
                            <svg className="w-4 h-4 group-hover:-translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                            </svg>
                            Back to Changes
                        </Link>
                    ) : (
                        <button
                            onClick={() => {
                                // Smart navigation back to track context
                                const today = new Date();
                                const year = today.getFullYear();
                                const month = String(today.getMonth() + 1).padStart(2, '0');
                                const day = String(today.getDate()).padStart(2, '0');
                                const todayStr = `${year}-${month}-${day}`;

                                const isToday = race.race_date === todayStr;
                                const trackCode = race.track_code || 'All'; // Fallback

                                let url = `/races?track=${trackCode}`;
                                if (!isToday) {
                                    url += `&tab=past&date=${race.race_date}`;
                                }
                                navigate(url);
                            }}
                            className="flex items-center gap-2 bg-black border border-purple-900/50 hover:bg-purple-900/20 text-gray-300 hover:text-white px-4 py-2 rounded-lg transition group text-sm font-medium"
                        >
                            <svg className="w-4 h-4 group-hover:-translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                            </svg>
                            Back to Track
                        </button>
                    )}

                    {/* Next/Prev Race Navigation */}
                    {/* Next/Prev Race Navigation */}
                    {navigation && (
                        <div className="flex items-center gap-2 w-full sm:w-auto">
                            {/* Debug Log */}
                            {console.log("Navigation Data:", navigation)}

                            {navigation.prev_race_key ? (
                                <Link
                                    to={`/race/${navigation.prev_race_key}`}
                                    className="flex-1 sm:flex-none px-4 py-2 rounded-lg border text-sm font-medium transition flex items-center justify-center gap-2 bg-black border-purple-900/50 text-purple-300 hover:bg-purple-900/20 hover:text-white hover:border-purple-500"
                                >
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                                    </svg>
                                    Prev Race
                                </Link>
                            ) : (
                                <button
                                    disabled
                                    className="flex-1 sm:flex-none px-4 py-2 rounded-lg border text-sm font-medium flex items-center justify-center gap-2 bg-black/50 border-gray-800 text-gray-600 cursor-not-allowed"
                                >
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                                    </svg>
                                    Prev Race
                                </button>
                            )}

                            {navigation.next_race_key ? (
                                <Link
                                    to={`/race/${navigation.next_race_key}`}
                                    className="flex-1 sm:flex-none px-4 py-2 rounded-lg border text-sm font-medium transition flex items-center justify-center gap-2 bg-black border-purple-900/50 text-purple-300 hover:bg-purple-900/20 hover:text-white hover:border-purple-500"
                                >
                                    Next Race
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                    </svg>
                                </Link>
                            ) : (
                                <button
                                    disabled
                                    className="flex-1 sm:flex-none px-4 py-2 rounded-lg border text-sm font-medium flex items-center justify-center gap-2 bg-black/50 border-gray-800 text-gray-600 cursor-not-allowed"
                                >
                                    Next Race
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                    </svg>
                                </button>
                            )}
                        </div>
                    )}
                </div>

                <div className="flex flex-col md:flex-row md:justify-between md:items-center gap-2">
                    <div>
                        <h3 className="text-2xl md:text-3xl font-bold text-white leading-tight">
                            Race {race.race_number} - {race.track_name}
                        </h3>
                        <p className="text-sm text-gray-400 mt-1">{race.race_date} • {race.post_time || 'TBD'}</p>
                    </div>
                    <span className={`self-start md:self-center px-4 py-1.5 rounded-full text-xs md:text-sm font-bold uppercase tracking-wider ${isCompleted
                        ? 'bg-green-900/30 text-green-400 border border-green-900/50'
                        : isUpcoming
                            ? 'bg-blue-900/30 text-blue-400 border border-blue-900/50'
                            : 'bg-gray-900/30 text-gray-400 border border-gray-800'
                        }`}>
                        {isCompleted ? 'Completed' : isUpcoming ? 'Upcoming' : race.race_status}
                    </span>
                </div>
            </div>

            {/* 1. Claims Section */}
            {isCompleted && claims && claims.length > 0 && (
                <div className="bg-black rounded-xl shadow-md p-4 md:p-6 border border-purple-900/20 opacity-0 animate-fadeIn" style={{ animationDelay: '100ms' }}>
                    <h4 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                        <span className="w-1 h-6 bg-purple-500 rounded-full"></span>
                        Claims
                    </h4>

                    {/* Desktop Table */}
                    <div className="hidden md:block overflow-x-auto">
                        <table className="w-full text-left text-gray-300">
                            <thead className="bg-purple-900/20 text-xs uppercase tracking-wider text-purple-300">
                                <tr>
                                    <th className="p-4 rounded-tl-lg">Horse</th>
                                    <th className="p-4">New Trainer</th>
                                    <th className="p-4">New Owner</th>
                                    <th className="p-4 text-right rounded-tr-lg">Price</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-purple-900/30">
                                {claims.map((claim, index) => (
                                    <tr key={index} className="hover:bg-purple-900/10 transition">
                                        <td className="p-4 font-bold text-white">{claim.horse_name}</td>
                                        <td className="p-4">{claim.new_trainer_name || 'N/A'}</td>
                                        <td className="p-4">{claim.new_owner_name || 'N/A'}</td>
                                        <td className="p-4 text-right text-green-400 font-mono">
                                            {claim.claim_price ? `$${claim.claim_price.toLocaleString()}` : '-'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {/* Mobile Cards */}
                    <div className="md:hidden space-y-4">
                        {claims.map((claim, index) => (
                            <div key={index} className="bg-gray-900/50 rounded-lg p-4 border border-purple-900/30 space-y-2">
                                <div className="flex justify-between items-start">
                                    <div className="font-bold text-white text-lg">{claim.horse_name}</div>
                                    <div className="text-green-400 font-mono font-bold">
                                        {claim.claim_price ? `$${claim.claim_price.toLocaleString()}` : '-'}
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 gap-2 text-sm">
                                    <div>
                                        <div className="text-gray-500 text-xs uppercase">New Trainer</div>
                                        <div className="text-gray-300">{claim.new_trainer_name || 'N/A'}</div>
                                    </div>
                                    <div>
                                        <div className="text-gray-500 text-xs uppercase">New Owner</div>
                                        <div className="text-gray-300">{claim.new_owner_name || 'N/A'}</div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* 1b. Race Changes Section */}
            {raceChanges.length > 0 && (
                <div className="bg-black rounded-xl shadow-md p-4 md:p-6 border border-yellow-900/30 opacity-0 animate-fadeIn" style={{ animationDelay: '120ms' }}>
                    <h4 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                        <span className="w-1 h-6 bg-yellow-500 rounded-full"></span>
                        Late Changes ({raceChanges.length})
                    </h4>
                    <div className="space-y-2">
                        {raceChanges.map((change, idx) => (
                            <div key={idx} className={`flex items-center gap-3 p-3 rounded-lg border ${change.change_type === 'Scratch'
                                ? 'bg-red-900/10 border-red-900/30'
                                : change.change_type === 'Jockey Change'
                                    ? 'bg-blue-900/10 border-blue-900/30'
                                    : 'bg-yellow-900/10 border-yellow-900/30'
                                }`}>
                                {change.program_number && change.program_number !== '-' && (
                                    (() => {
                                        const style = getPostColor(change.program_number);
                                        return (
                                            <div
                                                className="w-7 h-7 rounded-md flex-shrink-0 flex items-center justify-center font-bold text-xs shadow-sm"
                                                style={{ backgroundColor: style.bg, color: style.text }}
                                            >
                                                {change.program_number}
                                            </div>
                                        );
                                    })()
                                )}
                                <div className="flex-1">
                                    <span className="text-white font-medium">{change.horse_name}</span>
                                    <span className="mx-2 text-gray-500">•</span>
                                    <span className={`text-sm font-medium ${change.change_type === 'Scratch' ? 'text-red-400'
                                        : change.change_type === 'Jockey Change' ? 'text-blue-400'
                                            : 'text-yellow-400'
                                        }`}>
                                        {change.change_type}
                                    </span>
                                </div>
                                <div className="text-gray-400 text-sm">
                                    {change.description}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* 2. Horse Entries / Results Section */}
            <div className="bg-black rounded-xl shadow-md p-4 md:p-6 border border-purple-900/20 opacity-0 animate-fadeIn" style={{ animationDelay: '150ms' }}>
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-4 gap-2">
                    <h4 className="text-xl font-semibold text-white flex items-center gap-2">
                        <span className="w-1 h-6 bg-purple-500 rounded-full"></span>
                        {isUpcoming ? `Entries (${sortedEntries.length})` : `Results (${sortedEntries.length})`}
                    </h4>
                    {race.equibase_pdf_url && (
                        <a href={race.equibase_pdf_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-purple-400 hover:text-purple-300 hover:underline text-sm font-medium bg-purple-900/10 px-3 py-1.5 rounded-lg transition">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                            </svg>
                            Official PDF
                        </a>
                    )}
                </div>

                {/* Desktop Table View */}
                <div className="hidden md:block overflow-x-auto">
                    <table className="w-full text-left text-gray-300">
                        <thead className="bg-purple-900/20 text-xs uppercase tracking-wider text-purple-300">
                            <tr>
                                {isCompleted && <th className="p-4 rounded-tl-lg">Fin</th>}
                                <th className="p-4">Post</th>
                                <th className="p-4">Horse</th>
                                {isCompleted && <th className="p-4">Jockey</th>}
                                {isCompleted && <th className="p-4">Trainer</th>}
                                {isUpcoming && <th className="p-4">ML Odds</th>}
                                {isCompleted && <th className="p-4">Odds</th>}
                                {isCompleted && <th className="p-4">Win $</th>}
                                {isCompleted && <th className="p-4 rounded-tr-lg">Comments</th>}
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-purple-900/30">
                            {sortedEntries.map((entry, index) => (
                                <tr key={index} className={`hover:bg-purple-900/10 transition duration-200 
                                    ${entry.finish_position === 1 ? 'bg-yellow-900/10' : ''}
                                    ${entry.scratched ? 'opacity-50 line-through text-gray-600' : ''}
                                `}>
                                    {isCompleted && (
                                        <td className="p-4 font-bold text-white text-lg">
                                            {entry.finish_position || '-'}
                                        </td>
                                    )}
                                    <td className="p-4">
                                        {(() => {
                                            const style = getPostColor(entry.program_number);
                                            return (
                                                <span
                                                    className="inline-flex w-8 h-8 rounded-md items-center justify-center font-bold text-sm shadow-sm leading-none"
                                                    style={{ backgroundColor: style.bg, color: style.text }}
                                                >
                                                    {entry.program_number}
                                                </span>
                                            );
                                        })()}
                                    </td>
                                    <td className="p-4 font-bold text-purple-300">{entry.horse_name}</td>
                                    {isCompleted && <td className="p-4 text-sm">{entry.jockey_name || 'N/A'}</td>}
                                    {isCompleted && <td className="p-4 text-sm">{entry.trainer_name || 'N/A'}</td>}
                                    {isUpcoming && <td className="p-4">{entry.scratched ? 'SCR' : (entry.morning_line_odds || 'N/A')}</td>}
                                    {isCompleted && <td className="p-4">{entry.final_odds || 'N/A'}</td>}
                                    {isCompleted && (
                                        <td className="p-4 text-green-400 font-mono font-medium">
                                            {entry.win_payout ? `$${entry.win_payout}` : '-'}
                                        </td>
                                    )}
                                    {isCompleted && (
                                        <td className="p-4 text-xs text-gray-500 max-w-xs italic">
                                            {entry.run_comments || '-'}
                                        </td>
                                    )}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* Mobile Card View */}
                <div className="md:hidden space-y-4">
                    {sortedEntries.map((entry, index) => (
                        <div key={index} className={`p-4 rounded-xl border ${entry.finish_position === 1
                            ? 'bg-yellow-900/10 border-yellow-700/50'
                            : 'bg-gray-900/50 border-purple-900/30'
                            }`}>
                            <div className="flex justify-between items-start mb-3">
                                <div className="flex items-center gap-3">
                                    {isCompleted && (() => {
                                        const style = getPostColor(entry.program_number);
                                        return (
                                            <div
                                                className="inline-flex w-8 h-8 rounded-md items-center justify-center font-bold text-sm shadow-sm leading-none"
                                                style={{ backgroundColor: style.bg, color: style.text }}
                                            >
                                                {entry.program_number || '-'}
                                            </div>
                                        );
                                    })()}
                                    <div>
                                        <div className={`font-bold text-lg leading-none ${entry.scratched ? 'text-gray-500 line-through' : 'text-white'}`}>
                                            {entry.horse_name} {entry.scratched && '(SCR)'}
                                        </div>
                                    </div>
                                </div>
                                <div className="text-right">
                                    {isCompleted && entry.win_payout && (
                                        <div className="text-green-400 font-mono font-bold text-lg">${entry.win_payout}</div>
                                    )}
                                    <div className="text-sm font-medium text-purple-300">
                                        {isUpcoming ? `ML: ${entry.morning_line_odds || '-'}` : `Odds: ${entry.final_odds || '-'}`}
                                    </div>
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-y-2 gap-x-4 text-sm border-t border-white/10 pt-3">
                                <div>
                                    <span className="text-gray-500 text-xs uppercase block">Jockey</span>
                                    <span className="text-gray-300">{entry.jockey_name || 'N/A'}</span>
                                </div>
                                <div>
                                    <span className="text-gray-500 text-xs uppercase block">Trainer</span>
                                    <span className="text-gray-300">{entry.trainer_name || 'N/A'}</span>
                                </div>
                                {isCompleted && entry.run_comments && (
                                    <div className="col-span-2 mt-1">
                                        <span className="text-gray-500 text-xs uppercase block">Comments</span>
                                        <span className="text-gray-400 italic text-xs">{entry.run_comments}</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                    {uniqueEntries.length === 0 && (
                        <div className="text-center p-8 text-gray-500 italic">No entries found.</div>
                    )}
                </div>
            </div>

            {/* 3. Stats & Summary Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Race Summary */}
                <div className="bg-black rounded-xl shadow-md p-4 md:p-6 border border-purple-900/20 opacity-0 animate-fadeIn" style={{ animationDelay: '200ms' }}>
                    <h4 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                        <span className="w-1 h-6 bg-purple-500 rounded-full"></span>
                        Summary
                    </h4>
                    {race.conditions && (
                        <p className="text-sm text-gray-400 mb-4 italic bg-purple-900/10 p-3 rounded-lg border border-purple-900/30">
                            "{race.conditions}"
                        </p>
                    )}

                    <div className="space-y-3">
                        {raceConditions.map((cond, index) => (
                            <div key={index} className="flex justify-between items-center py-2 border-b border-gray-800 last:border-0">
                                <span className="text-sm text-gray-500 font-medium">{cond.detail}</span>
                                <span className="text-sm text-white font-medium text-right">{cond.value}</span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Exotic Payouts & Tech Data */}
                <div className="space-y-6">
                    {isCompleted && exotic_payouts && exotic_payouts.length > 0 && (
                        <div className="bg-black rounded-xl shadow-md p-4 md:p-6 border border-purple-900/20 opacity-0 animate-fadeIn" style={{ animationDelay: '250ms' }}>
                            <h4 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                                <span className="w-1 h-6 bg-green-500 rounded-full"></span>
                                Payouts
                            </h4>
                            <div className="space-y-3">
                                {exotic_payouts.map((payout, index) => (
                                    <div key={index} className="bg-gray-900 p-3 rounded-lg border border-gray-800 flex justify-between items-center">
                                        <div>
                                            <p className="text-purple-300 font-bold text-xs uppercase tracking-wider">{payout.wager_type}</p>
                                            <p className="text-white text-sm mt-0.5">{payout.winning_combination}</p>
                                        </div>
                                        <p className="text-green-400 font-mono font-bold text-lg">${payout.payout}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {(race.fractional_times || isUpcoming) && (
                        <div className="bg-black rounded-xl shadow-md p-4 md:p-6 border border-purple-900/20 opacity-0 animate-fadeIn" style={{ animationDelay: '275ms' }}>
                            <h4 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                                <span className="w-1 h-6 bg-blue-500 rounded-full"></span>
                                {isUpcoming ? 'Info' : 'Splits'}
                            </h4>
                            {race.fractional_times && (
                                <div className="p-4 bg-purple-900/10 rounded-lg border border-purple-900/50">
                                    <p className="text-purple-300 font-bold text-xs uppercase mb-2">Fractional Times</p>
                                    <p className="text-white font-mono text-sm">{race.fractional_times}</p>
                                </div>
                            )}
                            {isUpcoming && (
                                <div className="p-4 bg-blue-900/10 rounded-lg border border-blue-900/50">
                                    <p className="text-blue-300 font-bold text-xs uppercase mb-2">Status</p>
                                    <p className="text-gray-300 text-sm">
                                        Results pending. Check back after post time.
                                    </p>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
