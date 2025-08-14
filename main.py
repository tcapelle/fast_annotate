"""FastHTML Image Annotation Tool - Proper FastHTML implementation."""
from fasthtml.common import *
from starlette.responses import FileResponse, Response
from pathlib import Path
import yaml
import os
import re
from datetime import datetime
from dataclasses import dataclass
import simple_parsing as sp

@dataclass
class Config:
    title: str = "Image Annotation Tool"
    description: str = "Annotate images"
    num_classes: int = 5
    images_folder: str = "images"
    max_history: int = 10

config = sp.parse(Config, config_path="./config.yaml")

# Database setup
db = database(f'{config.images_folder}/annotations.db')

class Annotation:
    id: int
    image_path: str
    rating: int
    username: str
    timestamp: str
    marked: bool = False  # New field for marking images
    
annotations = db.create(Annotation, pk='id')

# Database is the single source of truth - no CSV imports needed

# Initialize FastHTML app with custom styles
app, rt = fast_app(
    hdrs=(
        Link(rel='stylesheet', href='/styles.css'),
    ),
    pico=False,  # We're using custom styles instead of Pico CSS
    debug=False  # Set to True for development
)

# State management
class AppState:
    def __init__(self):
        self.current_index = 0
        self.filter_unannotated = False
        self.history = []

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
        return Titled(config.title,
            Div("All images have been reviewed!", 
                style="max-width: 800px; margin: 2rem auto; padding: 2rem; background: white; border-radius: 8px;")
        )
    
    annotation_data = get_annotation_for_image(current_image)
    current_rating = annotation_data['rating']
    is_marked = annotation_data['marked']
    stats = get_progress_stats()
    
    return Titled(config.title,
        Div(
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
                Span("X", cls="kbd"), " mark/unmark",
                    cls="help-text"
                ),
                cls="controls"
            ),
            cls="container"
        ),
        Script(f"""
            // Keyboard shortcuts
            document.addEventListener('keydown', function(e) {{
                if (e.target.tagName === 'INPUT') return;
                
                // Number keys for rating
                if (e.key >= '1' && e.key <= '{config.num_classes}') {{
                    const btn = document.querySelectorAll('.rating-btn')[parseInt(e.key) - 1];
                    if (btn) btn.click();
                    e.preventDefault();
                    return;
                }}
                
                // Navigation shortcuts
                switch(e.key) {{
                    case 'ArrowLeft':
                        document.querySelector('.nav-btn:not(.undo-btn)')?.click();
                        e.preventDefault();
                        break;
                    case 'ArrowRight':
                        document.querySelector('.nav-btn:last-child')?.click();
                        e.preventDefault();
                        break;
                    case 'u': case 'U':
                        document.querySelector('.undo-btn')?.click();
                        e.preventDefault();
                        break;
                    case 'x': case 'X':
                        document.querySelector('#mark-checkbox')?.click();
                        e.preventDefault();
                        break;
                }}
            }});
        """)
    )

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
    """Save annotation and move to next image."""
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
            'index': state.current_index
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
        
        # Move to next image
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
    """Undo last annotation."""
    if state.history:
        last_action = state.history.pop()
        
        # Restore annotation
        image_name = last_action['image_name']
        old_rating = last_action['old_rating']
        
        if old_rating == 0:
            # Delete annotation
            # Use parameterized query
            existing = annotations("image_path=?", (image_name,), limit=1)
            if existing:
                annotations.delete(existing[0].id)
        else:
            # Restore old rating
            # Use parameterized query
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
    
    # Reset to first unannotated if filter is now active
    if state.filter_unannotated:
        images = get_image_files()
        annotated_images = {a.image_path for a in annotations()}
        for i, img in enumerate(images):
            if str(img) not in annotated_images:
                state.current_index = i
                break
    
    return index()

def navigate(direction):
    """Navigate through images."""
    images = get_image_files()
    
    if not state.filter_unannotated:
        # Normal navigation
        new_index = state.current_index + direction
        if 0 <= new_index < len(images):
            state.current_index = new_index
    else:
        # Skip annotated images
        annotated_images = {a.image_path for a in annotations()}
        new_index = state.current_index
        
        while True:
            new_index += direction
            if not (0 <= new_index < len(images)):
                break
            if str(images[new_index]) not in annotated_images:
                state.current_index = new_index
                break

# Find first unannotated image on startup
def find_first_unannotated():
    """Find the index of the first unannotated image."""
    images = get_image_files()
    annotated_images = {a.image_path for a in annotations()}
    for i, img in enumerate(images):
        if str(img) not in annotated_images:
            return i
    return 0

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
    
    images = get_image_files()
    print(f"  - Total images: {len(images)}")
    
    stats = get_progress_stats()
    print(f"  - Already annotated: {stats['annotated']}")
    print(f"  - Starting at image {state.current_index + 1}: {str(get_current_image()) if get_current_image() else 'None'}")
    
    serve()