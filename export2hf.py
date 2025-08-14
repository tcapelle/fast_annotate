#!/usr/bin/env python3
"""Export SQLite annotation database to Hugging Face dataset format."""

import sqlite3
from pathlib import Path
from dataclasses import dataclass
from PIL import Image
import pandas as pd
from datasets import Dataset, Features, Value, Image as HFImage, DatasetDict
import json
import simple_parsing as sp


def load_annotations(db_path):
    """Load annotations from SQLite database."""
    conn = sqlite3.connect(db_path)
    query = """
    SELECT 
        image_path,
        rating,
        username,
        timestamp,
        marked
    FROM annotation
    ORDER BY image_path
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def export_to_hf_dataset(images_folder, output_dir=None, split="train"):
    """Export annotations to Hugging Face dataset format.
    
    Args:
        images_folder: Path to the folder containing images and annotations.db
        output_dir: Output directory for the dataset (defaults to images_folder/hf_dataset)
        split: Dataset split name (default: "train")
    """
    images_folder = Path(images_folder)
    db_path = images_folder / "annotations.db"
    
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}")
    
    # Set default output directory
    if output_dir is None:
        output_dir = images_folder / "hf_dataset"
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(exist_ok=True, parents=True)
    
    print(f"Loading annotations from {db_path}")
    annotations_df = load_annotations(db_path)
    
    if annotations_df.empty:
        print("No annotations found in database")
        return
    
    print(f"Found {len(annotations_df)} annotated images")
    
    # Prepare data for HF dataset
    dataset_dict = {
        "image": [],
        "image_path": [],
        "rating": [],
        "username": [],
        "timestamp": [],
        "marked": []
    }
    
    # Process each annotation
    for _, row in annotations_df.iterrows():
        image_path = images_folder / row['image_path']
        
        if not image_path.exists():
            print(f"Warning: Image not found: {image_path}")
            continue
        
        try:
            # Load and verify image
            img = Image.open(image_path)
            img.verify()  # Verify it's a valid image
            
            # Re-open after verify (verify closes the file)
            img = Image.open(image_path)
            
            # Add to dataset
            dataset_dict["image"].append(img)
            dataset_dict["image_path"].append(row['image_path'])
            dataset_dict["rating"].append(row['rating'])
            dataset_dict["username"].append(row['username'])
            dataset_dict["timestamp"].append(row['timestamp'])
            dataset_dict["marked"].append(bool(row['marked']))
            
        except Exception as e:
            print(f"Error loading image {image_path}: {e}")
            continue
    
    if not dataset_dict["image"]:
        print("No valid images found")
        return
    
    print(f"Creating dataset with {len(dataset_dict['image'])} images")
    
    # Define features
    features = Features({
        "image": HFImage(),
        "image_path": Value("string"),
        "rating": Value("int32"),
        "username": Value("string"),
        "timestamp": Value("string"),
        "marked": Value("bool")
    })
    
    # Create dataset
    dataset = Dataset.from_dict(dataset_dict, features=features)
    
    # Create dataset dict with split
    dataset_dict = DatasetDict({split: dataset})
    
    # Save dataset
    print(f"Saving dataset to {output_dir}")
    dataset_dict.save_to_disk(str(output_dir))
    
    # Also save metadata
    metadata = {
        "num_images": len(dataset_dict[split]),
        "split": split,
        "images_folder": str(images_folder),
        "rating_distribution": dataset_dict[split]["rating"].count(lambda x: True),
        "annotators": list(set(dataset_dict[split]["username"])),
        "marked_count": sum(dataset_dict[split]["marked"])
    }
    
    # Calculate rating distribution
    ratings = dataset_dict[split]["rating"]
    rating_dist = {}
    for r in ratings:
        rating_dist[r] = rating_dist.get(r, 0) + 1
    metadata["rating_distribution"] = rating_dist
    
    with open(output_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\nDataset export complete!")
    print(f"  - Total images: {metadata['num_images']}")
    print(f"  - Rating distribution: {metadata['rating_distribution']}")
    print(f"  - Marked images: {metadata['marked_count']}")
    print(f"  - Output directory: {output_dir}")
    
    return dataset_dict


@dataclass
class ExportConfig:
    """Configuration for exporting annotations to Hugging Face dataset."""
    images_folder: str = sp.field(default="images", positional=True, help="The folder containing the images and annotations.db")
    output_dir: str = sp.field(default=None, help="The folder to export the dataset to. If not provided, it will be the same as the images_folder.")
    split: str = sp.field(default="train", help="The split to export. Default is 'train'.")


def main():
    config = sp.parse(ExportConfig)
    
    try:
        dataset = export_to_hf_dataset(
            config.images_folder,
            config.output_dir,
            config.split
        )
        
        if dataset:
            # Verify the exported dataset by loading it back
            output_dir = config.output_dir if config.output_dir else Path(config.images_folder) / "hf_dataset"
            print("\n" + "="*50)
            print("Verifying exported dataset...")
            print("="*50)
            
            from datasets import load_from_disk
            loaded_ds = load_from_disk(str(output_dir))
            
            print(f"\nLoaded dataset:")
            print(loaded_ds)
            
            if config.split in loaded_ds:
                print(f"\n{config.split} split:")
                print(loaded_ds[config.split])
                
                if len(loaded_ds[config.split]) > 0:
                    print(f"\nFirst example from {config.split} split:")
                    first_example = loaded_ds[config.split][0]
                    # Don't print the actual image data, just metadata
                    example_to_print = {k: v for k, v in first_example.items() if k != 'image'}
                    example_to_print['image'] = f"<PIL Image {first_example['image'].size if hasattr(first_example['image'], 'size') else 'N/A'}>"
                    print(example_to_print)
            
            print("\n✅ Dataset exported and verified successfully!")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())