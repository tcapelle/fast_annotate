"""FastHTML Image Annotation Tool - Proper FastHTML implementation."""
from fasthtml.common import *
from starlette.responses import FileResponse, Response
from pathlib import Path
import yaml
import os
import re
from datetime import datetime
from urllib.parse import urlencode, quote_plus
from dataclasses import dataclass
import simple_parsing as sp

@dataclass
class Config:
    images_folder: str = sp.field(positional=True, help="The folder containing the images and annotations.db")
    title: str = "Image Annotation Tool"
    description: str = "Annotate images"
    num_classes: int = 5
    max_history: int = 10

config = sp.parse(Config, config_path="./config.yaml")

# Database setup - will be reassigned when folder changes
db = database(f'{config.images_folder}/annotations.db')

class Annotation:
    id: int
    image_path: str
    rating: int
    username: str
    timestamp: str
    marked: bool = False  # New field for marking images
    
annotations = db.create(Annotation, pk='id')

def switch_folder(new_folder: str):
    """Switch to a different data folder."""
    global config, db, annotations, state
    
    # Update config
    config.images_folder = f"data/{new_folder}"
    
    # Create new database connection
    db = database(f'{config.images_folder}/annotations.db')
    annotations = db.create(Annotation, pk='id')
    
    # Reset state
    state.current_index = 0
    state.filter_unannotated = False
    state.filter_rating = None
    state.history.clear()
    state.selected.clear()
    state.last_anchor = None
    
    # Set to first unannotated
    state.current_index = find_first_unannotated()

# Database is the single source of truth - no CSV imports needed

# Initialize FastHTML app with custom styles
app, rt = fast_app(
    hdrs=(
        Link(rel='stylesheet', href='/styles.css'),
    ),
    pico=False,  # We're using custom styles instead of Pico CSS
    debug=True  # Enable debug mode to help troubleshoot
)

# State management
class AppState:
    def __init__(self):
        self.current_index = 0
        self.filter_unannotated = False
        self.filter_rating = None  # Filter by specific rating (1-5) or None for no filter
        self.history = []
        self.selected = set()  # set of image relative paths
        self.last_anchor = None  # last clicked image for shift-selection

state = AppState()

# Helper functions
def get_image_files():
    """Get all image files from the configured directory."""
    images_dir = Path(config.images_folder)
    images = []
    if images_dir.exists():
        for ext in ['.jpg', '.jpeg', '.png']:
            images.extend(images_dir.rglob(f"*{ext}"))
            images.extend(images_dir.rglob(f"*{ext.upper()}"))
    # Return paths relative to the images folder
    return sorted([img.relative_to(images_dir) for img in images])

def get_available_folders():
    """Get all available data folders."""
    data_dir = Path("data")
    if not data_dir.exists():
        return []
    return sorted([f.name for f in data_dir.iterdir() if f.is_dir()])

def get_username():
    """Get current username."""
    return os.environ.get('USER') or os.environ.get('USERNAME') or 'unknown'

def get_current_image():
    """Get current image based on state."""
    images = get_image_files()
    if not images:
        return None
    
    if state.filter_unannotated:
        # Find next unannotated image from current position
        annotated_images = {a.image_path for a in annotations()}
        for i in range(state.current_index, len(images)):
            if str(images[i]) not in annotated_images:
                return images[i]
        # Try from beginning if nothing found after current position
        for i in range(0, state.current_index):
            if str(images[i]) not in annotated_images:
                state.current_index = i
                return images[i]
        return None
    
    if state.filter_rating is not None:
        # Find next image with specific rating from current position
        rating_images = {a.image_path: a.rating for a in annotations() if a.rating == state.filter_rating}
        for i in range(state.current_index, len(images)):
            if str(images[i]) in rating_images:
                return images[i]
        # Try from beginning if nothing found after current position
        for i in range(0, state.current_index):
            if str(images[i]) in rating_images:
                state.current_index = i
                return images[i]
        return None
    
    if 0 <= state.current_index < len(images):
        return images[state.current_index]
    return None

def get_progress_stats():
    """Calculate progress statistics."""
    images = get_image_files()
    total = len(images)
    all_annotations = annotations()
    annotated_count = len(set(a.image_path for a in all_annotations if a.rating > 0))
    marked_count = len([a for a in all_annotations if getattr(a, 'marked', False)])
    
    return {
        'total': total,
        'annotated': annotated_count,
        'marked': marked_count,
        'remaining': total - annotated_count,
        'percentage': round(100 * annotated_count / total) if total > 0 else 0
    }

def get_annotation_for_image(image_path):
    """Get annotation data for a specific image."""
    # Use parameterized query - image_path should be the relative path string
    result = annotations("image_path=?", (str(image_path),), limit=1)
    if result:
        return {'rating': result[0].rating, 'marked': getattr(result[0], 'marked', False)}
    return {'rating': 0, 'marked': False}

