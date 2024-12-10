import discord
from discord.ext import commands
from discord import app_commands
import os
import random
import copy
from player_ai import guess_card
from storyteller_ai import generate_hint

intents = discord.Intents.default()
intents.message_content = True  # Allows the bot to read message content

bot = commands.Bot(command_prefix="!", intents=intents)

# Global variables for the game
players = []
game_started = False
cards_per_player = 6
cards_folder = 'cards'  # Folder containing the card images
storyteller_index = 0  # Index for the current storyteller
storyteller = ""
round_index = -1
storyteller_card = None  # Card chosen by the storyteller
hands = {}  # Card hands for each player
played_cards = []  # List of cards played by all players
played_card_names = []
played_cards_by_players = {}  # List of cards played and associated with players (excluding the storyteller)
storyteller_chose = False
votes = {}  # Dictionary storing the votes
points = {}  # Points for the players
ai_hint = ""
ai_cards = []

class DynamicVoteButton(discord.ui.View):
    def __init__(self, ctx, num_buttons, storyteller, card_list):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.result = None
        self.voted_users = set()  # Set to track who has voted
        self.storyteller = storyteller  # Add the storyteller as an attribute
        self.card_list = card_list
        global votes
        votes = {i: 0 for i in range(1, num_buttons + 1)}  # Initialize the votes
        self.create_buttons(num_buttons)

    # Function to create buttons dynamically
    def create_buttons(self, num_buttons):
        for i in range(1, num_buttons + 1):
            self.add_item(VoteButton(label=str(i), button_id=i, parent_view=self, card_list=self.card_list))

class VoteButton(discord.ui.Button):
    def __init__(self, label, button_id, parent_view, card_list):
        super().__init__(label=label, style=discord.ButtonStyle.primary, custom_id=str(button_id))
        self.button_id = button_id # button number (ex 1, 2, ...)
        self.parent_view = parent_view
        global played_cards_by_players, players, played_card_names
        self.card_list = card_list

    async def callback(self, interaction: discord.Interaction):
        # Check if the user is the storyteller
        if interaction.user == self.parent_view.storyteller:  # Check if the user is the storyteller
            await interaction.response.send_message("The storyteller can't vote!", ephemeral=True)
            return
        
        # Check if the user has already voted
        if interaction.user.id in self.parent_view.voted_users:
            await interaction.response.send_message("You already voted!", ephemeral=True)
            return

        # Check if the user is trying to vote for their own card
        user_card = played_cards_by_players.get(interaction.user)  # Get the card played by the user
        voted_card = self.card_list[self.button_id-1]

        if user_card == voted_card:
            await interaction.response.send_message("You can't vote for your own card!", ephemeral=True)
            return

        # Handle the user's vote
        self.parent_view.voted_users.add(interaction.user.id)  # Add the user to the list of voters
        votes[self.button_id] += 1  # Increment the vote for the chosen card
        await interaction.response.send_message(f"You voted for card {self.button_id}!", ephemeral=True)

        if "AI" in players and storyteller != "AI": # If AI needs to play
            played_cards_less_ai = []
            print("played_cards_less_ai:", played_cards_less_ai)
            print("played_card_names:", played_card_names)
            card_ai = played_cards_by_players['AI'] # Carta giocata dall'AI
            print("card_ai:", card_ai)
            played_cards_less_ai = [card for card in played_card_names if card != card_ai] # Remove from the voting options
            print("played_cards_less_ai:", played_cards_less_ai)
            carta_scelta = guess_card(ai_hint, played_cards_less_ai)
            button_index = played_card_names.index(carta_scelta)
            self.parent_view.voted_users.add(123456)  # Add AI to the list of voters
            votes[button_index+1] += 1

        # Check if all players voted
        if len(self.parent_view.voted_users) == len(players) - 1:  # Exclude the storyteller
            await self.parent_view.ctx.send("Everyone voted! Let's calculate the scores...")
            await calculate_scores(self.parent_view.ctx)  # Call score calculation



# Function to load the cards
def load_cards():
    return [f for f in os.listdir(cards_folder) if os.path.isfile(os.path.join(cards_folder, f))]

deck = load_cards()
complete_deck = load_cards()

async def narrator_ai(ctx: commands.Context):
    global ai_cards, storyteller_chose, storyteller_card, played_cards
    description, storyteller_card = generate_hint(ai_cards)
    storyteller_chose = True
    played_cards.append(("AI", storyteller_card)) 
    await send_message(ctx, f"Turbo has chosen and given a hint about their card: *'{description}'*.\n\nThe other players should now select a card that matches the description using '/playcard'")


