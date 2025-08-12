"""Data models and state management."""
import csv
import threading
import os
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from config import config

class AppState:
    """Application state manager."""
    
    def __init__(self):
        self.annotation_history: List[Tuple[str, int]] = []
        self.annotations = self.load_annotations()
        self.csv_lock = threading.Lock()
        self.image_files = self._load_images()
        self.current_index = self._find_first_unannotated()
        self.username = os.environ.get('USER') or os.environ.get('USERNAME') or 'unknown'
        self.filter_unannotated = False  # Filter to show only unannotated images
    
    def _load_images(self) -> List[Path]:
        """Load all image files from the configured directory."""
        images = []
        if config.images_dir.exists():
            for ext in config.allowed_extensions:
                images.extend(config.images_dir.glob(f"*{ext}"))
        return sorted(images)
    
    def _find_first_unannotated(self) -> int:
        """Find the index of the first unannotated image."""
        for i, img_file in enumerate(self.image_files):
            if img_file.name not in self.annotations:
                return i
        # If all images are annotated, return 0
        return 0 if self.image_files else 0
    
    def load_annotations(self) -> Dict[str, Dict]:
        """Load existing annotations from CSV with metadata."""
        annotations = {}
        if config.annotations_path.exists():
            try:
                with open(config.annotations_path, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Support both old and new column names
                        image_col = 'image_path' if 'image_path' in row else 'image_name'
                        class_col = 'class' if 'class' in row else 'annotation'
                        if image_col in row and class_col in row:
                            value = int(row[class_col])
                            # Validate that the rating is within range
                            if value in config.rating_range:
                                annotations[row[image_col]] = {
                                    'class': value,
                                    'username': row.get('username', 'unknown'),
                                    'timestamp': row.get('timestamp', '')
                                }
            except Exception as e:
                print(f"Error loading annotations: {e}")
        return annotations
    
    def save_all_annotations(self) -> bool:
        """Save all annotations to CSV file with metadata."""
        try:
            with self.csv_lock:
                with open(config.annotations_path, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=['image_path', 'class', 'username', 'timestamp'])
                    writer.writeheader()
                    for img_name, data in self.annotations.items():
                        if isinstance(data, dict):
                            writer.writerow({
                                'image_path': img_name, 
                                'class': data['class'],
                                'username': data.get('username', self.username),
                                'timestamp': data.get('timestamp', datetime.now().isoformat())
                            })
                        else:
                            # Handle old format (just the class value)
                            writer.writerow({
                                'image_path': img_name, 
                                'class': data,
                                'username': self.username,
                                'timestamp': datetime.now().isoformat()
                            })
            return True
        except Exception as e:
            print(f"Error saving annotations: {e}")
            return False
    
    def save_annotation(self, image_name: str, rating: int) -> bool:
        """Save a single annotation with metadata."""
        if rating not in config.rating_range:
            return False
        
        self.annotations[image_name] = {
            'class': rating,
            'username': self.username,
            'timestamp': datetime.now().isoformat()
        }
        return self.save_all_annotations()
    
    def add_to_history(self, image_name: str, old_annotation):
        """Add annotation to history for undo functionality."""
        self.annotation_history.append((image_name, old_annotation))
        if len(self.annotation_history) > config.max_history:
            self.annotation_history = self.annotation_history[-config.max_history:]
    
    def get_current_image(self) -> Optional[Path]:
        """Get current image file."""
        if not self.image_files or self.current_index >= len(self.image_files):
            return None
        return self.image_files[self.current_index]
    
    def get_annotation_value(self, image_name: str) -> int:
        """Get the class value for an image."""
        annotation = self.annotations.get(image_name)
        if isinstance(annotation, dict):
            return annotation.get('class', 0)
        return annotation if annotation else 0
    
    def navigate(self, direction: int) -> bool:
        """Navigate to next/previous image, optionally skipping annotated ones."""
        if not self.filter_unannotated:
            # Normal navigation
            new_index = self.current_index + direction
            if 0 <= new_index < len(self.image_files):
                self.current_index = new_index
                return True
        else:
            # Skip annotated images when filter is on
            new_index = self.current_index
            while True:
                new_index += direction
                if not (0 <= new_index < len(self.image_files)):
                    return False
                # Check if this image is unannotated
                if self.image_files[new_index].name not in self.annotations:
                    self.current_index = new_index
                    return True
                # If we've gone through all images and found none unannotated
                if abs(new_index - self.current_index) >= len(self.image_files):
                    return False
        return False
    
    def undo_last_annotation(self) -> Optional[str]:
        """Undo the last annotation and return the image name."""
        if not self.annotation_history:
            return None
        
        image_name, old_annotation = self.annotation_history.pop()
        
        # Find and set the index of the image we're undoing
        for i, img_file in enumerate(self.image_files):
            if img_file.name == image_name:
                self.current_index = i
                break
        
        if old_annotation is None or (isinstance(old_annotation, dict) and old_annotation.get('class', 0) == 0):
            # Remove annotation if it was previously unrated
            if image_name in self.annotations:
                del self.annotations[image_name]
        else:
            self.annotations[image_name] = old_annotation
        
        self.save_all_annotations()
        return image_name
    
    def get_progress_stats(self) -> Dict[str, int]:
        """Get annotation progress statistics."""
        total = len(self.image_files)
        annotated = len(self.annotations)
        return {
            'current': self.current_index + 1,
            'total': total,
            'annotated': annotated,
            'remaining': total - annotated,
            'percentage': round(100 * annotated / total) if total > 0 else 0
        }
    
    def toggle_filter(self) -> None:
        """Toggle the filter for showing only unannotated images."""
        self.filter_unannotated = not self.filter_unannotated
        
        # If filter is now on and current image is annotated, find next unannotated
        if self.filter_unannotated and self.get_current_image():
            current_img = self.get_current_image()
            if current_img.name in self.annotations:
                # Try to find next unannotated image
                original_index = self.current_index
                if not self.navigate(1):
                    # If forward navigation failed, try backward
                    self.current_index = original_index
                    if not self.navigate(-1):
                        # No unannotated images found, keep current position
                        self.current_index = original_index