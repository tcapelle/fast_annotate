import wandb
from pathlib import Path
import simple_parsing as sp
from dataclasses import dataclass

@dataclass
class ExportConfig:
    """Configuration for exporting annotations to Hugging Face dataset."""
    images_folder: Path = sp.field(default=Path("images"), positional=True, help="The folder containing the images and annotations.db")
    wandb_project: str = sp.field(default="track_limits_detection", help="The project name to use in wandb")
    wandb_entity: str = sp.field(default="milieu", help="The entity name to use in wandb")


def has_hf_ds(images_folder: Path) -> bool:
    arrow_files = list(images_folder.rglob("*.arrow"))
    return arrow_files

def has_annotations(images_folder: Path) -> bool:
    return (images_folder/"annotations.db").exists()

def main():
    config = sp.parse(ExportConfig)
    wandb.init(project=config.wandb_project, entity=config.wandb_entity)
    
    assert has_annotations(config.images_folder), "No annotations found"

    arrow_files = has_hf_ds(config.images_folder)
    assert len(arrow_files) > 0, "No Hugging Face dataset found, call `export2hf.py` first"

    if arrow_files[0].parent.name == "train":
        hf_folder = arrow_files[0].parent.parent
    else:
        hf_folder = arrow_files[0].parent
    
    hf_artifact = wandb.Artifact(name=config.images_folder.name+"_hf", type="dataset")
    hf_artifact.add_dir(hf_folder)
    wandb.log_artifact(hf_artifact)

    db_artifact = wandb.Artifact(name=config.images_folder.name, type="dataset")
    db_artifact.add_dir(config.images_folder)
    wandb.log_artifact(db_artifact)



if __name__ == "__main__":
    main()