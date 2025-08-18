#!/usr/bin/env -S uv run python
"""Upload Hugging Face dataset to W&B Artifacts.

Usage:
    uv run python upload_to_wandb.py --dataset_path <path> --artifact_name <name> [options]
    
Examples:
    # Basic upload with required arguments
    uv run python upload_to_wandb.py \\
        --dataset_path data/my_dataset_hf \\
        --artifact_name my_dataset_v1
    
    # Upload with custom entity and project
    uv run python upload_to_wandb.py \\
        --dataset_path data/my_dataset_hf \\
        --artifact_name my_dataset_v1 \\
        --entity my_team \\
        --project my_project \\
        --description "My annotated dataset"
    
    # Upload with metadata
    uv run python upload_to_wandb.py \\
        --dataset_path data/my_dataset_hf \\
        --artifact_name my_dataset_v1 \\
        --metadata-json '{"source": "youtube", "annotator": "user1"}' \\
        --yes  # Skip confirmation prompt
"""

import wandb
from pathlib import Path
import json
import sys
from typing import Optional
from dataclasses import dataclass, field
from simple_parsing import ArgumentParser

@dataclass
class UploadArgs:
    """Arguments for uploading a dataset to W&B Artifacts."""
    
    dataset_path: str
    """Path to the Hugging Face dataset directory to upload"""
    
    artifact_name: str
    """Name for the W&B artifact"""
    
    entity: str = "milieu"
    """W&B entity (team or username)"""
    
    project: str = "track_limits_detection"
    """W&B project name"""
    
    artifact_type: str = "dataset"
    """Type of artifact (default: dataset)"""
    
    description: str = ""
    """Description of the artifact"""
    
    metadata: dict = field(default_factory=dict)
    """Additional metadata to attach to the artifact (as JSON string on CLI)"""
    
    yes: bool = False
    """Skip confirmation prompt"""

def upload_dataset_to_wandb(
    dataset_path: str,
    entity: str,
    project: str,
    artifact_name: str,
    artifact_type: str = "dataset",
    description: str = "",
    metadata: Optional[dict] = None
):
    """
    Upload a dataset directory to W&B Artifacts.
    
    Args:
        dataset_path: Path to the dataset directory
        entity: W&B entity (team or username)
        project: W&B project name
        artifact_name: Name for the artifact
        artifact_type: Type of artifact (default: "dataset")
        description: Description of the artifact
        metadata: Optional metadata dictionary to attach
    """
    dataset_path = Path(dataset_path)
    
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset path not found: {dataset_path}")
    
    print(f"Uploading dataset from: {dataset_path}")
    print(f"To W&B: {entity}/{project}")
    print(f"Artifact name: {artifact_name}")
    
    # Initialize W&B run
    run = wandb.init(
        entity=entity,
        project=project,
        job_type="dataset_upload",
        name=f"upload_{artifact_name}"
    )
    
    try:
        # Create artifact
        artifact = wandb.Artifact(
            name=artifact_name,
            type=artifact_type,
            description=description,
            metadata=metadata or {}
        )
        
        # Add the entire dataset directory
        print(f"Adding directory to artifact: {dataset_path}")
        artifact.add_dir(str(dataset_path))
        
        # If there's a metadata.json file, read it and add to artifact metadata
        metadata_file = dataset_path / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                dataset_metadata = json.load(f)
                # Merge with provided metadata
                artifact.metadata.update(dataset_metadata)
                print(f"Added metadata from {metadata_file}")
        
        # Log the artifact
        print("Logging artifact to W&B...")
        run.log_artifact(artifact)
        
        # Get the artifact URL
        artifact_url = f"https://wandb.ai/{entity}/{project}/artifacts/{artifact_type}/{artifact_name}"
        print("\n✅ Dataset uploaded successfully!")
        print(f"Artifact URL: {artifact_url}")
        
        # Finish the run
        run.finish()
        
        return artifact_url
        
    except Exception as e:
        print(f"Error uploading to W&B: {e}")
        run.finish(exit_code=1)
        raise

def main():
    """Main function to upload a dataset to W&B."""
    
    # Parse command-line arguments
    parser = ArgumentParser(
        prog="upload_to_wandb",
        description="Upload a Hugging Face dataset to W&B Artifacts"
    )
    parser.add_arguments(UploadArgs, dest="args")
    
    # Add custom handling for metadata JSON
    parser.add_argument(
        "--metadata-json",
        type=str,
        help="Additional metadata as JSON string (e.g., '{\"source\": \"youtube\", \"annotator\": \"user1\"}')"
    )
    
    parsed_args = parser.parse_args()
    args = parsed_args.args
    
    # Parse metadata JSON if provided
    if hasattr(parsed_args, 'metadata_json') and parsed_args.metadata_json:
        try:
            args.metadata = json.loads(parsed_args.metadata_json)
        except json.JSONDecodeError as e:
            print(f"Error parsing metadata JSON: {e}")
            return 1
    
    # Validate dataset path
    dataset_path = Path(args.dataset_path)
    if not dataset_path.exists():
        print(f"Error: Dataset not found at {dataset_path}")
        print("\nPlease ensure the dataset directory exists.")
        print("If you need to export from raw images, use:")
        print("  uv run python export2hf.py <raw_images_dir> --output_dir <hf_dataset_dir>")
        return 1
    
    print("="*60)
    print("W&B Dataset Upload")
    print("="*60)
    print(f"Dataset: {args.dataset_path}")
    print(f"Entity: {args.entity}")
    print(f"Project: {args.project}")
    print(f"Name: {args.artifact_name}")
    print(f"Type: {args.artifact_type}")
    if args.description:
        print(f"Description: {args.description}")
    if args.metadata:
        print(f"Metadata: {json.dumps(args.metadata, indent=2)}")
    print("="*60)
    
    # Check if W&B is logged in
    try:
        if not wandb.api.api_key:
            print("\nError: Not logged in to W&B")
            print("Please run: wandb login")
            return 1
    except AttributeError:
        print("\nError: Not logged in to W&B")
        print("Please run: wandb login")
        return 1
    except ImportError as e:
        print(f"\nError: W&B not installed: {e}")
        print("Please ensure W&B is installed: uv add wandb")
        print("Then login: wandb login")
        return 1
    
    # Confirm upload (unless --yes flag is used)
    if not args.yes:
        response = input(f"\nProceed with upload to {args.entity}/{args.project}? (y/n): ")
        if response.lower() != 'y':
            print("Upload cancelled.")
            return 0
    
    try:
        # Upload the dataset
        artifact_url = upload_dataset_to_wandb(
            dataset_path=args.dataset_path,
            entity=args.entity,
            project=args.project,
            artifact_name=args.artifact_name,
            artifact_type=args.artifact_type,
            description=args.description,
            metadata=args.metadata
        )
        
        print("\n" + "="*60)
        print("Upload Complete!")
        print("="*60)
        print("\nYour dataset is now available at:")
        print(f"  {artifact_url}")
        print("\nTo use it in another project:")
        print(f"  artifact = run.use_artifact('{args.entity}/{args.project}/{args.artifact_name}:latest')")
        print("  artifact_dir = artifact.download()")
        
        return 0
        
    except Exception as e:
        print(f"\nUpload failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

