"""Advisory catalogue keyed by model class label.

Content is general, widely published plant-pathology guidance (symptoms to look for and cultural
prevention). It deliberately contains NO pesticide names, dosages or spray schedules: those must come
from local agricultural authorities (KVK / state agriculture department / agricultural university).
"""

CATALOG: dict[str, dict] = {
    "Apple___Apple_scab": {"type": "fungal", "look_for": "Olive-green to black, velvety spots on leaves and scabby spots on fruit.",
        "prevent": ["Collect and destroy fallen leaves", "Prune to open the canopy for airflow", "Prefer scab-resistant varieties when replanting"]},
    "Apple___Black_rot": {"type": "fungal", "look_for": "Purple-edged 'frog-eye' leaf spots, rotting fruit and sunken bark cankers.",
        "prevent": ["Remove mummified fruit and dead or cankered wood", "Keep orchard floor clean of prunings"]},
    "Apple___Cedar_apple_rust": {"type": "fungal", "look_for": "Bright yellow-orange spots on the upper leaf surface, sometimes with small tubes underneath.",
        "prevent": ["The fungus needs juniper/cedar as an alternate host; note any nearby", "Prefer resistant varieties"]},
    "Cherry_(including_sour)___Powdery_mildew": {"type": "fungal", "look_for": "White powdery patches on young leaves and shoots; leaves may curl.",
        "prevent": ["Improve airflow by pruning", "Avoid excess nitrogen fertiliser"]},
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": {"type": "fungal", "look_for": "Long, narrow, rectangular grey-tan lesions limited by leaf veins.",
        "prevent": ["Rotate away from maize", "Manage infected crop residue", "Use tolerant hybrids"]},
    "Corn_(maize)___Common_rust_": {"type": "fungal", "look_for": "Small cinnamon-brown powdery pustules on both leaf surfaces.",
        "prevent": ["Use resistant hybrids", "Monitor during cool, humid weather"]},
    "Corn_(maize)___Northern_Leaf_Blight": {"type": "fungal", "look_for": "Long cigar-shaped grey-green to tan lesions on leaves.",
        "prevent": ["Crop rotation and residue management", "Use resistant hybrids"]},
    "Grape___Black_rot": {"type": "fungal", "look_for": "Tan leaf spots with dark borders; berries shrivel into hard black mummies.",
        "prevent": ["Remove mummified berries and infected canes", "Open the canopy for airflow and sunlight"]},
    "Grape___Esca_(Black_Measles)": {"type": "fungal (trunk disease)", "look_for": "'Tiger-stripe' yellow/red bands between leaf veins; dark spotting on berries.",
        "prevent": ["Prune out affected wood in dry weather", "Protect large pruning wounds", "Seek expert advice: it is a trunk disease"]},
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)": {"type": "fungal", "look_for": "Irregular dark-brown spots on leaves that can lead to early leaf drop.",
        "prevent": ["Remove infected leaves and debris", "Improve canopy airflow"]},
    "Orange___Haunglongbing_(Citrus_greening)": {"type": "bacterial (psyllid-transmitted)", "urgent": True,
        "look_for": "Blotchy, uneven (asymmetric) yellowing of leaves; small lopsided bitter fruit.",
        "prevent": ["There is no cure; report suspected trees to the agriculture department", "Monitor and manage Asian citrus psyllid", "Use certified disease-free planting material"]},
    "Peach___Bacterial_spot": {"type": "bacterial", "look_for": "Small angular water-soaked spots turning purple-brown; holes in leaves ('shot-hole').",
        "prevent": ["Prefer tolerant varieties", "Avoid overhead irrigation"]},
    "Pepper,_bell___Bacterial_spot": {"type": "bacterial", "look_for": "Small water-soaked spots turning brown, often with a yellow halo; raised spots on fruit.",
        "prevent": ["Use disease-free seed and transplants", "Avoid overhead irrigation and working in wet foliage", "Rotate crops"]},
    "Potato___Early_blight": {"type": "fungal", "look_for": "Dark-brown spots with concentric rings ('target' pattern), starting on older leaves.",
        "prevent": ["Rotate crops", "Maintain balanced nutrition", "Remove infected plant debris"]},
    "Potato___Late_blight": {"type": "oomycete", "urgent": True, "look_for": "Dark water-soaked lesions, white growth on leaf undersides in humid weather; spreads within days.",
        "prevent": ["Use certified seed tubers", "Destroy infected plants and cull piles", "Avoid overhead irrigation"]},
    "Squash___Powdery_mildew": {"type": "fungal", "look_for": "White powdery spots on leaves and stems that spread to cover leaves.",
        "prevent": ["Improve spacing and airflow", "Prefer tolerant varieties"]},
    "Strawberry___Leaf_scorch": {"type": "fungal", "look_for": "Many small purple spots that merge so leaf edges look burnt.",
        "prevent": ["Remove old infected leaves", "Avoid overhead irrigation", "Renew plantings regularly"]},
    "Tomato___Bacterial_spot": {"type": "bacterial", "look_for": "Small dark water-soaked spots on leaves, sometimes with yellow halos; scabby fruit spots.",
        "prevent": ["Use clean seed and healthy transplants", "Avoid overhead irrigation", "Rotate crops"]},
    "Tomato___Early_blight": {"type": "fungal", "look_for": "Brown spots with concentric rings on older, lower leaves, with surrounding yellowing.",
        "prevent": ["Mulch and stake plants to keep leaves off soil", "Remove infected lower leaves", "Rotate crops"]},
    "Tomato___Late_blight": {"type": "oomycete", "urgent": True, "look_for": "Greasy grey-green to dark-brown leaf lesions, pale-white mould underneath in the morning, brown stem lesions, firm brown fruit rot.",
        "prevent": ["Isolate or remove infected plants promptly", "Keep foliage dry (drip irrigation, avoid evening watering)", "Avoid moving through wet foliage"]},
    "Tomato___Leaf_Mold": {"type": "fungal", "look_for": "Pale-yellow spots on the upper leaf surface with olive-grey velvety mould underneath; common in polyhouses.",
        "prevent": ["Ventilate to reduce humidity", "Space plants for airflow", "Remove infected leaves"]},
    "Tomato___Septoria_leaf_spot": {"type": "fungal", "look_for": "Many small round spots with dark edges and grey centres containing tiny black dots.",
        "prevent": ["Remove lower infected leaves", "Mulch to prevent soil splash", "Rotate crops"]},
    "Tomato___Spider_mites Two-spotted_spider_mite": {"type": "pest (mite)", "look_for": "Fine yellow speckling on leaves, fine webbing, tiny mites on leaf undersides (use a hand lens).",
        "prevent": ["Check leaf undersides regularly", "Avoid water stress", "Conserve natural predators"]},
    "Tomato___Target_Spot": {"type": "fungal", "look_for": "Brown spots with concentric rings, similar to early blight, on leaves and fruit.",
        "prevent": ["Improve airflow", "Remove infected debris", "Rotate crops"]},
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus": {"type": "viral (whitefly-transmitted)", "look_for": "Upward-curling, yellow-edged small leaves and stunted plants.",
        "prevent": ["Manage whiteflies; use insect nets in nurseries", "Remove infected plants early", "Prefer tolerant varieties"]},
    "Tomato___Tomato_mosaic_virus": {"type": "viral", "look_for": "Light- and dark-green mosaic mottling, distorted or fern-like leaves.",
        "prevent": ["Remove infected plants", "Wash hands and tools between plants", "Use clean seed"]},
}

HEALTHY = {"look_for": "No disease pattern was recognised on the photographed leaf.",
           "prevent": ["Continue regular scouting, especially after rain or humid spells", "Keep good field hygiene and airflow"]}

GENERAL_REFERENCES = [
    "Your nearest Krishi Vigyan Kendra (KVK) or state agriculture department extension officer",
    "Kisan Call Centre: 1800-180-1551 (toll-free, Government of India)",
]


def entry(label: str) -> dict | None:
    return CATALOG.get(label)