# Function to handle each round
async def round(ctx: commands.Context):
    global round_index, storyteller_index, ai_cards, storyteller
    # Select the storyteller
    if round_index == 0:
        storyteller = random.choice(players)  # Randomly select a storyteller
        storyteller_index = players.index(storyteller)  # Get the index of the storyteller
        if storyteller == "AI":
            await send_message(ctx, f"The game has started! **Turbo** has been chosen as the storyteller!\n\nReady for the hint?")
        else:
            await send_message(ctx, f"The game has started! **{storyteller.display_name}** is the storyteller! 🌟\n\nStoryteller, choose your card using '/choose'.")
    else:
        if storyteller_index == len(players)-1:  # Loop back to the start if at the end of the list
            storyteller_index = 0
        else:
            storyteller_index += 1  
        storyteller = players[storyteller_index]
        if storyteller == "AI":
            await send_message(ctx, f"🔄 A new round has started! **Turbo** is the new storyteller! 📜\n\nReady for the hint?")
        else:
            await send_message(ctx, f"🔄 A new round has started! **{storyteller.display_name}** is the new storyteller! 📜\n\nStoryteller, choose your card using '/choose'.")

    # Deal unique cards to each player
    for player in players:
        hand = random.sample(deck, cards_per_player)  # Remove cards from the deck
        hands[player] = hand
        for card in hand:
            deck.remove(card)

    # Send card images to each player privately
    for player, hand in hands.items():
        if player == "AI":
            ai_cards = hand
            if storyteller == "AI":
                await narrator_ai(ctx)
            print(f"Turbo received the following cards:: {', '.join(hand)}.")
        else:
            await player.send(f"This is round {round_index + 1}. Get ready! 🚀")
            for card_image in hand:
                file_path = os.path.join(cards_folder, card_image)
                await player.send(file=discord.File(file_path))
            print(f"Round {round_index + 1}.")
            print(f"{player.display_name} received the following cards: {', '.join(hand)}.")


# Function to send messages for both prefix and Slash commands
async def send_message(ctx, message):
    if ctx.interaction:
        if not ctx.interaction.response.is_done():
            await ctx.interaction.response.send_message(message)
        else:
            await ctx.interaction.followup.send(message)
    else:
        await ctx.send(message)


@bot.hybrid_command(name="choose", description="Choose the number of the card and give a hint about it.")
async def describe_and_choose(ctx: commands.Context, card_number: int, description: str):
    global storyteller_index, storyteller_card, hands, storyteller_chose, ai_hint
    storyteller = players[storyteller_index]

    if storyteller != "AI":
        # Check if the command author is the storyteller
        if ctx.author.id != storyteller.id:
            await send_message(ctx, "Only the storyteller can choose and describe the card at this stage.")
            return
        
        if storyteller_chose:
            await send_message(ctx, "The storyteller has already chosen the card.")
            return

        # Check card number
        hand = hands[storyteller]
        if card_number < 1 or card_number > len(hand):
            await send_message(ctx, "Invalid card number. Please choose a valid number from your hand.")
            return

        # Storyteller selects the card
        storyteller_chose = True
        storyteller_card = hand.pop(card_number - 1)  # Remove the card from the hand
        played_cards.append((ctx.author, storyteller_card))  # Add the card to the played cards
        if "AI" in players and storyteller != "AI":
            ai_hint = description # Send the description to the AI
        await ctx.interaction.response.send_message(f"{storyteller.display_name} has chosen and given a hint about their card: *'{description}'*.\n\nThe other players should now select a card that matches the description using '/playcard'")


# Command for players to choose a card
@bot.hybrid_command(name="playcard", description="Play a card")
async def play_card(ctx: commands.Context, card_number: int):
    global storyteller_index, hands, played_cards, played_cards_by_players
    storyteller = players[storyteller_index]

    # Check if the command author is the storyteller
    if ctx.author == storyteller:
        await send_message(ctx, "The storyteller cannot play a card at this stage.")
        return
    
    if not storyteller_chose:
        await send_message(ctx, "The storyteller has not yet chosen the card to play.")
        return

    # Check the card number
    hand = hands[ctx.author]
    if card_number < 1 or card_number > len(hand):
        await send_message(ctx, "Invalid card number. Please choose a valid number from your hand.")
        return

    # Player selects their card
    carta_scelta = hand.pop(card_number - 1)  # Add the card to the played cards
    played_cards.append((ctx.author, carta_scelta))  # Add the card to the played cards
    played_cards_by_players[ctx.author] = carta_scelta
    await send_message(ctx, f"{ctx.author.display_name} played a card.")
    # Handle AI's turn if needed
    if "AI" in players and storyteller != "AI":
        carta_scelta = guess_card(ai_hint, ai_cards)
        played_cards.append(("AI", carta_scelta))  # Add the AI's card
        played_cards_by_players["AI"] = carta_scelta
        await send_message(ctx, f"Turbo played a card.")

    # Check if all players (excluding the storyteller) have played a card
    if len(played_cards) == len(players):
        await show_cards(ctx)


