import { useParams } from 'react-router-dom';
import { useState, useEffect } from 'react';
import axios from 'axios';

export default function RaceDetails() {
    const { id } = useParams();
    const [raceData, setRaceData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchRaceDetails = async () => {
            try {
                setLoading(true);
                const response = await axios.get(`http://localhost:5001/api/race-details/${id}`);
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

    const { race, entries, exotic_payouts } = raceData;
    const isUpcoming = race.race_status === 'upcoming';
    const isCompleted = race.race_status === 'completed';

    // Sort entries by finish position for completed races, program number for upcoming
    const sortedEntries = [...entries].sort((a, b) => {
        if (isCompleted && a.finish_position && b.finish_position) {
            return a.finish_position - b.finish_position;
        }
        return parseInt(a.program_number) - parseInt(b.program_number);
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
            <div className="flex justify-between items-center">
                <h3 className="text-3xl font-bold text-white">
                    Race {race.race_number} - {race.track_name}
                </h3>
                <span className={`px-4 py-2 rounded-md text-sm font-medium ${
                    isCompleted
                        ? 'bg-green-900/30 text-green-400'
                        : isUpcoming
                        ? 'bg-blue-900/30 text-blue-400'
                        : 'bg-gray-900/30 text-gray-400'
                }`}>
                    {isCompleted ? 'Completed' : isUpcoming ? 'Upcoming' : race.race_status}
                </span>
            </div>

            <p className="text-sm text-gray-400 mb-4">{race.race_date} • {race.post_time || 'TBD'}</p>

            {/* Race Conditions Table */}
            <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/20 overflow-hidden opacity-0 animate-fadeIn" style={{ animationDelay: '100ms' }}>
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
                {race.equibase_chart_url && (
                    <div className="mt-4">
                        <a href={race.equibase_chart_url} target="_blank" rel="noopener noreferrer" className="text-purple-400 hover:text-purple-300 underline text-sm">
                            View Official Chart (Equibase)
                        </a>
                    </div>
                )}
                {race.equibase_pdf_url && (
                    <div className="mt-2">
                        <a href={race.equibase_pdf_url} target="_blank" rel="noopener noreferrer" className="text-purple-400 hover:text-purple-300 underline text-sm">
                            View PDF Chart (Equibase)
                        </a>
                    </div>
                )}
            </div>

            {/* Horse Entries Table */}
            <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/20 overflow-x-auto opacity-0 animate-fadeIn" style={{ animationDelay: '150ms' }}>
                <h4 className="text-xl font-semibold text-white mb-4">
                    {isUpcoming ? `Entries (${sortedEntries.length})` : `Results (${sortedEntries.length} entries)`}
                </h4>
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
                            <tr key={index} className={`border-t border-purple-900/50 hover:bg-purple-900/20 transition duration-200 ${
                                entry.finish_position === 1 ? 'bg-yellow-900/10' : ''
                            }`}>
                                {isCompleted && (
                                    <td className="p-4 font-bold text-white">
                                        {entry.finish_position || '-'}
                                    </td>
                                )}
                                <td className="p-4">{entry.program_number}</td>
                                <td className="p-4 font-bold text-purple-300">{entry.horse_name}</td>
                                {isCompleted && (
                                    <td className="p-4">{entry.jockey_id || 'N/A'}</td>
                                )}
                                {isCompleted && (
                                    <td className="p-4">{entry.trainer_id || 'N/A'}</td>
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

            {/* Exotic Payouts (only for completed races) */}
            {isCompleted && exotic_payouts && exotic_payouts.length > 0 && (
                <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/20 opacity-0 animate-fadeIn" style={{ animationDelay: '200ms' }}>
                    <h4 className="text-xl font-semibold text-white mb-4">Exotic Payouts</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {exotic_payouts.map((payout, index) => (
                            <div key={index} className="bg-purple-900/10 p-4 rounded-lg border border-purple-900/50">
                                <p className="text-purple-300 font-medium">{payout.wager_type}</p>
                                <p className="text-gray-300 text-sm mt-1">{payout.winning_combination}</p>
                                <p className="text-green-400 text-lg font-bold mt-2">${payout.payout}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Technical Data */}
            {(race.fractional_times || isUpcoming) && (
                <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/20 opacity-0 animate-fadeIn" style={{ animationDelay: '250ms' }}>
                    <h4 className="text-xl font-semibold text-white mb-4">
                        {isUpcoming ? 'Pre-Race Information' : 'Race Data'}
                    </h4>
                    <div className="space-y-4">
                        {race.fractional_times && (
                            <div className="p-4 bg-purple-900/10 rounded-lg border border-purple-900/50">
                                <p className="text-purple-300 font-medium">Fractional Times:</p>
                                <p className="text-gray-300 text-sm mt-1">{race.fractional_times}</p>
                            </div>
                        )}
                        {isUpcoming && (
                            <div className="p-4 bg-blue-900/10 rounded-lg border border-blue-900/50">
                                <p className="text-blue-300 font-medium">Race Status:</p>
                                <p className="text-gray-300 text-sm mt-1">
                                    This race has not been run yet. Results will be available after the race completes
                                    and is automatically crawled from Equibase.
                                </p>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
