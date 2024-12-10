import torch
from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import os

#Player role
#input: description from the narrator (str) and the 6 card in his hands (list)

model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")


def guess_card(hint, cards):
    cards_path = [f"cards/{file}" for file in cards]
    images = [Image.open(image_path) for image_path in cards_path]
    
    inputs = processor(text=[hint], images=images, return_tensors="pt", padding=True)
    
    with torch.no_grad():
        outputs = model(**inputs)
        logits_per_image = outputs.logits_per_image  # logit imgs
        logits_per_text = outputs.logits_per_text    # logit text
    probs = logits_per_image.softmax(dim=0)  # Probabilità normalizzate
    print(probs)
    chosen_index = torch.argmax(logits_per_image).item()  # Trova l'indice dell'immagine più somigliante
    print("\ncarta scelta da ai:", chosen_index)

    return cards[chosen_index]

