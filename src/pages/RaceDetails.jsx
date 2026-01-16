import { useParams, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import axios from 'axios';

export default function RaceDetails() {
    const { id } = useParams();
    const navigate = useNavigate();
    const [raceData, setRaceData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchRaceDetails = async () => {
            try {
                setLoading(true);
                const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';
                const response = await axios.get(`${baseUrl}/api/race-details/${id}`);
                setRaceData(response.data);
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
            <div className="text-white text-center p-20">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500"></div>
                <p className="mt-4">Loading details...</p>
            </div>
        );
    }

    if (error) return <div className="text-red-400 text-center p-20">{error}</div>;
    if (!raceData || !raceData.race) return <div className="text-gray-400 text-center p-20">Race not found.</div>;

    const { race, entries, exotic_payouts, claims } = raceData;
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

    // Sort entries by finish position for completed races, program number for upcoming
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
        <div className="space-y-8">
            <div className="flex flex-col gap-4">
                <button
                    onClick={() => navigate(-1)}
                    className="self-start flex items-center gap-2 text-gray-400 hover:text-white transition group"
                >
                    <svg className="w-4 h-4 group-hover:-translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                    </svg>
                    Back to Track
                </button>

                <div className="flex justify-between items-center">
                    <h3 className="text-3xl font-bold text-white">
                        Race {race.race_number} - {race.track_name}
                    </h3>
                    <span className={`px-4 py-2 rounded-md text-sm font-medium ${isCompleted
                        ? 'bg-green-900/30 text-green-400'
                        : isUpcoming
                            ? 'bg-blue-900/30 text-blue-400'
                            : 'bg-gray-900/30 text-gray-400'
                        }`}>
                        {isCompleted ? 'Completed' : isUpcoming ? 'Upcoming' : race.race_status}
                    </span>
                </div>
                <p className="text-sm text-gray-400">{race.race_date} • {race.post_time || 'TBD'}</p>
            </div>

            {/* 1. Claims Section (First Priority) */}
            {isCompleted && claims && claims.length > 0 && (
                <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/20 opacity-0 animate-fadeIn" style={{ animationDelay: '100ms' }}>
                    <h4 className="text-xl font-semibold text-white mb-4">Claims</h4>
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-gray-300">
                            <thead className="bg-purple-900/50">
                                <tr>
                                    <th className="p-4">Horse</th>
                                    <th className="p-4">New Trainer</th>
                                    <th className="p-4">New Owner</th>
                                    <th className="p-4 text-right">Price</th>
                                </tr>
                            </thead>
                            <tbody>
                                {claims.map((claim, index) => (
                                    <tr key={index} className="border-t border-purple-900/50 hover:bg-purple-900/20 transition">
                                        <td className="p-4 font-bold text-white">{claim.horse_name}</td>
                                        <td className="p-4">{claim.new_trainer_name || 'N/A'}</td>
                                        <td className="p-4">{claim.new_owner_name || 'N/A'}</td>
                                        <td className="p-4 text-right text-green-400">
                                            {claim.claim_price ? `$${claim.claim_price.toLocaleString()}` : '-'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* 2. Horse Entries / Results Table (Second Priority) */}
            <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/20 overflow-x-auto opacity-0 animate-fadeIn" style={{ animationDelay: '150ms' }}>
                <div className="flex justify-between items-center mb-4">
                    <h4 className="text-xl font-semibold text-white">
                        {isUpcoming ? `Entries (${sortedEntries.length})` : `Results (${sortedEntries.length} entries)`}
                    </h4>
                    {race.equibase_pdf_url && (
                        <a href={race.equibase_pdf_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-purple-400 hover:text-purple-300 hover:underline text-sm font-medium">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                            </svg>
                            Official Equibase PDF
                        </a>
                    )}
                </div>

                <table className="w-full text-left text-gray-300 min-w-max">
                    <thead className="bg-purple-900/50">
                        <tr>
                            {isCompleted && <th className="p-4">Fin</th>}
                            <th className="p-4">Post</th>
                            <th className="p-4">Horse</th>
                            {isCompleted && <th className="p-4">Jockey</th>}
                            {isCompleted && <th className="p-4">Trainer</th>}
                            {isUpcoming && <th className="p-4">ML Odds</th>}
                            {isCompleted && <th className="p-4">Odds</th>}
                            {isCompleted && <th className="p-4">Win $</th>}
                            {isCompleted && <th className="p-4">Comments</th>}
                        </tr>
                    </thead>
                    <tbody>
                        {sortedEntries.map((entry, index) => (
                            <tr key={index} className={`border-t border-purple-900/50 hover:bg-purple-900/20 transition duration-200 ${entry.finish_position === 1 ? 'bg-yellow-900/10' : ''
                                }`}>
                                {isCompleted && (
                                    <td className="p-4 font-bold text-white">
                                        {entry.finish_position || '-'}
                                    </td>
                                )}
                                <td className="p-4">{entry.program_number}</td>
                                <td className="p-4 font-bold text-purple-300">{entry.horse_name}</td>
                                {isCompleted && (
                                    <td className="p-4">{entry.jockey_name || 'N/A'}</td>
                                )}
                                {isCompleted && (
                                    <td className="p-4">{entry.trainer_name || 'N/A'}</td>
                                )}
                                {isUpcoming && (
                                    <td className="p-4">{entry.morning_line_odds || 'N/A'}</td>
                                )}
                                {isCompleted && (
                                    <td className="p-4">{entry.final_odds || 'N/A'}</td>
                                )}
                                {isCompleted && (
                                    <td className="p-4 text-green-400">
                                        {entry.win_payout ? `$${entry.win_payout}` : '-'}
                                    </td>
                                )}
                                {isCompleted && (
                                    <td className="p-4 text-xs text-gray-400 max-w-xs">
                                        <span className="line-clamp-2">{entry.run_comments || '-'}</span>
                                    </td>
                                )}
                            </tr>
                        ))}
                    </tbody>
                </table>
                {entries.length === 0 && (
                    <p className="text-gray-500 mt-4 italic text-center">No entries found for this race.</p>
                )}
            </div>

            {/* 3. Race Summary / Conditions (Third Priority) */}
            <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/20 overflow-hidden opacity-0 animate-fadeIn" style={{ animationDelay: '200ms' }}>
                <h4 className="text-xl font-semibold text-white mb-4">Race Summary</h4>
                {race.conditions && (
                    <p className="text-sm text-gray-400 mb-4 italic">{race.conditions}</p>
                )}
                <table className="w-full text-left text-gray-300">
                    <tbody>
                        {raceConditions.map((cond, index) => (
                            <tr key={index} className="border-b border-purple-900/50 last:border-b-0">
                                <td className="p-3 font-medium text-white">{cond.detail}</td>
                                <td className="p-3 text-gray-300">{cond.value}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* 4. Exotic Payouts and Technical Data */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {isCompleted && exotic_payouts && exotic_payouts.length > 0 && (
                    <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/20 opacity-0 animate-fadeIn" style={{ animationDelay: '250ms' }}>
                        <h4 className="text-xl font-semibold text-white mb-4">Exotic Payouts</h4>
                        <div className="space-y-4">
                            {exotic_payouts.map((payout, index) => (
                                <div key={index} className="bg-purple-900/10 p-3 rounded-lg border border-purple-900/50 flex justify-between items-center">
                                    <div>
                                        <p className="text-purple-300 font-medium text-sm">{payout.wager_type}</p>
                                        <p className="text-gray-300 text-xs">{payout.winning_combination}</p>
                                    </div>
                                    <p className="text-green-400 font-bold">${payout.payout}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {(race.fractional_times || isUpcoming) && (
                    <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/20 opacity-0 animate-fadeIn" style={{ animationDelay: '275ms' }}>
                        <h4 className="text-xl font-semibold text-white mb-4">
                            {isUpcoming ? 'Pre-Race Information' : 'Technical Data'}
                        </h4>
                        <div className="space-y-4">
                            {race.fractional_times && (
                                <div className="p-4 bg-purple-900/10 rounded-lg border border-purple-900/50">
                                    <p className="text-purple-300 font-medium text-sm">Fractional Times:</p>
                                    <p className="text-gray-300 text-sm mt-1">{race.fractional_times}</p>
                                </div>
                            )}
                            {isUpcoming && (
                                <div className="p-4 bg-blue-900/10 rounded-lg border border-blue-900/50">
                                    <p className="text-blue-300 font-medium text-sm">Race Status:</p>
                                    <p className="text-gray-300 text-xs mt-1">
                                        This race has not been run yet. Results will be available after the race completes.
                                    </p>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
