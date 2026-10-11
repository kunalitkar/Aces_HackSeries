# PlantDoc external evaluation

Generated 2026-10-11T09:21:55.082486+00:00 · model `efficientnet_v2_s@BiernyVR/crop-disease-classifier (weights sha256 038e6093)`

PlantDoc test split (github.com/pratikkayal/PlantDoc-Dataset), images matching a model class. **236 images** evaluated, 0 rejected by upload validation. Field photos; PlantDoc labels are image-level and somewhat noisy. Small per-class samples: treat as indicative, not a benchmark.

| Mode | Images | Correct | Accuracy | Macro recall |
|---|---:|---:|---:|---:|
| Unrestricted, all classes | 236 | 48 | 20.3% | 19.5% |
| Unrestricted, multi-class crops only | 204 | 37 | 18.1% | 17.1% |
| Crop-conditioned, multi-class crops | 204 | 80 | 39.2% | 37.2% |

Crop identified correctly (unrestricted): 36.4%

## Per class
| True class | n | Unrestricted | Crop-conditioned |
|---|---:|---:|---:|
| Apple___Apple_scab | 10 | 1/10 | 5/10 |
| Apple___Cedar_apple_rust | 10 | 0/10 | 1/10 |
| Apple___healthy | 9 | 0/9 | 4/9 |
| Blueberry___healthy | 11 | 5/11 | n/a (single-class crop) |
| Cherry_(including_sour)___healthy | 10 | 0/10 | 6/10 |
| Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot | 4 | 1/4 | 1/4 |
| Corn_(maize)___Common_rust_ | 10 | 8/10 | 9/10 |
| Corn_(maize)___Northern_Leaf_Blight | 12 | 2/12 | 2/12 |
| Grape___Black_rot | 8 | 1/8 | 2/8 |
| Grape___healthy | 12 | 6/12 | 9/12 |
| Peach___healthy | 9 | 0/9 | 4/9 |
| Pepper,_bell___Bacterial_spot | 9 | 1/9 | 1/9 |
| Pepper,_bell___healthy | 8 | 5/8 | 8/8 |
| Potato___Early_blight | 8 | 2/8 | 6/8 |
| Potato___Late_blight | 8 | 0/8 | 2/8 |
| Raspberry___healthy | 7 | 2/7 | n/a (single-class crop) |
| Soybean___healthy | 8 | 2/8 | n/a (single-class crop) |
| Squash___Powdery_mildew | 6 | 2/6 | n/a (single-class crop) |
| Strawberry___healthy | 8 | 0/8 | 1/8 |
| Tomato___Bacterial_spot | 9 | 1/9 | 1/9 |
| Tomato___Early_blight | 9 | 2/9 | 5/9 |
| Tomato___Late_blight | 10 | 5/10 | 8/10 |
| Tomato___Leaf_Mold | 6 | 0/6 | 0/6 |
| Tomato___Septoria_leaf_spot | 11 | 2/11 | 5/11 |
| Tomato___Tomato_Yellow_Leaf_Curl_Virus | 6 | 0/6 | 0/6 |
| Tomato___Tomato_mosaic_virus | 10 | 0/10 | 0/10 |
| Tomato___healthy | 8 | 0/8 | 0/8 |

## Most common confusions (crop-conditioned)
| True | Predicted | Count |
|---|---|---:|
| Corn_(maize)___Northern_Leaf_Blight | Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot | 9 |
| Pepper,_bell___Bacterial_spot | Pepper,_bell___healthy | 8 |
| Strawberry___healthy | Strawberry___Leaf_scorch | 7 |
| Tomato___healthy | Tomato___Early_blight | 6 |
| Apple___Cedar_apple_rust | Apple___Black_rot | 6 |
| Tomato___Tomato_Yellow_Leaf_Curl_Virus | Tomato___Early_blight | 5 |
| Peach___healthy | Peach___Bacterial_spot | 5 |
| Potato___Late_blight | Potato___Early_blight | 5 |
| Tomato___Septoria_leaf_spot | Tomato___Early_blight | 4 |
| Tomato___Bacterial_spot | Tomato___Early_blight | 4 |
| Tomato___Tomato_mosaic_virus | Tomato___Late_blight | 4 |
| Cherry_(including_sour)___healthy | Cherry_(including_sour)___Powdery_mildew | 4 |
