"""A small consistent local outline icon set; no external font or icon requests."""
from app import e

PATHS = {
 'ballot':'<path d="m8 3 2-2 8 8-5 5-8-8 3-3Z"/><path d="M4 11H2v10h20V11h-5M8 11h8m-7 5 2 2 4-4"/>',
 'explore':'<circle cx="12" cy="12" r="9"/><path d="m16 8-3 5-5 3 3-5 5-3Z"/>',
 'calendar':'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 11h18"/>',
 'image':'<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="1"/><path d="m3 16 6-5 4 4 3-2 5 5"/>',
 'check':'<rect x="3" y="3" width="18" height="18" rx="2"/><path d="m7 12 3 3 7-7"/>',
 'database':'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
 'book':'<path d="M12 5C8 2 4 3 2 4v16c3-1 6-1 10 1 4-2 7-2 10-1V4c-2-1-6-2-10 1Zm0 0v16"/>',
 'arrow':'<path d="M4 12h16m-6-6 6 6-6 6"/>',
 'key':'<circle cx="15" cy="8" r="5"/><path d="m11 12-8 8v-4l3-3h3"/>',
 'search':'<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6"/>'
}

def icon(name):
    return f'<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{PATHS[name]}</svg>'
