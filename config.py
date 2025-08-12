"""Configuration module for the annotation app."""
import yaml
from pathlib import Path
from dataclasses import dataclass

@dataclass
class AppConfig:
    """Application configuration."""
    title: str = "Image Annotation Tool"
    description: str = "Annotate images"
    num_classes: int = 5
    annotations_file: str = "annotations.csv"
    images_folder: str = "images"
    max_history: int = 10
    allowed_extensions: tuple = ('.jpg', '.jpeg', '.png')
    
    @classmethod
    def from_yaml(cls, yaml_path: str = "config.yaml") -> "AppConfig":
        """Load configuration from YAML file."""
        config_path = Path(yaml_path)
        if config_path.exists():
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f)
                return cls(**data)
        return cls()
    
    @property
    def images_dir(self) -> Path:
        """Get images directory as Path object."""
        return Path(self.images_folder)
    
    @property
    def annotations_path(self) -> Path:
        """Get annotations file as Path object."""
        return Path(self.annotations_file)
    
    @property
    def rating_range(self) -> range:
        """Get valid rating range."""
        return range(1, self.num_classes + 1)

# Load configuration
config = AppConfig.from_yaml()