def index_of_image(image_name: str) -> int:
    """Return index of an image (relative path str) in the image list, or -1."""
    imgs = get_image_files()
    for i, p in enumerate(imgs):
        if str(p) == image_name:
            return i
    return -1

def get_annotations_map():
    """Map of image_path -> {'rating': int, 'marked': bool}."""
    amap = {}
    for a in annotations():
        amap[a.image_path] = {'rating': a.rating, 'marked': getattr(a, 'marked', False)}
    return amap

def _filtered_items(q: str = '', rating: str = '', show: str = 'all', marked: str = '', sort: str = 'name'):
    """Return filtered and sorted list of (Path, rating, marked) across entire dataset."""
    q = (q or '').strip()
    rating_val = int(rating) if str(rating).isdigit() else None
    show = (show or 'all')
    marked_only = (marked == 'on' or marked == 'true' or marked == '1')

    imgs = get_image_files()
    amap = get_annotations_map()

    items = []
    for p in imgs:
        sp = str(p)
        ann = amap.get(sp, {'rating': 0, 'marked': False})
        r = ann['rating']
        m = ann['marked']
        if q and q.lower() not in sp.lower():
            continue
        if rating_val is not None and r != rating_val:
            continue
        if show == 'annotated' and r <= 0:
            continue
        if show == 'unannotated' and r > 0:
            continue
        if marked_only and not m:
            continue
        items.append((p, r, m))

    # Sort
    if sort == 'name_desc':
        items.sort(key=lambda t: str(t[0]).lower(), reverse=True)
    elif sort == 'rating_desc':
        items.sort(key=lambda t: (t[1], str(t[0]).lower()), reverse=True)
    elif sort == 'rating_asc':
        items.sort(key=lambda t: (t[1], str(t[0]).lower()))
    elif sort == 'marked_first':
        items.sort(key=lambda t: (not t[2], str(t[0]).lower()))
    else:  # name
        items.sort(key=lambda t: str(t[0]).lower())
    return items

