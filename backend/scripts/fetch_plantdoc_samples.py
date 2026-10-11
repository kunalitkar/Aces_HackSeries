"""Download the tomato classes of the PlantDoc TEST split for external evaluation (no training use)."""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "data" / "plantdoc_samples")
API = "https://api.github.com/repos/pratikkayal/PlantDoc-Dataset/contents/test/"
RAW = "https://raw.githubusercontent.com/pratikkayal/PlantDoc-Dataset/master/test/"

# local folder -> (PlantDoc test folder, matching model class)
CLASS_MAP = {
    "late_blight": ("Tomato leaf late blight", "Tomato___Late_blight"),
    "healthy": ("Tomato leaf", "Tomato___healthy"),
    "early_blight": ("Tomato Early blight leaf", "Tomato___Early_blight"),
    "septoria_leaf_spot": ("Tomato Septoria leaf spot", "Tomato___Septoria_leaf_spot"),
    "bacterial_spot": ("Tomato leaf bacterial spot", "Tomato___Bacterial_spot"),
    "mosaic_virus": ("Tomato leaf mosaic virus", "Tomato___Tomato_mosaic_virus"),
    "yellow_leaf_curl_virus": ("Tomato leaf yellow virus", "Tomato___Tomato_Yellow_Leaf_Curl_Virus"),
    "leaf_mold": ("Tomato mold leaf", "Tomato___Leaf_Mold"),
}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "agrisentry"})
    return urllib.request.urlopen(req, timeout=30).read()


if __name__ == "__main__":
    for folder, (remote, _) in CLASS_MAP.items():
        (OUT / folder).mkdir(parents=True, exist_ok=True)
        for item in json.loads(get(API + urllib.parse.quote(remote))):
            dest = OUT / folder / item["name"]
            if item["type"] != "file" or dest.exists():
                continue
            try:
                dest.write_bytes(get(RAW + urllib.parse.quote(remote) + "/" + urllib.parse.quote(item["name"], safe="")))
            except Exception as e:
                print("skip", item["name"], e)
        print(folder, len(list((OUT / folder).glob("*"))))
