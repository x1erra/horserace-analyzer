import { useState, useEffect } from 'react';
import { GiHorseHead } from 'react-icons/gi';
import { HiOutlineUser, HiOutlineFlag } from 'react-icons/hi';

export default function Favourites() {
    const [favourites, setFavourites] = useState([]);
    const [formData, setFormData] = useState({ name: '', type: 'Horse' });
    const [searchQuery, setSearchQuery] = useState('');
    const [filteredFavourites, setFilteredFavourites] = useState([]);

    // Load from localStorage on mount
    useEffect(() => {
        const savedFavourites = JSON.parse(localStorage.getItem('favourites')) || [];
        setFavourites(savedFavourites);
        setFilteredFavourites(savedFavourites);
    }, []);

    // Save to localStorage
    const saveFavourites = (updatedFavourites) => {
        localStorage.setItem('favourites', JSON.stringify(updatedFavourites));
        setFavourites(updatedFavourites);
        setFilteredFavourites(updatedFavourites.filter(fav =>
            fav.name.toLowerCase().includes(searchQuery.toLowerCase())
        ));
    };

    // Add favourite
    const handleAddFavourite = (e) => {
        e.preventDefault();
        if (!formData.name) return; // Basic validation
        const newFavourite = { ...formData, stats: { races: 10, wins: 3, winRate: 30 } }; // Placeholder stats; replace with real data later
        const updatedFavourites = [...favourites, newFavourite];
        saveFavourites(updatedFavourites);
        setFormData({ name: '', type: 'Horse' });
    };

    // Delete favourite
    const handleDeleteFavourite = (index) => {
        if (!window.confirm('Are you sure you want to remove this favourite?')) return;
        const updatedFavourites = favourites.filter((_, i) => i !== index);
        saveFavourites(updatedFavourites);
    };

    // Search filter
    const handleSearch = (e) => {
        const query = e.target.value.toLowerCase();
        setSearchQuery(query);
        setFilteredFavourites(favourites.filter(fav => fav.name.toLowerCase().includes(query)));
    };

    return (
        <div className="space-y-8">
            <h3 className="text-3xl font-bold text-white">Favourites</h3>
            <p className="text-sm text-gray-400 mb-4">Add and track your favorite trainers, jockeys, or horses with stats.</p>

            {/* Form to Add Favourite */}
            <form onSubmit={handleAddFavourite} className="bg-black rounded-xl shadow-md p-6 border border-purple-900/50 space-y-4">
                <h4 className="text-xl font-bold text-white mb-4">Add New Favourite</h4>
                <input
                    type="text"
                    placeholder="Name (e.g., Thunder Bolt or J. Smith)"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition duration-200"
                    required
                />
                <select
                    value={formData.type}
                    onChange={(e) => setFormData({ ...formData, type: e.target.value })}
                    className="w-full bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition duration-200"
                >
                    <option>Horse</option>
                    <option>Jockey</option>
                    <option>Trainer</option>
                </select>
                <button type="submit" className="w-full bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 text-white py-3 rounded-md transition duration-200 font-medium">
                    Add Favourite
                </button>
            </form>

            {/* Search Bar */}
            <input
                type="text"
                placeholder="Search favourites..."
                value={searchQuery}
                onChange={handleSearch}
                className="w-full bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition duration-200"
            />

            {/* Grid of Favourite Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredFavourites.length === 0 ? (
                    <p className="text-gray-400 col-span-full text-center">No favourites added yet.</p>
                ) : (
                    filteredFavourites.map((fav, index) => (
                        <div
                            key={index}
                            className="bg-black rounded-xl shadow-md p-6 hover:shadow-xl transition duration-300 border border-purple-900/50 opacity-0 animate-fadeIn"
                            style={{ animationDelay: `${index * 50}ms` }}
                        >
                            <h4 className="text-xl font-bold text-white mb-2 flex items-center gap-2">
                                {fav.type === 'Horse' ? <GiHorseHead className="w-6 h-6 text-purple-400" /> : fav.type === 'Jockey' ? <HiOutlineUser className="w-6 h-6 text-purple-400" /> : <HiOutlineFlag className="w-6 h-6 text-purple-400" />}
                                {fav.name} ({fav.type})
                            </h4>
                            <p className="text-sm text-gray-400 mb-4">Upcoming Races: {fav.stats.races}</p>
                            <div className="text-3xl font-bold text-purple-400 mb-4">
                                Win Rate: {fav.stats.winRate}%
                            </div>
                            <p className="text-lg text-purple-300 mb-6">
                                Wins: {fav.stats.wins} (Past Stats)
                            </p>
                            <button
                                onClick={() => handleDeleteFavourite(index)}
                                className="w-full bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 text-white py-2 rounded-md transition duration-200 text-center font-medium"
                            >
                                Remove
                            </button>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}