def render_browser_grid(q: str = '', rating: str = '', show: str = 'all', marked: str = '', sort: str = 'name', page: str = '1', per_page: int = 60):
    """Return a Div containing a responsive grid of images, filtered and paginated."""
    # Normalize inputs
    try:
        page_i = max(1, int(page or '1'))
    except Exception:
        page_i = 1
    items = _filtered_items(q=q, rating=rating, show=show, marked=marked, sort=sort)

    total = len(items)
    start = (page_i - 1) * per_page
    end = start + per_page
    page_items = items[start:end]
    total_pages = max(1, (total + per_page - 1) // per_page)

    def badge(content, cls):
        return Span(content, cls=cls)

    # Build grid cells
    cells = []
    for p, r, m in page_items:
        sp = str(p)
        badges = []
        if r and r > 0:
            badges.append(badge(f"★ {r}", 'rating-badge'))
        # Marked status will be shown as a banner overlay instead of a small badge

        # Action buttons: Open in annotator (explicit), click tile toggles selection
        qstr = urlencode({'image': str(sp)})
        open_btn = A("Open", href=f"/annotate?{qstr}", cls="grid-open")

        selected_cls = ' selected' if sp in state.selected else ''
        marked_cls = ' marked' if m else ''

        cells.append(
            Div(
                Div(
                    Img(src=f"/{config.images_folder}/{sp}", alt=sp, cls="grid-img"),
                    Div(*badges, cls="grid-badges"),
                    (Div("⚑ MARKED", cls="marked-banner") if m else None),
                    Div("✓", cls="select-check"),
                    cls=f"grid-thumb{selected_cls}{marked_cls}",
                    hx_post="/toggle_select",
                    hx_target="#browse-grid",
                    hx_swap="outerHTML",
                    hx_include=".browser-filters *",
                    hx_vals=f"js:{{image: '{sp}', shift: event.shiftKey}}"
                ),
                Div(sp, cls="grid-name"),
                Div(open_btn, cls="grid-actions"),
                cls=f"grid-item{selected_cls}{marked_cls}"
            )
        )

    # Pagination controls
    prev_disabled = page_i <= 1
    next_disabled = page_i >= total_pages
    # Keep other filters when paging
    def page_btn(label, new_page, disabled):
        params = {
            'q': q,
            'rating': rating or '',
            'show': show,
            'marked': 'on' if (marked in ('on','true','1')) else '',
            'sort': sort,
            'page': str(new_page)
        }
        return Button(
            label,
            disabled=disabled,
            hx_get=f"/browse_grid?{urlencode(params)}",
            hx_target="#browse-grid",
            hx_swap="outerHTML",
            cls="page-btn"
        )

    showing_from = (start + 1) if total > 0 else 0
    showing_to = min(end, total)
    grid = Div(
        Div(
            f"Showing {showing_from}–{showing_to} of {total} images",
            Div(
                page_btn("← Prev", page_i - 1, prev_disabled),
                Span(f"Page {page_i}/{total_pages}", cls="page-info"),
                page_btn("Next →", page_i + 1, next_disabled),
                cls="pager"
            ),
            cls="grid-meta"
        ),
        Div(*cells, cls="grid"),
        id="browse-grid"
    )
    return grid

@rt("/")
def index():
    """Main annotation interface."""
    images = get_image_files()
    if not images:
        return Titled(config.title,
            Div(f"No images found in {config.images_folder}/ directory", 
                style="max-width: 800px; margin: 2rem auto; padding: 2rem; background: white; border-radius: 8px;")
        )
    
    current_image = get_current_image()
    if not current_image:
        # If no current image, reset to first image to keep UI functional
        state.current_index = 0
        current_image = get_current_image()
    
    annotation_data = get_annotation_for_image(current_image)
    current_rating = annotation_data['rating']
    is_marked = annotation_data['marked']
    stats = get_progress_stats()
    
    return Titled(config.title,
        Div(
            # Folder selection section
            Div(
                Div(
                    Label("Choose Folder:", style="margin-right: 10px; font-weight: 600;"),
                    Select(
                        *[Option(folder, value=folder, selected=(f"data/{folder}" == config.images_folder)) 
                          for folder in get_available_folders()],
                        name="folder_select",
                        hx_post="/switch_folder",
                        hx_target="body",
                        hx_swap="outerHTML",
                        hx_trigger="change",
                        cls="folder-select",
                        style="padding: 8px 12px; border-radius: 6px; border: 2px solid #007bff; background: white; font-size: 14px; min-width: 300px;"
                    ),
                    style="display: flex; align-items: center; justify-content: center; margin-bottom: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px; border-left: 4px solid #007bff;"
                ),
                cls="folder-section"
            ),
            
            # Progress section
            Div(
                Div(
                    f"Image {state.current_index + 1} of {stats['total']} | ",
                    f"Annotated: {stats['annotated']}/{stats['total']} ({stats['percentage']}%) | ",
                    f"Marked: {stats['marked']} | ",
                    Span(f"📁 {config.images_folder}", cls="folder-name"),
                    cls="progress"
                ),
                Div(
                    A("Browse Dataset", href="/browse", cls="browse-link"),
                    cls="progress"
                ),
                Div(
                    Div(style=f"width: {stats['percentage']}%", cls="progress-fill"),
                    cls="progress-bar"
                ),
                Div(
                    Label(
                        Input(
                            type="checkbox",
                            checked=state.filter_unannotated,
                            hx_post="/toggle_filter",
                            hx_target="body",
                            hx_swap="outerHTML",
                            cls="filter-checkbox"
                        ),
                        " Show unannotated only",
                        cls="filter-label"
                    ),
                    Div(
                        Label("Filter by rating:", style="margin-right: 10px; font-weight: 500;"),
                        Select(
                            Option("All ratings", value="", selected=state.filter_rating is None),
                            *[Option(f"Rating {i}", value=str(i), selected=state.filter_rating == i) 
                              for i in range(1, config.num_classes + 1)],
                            name="rating_filter_select",
                            hx_post="/filter_rating",
                            hx_target="body",
                            hx_swap="outerHTML",
                            hx_trigger="change",
                            cls="rating-filter-select",
                            style="padding: 4px 8px; border-radius: 4px; border: 1px solid #ddd;"
                        ),
                        style="margin-top: 10px;"
                    ),
                    cls="filter-container"
                )
            ),
            
            # Current image info
            Div(f"Current: {current_image}", cls="progress"),
            
            # Image display
            Div(
                Img(src=f"/{config.images_folder}/{current_image}", alt=str(current_image)),
                cls="image-container"
            ),
            
            # Description if present
            Div(config.description, cls="description") if config.description else None,
            
            # Controls section
            Div(
                Div(
                    f"Current Rating: ",
                    Span(current_rating if current_rating > 0 else 'Not rated'),
                    cls="current-rating"
                ),
                
                # Rating buttons and mark checkbox in same row
                Div(
                    Div(
                        *[Button(
                            str(i),
                            cls=f"rating-btn {'active' if current_rating == i else ''}",
                            hx_post=f"/rate/{i}",
                            hx_target="body",
                            hx_swap="outerHTML"
                        ) for i in range(1, config.num_classes + 1)],
                        cls="rating-buttons"
                    ),
                    Div(
                        Label(
                            Input(
                                type="checkbox",
                                checked=is_marked,
                                hx_post="/mark",
                                hx_target="body",
                                hx_swap="outerHTML",
                                cls="mark-checkbox",
                                id="mark-checkbox"
                            ),
                            " Mark Image (X)",
                            cls="mark-label",
                            style="color: #dc3545; font-weight: 500; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; margin-left: 20px;"
                        )
                    ),
                    style="display: flex; align-items: center; justify-content: center; gap: 10px;"
                ),
                
                # Navigation controls
                Div(
                    Button(
                        "← Previous", cls="nav-btn",
                        hx_post="/prev",
                        hx_target="body",
                        hx_swap="outerHTML",
                        disabled=state.current_index == 0
                    ),
                    Button(
                        "Undo (U)", cls="nav-btn undo-btn",
                        hx_post="/undo",
                        hx_target="body",
                        hx_swap="outerHTML",
                        disabled=len(state.history) == 0
                    ),
                    Button(
                        "🗑️ Delete Image (D)", cls="nav-btn delete-btn",
                        hx_post="/delete",
                        hx_target="body",
                        hx_swap="outerHTML",
                        style="background-color: #dc3545; color: white; font-weight: bold;"
                    ),
                    Button(
                        "Next →", cls="nav-btn",
                        hx_post="/next",
                        hx_target="body",
                        hx_swap="outerHTML",
                        disabled=state.current_index >= len(images) - 1
                    ),
                    cls="nav-controls"
                ),
                
                # Help text
                Div(
                    "Keyboard shortcuts: ",
                    Span(f"1-{config.num_classes}", cls="kbd"), " rate & next | ",
                    Span("←→", cls="kbd"), " navigate | ",
                    Span("U", cls="kbd"), " undo | ",
                    Span("D", cls="kbd"), " delete | ",
                Span("X", cls="kbd"), " mark/unmark",
                    cls="help-text"
                ),
                cls="controls"
            ),
            cls="container"
        ),
        Script(f"""
            // Simple HTMX-based keyboard shortcuts
            document.addEventListener('keydown', function(e) {{
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
                
                // Number keys for rating (with navigation)
                if (e.key >= '1' && e.key <= '{config.num_classes}') {{
                    htmx.ajax('POST', '/rate_and_next/' + e.key, {{
                        target: 'body',
                        swap: 'outerHTML'
                    }});
                    e.preventDefault();
                    return;
                }}
                
                // Navigation shortcuts - trigger HTMX on existing buttons
                let targetBtn = null;
                switch(e.key) {{
                    case 'ArrowLeft':
                        targetBtn = document.querySelector('button[hx-post="/prev"]');
                        break;
                    case 'ArrowRight':
                        targetBtn = document.querySelector('button[hx-post="/next"]');
                        break;
                    case 'u': case 'U':
                        targetBtn = document.querySelector('button[hx-post="/undo"]');
                        break;
                    case 'd': case 'D':
                        targetBtn = document.querySelector('button[hx-post="/delete"]');
                        break;
                    case 'x': case 'X':
                        targetBtn = document.querySelector('#mark-checkbox');
                        break;
                }}
                
                if (targetBtn && !targetBtn.disabled) {{
                    htmx.trigger(targetBtn, 'click');
                    e.preventDefault();
                }}
            }});
        """)
    )

@rt("/browse")
def browse(q: str = '', rating: str = '', show: str = 'all', marked: str = '', sort: str = 'name', page: str = '1'):
    """Dataset browser: filter and review images and annotations."""
    stats = get_progress_stats()
    grid = render_browser_grid(q=q, rating=rating, show=show, marked=marked, sort=sort, page=page)

    # Filter form controls submit via HTMX to update only the grid
    filter_form = Form(
        Div(
            Input(type="search", name="q", placeholder="Search filename…", value=q or '',
                  hx_get="/browse_grid", hx_target="#browse-grid", hx_trigger="keyup changed delay:300ms", hx_swap="outerHTML", cls="filter-input"),
            Select(
                Option("All ratings", value="", selected=(not rating)),
                *[Option(f"Rating {i}", value=str(i), selected=(rating == str(i))) for i in range(1, config.num_classes + 1)],
                name="rating", hx_get="/browse_grid", hx_target="#browse-grid", hx_trigger="change", hx_swap="outerHTML", cls="filter-select"
            ),
            Select(
                Option("All", value="all", selected=(show == 'all')),
                Option("Annotated", value="annotated", selected=(show == 'annotated')),
                Option("Unannotated", value="unannotated", selected=(show == 'unannotated')),
                name="show", hx_get="/browse_grid", hx_target="#browse-grid", hx_trigger="change", hx_swap="outerHTML", cls="filter-select"
            ),
            Label(
                Input(type="checkbox", name="marked", checked=(marked in ('on','true','1')),
                      hx_get="/browse_grid", hx_target="#browse-grid", hx_trigger="change", hx_swap="outerHTML"),
                Span("Marked only", cls="filter-label"),
                cls="filter-check"
            ),
            Select(
                Option("Name ↑", value="name", selected=(sort == 'name')),
                Option("Name ↓", value="name_desc", selected=(sort == 'name_desc')),
                Option("Rating ↑", value="rating_asc", selected=(sort == 'rating_asc')),
                Option("Rating ↓", value="rating_desc", selected=(sort == 'rating_desc')),
                Option("Marked first", value="marked_first", selected=(sort == 'marked_first')),
                name="sort", hx_get="/browse_grid", hx_target="#browse-grid", hx_trigger="change", hx_swap="outerHTML", cls="filter-select"
            ),
            A("Reset", href="/browse", cls="filter-reset"),
            cls="browser-filters"
        )
    )

    # Selection toolbar
    sel_count = len(state.selected)
    selection_bar = Div(
        Div(f"Selected: {sel_count}", cls="sel-count"),
        Div(
            Select(
                Option("Set rating…", value=""),
                *[Option(f"{i}", value=str(i)) for i in range(1, config.num_classes + 1)],
                name="set_rating", cls="filter-select"
            ),
            Button("Apply", cls="page-btn",
                   hx_post="/batch_rate", hx_target="body", hx_swap="outerHTML", hx_include="[name='set_rating'], .browser-filters *"),
            Button("Mark", cls="page-btn",
                   hx_post="/batch_mark", hx_vals={"action": "mark"}, hx_target="body", hx_swap="outerHTML", hx_include=".browser-filters *, .selection-bar *"),
            Button("Unmark", cls="page-btn",
                   hx_post="/batch_mark", hx_vals={"action": "unmark"}, hx_target="body", hx_swap="outerHTML", hx_include=".browser-filters *, .selection-bar *"),
            Button("Clear Selection", cls="page-btn",
                   hx_post="/clear_selection", hx_target="body", hx_swap="outerHTML", hx_include=".browser-filters *, .selection-bar *"),
            Button("Open First", cls="page-btn",
                   hx_post="/open_first_selected", hx_target="body", hx_swap="outerHTML"),
            cls="sel-actions"
        ),
        cls="selection-bar"
    )

    return Titled(
        f"{config.title} · Browser",
        Div(
            Div(
                Div(
                    f"Total: {stats['total']} | Annotated: {stats['annotated']} | Marked: {stats['marked']} | Remaining: {stats['remaining']}",
                    cls="progress"
                ),
                Div(
                    A("← Back to Annotator", href="/", cls="browse-link"),
                    cls="progress"
                ),
            ),
            filter_form,
            selection_bar,
            grid,
            cls="browser-container"
        )
    )

@rt("/browse_grid")
def browse_grid(q: str = '', rating: str = '', show: str = 'all', marked: str = '', sort: str = 'name', page: str = '1'):
    """Partial: just the grid, for HTMX updates from the filter controls."""
    return render_browser_grid(q=q, rating=rating, show=show, marked=marked, sort=sort, page=page)

@rt("/annotate")
def annotate_query(image: str = ''):
    """Jump to annotator using a query parameter to avoid static route collisions."""
    if image:
        idx = index_of_image(image)
        if idx >= 0:
            state.current_index = idx
    return index()

@rt("/toggle_select", methods=["POST"])
def toggle_select(image: str = '', shift: str = '', q: str = '', rating: str = '', show: str = 'all', marked: str = '', sort: str = 'name', page: str = '1'):
    sp = image or ''
    shift_on = str(shift).lower() in ('1', 'true', 'on')
    if not sp:
        return render_browser_grid(q=q, rating=rating, show=show, marked=marked, sort=sort, page=page)

    if shift_on and state.last_anchor:
        # Select range between last_anchor and current within filtered, sorted items
        items = _filtered_items(q=q, rating=rating, show=show, marked=marked, sort=sort)
        order = [str(p) for (p, _r, _m) in items]
        try:
            i1 = order.index(state.last_anchor)
            i2 = order.index(sp)
            start, end = (i1, i2) if i1 <= i2 else (i2, i1)
            for s in order[start:end+1]:
                state.selected.add(s)
        except ValueError:
            # If either not in current order, just toggle single
            if sp in state.selected:
                state.selected.remove(sp)
            else:
                state.selected.add(sp)
        # Update anchor to current
        state.last_anchor = sp
    else:
        # Toggle single and set anchor
        if sp in state.selected:
            state.selected.remove(sp)
        else:
            state.selected.add(sp)
        state.last_anchor = sp
    return render_browser_grid(q=q, rating=rating, show=show, marked=marked, sort=sort, page=page)

@rt("/batch_rate", methods=["POST"])
def batch_rate(set_rating: str = '', q: str = '', rating: str = '', show: str = 'all', marked: str = '', sort: str = 'name', page: str = '1'):
    print(f"DEBUG batch_rate: set_rating='{set_rating}', selected_count={len(state.selected)}")
    if set_rating and set_rating.isdigit():
        val = int(set_rating)
        if 1 <= val <= config.num_classes:
            print(f"DEBUG: Applying rating {val} to {len(state.selected)} images")
            for spath in list(state.selected):
                print(f"DEBUG: Processing {spath}")
                existing = annotations("image_path=?", (spath,), limit=1)
                if existing:
                    annotations.update({'rating': val, 'timestamp': datetime.now().isoformat()}, existing[0].id)
                    print(f"DEBUG: Updated existing annotation for {spath}")
                else:
                    annotations.insert({
                        'image_path': spath,
                        'rating': val,
                        'username': get_username(),
                        'timestamp': datetime.now().isoformat(),
                        'marked': False
                    })
                    print(f"DEBUG: Created new annotation for {spath}")
        else:
            print(f"DEBUG: Rating {val} out of range (1-{config.num_classes})")
    else:
        print(f"DEBUG: Invalid set_rating value: '{set_rating}'")
    return browse(q=q, rating=rating, show=show, marked=marked, sort=sort, page=page)

@rt("/batch_mark", methods=["POST"])
def batch_mark(action: str = 'mark', q: str = '', rating: str = '', show: str = 'all', marked: str = '', sort: str = 'name', page: str = '1'):
    flag = True if action == 'mark' else False
    for spath in list(state.selected):
        existing = annotations("image_path=?", (spath,), limit=1)
        if existing:
            annotations.update({'marked': flag}, existing[0].id)
        else:
            annotations.insert({
                'image_path': spath,
                'rating': 0,
                'username': get_username(),
                'timestamp': datetime.now().isoformat(),
                'marked': flag
            })
    return browse(q=q, rating=rating, show=show, marked=marked, sort=sort, page=page)

@rt("/clear_selection", methods=["POST"])
def clear_selection(q: str = '', rating: str = '', show: str = 'all', marked: str = '', sort: str = 'name', page: str = '1'):
    state.selected.clear()
    return browse(q=q, rating=rating, show=show, marked=marked, sort=sort, page=page)

@rt("/open_first_selected", methods=["POST"])    
def open_first_selected():
    if state.selected:
        imgs = get_image_files()
        # Find first selected by list order
        for i, p in enumerate(imgs):
            if str(p) in state.selected:
                state.current_index = i
                break
        # Optionally clear selection? keep for now
    return index()

@rt("/annotate/{image_name:path}", methods=["GET", "POST"])
def annotate_image(image_name: str):
    """Jump to annotator at specific image from the browser."""
    idx = index_of_image(image_name)
    if idx >= 0:
        state.current_index = idx
    return index()

@rt("/styles.css")
def get_styles():
    """Serve the CSS file."""
    css_path = Path("styles.css")
    if css_path.exists():
        return FileResponse(str(css_path), media_type="text/css")
    return Response("/* Styles not found */", media_type="text/css")

@rt(f"/{config.images_folder}/{{image_name:path}}")
def get_image(image_name: str):
    """Serve image files with security checks."""
    # Allow nested paths with proper validation
    # Check for path traversal attempts
    if ".." in image_name or image_name.startswith("/"):
        return Response("Invalid path", status_code=400)
    
    # Validate the file extension
    if not image_name.lower().endswith(('.jpg', '.jpeg', '.png')):
        return Response("Invalid file type", status_code=400)
    
    image_path = Path(config.images_folder) / image_name
    
    # Ensure the resolved path is within images directory
    try:
        images_dir = Path(config.images_folder).resolve()
        resolved_path = image_path.resolve()
        if not str(resolved_path).startswith(str(images_dir)):
            return Response("Access denied", status_code=403)
    except:
        return Response("Invalid path", status_code=400)
    
    if image_path.exists():
        return FileResponse(
            str(image_path),
            headers={"Cache-Control": "public, max-age=3600"}
        )
    return Response("Image not found", status_code=404)

@rt("/rate/{rating:int}", methods=["POST"])
def rate(rating: int):
    """Save annotation (button click - stay on image)."""
    if rating < 1 or rating > config.num_classes:
        return index()
    
    current_image = get_current_image()
    if current_image:
        # Store in history for undo
        old_annotation_data = get_annotation_for_image(str(current_image))
        old_annotation = old_annotation_data['rating']
        state.history.append({
            'image_name': str(current_image),
            'old_rating': old_annotation,
            'index': state.current_index,
            'action': 'rate'
        })
        
        # Keep history limited
        if len(state.history) > config.max_history:
            state.history = state.history[-config.max_history:]
        
        # Save or update annotation
        # Use parameterized query to prevent SQL injection
        existing = annotations("image_path=?", (str(current_image),), limit=1)
        if existing:
            # Preserve marked status when updating rating
            annotations.update({
                'rating': rating, 
                'timestamp': datetime.now().isoformat()
            }, existing[0].id)
        else:
            annotations.insert({
                'image_path': str(current_image),
                'rating': rating,
                'username': get_username(),
                'timestamp': datetime.now().isoformat(),
                'marked': False
            })
        
        # Stay on current image after rating
    
    return index()

@rt("/rate_and_next/{rating:int}", methods=["POST"])
def rate_and_next(rating: int):
    """Save annotation and move to next image (keyboard shortcut)."""
    if rating < 1 or rating > config.num_classes:
        return index()
    
    current_image = get_current_image()
    if current_image:
        # Store in history for undo
        old_annotation_data = get_annotation_for_image(str(current_image))
        old_annotation = old_annotation_data['rating']
        state.history.append({
            'image_name': str(current_image),
            'old_rating': old_annotation,
            'index': state.current_index,
            'action': 'rate'
        })
        
        # Keep history limited
        if len(state.history) > config.max_history:
            state.history = state.history[-config.max_history:]
        
        # Save or update annotation
        existing = annotations("image_path=?", (str(current_image),), limit=1)
        if existing:
            # Preserve marked status when updating rating
            annotations.update({
                'rating': rating, 
                'timestamp': datetime.now().isoformat()
            }, existing[0].id)
        else:
            annotations.insert({
                'image_path': str(current_image),
                'rating': rating,
                'username': get_username(),
                'timestamp': datetime.now().isoformat(),
                'marked': False
            })
        
        # Move to next image for keyboard shortcuts
        navigate(1)
    
    return index()

@rt("/prev", methods=["POST"])
def prev():
    """Navigate to previous image."""
    navigate(-1)
    return index()

@rt("/next", methods=["POST"]) 
def next():
    """Navigate to next image."""
    navigate(1)
    return index()

@rt("/undo", methods=["POST"])
def undo():
    """Undo last action (rating or deletion)."""
    if state.history:
        last_action = state.history.pop()
        action_type = last_action.get('action', 'rate')  # Default to 'rate' for backward compatibility
        
        if action_type == 'delete':
            # Restore deleted image file
            image_name = last_action['image_name']
            image_data = last_action.get('image_data')
            old_rating = last_action['old_rating']
            
            if image_data:
                # Restore the image file
                image_path = Path(config.images_folder) / image_name
                try:
                    # Create parent directories if needed
                    image_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(image_path, 'wb') as f:
                        f.write(image_data)
                    print(f"Restored image file: {image_path}")
                    
                    # Restore annotation if there was one
                    if old_rating > 0:
                        annotations.insert({
                            'image_path': image_name,
                            'rating': old_rating,
                            'username': get_username(),
                            'timestamp': datetime.now().isoformat(),
                            'marked': False
                        })
                    
                except Exception as e:
                    print(f"Error restoring image file {image_path}: {e}")
            
            # Go back to that image
            state.current_index = last_action['index']
            
        else:
            # Handle rating undo (existing logic)
            image_name = last_action['image_name']
            old_rating = last_action['old_rating']
            
            if old_rating == 0:
                # Delete annotation
                existing = annotations("image_path=?", (image_name,), limit=1)
                if existing:
                    annotations.delete(existing[0].id)
            else:
                # Restore old rating
                existing = annotations("image_path=?", (image_name,), limit=1)
                if existing:
                    annotations.update({'rating': old_rating}, existing[0].id)
            
            # Go back to that image
            state.current_index = last_action['index']
    
    return index()

@rt("/mark", methods=["POST"])
def mark():
    """Toggle mark status for current image."""
    current_image = get_current_image()
    if current_image:
        # Check if annotation exists
        existing = annotations("image_path=?", (str(current_image),), limit=1)
        
        if existing:
            # Toggle the marked status
            current_marked = getattr(existing[0], 'marked', False)
            annotations.update({'marked': not current_marked}, existing[0].id)
        else:
            # Create new annotation with just marked flag
            annotations.insert({
                'image_path': str(current_image),
                'rating': 0,  # No rating yet
                'username': get_username(),
                'timestamp': datetime.now().isoformat(),
                'marked': True
            })
    
    return index()

@rt("/toggle_filter", methods=["POST"])
def toggle_filter():
    """Toggle filter for unannotated images."""
    state.filter_unannotated = not state.filter_unannotated
    
    # Clear rating filter when toggling unannotated filter
    if state.filter_unannotated:
        state.filter_rating = None
        images = get_image_files()
        annotated_images = {a.image_path for a in annotations()}
        for i, img in enumerate(images):
            if str(img) not in annotated_images:
                state.current_index = i
                break
    
    return index()

@rt("/filter_rating", methods=["POST"])
def filter_rating(rating_filter_select: str = ''):
    """Filter images by specific rating."""
    if rating_filter_select == '':
        state.filter_rating = None
    else:
        state.filter_rating = int(rating_filter_select)
        # Clear unannotated filter when filtering by rating
        state.filter_unannotated = False
    
    # Find first image with the selected rating
    if state.filter_rating is not None:
        images = get_image_files()
        rating_images = {a.image_path for a in annotations() if a.rating == state.filter_rating}
        for i, img in enumerate(images):
            if str(img) in rating_images:
                state.current_index = i
                break
    
    return index()

@rt("/switch_folder", methods=["POST"])
def switch_folder_endpoint(folder_select: str = ''):
    """Switch to a different data folder."""
    if folder_select and folder_select in get_available_folders():
        switch_folder(folder_select)
        print(f"Switched to folder: data/{folder_select}")
    
    return index()

@rt("/delete", methods=["POST"])
def delete():
    """Delete current image file and its annotation."""
    current_image = get_current_image()
    if current_image:
        image_path = Path(config.images_folder) / current_image
        
        # Store image data and annotation for undo
        image_data = None
        old_annotation_data = get_annotation_for_image(str(current_image))
        old_annotation = old_annotation_data['rating']
        
        if image_path.exists():
            try:
                # Read image data before deleting
                with open(image_path, 'rb') as f:
                    image_data = f.read()
                
                image_path.unlink()  # Delete the file
                print(f"Deleted image file: {image_path}")
            except Exception as e:
                print(f"Error deleting image file {image_path}: {e}")
                return index()  # Return without changes if file deletion fails
        
        # Store in history for undo (including image data)
        state.history.append({
            'image_name': str(current_image),
            'old_rating': old_annotation,
            'index': state.current_index,
            'action': 'delete',
            'image_data': image_data
        })
        
        # Keep history limited
        if len(state.history) > config.max_history:
            state.history = state.history[-config.max_history:]
        
        # Delete annotation if it exists
        existing = annotations("image_path=?", (str(current_image),), limit=1)
        if existing:
            annotations.delete(existing[0].id)
        
        # After deletion, the image list is refreshed and current index automatically
        # points to what was the next image, so no navigation needed
    
    return index()

def navigate(direction):
    """Navigate through images."""
    images = get_image_files()
    
    if state.filter_unannotated:
        # Skip annotated images
        annotated_images = {a.image_path for a in annotations()}
        new_index = state.current_index
        
        # Add safety counter to prevent infinite loops
        attempts = 0
        max_attempts = len(images)
        
        while attempts < max_attempts:
            new_index += direction
            if not (0 <= new_index < len(images)):
                break
            if str(images[new_index]) not in annotated_images:
                state.current_index = new_index
                break
            attempts += 1
    elif state.filter_rating is not None:
        # Skip images that don't have the selected rating
        rating_images = {a.image_path for a in annotations() if a.rating == state.filter_rating}
        new_index = state.current_index
        
        # Add safety counter to prevent infinite loops
        attempts = 0
        max_attempts = len(images)
        
        while attempts < max_attempts:
            new_index += direction
            if not (0 <= new_index < len(images)):
                break
            if str(images[new_index]) in rating_images:
                state.current_index = new_index
                break
            attempts += 1
    else:
        # Normal navigation
        new_index = state.current_index + direction
        if 0 <= new_index < len(images):
            state.current_index = new_index

# Find first unannotated image on startup
def find_first_unannotated():
    """Find the index of the first unannotated image."""
    images = get_image_files()
    annotated_images = {a.image_path for a in annotations()}
    for i, img in enumerate(images):
        if str(img) not in annotated_images:
            return i
    return 0

def cleanup_orphaned_entries():
    """Remove database entries for images that no longer exist."""
    images = get_image_files()
    existing_image_paths = {str(img) for img in images}
    
    # Get all annotations
    all_annotations = annotations()
    orphaned_count = 0
    
    for annotation in all_annotations:
        if annotation.image_path not in existing_image_paths:
            # Image file no longer exists, delete the annotation
            annotations.delete(annotation.id)
            orphaned_count += 1
            print(f"Removed orphaned entry for: {annotation.image_path}")
    
    if orphaned_count > 0:
        print(f"Cleaned up {orphaned_count} orphaned database entries")
    else:
        print("No orphaned database entries found")

# Set initial position
state.current_index = find_first_unannotated()

# Print startup info
if __name__ == "__main__":
    print(f"Starting {config.title}")
    print(f"Configuration:")
    print(f"  - Images folder: {config.images_folder}")
    print(f"  - Database: {config.images_folder}/annotations.db")
    print(f"  - Number of classes: {config.num_classes}")
    print(f"  - Annotating as: {get_username()}")
    
    # Clean up orphaned entries on startup
    print("Checking for orphaned database entries...")
    cleanup_orphaned_entries()
    
    images = get_image_files()
    print(f"  - Total images: {len(images)}")
    
    stats = get_progress_stats()
    print(f"  - Already annotated: {stats['annotated']}")
    print(f"  - Starting at image {state.current_index + 1}: {str(get_current_image()) if get_current_image() else 'None'}")
    
    try:
        serve(host="localhost", port=5001)
    except KeyboardInterrupt:
        print("\nShutting down...")
        print("Final cleanup of orphaned database entries...")
        cleanup_orphaned_entries()
        print("Goodbye!")
