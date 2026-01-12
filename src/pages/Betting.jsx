import { useState, useEffect } from 'react';

const API_BASE_URL = 'http://localhost:5001/api';

export default function Betting() {
    const [tickets, setTickets] = useState([]);
    const [winRate, setWinRate] = useState(0);
    const [races, setRaces] = useState([]);
    const [selectedRaceId, setSelectedRaceId] = useState('');
    const [raceDetails, setRaceDetails] = useState(null);
    const [loading, setLoading] = useState(false);

    // Form State
    const [formData, setFormData] = useState({
        horseNumber: '',
        horseName: '',
        betType: 'Win',
        amount: 2.00
    });

    // Load bets and races on mount
    useEffect(() => {
        fetchBets();
        fetchRaces();
    }, []);

    const fetchBets = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/bets`);
            const data = await res.json();
            if (data.bets) {
                setTickets(data.bets);
                updateWinRate(data.bets);
            }
        } catch (error) {
            console.error('Error fetching bets:', error);
        }
    };

    const fetchRaces = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/todays-races`);
            const data = await res.json();
            if (data.races) {
                setRaces(data.races);
            }
        } catch (error) {
            console.error('Error fetching races:', error);
        }
    };

    const fetchRaceDetails = async (raceKey) => {
        if (!raceKey) return;
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE_URL}/race-details/${raceKey}`);
            const data = await res.json();
            setRaceDetails(data);
            // Reset horse selection when race changes
            setFormData(prev => ({ ...prev, horseNumber: '', horseName: '' }));
        } catch (error) {
            console.error('Error fetching race details:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleRaceSelect = (e) => {
        const raceId = e.target.value;
        setSelectedRaceId(raceId);
        const race = races.find(r => r.id === raceId);
        if (race) {
            fetchRaceDetails(race.race_key);
        } else {
            setRaceDetails(null);
        }
    };

    const handleHorseSelect = (e) => {
        const number = e.target.value;
        const entry = raceDetails?.entries.find(ent => ent.program_number === number);
        setFormData({
            ...formData,
            horseNumber: number,
            horseName: entry ? entry.horse_name : ''
        });
    };

    const updateWinRate = (bets) => {
        const resolved = bets.filter(ticket => ticket.status !== 'Pending');
        const wins = resolved.filter(ticket => ticket.status === 'Win').length;
        const rate = resolved.length > 0 ? Math.round((wins / resolved.length) * 100) : 0;
        setWinRate(rate);
    };

    const handleCreateTicket = async (e) => {
        e.preventDefault();
        if (!selectedRaceId || !formData.horseNumber) return;

        try {
            const res = await fetch(`${API_BASE_URL}/bets`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    race_id: selectedRaceId,
                    horse_number: formData.horseNumber,
                    horse_name: formData.horseName,
                    bet_type: formData.betType,
                    amount: formData.amount
                })
            });

            if (res.ok) {
                fetchBets(); // Refresh list
                // Reset form
                setFormData({ ...formData, horseNumber: '', horseName: '' });
                alert('Bet placed successfully!');
            } else {
                alert('Failed to place bet');
            }
        } catch (error) {
            console.error('Error placing bet:', error);
        }
    };

    const handleResolveBets = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/bets/resolve`, { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                alert(`Resolved ${data.resolved_count} bets!`);
                fetchBets();
            } else {
                alert('Failed to resolve bets');
            }
        } catch (error) {
            console.error('Error resolving bets:', error);
        }
    };

    return (
        <div className="space-y-8">
            <div className="flex justify-between items-center">
                <h3 className="text-3xl font-bold text-white">Betting Simulator</h3>
                <button
                    onClick={handleResolveBets}
                    className="bg-black border border-purple-600 hover:bg-purple-900/20 hover:border-purple-500 text-white px-4 py-2 rounded-md transition duration-200 shadow-[0_0_10px_rgba(147,51,234,0.2)]"
                >
                    Check for Results / Resolve Bets
                </button>
            </div>

            <p className="text-sm text-gray-400 mb-4">Place virtual bets on uploaded races and track your performance.</p>

            {/* Win Rate Stat */}
            <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/50">
                <h4 className="text-xl font-bold text-white mb-2">Your Win Rate</h4>
                <p className="text-4xl font-bold text-purple-400">{winRate}%</p>
                <p className="text-sm text-gray-500 mt-1">Based on {tickets.filter(t => t.status !== 'Pending').length} resolved bets</p>
            </div>

            {/* Form to Create Ticket */}
            <form onSubmit={handleCreateTicket} className="bg-black rounded-xl shadow-md p-6 border border-purple-900/50 space-y-4">
                <h4 className="text-xl font-bold text-white mb-4">Place New Bet</h4>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Race Selector */}
                    <div>
                        <label className="block text-gray-400 text-sm mb-1">Select Race</label>
                        <select
                            value={selectedRaceId}
                            onChange={handleRaceSelect}
                            className="w-full bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition duration-200"
                            required
                        >
                            <option value="">-- Select a Race --</option>
                            {races.map(race => (
                                <option key={race.id} value={race.id}>
                                    {race.track_code} Race {race.race_number} ({race.race_status})
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Horse Selector */}
                    <div>
                        <label className="block text-gray-400 text-sm mb-1">Select Horse</label>
                        <select
                            value={formData.horseNumber}
                            onChange={handleHorseSelect}
                            className="w-full bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition duration-200"
                            disabled={!raceDetails}
                            required
                        >
                            <option value="">-- Select Horse --</option>
                            {raceDetails?.entries.map(entry => (
                                <option key={entry.program_number} value={entry.program_number}>
                                    #{entry.program_number} - {entry.horse_name} ({entry.morning_line_odds})
                                </option>
                            ))}
                        </select>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label className="block text-gray-400 text-sm mb-1">Bet Type</label>
                        <select
                            value={formData.betType}
                            onChange={(e) => setFormData({ ...formData, betType: e.target.value })}
                            className="w-full bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition duration-200"
                        >
                            <option>Win</option>
                            <option>Place</option>
                            <option>Show</option>
                            {/* <option>Exacta</option> */}
                            {/* <option>Trifecta</option> */}
                        </select>
                    </div>
                    <div>
                        <label className="block text-gray-400 text-sm mb-1">Amount ($)</label>
                        <input
                            type="number"
                            value={formData.amount}
                            onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                            className="w-full bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition duration-200"
                            min="2"
                            step="1"
                        />
                    </div>
                </div>

                <button type="submit" className="w-full bg-black border border-purple-600 hover:bg-purple-900/20 hover:border-purple-500 text-white py-3 rounded-md transition duration-200 font-medium shadow-[0_0_15px_rgba(147,51,234,0.3)]">
                    Place Bet
                </button>
            </form>

            {/* Tickets Table */}
            <div className="bg-black rounded-xl shadow-md overflow-hidden border border-purple-900/50">
                <table className="w-full text-left text-gray-300">
                    <thead className="bg-purple-900/50">
                        <tr>
                            <th className="p-4">Date</th>
                            <th className="p-4">Track/Race</th>
                            <th className="p-4">Horse</th>
                            <th className="p-4">Bet</th>
                            <th className="p-4">Status</th>
                            <th className="p-4">Payout</th>
                        </tr>
                    </thead>
                    <tbody>
                        {tickets.length === 0 ? (
                            <tr>
                                <td colSpan="6" className="p-4 text-center text-gray-400">No tickets found.</td>
                            </tr>
                        ) : (
                            tickets.map((ticket, index) => (
                                <tr key={index} className="border-t border-purple-900/50 hover:bg-purple-900/20 transition duration-200">
                                    <td className="p-4">{new Date(ticket.created_at).toLocaleDateString()}</td>
                                    <td className="p-4">
                                        {ticket.hranalyzer_races ? (
                                            `${ticket.hranalyzer_races.track_code} Race ${ticket.hranalyzer_races.race_number}`
                                        ) : 'Unknown'}
                                    </td>
                                    <td className="p-4">#{ticket.horse_number} {ticket.horse_name}</td>
                                    <td className="p-4">${ticket.bet_amount} {ticket.bet_type}</td>
                                    <td className="p-4">
                                        <span className={`px-2 py-1 rounded text-xs font-bold ${ticket.status === 'Win' ? 'bg-green-900 text-green-200' :
                                            ticket.status === 'Loss' ? 'bg-red-900 text-red-200' :
                                                'bg-yellow-900 text-yellow-200'
                                            }`}>
                                            {ticket.status}
                                        </span>
                                    </td>
                                    <td className="p-4 text-green-400 font-bold">
                                        {ticket.payout > 0 ? `$${ticket.payout.toFixed(2)}` : '-'}
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