# Function to show the mixed cards
async def show_cards(ctx: commands.Context):
    global played_cards, players, played_card_names
    random.shuffle(played_cards)

    # Prepare a list of files for the card images to be sent in one message
    cards_to_show = []
    message_cards = "Here are the cards:\n"

    # Prepare the message containing the numbers for the cards
    for i, (player, card) in enumerate(played_cards, start=1):
        file_path = os.path.join(cards_folder, card)
        cards_to_show.append(discord.File(file_path))  # Add the card file to the list
        played_card_names.append(card)

    # Send all the cards in one message
    await ctx.send(message_cards, files=cards_to_show)

    # Create buttons dynamically based on the number of cards
    num_buttons = len(played_cards)
    storyteller = players[storyteller_index]
    view = DynamicVoteButton(ctx, num_buttons, storyteller, played_card_names)

    # Send the voting buttons to the human players
    await ctx.send("Select the card you think is the storyteller's by clicking a button:", view=view)

    # Wait for votes to be collected
    await view.wait()


# Function to calculate the scores
async def calculate_scores(ctx: commands.Context):
    global storyteller_card, game_started, played_cards, played_card_names, votes, points, storyteller_index, storyteller, deck, round_index, storyteller_chose, ai_cards, ai_hint

    # Find the index of the storyteller's card
    storyteller_card_index = next(i for i, (player, card) in enumerate(played_cards, start=1) if player == storyteller)

    # Check if all or none voted for the storyteller's card
    if votes[storyteller_card_index] == 0 or votes[storyteller_card_index] == len(players) - 1:
        # No one or everyone voted for the storyteller's card
        for player in players:
            if player != storyteller:
                points[player] = points.get(player, 0) + 2  # Each other player gains 2 points
        await send_message(ctx, "No one or everyone voted for the storyteller's card. The storyteller scores 0 points, while all other players score 2 points each.")
    else:
        # Some players voted correctly
        points[storyteller] = points.get(storyteller, 0) + 3  # The storyteller scores 3 points
        for player, card in played_cards:
            if player != storyteller and votes[played_cards.index((player, card)) + 1] > 0:
                points[player] = points.get(player, 0) + 1  # Players who receive votes gain 1 point per vote
        await send_message(ctx, "The storyteller and those who voted correctly gain 3 points.")

    # Display the final scores
    await display_scores(ctx)

    # Check for end of game conditions
    # Verify if any player has reached the target score
    for player, score in points.items():
        if score >= 30:  
            if player == "AI":
                await send_message(ctx, "Turbo has reached 30 points and wins the game!")
            else:
                await send_message(ctx, f"{player.display_name} has reached 30 points and wins the game!")
            game_started = False
            round_index = -1
            storyteller_card = None
            hands.clear()
            played_cards.clear()
            played_card_names.clear()
            played_cards_by_players.clear()
            storyteller_chose = False
            votes.clear()
            deck = copy.deepcopy(complete_deck)
            ai_hint = ""
            ai_cards.clear()
            storyteller = ""
            return  # end the game
    # Check if the deck is out of cards.
    if len(deck) < cards_per_player * len(players):
        await send_message(ctx, "The deck is out of cards. The game ends here!")
        # Determine the winner(s)
        highest_score = max(points.values())
        winners = ["Turbo" if player == "AI" else player.display_name for player, score in points.items() if score == highest_score]
        #winners = [player.display_name for player, score in points.items() if score == highest_score]
        if len(winners) > 1:
            await send_message(ctx, f"The game is over! The winners are: {', '.join(winners)} with {highest_score} points!")
        else:
            await send_message(ctx, f"The game is over! The winner is {winners[0]} with {highest_score} points!")
        game_started = False
        round_index = -1
        storyteller_card = None
        hands.clear()
        played_cards.clear()
        played_card_names.clear()
        played_cards_by_players.clear()
        storyteller_chose = False
        votes.clear()
        deck = copy.deepcopy(complete_deck)
        ai_hint = ""
        ai_cards.clear()
        storyteller = ""
        return  # End the game

    # If the game is not ended, starts a new round: resets the game for the next turn
    round_index += 1
    storyteller_card = None
    hands.clear()
    played_cards.clear()
    played_cards_by_players.clear()
    played_card_names.clear()
    storyteller_chose = False
    votes.clear()
    ai_hint = ""
    ai_cards.clear()
    storyteller = ""

    await round(ctx)


