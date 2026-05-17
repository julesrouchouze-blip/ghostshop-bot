import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime

TOKEN = os.environ.get("DISCORD_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "0"))

PRODUCTS = [
    {"label": "McDonalds 50-74",      "price": 1.50,  "value": "mcdo_50_74"},
    {"label": "McDonalds 67 points",  "price": 1.67,  "value": "mcdo_67pts"},
    {"label": "McDonalds 75-99",      "price": 3.50,  "value": "mcdo_75_99"},
    {"label": "McDonalds 100-124",    "price": 4.50,  "value": "mcdo_100_124"},
    {"label": "McDonalds 125-149",    "price": 5.50,  "value": "mcdo_125_149"},
    {"label": "McDonalds 150-174",    "price": 6.50,  "value": "mcdo_150_174"},
    {"label": "McDonalds 175-199",    "price": 8.50,  "value": "mcdo_175_199"},
    {"label": "McDonalds 200-249",    "price": 9.50,  "value": "mcdo_200_249"},
    {"label": "McDonalds 250-299",    "price": 11.00, "value": "mcdo_250_299"},
    {"label": "McDonalds 300-349",    "price": 12.00, "value": "mcdo_300_349"},
    {"label": "McDonalds 325-349",    "price": 13.50, "value": "mcdo_325_349"},
    {"label": "McDonalds 350-399",    "price": 14.00, "value": "mcdo_350_399"},
    {"label": "McDonalds 375-400",    "price": 15.00, "value": "mcdo_375_400"},
    {"label": "McDonalds 400-499",    "price": 16.50, "value": "mcdo_400_499"},
    {"label": "McDonalds 500-599",    "price": 22.00, "value": "mcdo_500_599"},
    {"label": "McDonalds 600-699",    "price": 30.00, "value": "mcdo_600_699"},
    {"label": "McDonalds 700-899",    "price": 40.00, "value": "mcdo_700_899"},
    {"label": "McDonalds 900-1199",   "price": 52.00, "value": "mcdo_900_1199"},
    {"label": "McDonalds 1200-1399",  "price": 59.00, "value": "mcdo_1200_1399"},
    {"label": "McDonalds 1400-1599",  "price": 70.00, "value": "mcdo_1400_1599"},
    {"label": "McDonalds 1600-1800",  "price": 76.00, "value": "mcdo_1600_1800"},
    {"label": "McDonalds 1800-2100",  "price": 95.00, "value": "mcdo_1800_2100"},
]

DB_FILE = "wallets.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_balance(user_id):
    db = load_db()
    return db.get(str(user_id), {}).get("balance", 0.0)

def set_balance(user_id, amount):
    db = load_db()
    if str(user_id) not in db:
        db[str(user_id)] = {}
    db[str(user_id)]["balance"] = round(amount, 2)
    save_db(db)

def add_balance(user_id, amount):
    current = get_balance(str(user_id))
    set_balance(str(user_id), current + amount)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

class ProductSelect(discord.ui.Select):
    def __init__(self):
        options = []
        for p in PRODUCTS[:25]:
            options.append(discord.SelectOption(
                label=p["label"],
                description=f"Prix : {p['price']:.2f} EUR",
                value=p["value"],
                emoji="\U0001f354"
            ))
        super().__init__(
            placeholder="\U0001f6d2 Choisir ma commande...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="product_select"
        )

    async def callback(self, interaction):
        selected_value = self.values[0]
        product = next((p for p in PRODUCTS if p["value"] == selected_value), None)
        if not product:
            await interaction.response.send_message("Produit introuvable.", ephemeral=True)
            return
        user_balance = get_balance(str(interaction.user.id))
        if user_balance < product["price"]:
            manque = product["price"] - user_balance
            embed = discord.Embed(
                title="Solde insuffisant",
                description=(
                    f"Produit selectionne : **{product['label']}** a **{product['price']:.2f} EUR**\n\n"
                    f"Ton solde : **{user_balance:.2f} EUR**\n"
                    f"Il te manque : **{manque:.2f} EUR**\n\n"
                    f"Utilise le bouton Recharger mon wallet !"
                ),
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        new_balance = user_balance - product["price"]
        set_balance(str(interaction.user.id), new_balance)
        embed = discord.Embed(
            title="Commande confirmee !",
            description=(
                f"**{product['label']}**\n"
                f"Prix paye : **{product['price']:.2f} EUR**\n"
                f"Nouveau solde : **{new_balance:.2f} EUR**\n\n"
                f"Tu vas recevoir ta commande en MP !"
            ),
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"GhostShop - {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        log_channel = bot.get_channel(CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="Nouvelle commande",
                description=(
                    f"Acheteur : {interaction.user.mention} ({interaction.user.id})\n"
                    f"Produit : {product['label']}\n"
                    f"Prix : {product['price']:.2f} EUR\n"
                    f"Solde restant : {new_balance:.2f} EUR"
                ),
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            await log_channel.send(embed=log_embed)

class ShopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ProductSelect())

    @discord.ui.button(
        label="Recharger mon wallet",
        style=discord.ButtonStyle.success,
        emoji="\U0001f4b0",
        custom_id="recharge_wallet"
    )
    async def recharge_wallet(self, interaction, button):
        embed = discord.Embed(
            title="Recharger mon wallet",
            description=(
                "Pour recharger ton wallet, contacte un **Admin** en MP avec :\n"
                "- Ton pseudo Discord\n"
                "- Le montant souhaite\n"
                "- Ta preuve de paiement (screenshot)\n\n"
                "Rechargement effectue sous 24h."
            ),
            color=discord.Color.gold()
        )
        embed.set_footer(text="GhostShop - Paiement securise")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="Mon solde",
        style=discord.ButtonStyle.secondary,
        emoji="\U0001f4b3",
        custom_id="mon_solde"
    )
    async def mon_solde(self, interaction, button):
        balance = get_balance(str(interaction.user.id))
        embed = discord.Embed(
            title="Ton solde",
            description=f"**{balance:.2f} EUR**",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"GhostShop - {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="setup_shop", description="[ADMIN] Poste le panel de la boutique dans ce salon")
@app_commands.checks.has_permissions(administrator=True)
async def setup_shop(interaction):
    embed = discord.Embed(
        title="Boutique GhostShop",
        description=(
            "**Produits disponibles :**\n\n"
            + "\n".join([f"**{p['label']}** - {p['price']:.2f} EUR" for p in PRODUCTS])
            + "\n\nSelectionnez un produit dans le menu ci-dessous"
        ),
        color=discord.Color.dark_orange()
    )
    view = ShopView()
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("Panel poste !", ephemeral=True)

@bot.tree.command(name="recharge", description="[ADMIN] Recharger le wallet d'un utilisateur")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(user="L'utilisateur a recharger", montant="Montant en euros a ajouter")
async def recharge(interaction, user: discord.Member, montant: float):
    add_balance(str(user.id), montant)
    new_balance = get_balance(str(user.id))
    embed = discord.Embed(
        title="Wallet recharge",
        description=(
            f"Utilisateur : {user.mention}\n"
            f"Ajoute : {montant:.2f} EUR\n"
            f"Nouveau solde : {new_balance:.2f} EUR"
        ),
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
    try:
        dm_embed = discord.Embed(
            title="Ton wallet a ete recharge !",
            description=f"+{montant:.2f} EUR ont ete ajoutes.\nNouveau solde : **{new_balance:.2f} EUR**",
            color=discord.Color.green()
        )
        await user.send(embed=dm_embed)
    except Exception:
        pass

@bot.tree.command(name="solde_admin", description="[ADMIN] Voir le solde d'un utilisateur")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(user="L'utilisateur dont voir le solde")
async def solde_admin(interaction, user: discord.Member):
    balance = get_balance(str(user.id))
    await interaction.response.send_message(f"Solde de {user.mention} : **{balance:.2f} EUR**", ephemeral=True)

@bot.tree.command(name="reset_solde", description="[ADMIN] Remettre le solde d'un utilisateur a 0")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(user="L'utilisateur a reinitialiser")
async def reset_solde(interaction, user: discord.Member):
    set_balance(str(user.id), 0.0)
    await interaction.response.send_message(f"Solde de {user.mention} remis a 0.00 EUR", ephemeral=True)

@bot.event
async def on_ready():
    print(f"Bot connecte : {bot.user} ({bot.user.id})")
    bot.add_view(ShopView())
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} commandes synchronisees")
    except Exception as e:
        print(f"Erreur sync : {e}")

bot.run(TOKEN)
