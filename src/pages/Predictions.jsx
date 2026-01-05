import { useState } from 'react';

export default function Predictions() {
    const [sortCriteria, setSortCriteria] = useState([{ column: 'winProb', direction: 'desc' }]); // Default multi-sort array

    // Sample prediction data (replace with real API data later)
    const allPredictions = [
        { raceId: 1, horse: 'Thunder Bolt', winProb: 35, value: '+EV', confidence: 'High' },
        { raceId: 2, horse: 'Speed Demon', winProb: 25, value: 'Neutral', confidence: 'Medium' },
        { raceId: 3, horse: 'Lightning Strike', winProb: 40, value: '+EV', confidence: 'High' },
        { raceId: 4, horse: 'Shadow Runner', winProb: 20, value: '-EV', confidence: 'Low' },
        { raceId: 5, horse: 'Golden Hoof', winProb: 30, value: 'Neutral', confidence: 'Medium' },
        { raceId: 6, horse: 'Storm Chaser', winProb: 45, value: '+EV', confidence: 'High' },
        { raceId: 7, horse: 'Wind Rider', winProb: 35, value: '+EV', confidence: 'Medium' }, // Added for tie-testing
        { raceId: 8, horse: 'Fire Blaze', winProb: 25, value: 'Neutral', confidence: 'High' }, // Added for tie-testing
    ];

    // Multi-column sorting function (fixed logic for correct desc ordering)
    const sortedPredictions = [...allPredictions].sort((a, b) => {
        for (let crit of sortCriteria) {
            let valA = a[crit.column];
            let valB = b[crit.column];

            // Handle string sorting
            if (typeof valA === 'string') {
                valA = valA.toLowerCase();
                valB = valB.toLowerCase();
            }

            if (valA < valB) return crit.direction === 'asc' ? -1 : 1;
            if (valA > valB) return crit.direction === 'asc' ? 1 : 1;
        }
        return 0; // Equal if all criteria tie
    });

    // Handle column sort click (supports Shift for multi-sort)
    const handleSort = (column, e) => {
        const newDirection = 'desc'; // Default to desc on new column

        if (e.shiftKey) {
            // Add as secondary sort if Shift held
            const existingCrit = sortCriteria.find(crit => crit.column === column);
            const newCrit = { column, direction: existingCrit ? (existingCrit.direction === 'asc' ? 'desc' : 'asc') : newDirection };
            const updatedCriteria = sortCriteria.filter(crit => crit.column !== column); // Remove old if exists
            setSortCriteria([...updatedCriteria, newCrit]); // Add as last (lowest priority)
        } else {
            // Replace as primary sort
            setSortCriteria([{ column, direction: sortCriteria[0]?.column === column && sortCriteria[0].direction === 'desc' ? 'asc' : 'desc' }]);
        }
    };

    // Get arrow for a column
    const getArrow = (column) => {
        const crit = sortCriteria.find(c => c.column === column);
        if (!crit) return null;
        return crit.direction === 'asc' ? '▲' : '▼';
    };

    return (
        <div className="space-y-8">
            <h3 className="text-3xl font-bold text-white">Model Predictions</h3>
            <p className="text-sm text-gray-400 mb-4">High-confidence value bets and analysis. Hold Shift + click headers for multi-column sort.</p>

            {/* Predictions table - now multi-sortable */}
            <div className="bg-black rounded-xl shadow-md overflow-x-auto border border-purple-900/50">
                <table className="w-full text-left text-gray-300 min-w-max">
                    <thead className="bg-purple-900/50">
                        <tr>
                            <th className="p-4 cursor-pointer hover:bg-purple-900/70 transition duration-200" onClick={(e) => handleSort('raceId', e)}>
                                Race ID {getArrow('raceId')}
                            </th>
                            <th className="p-4 cursor-pointer hover:bg-purple-900/70 transition duration-200" onClick={(e) => handleSort('horse', e)}>
                                Horse {getArrow('horse')}
                            </th>
                            <th className="p-4 cursor-pointer hover:bg-purple-900/70 transition duration-200" onClick={(e) => handleSort('winProb', e)}>
                                Win Prob {getArrow('winProb')}
                            </th>
                            <th className="p-4 cursor-pointer hover:bg-purple-900/70 transition duration-200" onClick={(e) => handleSort('value', e)}>
                                Value {getArrow('value')}
                            </th>
                            <th className="p-4 cursor-pointer hover:bg-purple-900/70 transition duration-200" onClick={(e) => handleSort('confidence', e)}>
                                Confidence {getArrow('confidence')}
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {sortedPredictions.length === 0 ? (
                            <tr>
                                <td colSpan="5" className="p-4 text-center text-gray-400">No predictions available.</td>
                            </tr>
                        ) : (
                            sortedPredictions.map((pred, index) => (
                                <tr key={index} className="border-t border-purple-900/50 hover:bg-purple-900/20 transition duration-200">
                                    <td className="p-4">{pred.raceId}</td>
                                    <td className="p-4">{pred.horse}</td>
                                    <td className="p-4 text-purple-400">{pred.winProb}%</td>
                                    <td className="p-4 text-green-400">{pred.value}</td>
                                    <td className="p-4">{pred.confidence}</td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
            <button className="bg-purple-600 hover:bg-purple-700 text-white px-6 py-3 rounded-md transition duration-200">
                Run New Predictions
            </button>
        </div>
    );
}