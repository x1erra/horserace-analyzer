import { Link } from 'react-router-dom';
import { useState, useEffect } from 'react';

export default function Horses() {
    const [searchQuery, setSearchQuery] = useState('');
    const [filteredHorses, setFilteredHorses] = useState([]);

    // Sample horse data (replace with real API data later)
    const allHorses = [
        { id: 1, name: 'Thunder Bolt', age: 5, trainer: 'J. Smith', speed: 95, form: '1-2-3' },
        { id: 2, name: 'Speed Demon', age: 4, trainer: 'A. Johnson', speed: 92, form: '2-1-4' },
        { id: 3, name: 'Lightning Strike', age: 6, trainer: 'M. Brown', speed: 98, form: '3-3-1' },
        { id: 4, name: 'Shadow Runner', age: 5, trainer: 'S. Lee', speed: 90, form: '4-2-2' },
        { id: 5, name: 'Golden Hoof', age: 4, trainer: 'K. Davis', speed: 96, form: '1-4-3' },
        { id: 6, name: 'Storm Chaser', age: 7, trainer: 'R. Wilson', speed: 93, form: '2-3-1' },
    ];

    // Filter logic
    useEffect(() => {
        const filtered = allHorses.filter(horse =>
            horse.name.toLowerCase().includes(searchQuery.toLowerCase())
        );
        setFilteredHorses(filtered);
    }, [searchQuery]);

    return (
        <div className="space-y-8">
            <h3 className="text-3xl font-bold text-white">Horse Profiles</h3>
            <p className="text-sm text-gray-400 mb-4">Search and view detailed stats for horses.</p>

            {/* Search bar - functional */}
            <input
                type="text"
                placeholder="Search horses..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition"
            />

            {/* Grid of horse cards - filtered dynamically with fade-in animation */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredHorses.length === 0 ? (
                    <p className="text-gray-400 col-span-full text-center">No horses match your search.</p>
                ) : (
                    filteredHorses.map((horse, index) => (
                        <div
                            key={horse.id}
                            className="bg-black rounded-xl shadow-md p-6 hover:shadow-xl transition border border-purple-900/50 opacity-0 animate-fadeIn"
                            style={{ animationDelay: `${index * 50}ms` }}
                        >
                            <h4 className="text-xl font-bold text-white mb-2">{horse.name}</h4>
                            <p className="text-sm text-gray-400 mb-4">Age: {horse.age} • Trainer: {horse.trainer}</p>
                            <div className="text-3xl font-bold text-purple-400 mb-4">Speed Rating: {horse.speed}</div>
                            <p className="text-lg text-purple-300 mb-6">Recent Form: {horse.form}</p>
                            <Link
                                to={`/horse/${horse.id}`} // Placeholder link; create HorseDetails page later if needed
                                className="w-full block bg-purple-600 hover:bg-purple-700 text-white py-2 rounded-md transition text-center"
                            >
                                View Profile
                            </Link>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}