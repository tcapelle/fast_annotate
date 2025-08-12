"""UI components for the annotation app."""
from fasthtml.common import *
from config import config

def get_app_styles():
    """Return application styles."""
    return Style("""
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 10px; background: #f5f5f5; }
        h1 { color: #212529 !important; font-weight: 600; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .image-container { text-align: center; margin-bottom: 10px; position: relative; min-height: 400px; display: flex; align-items: center; justify-content: center; }
        .image-container img { max-width: 100%; max-height: 400px; border: 2px solid #ddd; border-radius: 4px; }
        .controls { display: flex; flex-direction: column; align-items: center; gap: 10px; }
        .rating-controls { display: flex; align-items: center; gap: 10px; }
        .slider { width: 250px; }
        .rating-buttons { display: flex; gap: 8px; }
        .rating-btn { padding: 8px 12px; border: 2px solid #007bff; background: white; color: #007bff; cursor: pointer; border-radius: 4px; font-size: 14px; font-weight: bold; transition: all 0.2s; }
        .rating-btn:hover { transform: scale(1.05); }
        .rating-btn.active { background: #007bff; color: white; }
        .nav-controls { display: flex; gap: 8px; margin-top: 10px; }
        .nav-btn { padding: 8px 16px; border: none; background: #28a745; color: white; cursor: pointer; border-radius: 4px; font-size: 13px; transition: background 0.2s; }
        .nav-btn:hover { background: #218838; }
        .nav-btn:disabled { background: #ccc; cursor: not-allowed; }
        .undo-btn { background: #ffc107; color: black; }
        .undo-btn:hover { background: #e0a800; }
        .progress { margin-bottom: 8px; font-size: 13px; color: #333; font-weight: 500; }
        .progress-bar { width: 100%; height: 3px; background: #e9ecef; border-radius: 2px; margin: 5px 0 10px 0; }
        .progress-fill { height: 100%; background: #007bff; border-radius: 2px; transition: width 0.3s; }
        .current-rating { font-size: 16px; font-weight: bold; color: #007bff; margin: 8px 0; }
        .kbd { padding: 2px 4px; font-size: 10px; color: #fff; background-color: #333; border-radius: 3px; }
        .help-text { font-size: 11px; color: #666; margin-top: 8px; }
        .description { font-size: 13px; color: #495057; margin-bottom: 10px; text-align: center; font-weight: 500; }
    """)

def get_app_script(current_annotation: int):
    """Return application JavaScript."""
    return Script(f"""
        let currentRating = {current_annotation or 3};
        const NUM_CLASSES = {config.num_classes};
        
        function setRating(rating) {{
            if (rating < 1 || rating > NUM_CLASSES) return;
            
            currentRating = rating;
            document.getElementById('rating-slider').value = rating;
            
            // Update button styles
            document.querySelectorAll('.rating-btn').forEach((btn, index) => {{
                btn.classList.toggle('active', index === rating - 1);
            }});
            
            // Save and advance to next image
            saveAndNext(rating);
        }}
        
        function saveAndNext(rating) {{
            fetch('/annotate_and_next', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{rating: rating}})
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    location.reload();
                }}
            }})
            .catch(error => console.error('Error:', error));
        }}
        
        function navigate(direction) {{
            fetch('/navigate', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{direction: direction}})
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    location.reload();
                }}
            }})
            .catch(error => console.error('Error:', error));
        }}
        
        function undoAnnotation() {{
            fetch('/undo', {{method: 'POST'}})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    location.reload();
                }}
            }})
            .catch(error => console.error('Error:', error));
        }}
        
        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {{
            if (e.target.tagName === 'INPUT' && e.target.type !== 'range') return;
            
            // Dynamic number key handling based on num_classes
            if (e.key >= '1' && e.key <= String(NUM_CLASSES)) {{
                setRating(parseInt(e.key));
                e.preventDefault();
                return;
            }}
            
            switch(e.key) {{
                case 'ArrowLeft':
                    navigate(-1);
                    e.preventDefault();
                    break;
                case 'ArrowRight':
                    navigate(1);
                    e.preventDefault();
                    break;
                case 'u': case 'U':
                    undoAnnotation();
                    e.preventDefault();
                    break;
            }}
        }});
        
        // Update slider display
        document.getElementById('rating-slider')?.addEventListener('input', function(e) {{
            currentRating = parseInt(e.target.value);
            
            // Update button styles
            document.querySelectorAll('.rating-btn').forEach((btn, index) => {{
                btn.classList.toggle('active', index === currentRating - 1);
            }});
            
            // Update display
            document.getElementById('rating-display').textContent = currentRating;
        }});
    """)

def create_progress_bar(stats: dict) -> Div:
    """Create a progress bar component."""
    return Div(
        Div(
            f"Image {stats['current']} of {stats['total']} | ",
            f"Annotated: {stats['annotated']}/{stats['total']} ({stats['percentage']}%)",
            cls="progress"
        ),
        Div(
            Div(style=f"width: {stats['percentage']}%", cls="progress-fill"),
            cls="progress-bar"
        )
    )

def create_rating_buttons(current_annotation: int) -> Div:
    """Create rating buttons based on num_classes."""
    buttons = []
    for i in config.rating_range:
        buttons.append(
            Button(
                str(i), type="button",
                cls=f"rating-btn {'active' if current_annotation == i else ''}",
                onclick=f"setRating({i})"
            )
        )
    return Div(*buttons, cls="rating-buttons")

def create_navigation_controls(state) -> Div:
    """Create navigation control buttons."""
    return Div(
        Button(
            "← Previous", type="button", cls="nav-btn",
            onclick="navigate(-1)",
            disabled=state.current_index == 0
        ),
        Button(
            "Undo (U)", type="button", cls="nav-btn undo-btn",
            onclick="undoAnnotation()",
            disabled=len(state.annotation_history) == 0
        ),
        Button(
            "Next →", type="button", cls="nav-btn",
            onclick="navigate(1)",
            disabled=state.current_index >= len(state.image_files) - 1
        ),
        cls="nav-controls"
    )

def create_help_text() -> Div:
    """Create keyboard shortcuts help text."""
    return Div(
        "Keyboard shortcuts: ",
        Span(f"1-{config.num_classes}", cls="kbd"), " rate & next | ",
        Span("←→", cls="kbd"), " navigate | ",
        Span("U", cls="kbd"), " undo",
        cls="help-text"
    )