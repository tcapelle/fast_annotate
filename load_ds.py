from datasets import load_from_disk

ds_name = "./f1_game_images/hf_dataset"

ds = load_from_disk(ds_name)["train"]

print(ds)

print(ds[0])