import torch
from PIL import Image
import os
import openai
import random
from descr_generator import generate_descr

#Narrator role
#input: the 6 card in his hands
openai.api_key = 'TOKEN'

# Function to generate clues with GPT-3.5
def GPT_generation(description):
    prompt = f"I have an image described as: '{description}'. Imagine you are the storyteller in a Dixit game. Provide five different very short clues, no more than four words each."
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "You are a creative storyteller giving cryptic and evocative clues, based on a visual description."},
                  {"role": "user", "content": prompt}],
        max_tokens=50,
        temperature=0.9,
        top_p=1.0
    )
    clues = response['choices'][0]['message']['content'].strip()
    return clues

# Main function to generate a clue for a specific card
def generate_hint(cards):
    card = random.choice(cards)
    description = generate_descr(card)
    clues = GPT_generation(description)
    print(clues)
    clues_splitted = clues.split("\n")
    cleaned_clues = [clue.lstrip('0123456789. ').rstrip('.') for clue in clues_splitted if clue]  # Rimuove i numeri e gli spazi
    random_clue = random.choice(cleaned_clues)
    print(f"Random Clue: {random_clue}")
    return random_clue, card
