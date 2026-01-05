import { useParams } from 'react-router-dom';

export default function RaceDetails() {
    const { id } = useParams(); // Gets the race ID from URL

    // Sample race conditions data (TEMPORARY: Replace with parsed data from PDF, e.g., via props or state from backend API)
    const raceConditions = [
        { detail: 'Track', value: 'Gulfstream Park' },
        { detail: 'Race Type', value: 'Maiden Optional Claiming' },
        { detail: 'Distance/Surface', value: '1 Mile (Turf)' },
        { detail: 'Purse', value: '$50,000 ($3K FOA, $7K FBIF)' },
        { detail: 'Claiming Price', value: '$50,000' },
        { detail: 'Weight', value: '122 lbs' },
        { detail: 'Eligibility', value: 'Maidens, Fillies 3yo, Florida-bred' },
        { detail: 'Post Time', value: '12:20 ET' },
        { detail: 'Rail Position', value: '73 feet' },
        { detail: 'Beyer Par', value: 'NA' },
    ];

    // Sample horse entries data (TEMPORARY: Replace with parsed data from PDF, e.g., via props or state from backend API)
    const horseEntries = [
        { post: 1, horse: 'Striking Finale', jockey: 'Ruiz J', trainer: 'Trombetta MJ', ml: 18.70, starts: 3, wps: '0-1-0', avgBeyer: 52, keyNotes: '2nd on turf 10/4/25' },
        { post: 2, horse: 'Golden Hope', jockey: 'Castellano JJ', trainer: 'Mott WG', ml: 'TBD', starts: 0, wps: '0-0-0', avgBeyer: '-', keyNotes: '★ $300K yearling, Debut' },
        { post: 3, horse: 'TooLooseLaTrek', jockey: 'TBD', trainer: 'TBD', ml: 'TBD', starts: 0, wps: '0-0-0', avgBeyer: '-', keyNotes: 'Debut' },
        { post: 4, horse: 'Vanish', jockey: 'Hernandez RM', trainer: 'Maker MJ', ml: 2.90, starts: 2, wps: '0-0-0', avgBeyer: 54, keyNotes: '2 starts' },
        { post: 5, horse: 'Blazing Bridgette', jockey: 'Bravo J', trainer: 'David CA', ml: 4.60, starts: 4, wps: '1-0-0', avgBeyer: 51, keyNotes: '✅ ONLY WINNER' },
        { post: 6, horse: 'Angelic Quality', jockey: 'Franco M', trainer: 'Mott WG', ml: 18.28, starts: 1, wps: '0-0-0', avgBeyer: 40, keyNotes: '$130K yearling' },
        { post: 7, horse: 'Colonial Sense', jockey: 'Zayas EJ', trainer: "D'Angelo JF", ml: 7.60, starts: 2, wps: '0-1-0', avgBeyer: 53, keyNotes: 'Distance experience' },
        { post: 8, horse: 'Drupe', jockey: 'TBD', trainer: 'Gambolati C', ml: 'TBD', starts: 0, wps: '0-0-0', avgBeyer: '-', keyNotes: '$190K yearling, Debut' },
        { post: 9, horse: 'Sally J.', jockey: 'TBD', trainer: 'TBD', ml: 'TBD', starts: 1, wps: '0-0-0', avgBeyer: 31, keyNotes: '1 start' },
        { post: 10, horse: 'SisterSlew', jockey: 'TBD', trainer: 'TBD', ml: 'TBD', starts: 0, wps: '0-0-0', avgBeyer: '-', keyNotes: 'Debut' },
        { post: 11, horse: 'EternalMandate*', jockey: 'TBD', trainer: 'Maker MJ', ml: 'TBD', starts: 0, wps: '0-0-0', avgBeyer: '-', keyNotes: 'Foreign-bred (*)' },
        { post: 12, horse: 'GloriousBoy', jockey: 'TBD', trainer: 'TBD', ml: 'TBD', starts: 0, wps: '0-0-0', avgBeyer: '-', keyNotes: 'Debut' },
        { post: 13, horse: 'Affirming*', jockey: 'Marin S', trainer: 'Pletcher TA', ml: 14.00, starts: 3, wps: '0-0-0', avgBeyer: 51, keyNotes: 'Foreign-bred, claimed' },
    ];

    // Sample pace figures data (TEMPORARY: Replace with parsed data from PDF, e.g., via props or state from backend API)
    const paceFigures = [
        { post: 1, horse: 'Striking Finale', early: 54, late: 39 },
        { post: 4, horse: 'Vanish', early: 86, late: 57 },
        { post: 5, horse: 'Blazing Bridgette', early: 58, late: 74 },
        { post: 6, horse: 'AngelicQuality', early: 87, late: 45 },
        { post: 7, horse: 'ColonialSense', early: 62, late: 71 },
        { post: 10, horse: 'SisterSlew', early: 39, late: 72 },
        { post: 11, horse: 'EternalMandate*', early: 83, late: 45 },
        { post: 13, horse: 'Affirming*', early: 60, late: 68 },
    ];

    return (
        <div className="space-y-8">
            <h3 className="text-3xl font-bold text-white">
                Race {id} Details - Gulfstream Park
            </h3>
            <p className="text-sm text-gray-400 mb-4">Jan 4, 2026 • 3:45 PM</p>

            {/* Race Conditions Table */}
            <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/20 overflow-hidden opacity-0 animate-fadeIn" style={{ animationDelay: '100ms' }}>
                <h4 className="text-xl font-semibold text-white mb-4">Race Conditions</h4>
                <table className="w-full text-left text-gray-300">
                    <tbody>
                        {raceConditions.map((cond, index) => (
                            <tr key={index} className="border-b border-purple-900/50 last:border-b-0">
                                <td className="p-3 font-medium text-white">{cond.detail}</td>
                                <td className="p-3 text-gray-300">{cond.value}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                <p className="text-sm text-yellow-400 mt-4 flex items-center gap-2">
                    <span className="text-xl">⚠️</span>
                    Note: If turf deemed inadvisable, race will be run on Tapeta Course at One Mile and Seventy Yards.
                </p>
            </div>

            {/* Complete Horse Entries Table */}
            <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/20 overflow-x-auto opacity-0 animate-fadeIn" style={{ animationDelay: '150ms' }}>
                <h4 className="text-xl font-semibold text-white mb-4">Complete Horse Entries ({horseEntries.length} horses)</h4>
                <table className="w-full text-left text-gray-300 min-w-max">
                    <thead className="bg-purple-900/50">
                        <tr>
                            <th className="p-4">Post</th>
                            <th className="p-4">Horse</th>
                            <th className="p-4">Jockey</th>
                            <th className="p-4">Trainer</th>
                            <th className="p-4">ML</th>
                            <th className="p-4">Starts</th>
                            <th className="p-4">W-P-S</th>
                            <th className="p-4">Avg Beyer</th>
                            <th className="p-4">Key Notes</th>
                        </tr>
                    </thead>
                    <tbody>
                        {horseEntries.map((entry, index) => (
                            <tr key={index} className="border-t border-purple-900/50 hover:bg-purple-900/20 transition duration-200">
                                <td className="p-4">{entry.post}</td>
                                <td className="p-4">{entry.horse}</td>
                                <td className="p-4">{entry.jockey}</td>
                                <td className="p-4">{entry.trainer}</td>
                                <td className="p-4">{entry.ml}</td>
                                <td className="p-4">{entry.starts}</td>
                                <td className="p-4">{entry.wps}</td>
                                <td className="p-4">{entry.avgBeyer}</td>
                                <td className="p-4 text-purple-300">{entry.keyNotes}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* TimeformUS Pace Figures Table */}
            <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/20 overflow-x-auto opacity-0 animate-fadeIn" style={{ animationDelay: '200ms' }}>
                <h4 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                    <span className="text-yellow-400">⚡</span> TimeformUS Pace Figures
                </h4>
                <table className="w-full text-left text-gray-300 min-w-max">
                    <thead className="bg-purple-900/50">
                        <tr>
                            <th className="p-4">Post</th>
                            <th className="p-4">Horse</th>
                            <th className="p-4">Early</th>
                            <th className="p-4">Late</th>
                        </tr>
                    </thead>
                    <tbody>
                        {paceFigures.map((pace, index) => (
                            <tr key={index} className="border-t border-purple-900/50 hover:bg-purple-900/20 transition duration-200">
                                <td className="p-4">{pace.post}</td>
                                <td className="p-4">{pace.horse}</td>
                                <td className="p-4 text-purple-400">{pace.early}</td>
                                <td className="p-4 text-purple-400">{pace.late}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Predictions & Analysis - existing */}
            <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/20 opacity-0 animate-fadeIn" style={{ animationDelay: '250ms' }}>
                <h4 className="text-xl font-semibold text-white mb-4">Predictions & Analysis</h4>
                <p className="text-gray-300">Detailed model output, speed figures, pace analysis here.</p>
            </div>

            <button className="bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 text-white px-6 py-3 rounded-md transition duration-200 font-medium opacity-0 animate-fadeIn" style={{ animationDelay: '300ms' }}>
                Run Model Again
            </button>
        </div>
    );
}