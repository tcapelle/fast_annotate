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
        .folder-name { color: #007bff; font-weight: 600; }
        .progress-bar { width: 100%; height: 3px; background: #e9ecef; border-radius: 2px; margin: 5px 0 10px 0; }
        .progress-fill { height: 100%; background: #007bff; border-radius: 2px; transition: width 0.3s; }
        .filter-container { margin: 8px 0; text-align: center; }
        .filter-label { font-size: 13px; color: #495057; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; }
        .filter-checkbox { cursor: pointer; }
        .current-rating { font-size: 16px; font-weight: bold; color: #007bff; margin: 8px 0; }
        .kbd { padding: 2px 4px; font-size: 10px; color: #fff; background-color: #333; border-radius: 3px; }
        .help-text { font-size: 11px; color: #666; margin-top: 8px; }
        .description { font-size: 13px; color: #495057; margin-bottom: 10px; text-align: center; font-weight: 500; }
    """)

def get_app_script():
    """Return application JavaScript for keyboard shortcuts."""
    return Script(f"""
        // Keyboard shortcuts only - HTMX handles all interactions
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
            }}
        }});
    """)

def create_progress_bar(stats: dict, filter_active: bool = False) -> Div:
    """Create a progress bar component with folder info and filter."""
    return Div(
        Div(
            f"Image {stats['current']} of {stats['total']} | ",
            f"Annotated: {stats['annotated']}/{stats['total']} ({stats['percentage']}%) | ",
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
                    checked=filter_active,
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
    )

def create_rating_buttons(current_annotation: int) -> Div:
    """Create rating buttons based on num_classes."""
    buttons = []
    for i in config.rating_range:
        buttons.append(
            Button(
                str(i),
                cls=f"rating-btn {'active' if current_annotation == i else ''}",
                hx_post=f"/rate/{i}",
                hx_target="body",
                hx_swap="outerHTML"
            )
        )
    return Div(*buttons, cls="rating-buttons")

def create_navigation_controls(state) -> Div:
    """Create navigation control buttons."""
    return Div(
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
            disabled=len(state.annotation_history) == 0
        ),
        Button(
            "Next →", cls="nav-btn",
            hx_post="/next",
            hx_target="body",
            hx_swap="outerHTML",
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