# Fast Image Annotation

![](fast_annotate.png)

A fastHTML image annotator - Simple, keyboard-driven image annotation tool built with FastHTML.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![FastHTML](https://img.shields.io/badge/FastHTML-latest-green)
![License](https://img.shields.io/badge/license-MIT-blue)

## Features

- **Fast annotation** - Keyboard shortcuts (1-5 keys) for instant rating and auto-advance
- **Smart resume** - Automatically starts from the first unannotated image
- **Undo support** - Quickly fix mistakes with the U key
- **Progress tracking** - Visual progress bar and statistics
- **Multi-user support** - Tracks username and timestamp for each annotation
- **Configurable** - YAML-based configuration for flexibility

## Quick Start

```bash
# Clone and install
git clone https://github.com/yourusername/fast_image_annotation.git
cd fast_image_annotation
pip install .

# Configure (edit config.yaml)
# Place images in images/ folder

# Run
python main.py
```

Open browser to `http://localhost:5001`

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1-5` | Rate and advance to next |
| `Left/Right Arrow` | Navigate images |
| `U` | Undo last annotation |

## Configuration

Edit `config.yaml`:

```yaml
title: "Image Annotation Tool"
description: "Rate each image from 1 to 5"
num_classes: 5  # Number of rating classes
annotations_file: "annotations.csv"
images_folder: "images"
```

## Output Format

CSV with columns: `image_path`, `class`, `username`, `timestamp`

```csv
image_path,class,username,timestamp
img001.jpg,3,john,2024-08-12T10:45:23.123456
img002.jpg,5,john,2024-08-12T10:45:25.654321
```

## Project Structure

```
main.py              # Application entry point
config.py            # Configuration management
models.py            # Data models
ui_components.py     # UI components
config.yaml          # User configuration
pyproject.toml       # Project metadata and dependencies
```

## License

MIT License - see [LICENSE](LICENSE) file.

## Acknowledgments

Built with [FastHTML](https://github.com/AnswerDotAI/fasthtml) - The fast, Pythonic way to create web applications, enjoy.