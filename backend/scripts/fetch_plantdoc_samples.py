"""Download the small tomato subset of the PlantDoc TEST split (late blight + healthy) for sanity evaluation."""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "data" / "plantdoc_samples")
API = "https://api.github.com/repos/pratikkayal/PlantDoc-Dataset/contents/test/"
SETS = {"late_blight": "Tomato leaf late blight", "healthy": "Tomato leaf"}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "agrisentry"})
    return urllib.request.urlopen(req, timeout=30).read()


for folder, remote in SETS.items():
    (OUT / folder).mkdir(parents=True, exist_ok=True)
    listing = json.loads(get(API + urllib.parse.quote(remote)))
    for item in listing:
        if item["type"] != "file":
            continue
        dest = OUT / folder / item["name"]
        if not dest.exists():
            url = ("https://raw.githubusercontent.com/pratikkayal/PlantDoc-Dataset/master/test/"
                   + urllib.parse.quote(remote) + "/" + urllib.parse.quote(item["name"], safe=""))
            try:
                dest.write_bytes(get(url))
            except Exception as e:
                print("skip", item["name"], e)
    print(folder, len(list((OUT / folder).glob("*"))))
