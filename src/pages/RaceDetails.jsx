import { useParams } from 'react-router-dom';

export default function RaceDetails() {
    const { id } = useParams();

    return (
        <div className="space-y-8">
            <h3 className="text-3xl font-bold text-white opacity-0 animate-fadeIn" style={{ animationDelay: '0ms' }}>
                Race {id} Details - Gulfstream Park
            </h3>
            <p className="text-sm text-gray-400 mb-4 opacity-0 animate-fadeIn" style={{ animationDelay: '50ms' }}>Jan 4, 2026 • 3:45 PM</p>

            {/* Horse list/table */}
            <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/20 opacity-0 animate-fadeIn" style={{ animationDelay: '100ms' }}>
                <h4 className="text-xl font-semibold text-white mb-4">Horse List</h4>
                <ul className="space-y-4">
                    <li className="flex justify-between text-gray-300">
                        <span>#1 Speed Demon</span>
                        <span className="text-purple-400">25% Win Prob</span>
                    </li>
                    <li className="flex justify-between text-gray-300">
                        <span>#2 Thunder Bolt</span>
                        <span className="text-purple-400">35% Win Prob</span>
                    </li>
                    {/* Add more dynamically later */}
                </ul>
            </div>

            {/* Predictions & Analysis */}
            <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/20 opacity-0 animate-fadeIn" style={{ animationDelay: '150ms' }}>
                <h4 className="text-xl font-semibold text-white mb-4">Predictions & Analysis</h4>
                <p className="text-gray-300">Detailed model output, speed figures, pace analysis here.</p>
                {/* Add pie chart here if desired */}
            </div>

            <button className="bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 text-white px-6 py-3 rounded-md transition duration-200 font-medium opacity-0 animate-fadeIn" style={{ animationDelay: '200ms' }}>
                Run Model Again
            </button>
        </div>
    );
}