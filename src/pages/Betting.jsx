import { useState, useEffect } from 'react';

export default function Betting() {
    const [tickets, setTickets] = useState([]);
    const [winRate, setWinRate] = useState(0);
    const [formData, setFormData] = useState({ raceId: '', horse: '', betType: 'Win' });

    // Load from localStorage on mount
    useEffect(() => {
        const savedTickets = JSON.parse(localStorage.getItem('bettingTickets')) || [];
        setTickets(savedTickets);
        updateWinRate(savedTickets);
    }, []);

    // Update win rate
    const updateWinRate = (updatedTickets) => {
        const resolved = updatedTickets.filter(ticket => ticket.status !== 'Pending');
        const wins = resolved.filter(ticket => ticket.status === 'Win').length;
        const rate = resolved.length > 0 ? Math.round((wins / resolved.length) * 100) : 0;
        setWinRate(rate);
    };

    // Save to localStorage
    const saveTickets = (updatedTickets) => {
        localStorage.setItem('bettingTickets', JSON.stringify(updatedTickets));
        setTickets(updatedTickets);
        updateWinRate(updatedTickets);
    };

    // Create ticket
    const handleCreateTicket = (e) => {
        e.preventDefault();
        if (!formData.raceId || !formData.horse) return; // Basic validation
        const newTicket = { ...formData, status: 'Pending' };
        const updatedTickets = [...tickets, newTicket];
        saveTickets(updatedTickets);
        setFormData({ raceId: '', horse: '', betType: 'Win' });
    };

    // Mark win/loss
    const handleMarkStatus = (index, status) => {
        const updatedTickets = [...tickets];
        updatedTickets[index].status = status;
        saveTickets(updatedTickets);
    };

    // Delete ticket
    const handleDeleteTicket = (index) => {
        if (!window.confirm('Are you sure you want to delete this ticket? This will update your win rate if resolved.')) return;
        const updatedTickets = tickets.filter((_, i) => i !== index);
        saveTickets(updatedTickets);
    };

    return (
        <div className="space-y-8">
            <h3 className="text-3xl font-bold text-white">Betting Simulator</h3>
            <p className="text-sm text-gray-400 mb-4">Create virtual bet tickets and track your win rate over time.</p>

            {/* Win Rate Stat */}
            <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/50">
                <h4 className="text-xl font-bold text-white mb-2">Your Win Rate</h4>
                <p className="text-4xl font-bold text-purple-400">{winRate}%</p>
            </div>

            {/* Form to Create Ticket */}
            <form onSubmit={handleCreateTicket} className="bg-black rounded-xl shadow-md p-6 border border-purple-900/50 space-y-4">
                <h4 className="text-xl font-bold text-white mb-4">Create New Ticket</h4>
                <input
                    type="text"
                    placeholder="Race ID (e.g., 1)"
                    value={formData.raceId}
                    onChange={(e) => setFormData({ ...formData, raceId: e.target.value })}
                    className="w-full bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition duration-200"
                    required
                />
                <input
                    type="text"
                    placeholder="Horse Name or Number"
                    value={formData.horse}
                    onChange={(e) => setFormData({ ...formData, horse: e.target.value })}
                    className="w-full bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition duration-200"
                    required
                />
                <select
                    value={formData.betType}
                    onChange={(e) => setFormData({ ...formData, betType: e.target.value })}
                    className="w-full bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition duration-200"
                >
                    <option>Win</option>
                    <option>Place</option>
                    <option>Show</option>
                    <option>Exacta</option>
                    <option>Trifecta</option>
                </select>
                <button type="submit" className="w-full bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 text-white py-3 rounded-md transition duration-200 font-medium">
                    Create Ticket
                </button>
            </form>

            {/* Tickets Table */}
            <div className="bg-black rounded-xl shadow-md overflow-hidden border border-purple-900/50">
                <table className="w-full text-left text-gray-300">
                    <thead className="bg-purple-900/50">
                        <tr>
                            <th className="p-4">Race ID</th>
                            <th className="p-4">Horse</th>
                            <th className="p-4">Bet Type</th>
                            <th className="p-4">Status</th>
                            <th className="p-4">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {tickets.length === 0 ? (
                            <tr>
                                <td colSpan="5" className="p-4 text-center text-gray-400">No tickets created yet.</td>
                            </tr>
                        ) : (
                            tickets.map((ticket, index) => (
                                <tr key={index} className="border-t border-purple-900/50 hover:bg-purple-900/20 transition duration-200">
                                    <td className="p-4">{ticket.raceId}</td>
                                    <td className="p-4">{ticket.horse}</td>
                                    <td className="p-4">{ticket.betType}</td>
                                    <td className="p-4">{ticket.status}</td>
                                    <td className="p-4 flex gap-2">
                                        {ticket.status === 'Pending' && (
                                            <>
                                                <button
                                                    onClick={() => handleMarkStatus(index, 'Win')}
                                                    className="bg-gradient-to-r from-green-600 to-green-700 hover:from-green-700 hover:to-green-800 text-white px-3 py-1 rounded-md transition duration-200 text-sm font-medium"
                                                >
                                                    Mark Win
                                                </button>
                                                <button
                                                    onClick={() => handleMarkStatus(index, 'Loss')}
                                                    className="bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 text-white px-3 py-1 rounded-md transition duration-200 text-sm font-medium"
                                                >
                                                    Mark Loss
                                                </button>
                                            </>
                                        )}
                                        <button
                                            onClick={() => handleDeleteTicket(index)}
                                            className="bg-gradient-to-r from-gray-600 to-gray-700 hover:from-gray-700 hover:to-gray-800 text-white px-3 py-1 rounded-md transition duration-200 text-sm font-medium"
                                        >
                                            Delete
                                        </button>
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