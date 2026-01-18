
export const getPostColor = (number) => {
    const num = parseInt(number);
    if (isNaN(num)) return { bg: '#374151', text: '#FFFFFF' };

    switch (num) {
        case 1: return { bg: '#EF4444', text: '#FFFFFF' }; // Red
        case 2: return { bg: '#FFFFFF', text: '#000000' }; // White
        case 3: return { bg: '#3B82F6', text: '#FFFFFF' }; // Blue
        case 4: return { bg: '#EAB308', text: '#000000' }; // Yellow
        case 5: return { bg: '#22C55E', text: '#FFFFFF' }; // Green
        case 6: return { bg: '#000000', text: '#FACC15' }; // Black with Yellow text
        case 7: return { bg: '#F97316', text: '#000000' }; // Orange with Black text
        case 8: return { bg: '#EC4899', text: '#000000' }; // Pink with Black text
        case 9: return { bg: '#06B6D4', text: '#000000' }; // Turquoise with Black text
        case 10: return { bg: '#A855F7', text: '#FFFFFF' }; // Purple
        case 11: return { bg: '#9CA3AF', text: '#FFFFFF' }; // Grey
        case 12: return { bg: '#84CC16', text: '#000000' }; // Lime with Black text
        case 13: return { bg: '#78350F', text: '#FFFFFF' }; // Brown
        case 14: return { bg: '#831843', text: '#FFFFFF' }; // Maroon
        case 15: return { bg: '#C3B091', text: '#000000' }; // Khaki
        case 16: return { bg: '#60A5FA', text: '#FFFFFF' }; // Copen Blue
        case 17: return { bg: '#1E3A8A', text: '#FFFFFF' }; // Navy
        case 18: return { bg: '#14532D', text: '#FFFFFF' }; // Forest Green
        case 19: return { bg: '#0EA5E9', text: '#FFFFFF' }; // Moonstone
        case 20: return { bg: '#D946EF', text: '#FFFFFF' }; // Fuschia
        default: return { bg: '#374151', text: '#FFFFFF' };
    }
};
