import { useParams } from 'react-router-dom';
import { useState, useEffect } from 'react';
import axios from 'axios';

export default function RaceDetails() {
    const { id } = useParams();
    const [race, setRace] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [crawling, setCrawling] = useState(false);

    const fetchRaceDetails = async () => {
        try {
            setLoading(true);
            const response = await axios.get(`http://localhost:5001/api/race-details/${id}`);
            setRace(response.data);
            setError(null);
        } catch (err) {
            console.error("Error fetching race details:", err);
            setError("Failed to load race details.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchRaceDetails();
    }, [id]);

    const handleCrawl = async () => {
        try {
            setCrawling(true);
            await axios.post(`http://localhost:5001/api/crawl-race/${id}`);
            // Re-fetch details after successful crawl to get the new horse data
            await fetchRaceDetails();
        } catch (err) {
            console.error("Crawl error:", err);
            alert("Failed to fetch full results from the PDF chart.");
        } finally {
            setCrawling(false);
        }
    };

    if (loading) return <div className="text-white text-center p-20">Loading details...</div>;
    if (error) return <div className="text-red-400 text-center p-20">{error}</div>;
    if (!race) return <div className="text-gray-400 text-center p-20">Race not found.</div>;

    const raceConditions = [
        { detail: 'Track', value: race.track },
        { detail: 'Date', value: race.date },
        { detail: 'Race Number', value: id.split('-').pop() },
        { detail: 'Winning Horse', value: race.topPick },
        { detail: 'Surface/Distance', value: race.detailed_info?.distance || 'N/A' },
        { detail: 'Conditions', value: race.detailed_info?.conditions || 'N/A' },
    ];

    // Use horses from API if available, otherwise just show winner
    const horseEntries = race.horses && race.horses.length > 0
        ? race.horses
        : [{
            program_number: 'N/A',
            horse_name: race.topPick,
            jockey: 'N/A',
            trainer: 'N/A',
            odds: 'N/A',
            finish_position: 1,
            comments: 'Winner (From Summary)'
        }];

    return (
        <div className="space-y-8">
            <div className="flex justify-between items-center">
                <h3 className="text-3xl font-bold text-white">
                    {race.name}
                </h3>
                <button
                    onClick={handleCrawl}
                    disabled={crawling}
                    className={`px-4 py-2 rounded-md font-medium transition ${crawling ? 'bg-gray-600' : 'bg-purple-600 hover:bg-purple-700'} text-white text-sm`}
                >
                    {crawling ? 'Parsing PDF Chart...' : 'Fetch Full Results (PDF)'}
                </button>
            </div>

            <p className="text-sm text-gray-400 mb-4">{race.date} • {race.time || 'N/A'}</p>

            {/* Race Conditions Table */}
            <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/20 overflow-hidden opacity-0 animate-fadeIn" style={{ animationDelay: '100ms' }}>
                <h4 className="text-xl font-semibold text-white mb-4">Race Summary</h4>
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
                {race.chart_url && (
                    <div className="mt-4">
                        <a href={race.chart_url} target="_blank" rel="noopener noreferrer" className="text-purple-400 hover:text-purple-300 underline text-sm">
                            View Official Chart (Equibase)
                        </a>
                    </div>
                )}
            </div>

            {/* Complete Horse Entries Table */}
            <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/20 overflow-x-auto opacity-0 animate-fadeIn" style={{ animationDelay: '150ms' }}>
                <h4 className="text-xl font-semibold text-white mb-4">Complete Results ({horseEntries.length} entries)</h4>
                <table className="w-full text-left text-gray-300 min-w-max">
                    <thead className="bg-purple-900/50">
                        <tr>
                            <th className="p-4">Fin</th>
                            <th className="p-4">Post</th>
                            <th className="p-4">Horse</th>
                            <th className="p-4">Jockey</th>
                            <th className="p-4">Trainer</th>
                            <th className="p-4">Odds</th>
                            <th className="p-4">Comments</th>
                        </tr>
                    </thead>
                    <tbody>
                        {horseEntries.map((entry, index) => (
                            <tr key={index} className="border-t border-purple-900/50 hover:bg-purple-900/20 transition duration-200">
                                <td className="p-4 font-bold text-white">{entry.finish_position || index + 1}</td>
                                <td className="p-4">{entry.program_number}</td>
                                <td className="p-4 font-bold text-purple-300">{entry.horse_name}</td>
                                <td className="p-4">{entry.jockey}</td>
                                <td className="p-4">{entry.trainer}</td>
                                <td className="p-4">{entry.odds}</td>
                                <td className="p-4 text-xs text-gray-400 max-w-xs truncate">{entry.comments}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                {(!race.horses || race.horses.length === 0) && (
                    <p className="text-xs text-gray-500 mt-4 italic">Note: Only finishing summary is available. Click 'Fetch Full Results' to parse the PDF chart for all horses.</p>
                )}
            </div>

            {/* Predictions & Analysis */}
            <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/20 opacity-0 animate-fadeIn" style={{ animationDelay: '250ms' }}>
                <h4 className="text-xl font-semibold text-white mb-4">Technical Data</h4>
                <div className="space-y-4">
                    <div className="p-4 bg-purple-900/10 rounded-lg border border-purple-900/50">
                        <p className="text-purple-300 font-medium">Fractional Times:</p>
                        <p className="text-gray-300 text-sm mt-1">{race.fractional_times || 'No fractional data available'}</p>
                    </div>
                    <div className="p-4 bg-purple-900/10 rounded-lg border border-purple-900/50">
                        <p className="text-purple-300 font-medium">Payouts:</p>
                        <p className="text-gray-300 text-sm mt-1">{race.payouts || 'No payout data available'}</p>
                    </div>
                </div>
            </div>

            <button className="bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 text-white px-6 py-3 rounded-md transition duration-200 font-medium opacity-0 animate-fadeIn" style={{ animationDelay: '300ms' }}>
                Run Model Again
            </button>
        </div>
    );
}