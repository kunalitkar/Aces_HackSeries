"""Download the PlantDoc TEST split (all classes that map to a model class) for external evaluation (no training use)."""
import json
import re
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
    "apple_scab": ("Apple Scab Leaf", "Apple___Apple_scab"),
    "apple_healthy": ("Apple leaf", "Apple___healthy"),
    "apple_rust": ("Apple rust leaf", "Apple___Cedar_apple_rust"),
    "pepper_bacterial_spot": ("Bell_pepper leaf spot", "Pepper,_bell___Bacterial_spot"),
    "pepper_healthy": ("Bell_pepper leaf", "Pepper,_bell___healthy"),
    "blueberry_healthy": ("Blueberry leaf", "Blueberry___healthy"),
    "cherry_healthy": ("Cherry leaf", "Cherry_(including_sour)___healthy"),
    "corn_gray_leaf_spot": ("Corn Gray leaf spot", "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot"),
    "corn_northern_leaf_blight": ("Corn leaf blight", "Corn_(maize)___Northern_Leaf_Blight"),
    "corn_common_rust": ("Corn rust leaf", "Corn_(maize)___Common_rust_"),
    "peach_healthy": ("Peach leaf", "Peach___healthy"),
    "potato_early_blight": ("Potato leaf early blight", "Potato___Early_blight"),
    "potato_late_blight": ("Potato leaf late blight", "Potato___Late_blight"),
    "raspberry_healthy": ("Raspberry leaf", "Raspberry___healthy"),
    "soybean_healthy": ("Soyabean leaf", "Soybean___healthy"),
    "squash_powdery_mildew": ("Squash Powdery mildew leaf", "Squash___Powdery_mildew"),
    "strawberry_healthy": ("Strawberry leaf", "Strawberry___healthy"),
    "grape_black_rot": ("grape leaf black rot", "Grape___Black_rot"),
    "grape_healthy": ("grape leaf", "Grape___healthy"),
}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "agrisentry"})
    return urllib.request.urlopen(req, timeout=30).read()


if __name__ == "__main__":
    for folder, (remote, _) in CLASS_MAP.items():
        (OUT / folder).mkdir(parents=True, exist_ok=True)
        for item in json.loads(get(API + urllib.parse.quote(remote))):
            dest = OUT / folder / re.sub(r'[<>:"/\|?*]', "_", item["name"])[:150]  # Windows-safe name
            if item["type"] != "file" or dest.exists():
                continue
            try:
                dest.write_bytes(get(RAW + urllib.parse.quote(remote) + "/" + urllib.parse.quote(item["name"], safe="")))
            except Exception as e:
                print("skip", item["name"], e)
        print(folder, len(list((OUT / folder).glob("*"))))
