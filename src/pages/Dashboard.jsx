import { Link } from 'react-router-dom'; // New import for links

export default function Dashboard() {
    return (
        <div className="space-y-8">
            <h3 className="text-3xl font-bold text-white">
                Today's Races
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {[1, 2, 3, 4, 5, 6].map((i) => (
                    <div
                        key={i}
                        className="bg-black rounded-xl shadow-md p-6 hover:shadow-xl transition border border-purple-900/50"
                    >
                        <h4 className="text-xl font-bold text-white mb-2">
                            Race {i} - Gulfstream Park
                        </h4>
                        <p className="text-sm text-gray-400 mb-4">Jan 4, 2026 • 3:45 PM</p>
                        <div className="text-3xl font-bold text-purple-400 mb-4">
                            # {i + 2} Thunder Bolt
                        </div>
                        <p className="text-lg text-purple-300 mb-6">
                            {30 + i * 2}% Win Prob
                        </p>
                        <Link
                            to={`/race/${i}`} // Dynamic link to /race/1, /race/2, etc.
                            className="w-full block bg-purple-600 hover:bg-purple-700 text-white py-2 rounded-md transition text-center"
                        >
                            Analyze
                        </Link>
                    </div>
                ))}
            </div>
        </div>
    );
}