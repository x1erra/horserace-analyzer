export default function Header({ onToggleSidebar }) {
    return (
        <header className="bg-black shadow-md p-4 flex items-center justify-between border-b border-purple-900/50">
            <div className="flex items-center gap-4">
                {/* Hamburger for mobile */}
                <button onClick={onToggleSidebar} className="md:hidden text-white text-2xl">
                    ☰
                </button>
                <h2 className="text-2xl font-semibold text-white">
                    Dashboard
                </h2>
            </div>
            <div className="flex items-center gap-4">
                <span className="text-sm text-gray-300">Accuracy: 82%</span>
                <button className="bg-purple-800 hover:bg-purple-900 text-white px-4 py-2 rounded-md transition">
                    Refresh Data
                </button>
            </div>
        </header>
    );
}