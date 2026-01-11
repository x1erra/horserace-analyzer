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
            {/* Removed Refresh Data and Accuracy as requested */}
            <div className="flex items-center gap-4">
            </div>
        </header>
    );
}