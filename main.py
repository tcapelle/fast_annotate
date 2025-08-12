"""Main application file - modular version with config.yaml support."""
from pathlib import Path
from fasthtml.common import *
from starlette.responses import FileResponse
import re

# Import our modules
from config import config
from models import AppState
from ui_components import (
    get_app_styles,
    get_app_script,
    create_progress_bar,
    create_rating_buttons,
    create_navigation_controls,
    create_help_text
)

# Initialize app
app, rt = fast_app()

# Initialize state
state = AppState()

@rt("/")
def index():
    """Main annotation interface."""
    if not state.image_files:
        return Titled(config.title,
            Div(f"No images found in {config.images_folder}/ directory", cls="container")
        )
    
    current_image = state.get_current_image()
    if not current_image:
        return Titled(config.title,
            Div("All images have been reviewed!", cls="container")
        )
    
    current_annotation = state.get_annotation_value(current_image.name)
    stats = state.get_progress_stats()
    
    return Titled(config.title,
        get_app_styles(),
        Div(
            create_progress_bar(stats, state.filter_unannotated),
            Div(
                f"Current: {current_image.name}",
                cls="progress"
            ),
            Div(
                Img(src=f"/{config.images_folder}/{current_image.name}", alt=current_image.name),
                cls="image-container"
            ),
            Div(config.description, cls="description") if config.description else None,
            Div(
                Div(
                    f"Current Rating: ",
                    Span(current_annotation if current_annotation > 0 else 'Not rated', id="rating-display"),
                    cls="current-rating"
                ),
                create_rating_buttons(current_annotation),
                create_navigation_controls(state),
                create_help_text(),
                cls="controls"
            ),
            cls="container"
        ),
        get_app_script()
    )

@rt(f"/{config.images_folder}/{{image_name:path}}")
def get_image(image_name: str):
    """Serve image files with security checks."""
    # Validate filename to prevent path traversal
    if not re.match(r'^[a-zA-Z0-9_.-]+\.(jpg|jpeg|png)$', image_name, re.IGNORECASE):
        return Response("Invalid filename", status_code=400)
    
    image_path = config.images_dir / image_name
    
    # Ensure the resolved path is within images directory
    try:
        if not str(image_path.resolve()).startswith(str(config.images_dir.resolve())):
            return Response("Access denied", status_code=403)
    except:
        return Response("Invalid path", status_code=400)
    
    if image_path.exists() and image_path.suffix.lower() in config.allowed_extensions:
        return FileResponse(
            str(image_path),
            headers={"Cache-Control": "public, max-age=3600"}
        )
    return Response("Image not found", status_code=404)

@rt("/rate/{rating:int}", methods=["POST"])
def rate(rating: int):
    """Save annotation and move to next image."""
    if rating not in config.rating_range:
        return index()
    
    current_image = state.get_current_image()
    if current_image:
        # Store in history for undo
        old_annotation = state.annotations.get(current_image.name, None)
        state.add_to_history(current_image.name, old_annotation)
        
        # Save annotation
        state.save_annotation(current_image.name, rating)
        
        # Move to next image
        state.navigate(1)
    
    return index()

@rt("/prev", methods=["POST"])
def prev():
    """Navigate to previous image."""
    state.navigate(-1)
    return index()

@rt("/next", methods=["POST"])
def next():
    """Navigate to next image."""
    state.navigate(1)
    return index()

@rt("/undo", methods=["POST"])
def undo():
    """Undo last annotation and go back to previous image."""
    state.undo_last_annotation()
    return index()

@rt("/toggle_filter", methods=["POST"])
def toggle_filter():
    """Toggle the filter for showing only unannotated images."""
    state.toggle_filter()
    return index()

if __name__ == "__main__":
    print(f"Starting {config.title}")
    print(f"Configuration:")
    print(f"  - Images folder: {config.images_folder}")
    print(f"  - Annotations file: {config.annotations_file}")
    print(f"  - Number of classes: {config.num_classes}")
    print(f"  - Annotating as: {state.username}")
    print(f"  - Total images: {len(state.image_files)}")
    print(f"  - Already annotated: {len(state.annotations)}")
    print(f"  - Starting at image {state.current_index + 1}: {state.get_current_image().name if state.get_current_image() else 'None'}")
    
    serve()