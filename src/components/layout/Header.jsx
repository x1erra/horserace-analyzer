export default function Header({ onToggleSidebar }) {
    return (
        <header className="md:hidden bg-black shadow-md p-4 flex items-center border-b border-purple-900/50">
            <button onClick={onToggleSidebar} className="text-white text-2xl">
                ☰
            </button>
        </header>
    );
}