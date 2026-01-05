import { Link } from 'react-router-dom';
import { useState, useEffect } from 'react';

export default function Races() {
    const [selectedTrack, setSelectedTrack] = useState('All Tracks');
    const [selectedDate, setSelectedDate] = useState('Today');
    const [filteredRaces, setFilteredRaces] = useState([]);

    // Sample race data (replace with real API data later)
    const allRaces = [
        { id: 1, name: 'Race 1 - Gulfstream Park', date: 'Jan 4, 2026', time: '3:45 PM', track: 'Gulfstream Park', topPick: 'Thunder Bolt', winProb: 35 },
        { id: 2, name: 'Race 2 - Aqueduct', date: 'Jan 4, 2026', time: '4:15 PM', track: 'Aqueduct', topPick: 'Speed Demon', winProb: 25 },
        { id: 3, name: 'Race 3 - Santa Anita', date: 'Jan 4, 2026', time: '5:00 PM', track: 'Santa Anita', topPick: 'Lightning Strike', winProb: 40 },
        { id: 4, name: 'Race 4 - Gulfstream Park', date: 'Jan 5, 2026', time: '2:30 PM', track: 'Gulfstream Park', topPick: 'Shadow Runner', winProb: 20 },
        { id: 5, name: 'Race 5 - Aqueduct', date: 'Jan 5, 2026', time: '3:00 PM', track: 'Aqueduct', topPick: 'Golden Hoof', winProb: 30 },
        { id: 6, name: 'Race 6 - Santa Anita', date: 'Jan 5, 2026', time: '4:45 PM', track: 'Santa Anita', topPick: 'Storm Chaser', winProb: 45 },
        { id: 7, name: 'Race 7 - Gulfstream Park', date: 'Jan 6, 2026', time: '1:45 PM', track: 'Gulfstream Park', topPick: 'Wind Rider', winProb: 28 },
        { id: 8, name: 'Race 8 - Aqueduct', date: 'Jan 6, 2026', time: '2:15 PM', track: 'Aqueduct', topPick: 'Fire Blaze', winProb: 38 },
        { id: 9, name: 'Race 9 - Santa Anita', date: 'Jan 6, 2026', time: '3:00 PM', track: 'Santa Anita', topPick: 'Moon Shadow', winProb: 32 },
    ];

    // Filter logic
    useEffect(() => {
        let filtered = allRaces;

        if (selectedTrack !== 'All Tracks') {
            filtered = filtered.filter(race => race.track === selectedTrack);
        }

        if (selectedDate === 'Today') {
            filtered = filtered.filter(race => race.date === 'Jan 4, 2026');
        } else if (selectedDate === 'Tomorrow') {
            filtered = filtered.filter(race => race.date === 'Jan 5, 2026');
        } else if (selectedDate === 'This Week') {
            filtered = filtered.filter(race => race.date <= 'Jan 10, 2026');
        }

        setFilteredRaces(filtered);
    }, [selectedTrack, selectedDate]);

    return (
        <div className="space-y-8">
            <h3 className="text-3xl font-bold text-white">All Races</h3>
            <p className="text-sm text-gray-400 mb-4">Browse and filter upcoming races across tracks.</p>

            {/* Filter bar */}
            <div className="flex flex-col md:flex-row gap-4 mb-8">
                <select
                    value={selectedTrack}
                    onChange={(e) => setSelectedTrack(e.target.value)}
                    className="w-full md:w-auto bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition"
                >
                    <option>All Tracks</option>
                    <option>Gulfstream Park</option>
                    <option>Aqueduct</option>
                    <option>Santa Anita</option>
                </select>
                <select
                    value={selectedDate}
                    onChange={(e) => setSelectedDate(e.target.value)}
                    className="w-full md:w-auto bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition"
                >
                    <option>Today</option>
                    <option>Tomorrow</option>
                    <option>This Week</option>
                </select>
            </div>

            {/* Grid of race cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredRaces.length === 0 ? (
                    <p className="text-gray-400 col-span-full text-center">No races match your filters.</p>
                ) : (
                    filteredRaces.map((race) => (
                        <div
                            key={race.id}
                            className="bg-black rounded-xl shadow-md p-6 hover:shadow-xl transition border border-purple-900/50 opacity-0 animate-fadeIn"
                            style={{ animationDelay: `${race.id * 50}ms` }}
                        >
                            <h4 className="text-xl font-bold text-white mb-2">
                                {race.name}
                            </h4>
                            <p className="text-sm text-gray-400 mb-4">{race.date} • {race.time}</p>
                            <div className="text-3xl font-bold text-purple-400 mb-4">
                                # {race.id + 2} {race.topPick}
                            </div>
                            <p className="text-lg text-purple-300 mb-6">
                                {race.winProb}% Win Prob
                            </p>
                            <Link
                                to={`/race/${race.id}`}
                                className="w-full block bg-purple-600 hover:bg-purple-700 text-white py-2 rounded-md transition text-center"
                            >
                                Analyze
                            </Link>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}