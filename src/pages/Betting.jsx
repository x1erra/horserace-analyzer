import { useState, useEffect } from 'react';
import { Wallet, RefreshCw, Plus, Trash2, TrendingUp, DollarSign, Percent, ChevronDown, ChevronUp } from 'lucide-react';
import { getPostColor } from '../utils/saddleCloth';

// Use environment variable for API URL (defaults to localhost if not set)
const API_ROOT = import.meta.env.VITE_API_URL || 'http://localhost:5001';
const API_BASE_URL = `${API_ROOT}/api`;

// Format dollar values with commas: 24368000 → "24,368,000.00"
const fmtMoney = (val) => {
    const num = parseFloat(val) || 0;
    return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

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
    const [stats, setStats] = useState({ winRate: 0, pnl: 0, totalWagered: 0, roi: 0 });
    const [bankroll, setBankroll] = useState(0);
    const [isBankModalOpen, setIsBankModalOpen] = useState(false);
    const [addFundsAmount, setAddFundsAmount] = useState('100');

    const [races, setRaces] = useState([]);
    const [selectedRaceId, setSelectedRaceId] = useState('');
    const [raceDetails, setRaceDetails] = useState(null);
    const [loading, setLoading] = useState(false);

    // Layout State - persist collapse state in localStorage
    const [isBetFormOpen, setIsBetFormOpen] = useState(() => {
        const saved = localStorage.getItem('hra_bet_form_open');
        return saved !== null ? saved === 'true' : true;
    });

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
        fetchWallet();
    }, []);

    const fetchWallet = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/wallet`);
            const data = await res.json();
            if (data.balance !== undefined) {
                setBankroll(data.balance);
            }
        } catch (error) {
            console.error('Error fetching wallet:', error);
        }
    };

    // Persist bankroll
    // Persist bankroll REMOVED


    // Persist bet form open/close state
    useEffect(() => {
        localStorage.setItem('hra_bet_form_open', isBetFormOpen.toString());
    }, [isBetFormOpen]);

    const fetchBets = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/bets`);
            const data = await res.json();
            if (data.bets) {
                // Sort by Date Desc
                const sortedBets = data.bets.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
                setTickets(sortedBets);
                calculateStats(data.bets);
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
            if (data.entries) {
                data.entries.sort((a, b) => {
                    const numA = parseInt(a.program_number, 10) || 999;
                    const numB = parseInt(b.program_number, 10) || 999;
                    return numA - numB;
                });
            }
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
        const numericAmount = parseFloat(amount) || 0;
        const n = selectedHorseIds.length;
        if (betType === 'Exacta Box') {
            // P(n,2) = n * (n-1)
            return n * (n - 1) * numericAmount;
        } else if (betType === 'Trifecta Box') {
            // P(n,3)
            return n * (n - 1) * (n - 2) * numericAmount;
        } else if (betType === 'Win Place Show') {
            return numericAmount * 3;
        } else if (betType === 'Win Place' || betType === 'Place Show') {
            return numericAmount * 2;
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
            return countCombs(1, []) * numericAmount;
        }
        return numericAmount; // Single bet
    };

    const totalCost = calculateCost();
    const isValid = isBoxBet
        ? (betType === 'Exacta Box' ? selectedHorseIds.length >= 2 : selectedHorseIds.length >= 3)
        : isKeyBet
            ? ((betType === 'Exacta Key' || betType === 'Exacta') ? posSelections[1].length > 0 && posSelections[2].length > 0
                : posSelections[1].length > 0 && posSelections[2].length > 0 && posSelections[3].length > 0)
            : !!selectedHorseId;

    const calculateStats = (bets) => {
        const resolved = bets.filter(ticket => !['Pending', 'Returned', 'Cancelled'].includes(ticket.status));
        const wins = resolved.filter(ticket => ticket.status === 'Win').length;
        const rate = resolved.length > 0 ? Math.round((wins / resolved.length) * 100) : 0;

        const totalWagered = resolved.reduce((acc, t) => acc + (parseFloat(t.bet_cost) || parseFloat(t.bet_amount) || 0), 0);
        const totalPayout = resolved.reduce((acc, t) => acc + (parseFloat(t.payout) || 0), 0);
        const pnl = totalPayout - totalWagered;
        const roi = totalWagered > 0 ? ((pnl / totalWagered) * 100).toFixed(1) : 0;

        setStats({
            winRate: rate,
            pnl: pnl,
            totalWagered: totalWagered,
            roi: roi,
            resolvedCount: resolved.length
        });
    };

    const handleCreateTicket = async (e) => {
        e.preventDefault();
        if (!selectedRaceId || !isValid) return;

        if (totalCost > bankroll) {
            alert("Insufficient funds! Please add money to your wallet.");
            setIsBankModalOpen(true);
            return;
        }

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
            amount: parseFloat(amount),
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
                const data = await res.json();
                // Update balance from response
                if (data.new_balance !== undefined) {
                    setBankroll(data.new_balance);
                } else {
                    fetchWallet();
                }
                fetchBets();
                // Reset form slightly
                // Reset form slightly
                if (isBoxBet) setSelectedHorseIds([]);
                else if (isKeyBet) setPosSelections({ 1: [], 2: [], 3: [] });
                else setSelectedHorseId('');
                alert('Bet placed successfully!');
            } else {
                const err = await res.json();
                alert(`Failed to place bet: ${err.error || 'Unknown error'}`);
            }
        } catch (error) {
            console.error('Error placing bet:', error);
        }
    };

    const handleResolveBets = async () => {
        setLoading(true);
        // Identify currently pending bets to track winnings
        const pendingIds = tickets.filter(t => t.status === 'Pending').map(t => t.id);

        try {
            const res = await fetch(`${API_BASE_URL}/bets/resolve`, { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                alert(`Resolved ${data.resolved_count} bets!`);

                // Fetch updated bets to calculate winnings
                const betsRes = await fetch(`${API_BASE_URL}/bets`);
                const betsData = await betsRes.json();

                if (betsData.bets) {
                    // Check for new earnings from the previously pending bets
                    let newEarnings = 0;
                    betsData.bets.forEach(bet => {
                        if (pendingIds.includes(bet.id) && bet.status === 'Win') {
                            newEarnings += (parseFloat(bet.payout) || 0);
                        }
                    });

                    if (newEarnings > 0) {
                        // Refresh wallet from server as it should be credited there
                        fetchWallet();
                        alert(`You won $${fmtMoney(newEarnings)}!`);
                    }

                    // Update main state
                    const sortedBets = betsData.bets.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
                    setTickets(sortedBets);
                    calculateStats(betsData.bets);
                }
            } else {
                alert('Failed to resolve bets');
            }
        } catch (error) {
            console.error('Error resolving bets:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleResetStats = async () => {
        if (!confirm('Are you sure you want to delete ALL betting history? This action cannot be undone.')) return;
        try {
            const res = await fetch(`${API_BASE_URL}/bets`, { method: 'DELETE' });
            if (res.ok) {
                setTickets([]);
                calculateStats([]);
                // Refresh wallet to reflect any pending bet refunds
                fetchWallet();
                alert('All betting history has been deleted. Pending bets refunded.');
            } else {
                alert('Failed to delete betting history.');
            }
        } catch (error) {
            console.error('Error deleting betting history:', error);
        }
    };

    const handleDeleteBet = async (ticketId) => {
        if (!confirm('Are you sure you want to delete this bet? This action cannot be undone.')) return;

        try {
            const res = await fetch(`${API_BASE_URL}/bets/${ticketId}`, { method: 'DELETE' });
            if (res.ok) {
                const data = await res.json();
                // Sync wallet if refund occurred
                if (data.new_balance !== undefined) {
                    setBankroll(data.new_balance);
                } else {
                    fetchWallet();
                }
                // Remove from state
                const remaining = tickets.filter(t => t.id !== ticketId);
                setTickets(remaining);
                calculateStats(remaining);
            } else {
                alert('Failed to delete bet');
            }
        } catch (error) {
            console.error('Error deleting bet:', error);
        }
    };

    const handleAddFunds = async (e) => {
        e.preventDefault();
        const amountToAdd = parseFloat(addFundsAmount);
        if (amountToAdd > 0) {
            try {
                const res = await fetch(`${API_BASE_URL}/wallet/transaction`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ type: 'deposit', amount: amountToAdd })
                });
                const data = await res.json();
                if (data.success) {
                    setBankroll(data.balance);
                    setIsBankModalOpen(false);
                    alert(`Successfully added $${fmtMoney(amountToAdd)} to your wallet!`);
                } else {
                    alert('Failed to add funds');
                }
            } catch (error) {
                console.error('Error adding funds:', error);
                alert(`Error adding funds: ${error.message}`);
            }
        } else {
            alert('Please enter a valid amount.');
        }
    };

    const handleBurnFunds = async (e) => {
        e.preventDefault();
        const amountToBurn = parseFloat(addFundsAmount);
        if (amountToBurn > 0) {
            try {
                const res = await fetch(`${API_BASE_URL}/wallet/transaction`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ type: 'withdraw', amount: amountToBurn })
                });
                const data = await res.json();
                if (data.success) {
                    setBankroll(data.balance);
                    setIsBankModalOpen(false);
                    alert(`Successfully burned $${fmtMoney(amountToBurn)} from your wallet!`);
                } else {
                    alert(`Failed to burn funds: ${data.error}`);
                }
            } catch (error) {
                console.error('Error burning funds:', error);
            }
        } else {
            alert('Please enter a valid amount to burn.');
        }
    };

    return (
        <div className="space-y-8 relative">
            {/* Header Area */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h3 className="text-3xl font-bold text-white">Betting Simulator</h3>
                    <p className="text-sm text-gray-400 mt-1">Place virtual bets on upcoming races.</p>
                </div>

                <div className="flex items-center gap-4">
                    {/* Wallet Display */}
                    <button
                        onClick={() => setIsBankModalOpen(true)}
                        className="group flex items-center gap-3 bg-gray-900 border border-purple-500/30 px-4 py-2 rounded-lg hover:bg-gray-800 transition shadow-[0_0_15px_rgba(147,51,234,0.1)]"
                    >
                        <div className="bg-purple-900/30 p-1.5 rounded-full group-hover:bg-purple-600/40 transition">
                            <Wallet className="w-5 h-5 text-purple-300" />
                        </div>
                        <div className="text-left">
                            <span className="block text-[10px] text-gray-400 uppercase tracking-widest font-bold">Wallet</span>
                            <span className="block text-xl font-mono font-bold text-green-400">${fmtMoney(bankroll)}</span>
                        </div>
                        <Plus className="w-4 h-4 text-gray-500 group-hover:text-white ml-2" />
                    </button>

                    <button
                        onClick={handleResolveBets}
                        disabled={loading}
                        className="bg-black border border-purple-900/50 hover:bg-purple-900/20 hover:border-purple-500/50 text-purple-300 hover:text-white px-4 py-3 rounded-lg transition duration-200 flex items-center gap-2 disabled:opacity-50 shadow-[0_0_10px_rgba(147,51,234,0.1)]"
                    >
                        {loading ? <RefreshCw className="w-5 h-5 animate-spin" /> : <RefreshCw className="w-5 h-5" />}
                        <span className="hidden md:inline">Check Results</span>
                    </button>
                </div>
            </div>

            {/* Bank Modal */}
            {isBankModalOpen && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
                    <div className="bg-gray-900 border border-purple-500/50 rounded-xl p-6 w-full max-w-sm shadow-2xl animate-in fade-in zoom-in duration-200">
                        <div className="flex justify-between items-center mb-6">
                            <h4 className="text-xl font-bold text-white">Add Funds</h4>
                            <button onClick={() => setIsBankModalOpen(false)} className="text-gray-400 hover:text-white">✕</button>
                        </div>
                        <form onSubmit={handleAddFunds} className="space-y-4">
                            <div>
                                <label className="block text-sm text-gray-400 mb-2">Amount to Add ($)</label>
                                <div className="relative">
                                    <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500">$</span>
                                    <input
                                        type="number"
                                        value={addFundsAmount}
                                        onChange={(e) => setAddFundsAmount(e.target.value)}
                                        className="w-full bg-black border border-purple-900/50 text-white pl-8 pr-4 py-3 rounded-lg focus:border-purple-500 outline-none text-lg font-bold"
                                        placeholder="0.00"
                                        autoFocus
                                        min="1"
                                    />
                                </div>
                            </div>
                            <div className="grid grid-cols-3 gap-2">
                                {[100, 500, 1000].map(val => (
                                    <button
                                        key={val}
                                        type="button"
                                        onClick={() => setAddFundsAmount(val)}
                                        className="bg-gray-800 hover:bg-gray-700 text-gray-300 py-2 rounded text-sm font-medium transition"
                                    >
                                        +${val}
                                    </button>
                                ))}
                            </div>
                            <button type="submit" className="w-full bg-green-600 hover:bg-green-500 text-white font-bold py-3 rounded-lg transition shadow-[0_0_15px_rgba(34,197,94,0.3)]">
                                Add Funds
                            </button>
                        </form>
                    </div>
                </div>
            )}

            {/* Performance Stats Grid - Compact on mobile */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 md:gap-4">
                {/* Win Rate */}
                <div className="bg-black rounded-xl p-3 md:p-5 border border-purple-900/30 flex items-center gap-2 md:gap-4 relative overflow-hidden group">
                    <div className="hidden md:block absolute right-0 top-0 p-3 opacity-10 group-hover:opacity-20 transition">
                        <TrendingUp className="w-16 h-16 text-purple-500" />
                    </div>
                    <div className="bg-purple-900/20 p-2 md:p-3 rounded-lg">
                        <Percent className="w-4 h-4 md:w-6 md:h-6 text-purple-400" />
                    </div>
                    <div>
                        <p className="text-[10px] md:text-xs text-gray-500 uppercase tracking-wider font-bold">Win Rate</p>
                        <p className="text-lg md:text-2xl font-bold text-white">{stats.winRate}%</p>
                    </div>
                </div>

                {/* Net P&L */}
                <div className="bg-black rounded-xl p-3 md:p-5 border border-purple-900/30 flex items-center gap-2 md:gap-4 relative overflow-hidden group">
                    <div className="hidden md:block absolute right-0 top-0 p-3 opacity-10 group-hover:opacity-20 transition">
                        <DollarSign className="w-16 h-16 text-green-500" />
                    </div>
                    <div className={`p-2 md:p-3 rounded-lg ${stats.pnl >= 0 ? 'bg-green-900/20' : 'bg-red-900/20'}`}>
                        <DollarSign className={`w-4 h-4 md:w-6 md:h-6 ${stats.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`} />
                    </div>
                    <div>
                        <p className="text-[10px] md:text-xs text-gray-500 uppercase tracking-wider font-bold">Net P&L</p>
                        <p className={`text-lg md:text-2xl font-bold ${stats.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {stats.pnl >= 0 ? '+' : ''}${fmtMoney(stats.pnl)}
                        </p>
                    </div>
                </div>

                {/* Total Wagered */}
                <div className="bg-black rounded-xl p-3 md:p-5 border border-purple-900/30 flex items-center gap-2 md:gap-4">
                    <div className="bg-blue-900/20 p-2 md:p-3 rounded-lg">
                        <Wallet className="w-4 h-4 md:w-6 md:h-6 text-blue-400" />
                    </div>
                    <div>
                        <p className="text-[10px] md:text-xs text-gray-500 uppercase tracking-wider font-bold">Wagered</p>
                        <p className="text-lg md:text-2xl font-bold text-white">${fmtMoney(stats.totalWagered)}</p>
                    </div>
                </div>

                {/* ROI / Reset */}
                <div className="bg-black rounded-xl p-3 md:p-5 border border-purple-900/30 flex justify-between items-center pr-2 md:pr-8">
                    <div className="flex items-center gap-2 md:gap-4">
                        <div className={`p-2 md:p-3 rounded-lg ${parseFloat(stats.roi) >= 0 ? 'bg-indigo-900/20' : 'bg-red-900/20'}`}>
                            <TrendingUp className={`w-4 h-4 md:w-6 md:h-6 ${parseFloat(stats.roi) >= 0 ? 'text-indigo-400' : 'text-red-400'}`} />
                        </div>
                        <div>
                            <p className="text-[10px] md:text-xs text-gray-500 uppercase tracking-wider font-bold">ROI</p>
                            <p className={`text-lg md:text-2xl font-bold ${parseFloat(stats.roi) >= 0 ? 'text-indigo-400' : 'text-red-400'}`}>
                                {stats.roi}%
                            </p>
                        </div>
                    </div>

                    {/* Reset Button */}
                    <button
                        onClick={handleResetStats}
                        className="text-gray-600 hover:text-red-500 transition p-1 md:p-2 hover:bg-red-900/20 rounded-full"
                        title="Reset Stats & History"
                    >
                        <Trash2 className="w-4 h-4 md:w-5 md:h-5" />
                    </button>
                </div>
            </div>

            {/* Form to Create Ticket */}
            <form onSubmit={handleCreateTicket} className="bg-black rounded-xl shadow-md p-6 border border-purple-900/50 space-y-6">
                <div className="flex justify-between items-center mb-4 border-b border-gray-800 pb-2">
                    <h4 className="text-xl font-bold text-white">Place New Bet</h4>
                    <button
                        type="button"
                        onClick={() => setIsBetFormOpen(!isBetFormOpen)}
                        className="text-gray-400 hover:text-white transition p-1 hover:bg-gray-800 rounded"
                    >
                        {isBetFormOpen ? <ChevronDown className="w-5 h-5" /> : <ChevronUp className="w-5 h-5" />}
                    </button>
                </div>

                {isBetFormOpen && (
                    <>

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
                                    ${fmtMoney(totalCost)}
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
                            className={`
                                w-full py-4 rounded-lg font-bold text-lg transition-all
                                ${isValid && selectedRaceId
                                    ? 'bg-purple-900/40 text-purple-100 border border-purple-500/30 hover:bg-purple-800/50 hover:border-purple-500/50 shadow-[0_0_15px_rgba(147,51,234,0.1)]'
                                    : 'bg-gray-900 text-gray-600 border border-gray-800 cursor-not-allowed opacity-50'}
                            `}
                        >
                            Place Bet
                        </button>
                    </>
                )}
            </form>

            {/* Bank Modal */}
            {isBankModalOpen && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
                    <div className="bg-gray-900 border border-purple-500/50 rounded-xl p-6 w-full max-w-sm shadow-2xl animate-in fade-in zoom-in duration-200">
                        <div className="flex justify-between items-center mb-6">
                            <h4 className="text-xl font-bold text-white">Add Funds</h4>
                            <button onClick={() => setIsBankModalOpen(false)} className="text-gray-400 hover:text-white">✕</button>
                        </div>
                        <form onSubmit={handleAddFunds} className="space-y-4">
                            <div>
                                <label className="block text-sm text-gray-400 mb-2">Amount to Add ($)</label>
                                <div className="relative">
                                    <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500">$</span>
                                    <input
                                        type="number"
                                        value={addFundsAmount}
                                        onChange={(e) => setAddFundsAmount(e.target.value)}
                                        className="w-full bg-black border border-purple-900/50 text-white pl-8 pr-4 py-3 rounded-lg focus:border-purple-500 outline-none text-lg font-bold"
                                        placeholder="0.00"
                                        autoFocus
                                        min="1"
                                    />
                                </div>
                            </div>
                            <div className="grid grid-cols-3 gap-2">
                                {[100, 500, 1000].map(val => (
                                    <button
                                        key={val}
                                        type="button"
                                        onClick={() => setAddFundsAmount(val)}
                                        className="bg-gray-800 hover:bg-gray-700 text-gray-300 py-2 rounded text-sm font-medium transition"
                                    >
                                        +${val}
                                    </button>
                                ))}
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <button type="submit" onClick={handleAddFunds} className="w-full bg-green-600 hover:bg-green-500 text-white font-bold py-3 rounded-lg transition shadow-[0_0_15px_rgba(34,197,94,0.3)]">
                                    Add Funds
                                </button>
                                <button type="button" onClick={handleBurnFunds} className="w-full bg-red-600 hover:bg-red-500 text-white font-bold py-3 rounded-lg transition shadow-[0_0_15px_rgba(220,38,38,0.3)]">
                                    Burn Funds
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}


            {/* Tickets Table */}
            <div className="bg-black rounded-xl shadow-md overflow-hidden border border-purple-900/50">
                {/* Desktop Table View */}
                <div className="hidden md:block overflow-x-auto">
                    <table className="w-full text-left text-gray-300">
                        <thead className="bg-purple-900/30 border-b border-purple-900/50">
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
                        <tbody className="divide-y divide-purple-900/20">
                            {tickets.length === 0 ? (
                                <tr>
                                    <td colSpan="8" className="p-8 text-center text-gray-500 italic">No tickets found.</td>
                                </tr>
                            ) : (
                                tickets.map((ticket, index) => (
                                    <tr key={ticket.id || index} className="hover:bg-purple-900/10 transition duration-200 group">
                                        <td className="p-4 text-gray-300 font-medium whitespace-nowrap">{new Date(ticket.created_at).toLocaleDateString()}</td>
                                        <td className="p-4">
                                            {ticket.hranalyzer_races ? (
                                                <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-md bg-purple-900/20 text-purple-300 text-xs font-bold border border-purple-500/30 font-mono">
                                                    {ticket.hranalyzer_races.track_code} R{ticket.hranalyzer_races.race_number}
                                                </span>
                                            ) : <span className="text-gray-500">Unknown</span>}
                                        </td>
                                        <td className="p-4">
                                            {ticket.selection ? (
                                                <div className="flex flex-wrap gap-1">
                                                    {ticket.selection.map((num, idx) => {
                                                        const pgm = Array.isArray(num) ? num[0] : num; // Simplify array handling if needed, or map properly
                                                        // Actually, ticket.selection for Box/Key might be [ [1,2], [3], [4] ] or similar?
                                                        // Let's look at how it was rendered before: 
                                                        // #{Array.isArray(num) ? num.join(',') : num}

                                                        // For now, let's just style individual numbers if they are simple, or keep the grey box for complex
                                                        // BUT the user mostly cares about WIN bets which are single numbers.

                                                        const displayVal = Array.isArray(num) ? num.join(',') : num;
                                                        const style = !Array.isArray(num) ? getPostColor(num) : { bg: '#1f2937', text: '#fff' };

                                                        return (
                                                            <span key={`${idx}-${displayVal}`}
                                                                className="text-xs px-1.5 py-0.5 rounded border border-gray-700 font-bold"
                                                                style={{ backgroundColor: style.bg, color: style.text }}
                                                            >
                                                                #{displayVal}
                                                            </span>
                                                        );
                                                    })}
                                                </div>
                                            ) : (
                                                <div className="flex items-center gap-2">
                                                    {(() => {
                                                        const style = getPostColor(ticket.horse_number);
                                                        return (
                                                            <div
                                                                className="w-6 h-6 rounded flex items-center justify-center text-xs font-bold"
                                                                style={{ backgroundColor: style.bg, color: style.text }}
                                                            >
                                                                {ticket.horse_number}
                                                            </div>
                                                        );
                                                    })()}
                                                    <span className="text-purple-300 font-mono text-sm">{ticket.horse_name}</span>
                                                </div>
                                            )}
                                        </td>
                                        <td className="p-4 text-sm text-gray-300">{ticket.bet_type}</td>
                                        <td className="p-4 text-sm text-gray-300">${fmtMoney(ticket.bet_cost || ticket.bet_amount)}</td>
                                        <td className="p-4">
                                            <span className={`px-2 py-1 rounded text-xs font-bold ${ticket.status === 'Win' ? 'bg-green-900 text-green-200' :
                                                ticket.status === 'Loss' ? 'bg-red-900 text-red-200' :
                                                    ticket.status === 'Returned' ? 'bg-orange-900 text-orange-200' :
                                                        'bg-yellow-900 text-yellow-200'
                                                }`}>
                                                {ticket.status}
                                            </span>
                                        </td>
                                        <td className="p-4 text-right text-green-400 font-bold">
                                            {ticket.payout > 0 ? `$${fmtMoney(ticket.payout)}` : '-'}
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

                {/* Mobile Card View */}
                <div className="md:hidden divide-y divide-purple-900/20">
                    {tickets.length === 0 ? (
                        <div className="p-8 text-center text-gray-400">No tickets found.</div>
                    ) : (
                        tickets.map((ticket, index) => (
                            <div key={ticket.id || index} className="p-4 space-y-3 hover:bg-purple-900/10 transition">
                                <div className="flex justify-between items-start">
                                    <div>
                                        <div className="text-white font-bold text-lg">
                                            {ticket.hranalyzer_races ? (
                                                `${ticket.hranalyzer_races.track_code} R${ticket.hranalyzer_races.race_number}`
                                            ) : 'Unknown'}
                                        </div>
                                        <div className="text-xs text-gray-500">
                                            {new Date(ticket.created_at).toLocaleDateString()} • {ticket.bet_type}
                                        </div>
                                    </div>
                                    <div className="flex flex-col items-end gap-2">
                                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${ticket.status === 'Win' ? 'bg-green-900 text-green-200' :
                                            ticket.status === 'Loss' ? 'bg-red-900 text-red-200' :
                                                'bg-yellow-900 text-yellow-200'
                                            }`}>
                                            {ticket.status}
                                        </span>
                                        <button
                                            onClick={() => handleDeleteBet(ticket.id)}
                                            className="bg-red-900/20 hover:bg-red-900/50 text-red-400 p-2 rounded transition"
                                            title="Delete Bet"
                                        >
                                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                            </svg>
                                        </button>
                                    </div>
                                </div>

                                <div className="bg-purple-900/10 p-3 rounded-lg border border-purple-900/20">
                                    <div className="text-xs text-gray-500 uppercase mb-1">Selection</div>
                                    {ticket.selection ? (
                                        <div className="flex flex-wrap gap-1">
                                            {ticket.selection.map((num, idx) => {
                                                const displayVal = Array.isArray(num) ? num.join(',') : num;
                                                const style = !Array.isArray(num) ? getPostColor(num) : { bg: '#1f2937', text: '#fff' };
                                                return (
                                                    <span key={`${idx}-${displayVal}`}
                                                        className="text-xs px-1.5 py-0.5 rounded border border-gray-700 font-bold"
                                                        style={{ backgroundColor: style.bg, color: style.text }}
                                                    >
                                                        #{displayVal}
                                                    </span>
                                                );
                                            })}
                                        </div>
                                    ) : (
                                        <div className="flex items-center gap-2">
                                            {(() => {
                                                const style = getPostColor(ticket.horse_number);
                                                return (
                                                    <div
                                                        className="w-6 h-6 rounded flex items-center justify-center text-xs font-bold"
                                                        style={{ backgroundColor: style.bg, color: style.text }}
                                                    >
                                                        {ticket.horse_number}
                                                    </div>
                                                );
                                            })()}
                                            <span className="text-purple-300 font-mono text-sm">{ticket.horse_name}</span>
                                        </div>
                                    )}
                                </div>

                                <div className="flex justify-between items-center bg-black/40 p-2 rounded-md">
                                    <div>
                                        <span className="text-[10px] text-gray-500 uppercase block">Cost</span>
                                        <span className="text-white font-medium">${fmtMoney(ticket.bet_cost || ticket.bet_amount)}</span>
                                    </div>
                                    <div className="text-right">
                                        <span className="text-[10px] text-gray-500 uppercase block">Payout</span>
                                        <span className={`font-bold ${ticket.payout > 0 ? 'text-green-400' : 'text-gray-600'}`}>
                                            {ticket.payout > 0 ? `$${fmtMoney(ticket.payout)}` : '-'}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div >
    );
}
