import { useState, useEffect } from 'react';

// Use environment variable for API URL (defaults to localhost if not set)
const API_ROOT = import.meta.env.VITE_API_URL || 'http://localhost:5001';
const API_BASE_URL = `${API_ROOT}/api`;

// Simple Tooltip Component
const Tooltip = ({ text, children }) => {
    const [isVisible, setIsVisible] = useState(false);

    return (
        <div
            className="relative inline-block"
            onMouseEnter={() => setIsVisible(true)}
            onMouseLeave={() => setIsVisible(false)}
        >
            {children}
            {isVisible && (
                <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-64 p-3 bg-gray-900 text-xs text-gray-300 rounded shadow-xl border border-purple-500/30 z-50">
                    {text}
                    {/* Arrow */}
                    <div className="absolute top-full left-1/2 transform -translate-x-1/2 border-8 border-transparent border-t-gray-900"></div>
                </div>
            )}
        </div>
    );
};

export default function Betting() {
    const [tickets, setTickets] = useState([]);
    const [winRate, setWinRate] = useState(0);
    const [races, setRaces] = useState([]);
    const [selectedRaceId, setSelectedRaceId] = useState('');
    const [raceDetails, setRaceDetails] = useState(null);
    const [loading, setLoading] = useState(false);

    // Form State
    const [betType, setBetType] = useState('Win');
    const [amount, setAmount] = useState(2.00);

    // Single Selection
    const [selectedHorseId, setSelectedHorseId] = useState('');

    // Multi Selection (for Box)
    const [selectedHorseIds, setSelectedHorseIds] = useState([]);

    // Logic Selection (for Keys)
    // Structure: { 1: [ids], 2: [ids], 3: [ids] }
    const [posSelections, setPosSelections] = useState({ 1: [], 2: [], 3: [] });

    // Derived State
    const isBoxBet = ['Exacta Box', 'Trifecta Box'].includes(betType);
    const isKeyBet = ['Exacta Key', 'Trifecta Key', 'Exacta', 'Trifecta'].includes(betType);

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
                // Sort by Date Desc
                const sortedBets = data.bets.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
                setTickets(sortedBets);
                updateWinRate(data.bets);
            }
        } catch (error) {
            console.error('Error fetching bets:', error);
        }
    };

    const fetchRaces = async () => {
        try {
            // Filter for UPCOMING races only
            const res = await fetch(`${API_BASE_URL}/todays-races?status=Upcoming`);
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
            // Reset selection
            setSelectedHorseId('');
            setSelectedHorseIds([]);
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

    const toggleHorseSelection = (pgm) => {
        if (selectedHorseIds.includes(pgm)) {
            setSelectedHorseIds(selectedHorseIds.filter(id => id !== pgm));
        } else {
            setSelectedHorseIds([...selectedHorseIds, pgm]);
        }
    };

    const togglePosSelection = (pos, pgm) => {
        // For Straight Exacta/Trifecta, enforce single selection per position
        const isStraight = ['Exacta', 'Trifecta'].includes(betType);

        setPosSelections(prev => {
            const current = prev[pos] || [];

            if (current.includes(pgm)) {
                return { ...prev, [pos]: current.filter(id => id !== pgm) };
            } else {
                if (isStraight) {
                    // Replace current selection for this position
                    return { ...prev, [pos]: [pgm] };
                } else {
                    // Append for Key bets
                    return { ...prev, [pos]: [...current, pgm] };
                }
            }
        });
    };

    // Cost Calculation Logic
    const calculateCost = () => {
        const n = selectedHorseIds.length;
        if (betType === 'Exacta Box') {
            // P(n,2) = n * (n-1)
            return n * (n - 1) * amount;
        } else if (betType === 'Trifecta Box') {
            // P(n,3)
            return n * (n - 1) * (n - 2) * amount;
        } else if (betType === 'Win Place Show') {
            return amount * 3;
        } else if (betType === 'Win Place' || betType === 'Place Show') {
            return amount * 2;
        } else if (isKeyBet) {
            // Recursive combination counter for Key bets
            const countCombs = (depth, currentPath) => {
                const maxDepth = (betType === 'Exacta Key' || betType === 'Exacta') ? 2 : 3;
                if (depth > maxDepth) return 1;

                const candidates = posSelections[depth] || [];
                if (!Array.isArray(candidates)) return 0;
                let count = 0;
                for (const pgm of candidates) {
                    if (!currentPath.includes(pgm)) {
                        count += countCombs(depth + 1, [...currentPath, pgm]);
                    }
                }
                return count;
            };

            // If pos 1 is empty, 0 combinations
            if (!posSelections[1] || !Array.isArray(posSelections[1]) || posSelections[1].length === 0) return 0;
            return countCombs(1, []) * amount;
        }
        return amount; // Single bet
    };

    const totalCost = calculateCost();
    const isValid = isBoxBet
        ? (betType === 'Exacta Box' ? selectedHorseIds.length >= 2 : selectedHorseIds.length >= 3)
        : isKeyBet
            ? ((betType === 'Exacta Key' || betType === 'Exacta') ? posSelections[1].length > 0 && posSelections[2].length > 0
                : posSelections[1].length > 0 && posSelections[2].length > 0 && posSelections[3].length > 0)
            : !!selectedHorseId;

    const updateWinRate = (bets) => {
        const resolved = bets.filter(ticket => ticket.status !== 'Pending');
        const wins = resolved.filter(ticket => ticket.status === 'Win').length;
        const rate = resolved.length > 0 ? Math.round((wins / resolved.length) * 100) : 0;
        setWinRate(rate);
    };

    const handleCreateTicket = async (e) => {
        e.preventDefault();
        if (!selectedRaceId || !isValid) return;

        // Prepare Payload
        let selectionData = null;
        if (isBoxBet) selectionData = selectedHorseIds;
        else if (isKeyBet) {
            // Convert {1:[], 2:[]} to [[], []]
            // Ensure strictly ordered list
            selectionData = [];
            const max = (betType === 'Exacta Key' || betType === 'Exacta') ? 2 : 3;
            for (let i = 1; i <= max; i++) {
                selectionData.push(posSelections[i] || []);
            }
        }

        const payload = {
            race_id: selectedRaceId,
            bet_type: betType,
            amount: amount,
            horse_number: !isBoxBet && !isKeyBet ? selectedHorseId : null,
            horse_name: !isBoxBet && !isKeyBet ? raceDetails?.entries.find(e => e.program_number === selectedHorseId)?.horse_name : null,
            selection: selectionData
        };

        try {
            const res = await fetch(`${API_BASE_URL}/bets`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                fetchBets();
                // Reset form slightly
                // Reset form slightly
                if (isBoxBet) setSelectedHorseIds([]);
                else if (isKeyBet) setPosSelections({ 1: [], 2: [], 3: [] });
                else setSelectedHorseId('');
                alert('Bet placed successfully!');
            } else {
                alert('Failed to place bet');
            }
        } catch (error) {
            console.error('Error placing bet:', error);
        }
    };

    const handleResolveBets = async () => {
        setLoading(true);
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
        } finally {
            setLoading(false);
        }
    };

    const handleDeleteBet = async (ticketId) => {
        if (!confirm('Are you sure you want to delete this bet? This action cannot be undone.')) return;

        try {
            const res = await fetch(`${API_BASE_URL}/bets/${ticketId}`, { method: 'DELETE' });
            if (res.ok) {
                // Remove from state
                setTickets(tickets.filter(t => t.id !== ticketId));
                // Recalculate win rate
                const remaining = tickets.filter(t => t.id !== ticketId);
                updateWinRate(remaining);
            } else {
                alert('Failed to delete bet');
            }
        } catch (error) {
            console.error('Error deleting bet:', error);
        }
    };

    return (
        <div className="space-y-8">
            <div className="flex justify-between items-center">
                <h3 className="text-3xl font-bold text-white">Betting Simulator</h3>
                <button
                    onClick={handleResolveBets}
                    disabled={loading}
                    className="bg-black border border-purple-600 hover:bg-purple-900/20 hover:border-purple-500 text-white px-4 py-2 rounded-md transition duration-200 shadow-[0_0_10px_rgba(147,51,234,0.2)] disabled:opacity-50"
                >
                    {loading ? 'Processing...' : 'Check for Results / Resolve Bets'}
                </button>
            </div>

            <p className="text-sm text-gray-400 mb-4">Place virtual bets on upcoming races. Races will disappear from selection once they start.</p>

            {/* Win Rate Stat */}
            <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/50">
                <h4 className="text-xl font-bold text-white mb-2">Your Win Rate</h4>
                <p className="text-4xl font-bold text-purple-400">{winRate}%</p>
                <p className="text-sm text-gray-500 mt-1">Based on {tickets.filter(t => t.status !== 'Pending').length} resolved bets</p>
            </div>

            {/* Form to Create Ticket */}
            <form onSubmit={handleCreateTicket} className="bg-black rounded-xl shadow-md p-6 border border-purple-900/50 space-y-6">
                <h4 className="text-xl font-bold text-white mb-4 border-b border-gray-800 pb-2">Place New Bet</h4>

                {/* Race Selection */}
                <div>
                    <label className="block text-gray-400 text-sm mb-1">Select Race (Today's Upcoming)</label>
                    <select
                        value={selectedRaceId}
                        onChange={handleRaceSelect}
                        className="w-full bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition duration-200"
                        required
                    >
                        <option value="">-- Select a Race --</option>
                        {(() => {
                            // Group races by track
                            const grouped = races.reduce((acc, race) => {
                                const track = race.track_code;
                                if (!acc[track]) acc[track] = [];
                                acc[track].push(race);
                                return acc;
                            }, {});

                            // Sort tracks alphabetically
                            return Object.keys(grouped).sort().map(trackCode => (
                                <optgroup key={trackCode} label={trackCode}>
                                    {grouped[trackCode]
                                        .sort((a, b) => a.race_number - b.race_number)
                                        .map(race => (
                                            <option key={race.id} value={race.id}>
                                                Race {race.race_number} - Post: {race.post_time}
                                            </option>
                                        ))}
                                </optgroup>
                            ));
                        })()}
                    </select>
                </div>

                {/* Bet Type & Amount */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label className="block text-gray-400 text-sm mb-1">Bet Type</label>
                        <select
                            value={betType}
                            onChange={(e) => {
                                setBetType(e.target.value);
                                // Reset selections on type change to avoid confusion
                                setSelectedHorseId('');
                                setSelectedHorseIds([]);
                                setPosSelections({ 1: [], 2: [], 3: [] });
                            }}
                            className="w-full bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition duration-200"
                        >
                            <option value="Win">Win</option>
                            <option value="Win Place">Win Place</option>
                            <option value="Win Place Show">Win Place Show</option>
                            <option value="Place">Place</option>
                            <option value="Place Show">Place Show</option>
                            <option value="Show">Show</option>
                            <option value="Exacta">Exacta (Straight)</option>
                            <option value="Trifecta">Trifecta (Straight)</option>
                            <option value="Exacta Box">Exacta Box</option>
                            <option value="Trifecta Box">Trifecta Box</option>
                            <option value="Exacta Key">Exacta Key</option>
                            <option value="Trifecta Key">Trifecta Key</option>
                        </select>
                    </div>
                    <div>
                        <label className="block text-gray-400 text-sm mb-1">Unit Amount ($)</label>
                        <input
                            type="number"
                            value={amount}
                            onChange={(e) => setAmount(e.target.value)}
                            className="w-full bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition duration-200"
                            min="1"
                            step="1"
                        />
                    </div>
                </div>

                {/* Horse Selection Area */}
                <div className="bg-gray-900/30 p-4 rounded-lg border border-gray-800">
                    <label className="block text-gray-300 font-bold mb-3">
                        {isBoxBet
                            ? `Select Horses for ${betType} (Select multiple)`
                            : isKeyBet
                                ? `Construct ${betType} (Select for each position)`
                                : `Select Horse for ${betType}`
                        }
                    </label>

                    {!raceDetails ? (
                        <p className="text-gray-500 italic text-sm">Select a race to view horses.</p>
                    ) : isKeyBet ? (
                        // Position Selection Grid
                        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                            {[1, 2, ((betType === 'Trifecta Key' || betType === 'Trifecta') ? 3 : null)].filter(Boolean).map(pos => (
                                <div key={pos} className="bg-black/50 p-3 rounded border border-gray-800">
                                    <h5 className="text-purple-400 font-bold text-sm mb-2 text-center uppercase tracking-wide">
                                        Position {pos}
                                    </h5>
                                    <div className="space-y-1 max-h-60 overflow-y-auto custom-scrollbar">
                                        {raceDetails.entries.map((entry, index) => {
                                            const isSelected = posSelections[pos]?.includes(entry.program_number);
                                            // Check overlapping (visual aid only, backend handles validity)
                                            // const isUsedElsewhere = false; // Could implement

                                            return (
                                                <div
                                                    key={entry.program_number || index}
                                                    onClick={() => !entry.scratched && togglePosSelection(pos, entry.program_number)}
                                                    className={`
                                                        p-1.5 rounded flex items-center justify-between transition text-xs
                                                        ${entry.scratched
                                                            ? 'opacity-30 cursor-not-allowed bg-black/20'
                                                            : 'cursor-pointer'}
                                                        ${isSelected
                                                            ? 'bg-purple-900 text-white font-bold border border-purple-500'
                                                            : !entry.scratched ? 'bg-gray-900 text-gray-400 hover:bg-gray-800 border border-transparent' : ''}
                                                    `}
                                                >
                                                    <span className={entry.scratched ? 'line-through' : ''}>#{entry.program_number || 'SCR'}</span>
                                                    <span className={`truncate w-16 text-right ${entry.scratched ? 'line-through' : ''}`}>{entry.horse_name}</span>
                                                </div>
                                            )
                                        })}
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : isBoxBet ? (
                        // Multi-Select Grid
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-2 max-h-60 overflow-y-auto pr-2 custom-scrollbar">
                            {raceDetails.entries.map((entry, index) => {
                                const isSelected = selectedHorseIds.includes(entry.program_number);
                                const isScratched = entry.scratched || entry.program_number === 'SCR' || !entry.program_number;

                                return (
                                    <div
                                        key={entry.program_number || index}
                                        onClick={() => !isScratched && toggleHorseSelection(entry.program_number)}
                                        className={`
                                            p-2 rounded border flex items-center gap-2 transition select-none
                                            ${isScratched
                                                ? 'opacity-30 cursor-not-allowed bg-black/20 border-transparent'
                                                : 'cursor-pointer'}
                                            ${isSelected
                                                ? 'bg-purple-900/50 border-purple-500 text-white'
                                                : !isScratched ? 'bg-black border-gray-700 text-gray-400 hover:bg-gray-800' : ''}
                                        `}
                                    >
                                        <div className={`w-4 h-4 rounded-sm border flex items-center justify-center ${isSelected ? 'bg-purple-500 border-purple-500' : 'border-gray-500'}`}>
                                            {isSelected && <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>}
                                        </div>
                                        <span className={`font-mono font-bold ${isScratched ? 'line-through' : ''}`}>#{entry.program_number || 'SCR'}</span>
                                        <span className={`truncate text-xs ${isScratched ? 'line-through' : ''}`}>{entry.horse_name}</span>
                                        <span className="ml-auto text-xs text-gray-500">{isScratched ? 'SCR' : entry.morning_line_odds}</span>
                                    </div>
                                );
                            })}
                        </div>
                    ) : (
                        // Single Select Dropdown
                        <select
                            value={selectedHorseId}
                            onChange={(e) => setSelectedHorseId(e.target.value)}
                            className="w-full bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition duration-200"
                            required
                        >
                            <option value="">-- Select Horse --</option>
                            {raceDetails.entries.map(entry => (
                                <option
                                    key={entry.program_number || entry.horse_name}
                                    value={entry.program_number}
                                    disabled={entry.scratched || !entry.program_number || entry.program_number === 'SCR'}
                                >
                                    #{entry.program_number || 'SCR'} - {entry.horse_name} ({entry.scratched ? 'SCR' : entry.morning_line_odds})
                                </option>
                            ))}
                        </select>
                    )}
                </div>

                {/* Total Cost Display */}
                <div className="flex justify-between items-center bg-purple-900/20 p-4 rounded-lg border border-purple-900/50">
                    <div className="flex items-center gap-2">
                        <span className="text-gray-400 text-sm uppercase tracking-wide">Total Cost</span>
                        <Tooltip text={
                            betType === 'Exacta Box'
                                ? "Exacta Box covers all 1st & 2nd place permutations. Cost = (Horses × (Horses - 1)) × Unit Amount."
                                : betType === 'Trifecta Box'
                                    ? "Trifecta Box covers all 1st, 2nd & 3rd place permutations. Cost = (Horses × (Horses - 1) × (Horses - 2)) × Unit Amount."
                                    : betType === 'Win Place Show'
                                        ? "Win Place Show (WPS) places three separate bets on the same horse. Cost = 3 × Unit Amount."
                                        : (betType === 'Win Place' || betType === 'Place Show')
                                            ? "Covers two positions. Cost = 2 × Unit Amount."
                                            : "Standard bet cost is simply the Unit Amount."
                        }>
                            <svg className="w-4 h-4 text-purple-400 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        </Tooltip>
                    </div>
                    <div className="text-right">
                        <span className={`text-2xl font-bold ${totalCost > 0 ? 'text-white' : 'text-gray-600'}`}>
                            ${totalCost.toFixed(2)}
                        </span>
                        {isBoxBet && selectedHorseIds.length > 0 && (
                            <p className="text-xs text-gray-400">
                                {selectedHorseIds.length} horses · {Math.round(totalCost / amount)} combinations
                            </p>
                        )}
                    </div>
                </div>

                <button
                    type="submit"
                    disabled={!isValid || !selectedRaceId}
                    className="w-full bg-black border border-purple-600 hover:bg-purple-900/20 hover:border-purple-500 text-white py-3 rounded-md transition duration-200 font-medium shadow-[0_0_15px_rgba(147,51,234,0.3)] disabled:opacity-50 disabled:cursor-not-allowed"
                >
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
                            <th className="p-4">Selection</th>
                            <th className="p-4">Bet Type</th>
                            <th className="p-4">Cost</th>
                            <th className="p-4">Status</th>
                            <th className="p-4 text-right">Payout</th>
                            <th className="p-4 text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {tickets.length === 0 ? (
                            <tr>
                                <td colSpan="8" className="p-4 text-center text-gray-400">No tickets found.</td>
                            </tr>
                        ) : (
                            tickets.map((ticket, index) => (
                                <tr key={index} className="border-t border-purple-900/50 hover:bg-purple-900/20 transition duration-200">
                                    <td className="p-4 text-sm text-gray-500">{new Date(ticket.created_at).toLocaleDateString()}</td>
                                    <td className="p-4">
                                        {ticket.hranalyzer_races ? (
                                            <span className="font-medium text-white">
                                                {ticket.hranalyzer_races.track_code} R{ticket.hranalyzer_races.race_number}
                                            </span>
                                        ) : 'Unknown'}
                                    </td>
                                    <td className="p-4">
                                        {ticket.selection ? (
                                            <div className="flex flex-wrap gap-1">
                                                {ticket.selection.map((num, idx) => (
                                                    <span key={`${idx}-${Array.isArray(num) ? num.join(',') : num}`} className="bg-gray-800 text-xs px-1.5 py-0.5 rounded border border-gray-700">
                                                        #{Array.isArray(num) ? num.join(',') : num}
                                                    </span>
                                                ))}
                                            </div>
                                        ) : (
                                            <span className="text-purple-300 font-mono">#{ticket.horse_number} {ticket.horse_name}</span>
                                        )}
                                    </td>
                                    <td className="p-4 text-sm">{ticket.bet_type}</td>
                                    <td className="p-4 text-sm">${ticket.bet_cost || ticket.bet_amount}</td>
                                    <td className="p-4">
                                        <span className={`px-2 py-1 rounded text-xs font-bold ${ticket.status === 'Win' ? 'bg-green-900 text-green-200' :
                                            ticket.status === 'Loss' ? 'bg-red-900 text-red-200' :
                                                'bg-yellow-900 text-yellow-200'
                                            }`}>
                                            {ticket.status}
                                        </span>
                                    </td>
                                    <td className="p-4 text-right text-green-400 font-bold">
                                        {ticket.payout > 0 ? `$${ticket.payout.toFixed(2)}` : '-'}
                                    </td>
                                    <td className="p-4 text-right">
                                        <button
                                            onClick={() => handleDeleteBet(ticket.id)}
                                            className="bg-red-900/20 hover:bg-red-900/50 text-red-400 p-2 rounded transition"
                                            title="Delete Bet"
                                        >
                                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                            </svg>
                                        </button>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div >
    );
}
