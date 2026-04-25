const WOODBINE_TRACK = { name: 'Woodbine', code: 'WO' };

const sortWoodbineFirst = (a, b) => {
    const aName = typeof a === 'string' ? a : a.name || a.code;
    const bName = typeof b === 'string' ? b : b.name || b.code;

    if (aName === WOODBINE_TRACK.name) return -1;
    if (bName === WOODBINE_TRACK.name) return 1;
    if (a.code === WOODBINE_TRACK.code) return -1;
    if (b.code === WOODBINE_TRACK.code) return 1;

    return aName.localeCompare(bName) || (a.code || '').localeCompare(b.code || '');
};

export function withCanonicalTrackOptions(tracks = []) {
    const byCode = new Map();

    tracks.forEach((track) => {
        const code = (track?.code || '').trim();
        if (!code) return;

        byCode.set(code, {
            name: (track?.name || code).trim(),
            code,
        });
    });

    byCode.set(WOODBINE_TRACK.code, WOODBINE_TRACK);

    return [...byCode.values()].sort(sortWoodbineFirst);
}

export function withCanonicalTrackNames(tracks = []) {
    const names = new Set(
        tracks
            .map((track) => (typeof track === 'string' ? track : track?.name || track?.code))
            .filter(Boolean)
    );

    names.delete('WO');
    names.add(WOODBINE_TRACK.name);

    return [...names].sort(sortWoodbineFirst);
}

export function getTrackDisplayName(item = {}) {
    if (item.track_name) return item.track_name;
    if (item.track_code === WOODBINE_TRACK.code) return WOODBINE_TRACK.name;
    return item.track_code || '';
}