# Function to display the scores
async def display_scores(ctx: commands.Context):
    global points
    punteggi = "```md\n"
    punteggi += "| Player         | Points |\n"
    punteggi += "|-------------------|-------|\n"
    for player in players:
        if player == "AI":
            punteggi += f"| {'Turbo':<17} | {points.get(player, 0):<5} |\n"
        else:
            punteggi += f"| {player.display_name:<17} | {points.get(player, 0):<5} |\n"
    punteggi += "```"
    await send_message(ctx, f"Current scores:\n{punteggi}")


# Event: When the bot is ready
@bot.event
async def on_ready():
    print(f'Bot connected as {bot.user}')
    await bot.tree.sync()

# Command to strat the game
@bot.hybrid_command(name="dixit", description="Start a new game of Dixit")
async def dixit_game(ctx: commands.Context):
    global players, game_started, round_index
    if game_started:
        await send_message(ctx, "A game is already in progress!")
    else:
        players = []
        game_started = True
        storyteller_index = 0
        await send_message(ctx, "\nDixit game started! 🎲\n\nUse the following commands:\n- `/ai`: Add Turbo AI to the game\n- `/join`: Join the game\n- `/start`: Start the game\n- `/playcard`: Play your card (player)\n- `/describe_and_choose`: Describe and choose a card (storyteller)\n- `/endgame`: End the game\n\nHave fun! 🌟")
        
# Command to join the game
@bot.hybrid_command(name="join", description="Join the game")
async def join_game(ctx: commands.Context):
    if game_started:
        player = ctx.author
        if len(players) >= 6:
            await send_message(ctx, f"{player.display_name} cannot join! The maximum number of players has been reached.")
        elif round_index >= 0:
            await send_message(ctx, f"{player.display_name} cannot join! The game has already started.")
        elif player not in players:
            players.append(player)
            await send_message(ctx, f"Welcome to the game, {player.display_name}! 🎉 Use `/start` when ready.")
            print(f"{player.display_name} joined the game.")
        else:
            await send_message(ctx, f"{player.display_name} is already in the game!")
    else:
        await send_message(ctx, "No active game. Use `/dixit` to start one.")

# Command to add AI to the game
@bot.hybrid_command(name="ai", description="Add Turbo AI to the game")
async def ai_game(ctx: commands.Context):
    global players
    if game_started:
        if "AI" in players:  # Check if AI is already in the game
            await send_message(ctx, "Turbo is already in the game!")
        elif len(players) >= 6:
            await send_message(ctx, "Turbo cannot join! The maximum number of players has been reached.")
        elif round_index >= 0:
            await send_message(ctx, "Turbo cannot join! The game has already started.")
        else:
            players.append("AI")  # Add AI to the game
            await send_message(ctx, "Turbo has joined the game! 🤖")
    else:
        await send_message(ctx, "No active game. Use `/dixit` to start one.")

# Command to officially start the game
@bot.hybrid_command(name="start", description="Officially start the game")
async def start_game(ctx: commands.Context):
    global game_started, round_index
    if not game_started:
        await send_message(ctx, "No active game. Use `/dixit` to start one.")
    elif len(players) < 3:
        await send_message(ctx, "At least 3 players are needed to start the game.")
    else:
        round_index = round_index+1
        await round(ctx)

# Command to forcibly end the game
@bot.hybrid_command(name="endgame", description="End the current game")
async def end_game(ctx: commands.Context):
    global game_started, round_index, storyteller_card, storyteller, hands, played_cards, played_cards_by_players, storyteller_chose, votes, deck, ai_hint, ai_cards
    player = ctx.author
    if not game_started:
        await send_message(ctx, f"There is no game to end.")
    else:
        await send_message(ctx, f"The game was ended by {player.display_name}.")
        game_started = False  # La partita è finita, non è più attiva
        round_index = -1
        storyteller_card = None
        hands.clear()
        played_cards.clear()
        played_cards_by_players.clear()
        storyteller_chose = False
        votes.clear()
        deck = copy.deepcopy(complete_deck)
        ai_hint = ""
        ai_cards.clear()
        storyteller = ""



bot.run('TOKEN')

