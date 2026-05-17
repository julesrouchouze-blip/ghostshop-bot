import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
from datetime import datetime

TOKEN = os.environ.get("DISCORD_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "0"))
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

PRODUCTS = [
    {"label": "KFC 300-499 points",   "price": 3.00,  "value": "kfc_300_499"},
    {"label": "KFC 500-799 points",   "price": 4.00,  "value": "kfc_500_799"},
    {"label": "KFC 800-999 points",   "price": 5.00,  "value": "kfc_800_999"},
    {"label": "KFC 1000-1299 points", "price": 6.00,  "value": "kfc_1000_1299"},
    {"label": "KFC 1300-1599 points", "price": 6.50,  "value": "kfc_1300_1599"},
    {"label": "KFC 1600-1799 points", "price": 8.00,  "value": "kfc_1600_1799"},
    {"label": "KFC 1800-1999 points", "price": 8.50,  "value": "kfc_1800_1999"},
    {"label": "KFC 2000-2399 points", "price": 9.50,  "value": "kfc_2000_2399"},
    {"label": "KFC 2400-2500 points", "price": 10.50, "value": "kfc_2400_2500"},
]

WALLETS_FILE = "wallets.json"

def load_wallets():
    if os.path.exists(WALLETS_FILE):
        with open(WALLETS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_wallets(w):
    with open(WALLETS_FILE, "w") as f:
        json.dump(w, f, indent=2)

def get_balance(user_id):
    w = load_wallets()
    return w.get(str(user_id), {}).get("balance", 0.0)

def set_balance(user_id, amount):
    w = load_wallets()
    uid = str(user_id)
    if uid not in w:
        w[uid] = {}
    w[uid]["balance"] = round(amount, 2)
    save_wallets(w)

def add_balance(user_id, amount):
    current = get_balance(user_id)
    set_balance(user_id, current + amount)
    return get_balance(user_id)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


class QuantiteModal(discord.ui.Modal):
    def __init__(self, produit: dict):
        super().__init__(title=f"Quantite - {produit['label'][:40]}")
        self.produit = produit
        self.quantite = discord.ui.TextInput(
            label="Combien de comptes voulez-vous ?",
            placeholder="Ex: 2  (max 10)",
            min_length=1,
            max_length=2,
            required=True
        )
        self.add_item(self.quantite)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.quantite.value)
            if qty < 1 or qty > 10:
                await interaction.response.send_message(
                    "Quantite invalide (1 a 10 max).", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message(
                "Veuillez entrer un nombre valide.", ephemeral=True)
            return

        produit = self.produit
        total = round(produit["price"] * qty, 2)
        solde = get_balance(interaction.user.id)

        if solde < total:
            await interaction.response.send_message(
                f"Solde insuffisant ! Tu as **{solde:.2f} euros** mais la commande coute **{total:.2f} euros** ({qty}x{produit['price']:.2f} euros).",
                ephemeral=True)
            return

        add_balance(interaction.user.id, -total)
        nouveau_solde = get_balance(interaction.user.id)

        embed = discord.Embed(
            title="Commande confirmee !",
            description=(
                f"**{produit['label']}** x{qty}\n"
                f"Prix unitaire : **{produit['price']:.2f} euros**\n"
                f"Total debite : **{total:.2f} euros**\n\n"
                f"Solde restant : **{nouveau_solde:.2f} euros**\n\n"
                f"Vos comptes KFC vont etre livres sous peu !"
            ),
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        if ADMIN_ID:
            admin = bot.get_user(ADMIN_ID)
            if admin:
                try:
                    await admin.send(
                        f"Nouvelle commande KFC de {interaction.user} ({interaction.user.id})\n"
                        f"Produit : **{produit['label']}** x{qty}\n"
                        f"Total : **{total:.2f} euros**"
                    )
                except Exception:
                    pass


class RechargeModal(discord.ui.Modal, title="Recharger mon wallet"):
    montant = discord.ui.TextInput(
        label="Montant a recharger (en euros)",
        placeholder="Ex: 10.00",
        min_length=1,
        max_length=10,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = float(self.montant.value.replace(",", "."))
            if amount <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "Montant invalide.", ephemeral=True)
            return

        solde = get_balance(interaction.user.id)
        guild = interaction.guild
        admin_user = guild.get_member(ADMIN_ID) if ADMIN_ID else None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        if admin_user:
            overwrites[admin_user] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        category = interaction.channel.category

        ticket_channel = await guild.create_text_channel(
            name=f"recharge-{interaction.user.name}",
            overwrites=overwrites,
            category=category,
            reason=f"Demande de recharge de {interaction.user}"
        )

        embed = discord.Embed(
            title="Demande de recharge - KFC",
            description=(
                f"Utilisateur : {interaction.user.mention}\n"
                f"Montant demande : **{amount:.2f} euros**\n"
                f"Solde actuel : **{solde:.2f} euros**\n\n"
                f"Un administrateur va traiter votre demande.\n"
                f"Utilisez **/fermer_ticket** pour fermer ce ticket."
            ),
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )

        mention_admin = admin_user.mention if admin_user else "Admin"
        await ticket_channel.send(
            content=f"{interaction.user.mention} {mention_admin}",
            embed=embed
        )

        await interaction.response.send_message(
            f"Ticket cree ! Rendez-vous dans {ticket_channel.mention}",
            ephemeral=True
        )


class SelectProduit(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=p["label"],
                value=p["value"],
                description=f"{p['price']:.2f} EUR"
            )
            for p in PRODUCTS
        ]
        super().__init__(
            placeholder="Choisir ma commande KFC...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        valeur = self.values[0]
        produit = next(p for p in PRODUCTS if p["value"] == valeur)
        await interaction.response.send_modal(QuantiteModal(produit))


class BoutonRecharger(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Recharger mon wallet",
            style=discord.ButtonStyle.success,
            custom_id="recharger_kfc"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RechargeModal())


class BoutonSolde(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Mon solde",
            style=discord.ButtonStyle.secondary,
            custom_id="solde_kfc"
        )

    async def callback(self, interaction: discord.Interaction):
        solde = get_balance(interaction.user.id)
        await interaction.response.send_message(
            f"Ton solde : **{solde:.2f} euros**",
            ephemeral=True
        )


class VueShop(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(BoutonRecharger())
        self.add_item(BoutonSolde())
        self.add_item(SelectProduit())


@tree.command(name="setup_shop", description="[ADMIN] Poste le panel KFC dans ce salon")
@app_commands.checks.has_permissions(administrator=True)
async def setup_shop(interaction: discord.Interaction):
    lines = "\n".join([f"**{p['label']}** - {p['price']:.2f} EUR" for p in PRODUCTS])
    embed = discord.Embed(
        title="KFC Shop",
        description=lines + "\n\nSelectionnez un produit dans le menu ci-dessous",
        color=discord.Color.red()
    )
    await interaction.response.send_message("Envoi en cours...", ephemeral=True)
    await interaction.channel.send(embed=embed, view=VueShop())


@tree.command(name="recharge", description="[ADMIN] Recharger le wallet d un membre")
@app_commands.checks.has_permissions(administrator=True)
async def recharge(interaction: discord.Interaction, membre: discord.Member, montant: float):
    nouveau = add_balance(membre.id, montant)
    await interaction.response.send_message(
        f"**{montant:.2f} euros** ajoute au wallet de {membre.mention}. Nouveau solde : **{nouveau:.2f} euros**",
        ephemeral=True
    )


@tree.command(name="solde_admin", description="[ADMIN] Voir le solde d un membre")
@app_commands.checks.has_permissions(administrator=True)
async def solde_admin(interaction: discord.Interaction, membre: discord.Member):
    solde = get_balance(membre.id)
    await interaction.response.send_message(
        f"{membre.mention} a **{solde:.2f} euros** dans son wallet.",
        ephemeral=True
    )


@tree.command(name="reset_solde", description="[ADMIN] Remettre le solde d un membre a zero")
@app_commands.checks.has_permissions(administrator=True)
async def reset_solde(interaction: discord.Interaction, membre: discord.Member):
    set_balance(membre.id, 0.0)
    await interaction.response.send_message(
        f"Solde de {membre.mention} remis a **0.00 euros**.",
        ephemeral=True
    )


@tree.command(name="fermer_ticket", description="Fermer ce ticket de recharge")
async def fermer_ticket(interaction: discord.Interaction):
    if "recharge-" in interaction.channel.name:
        await interaction.response.send_message("Fermeture du ticket dans 5 secondes...")
        await asyncio.sleep(5)
        await interaction.channel.delete(reason="Ticket ferme")
    else:
        await interaction.response.send_message(
            "Cette commande ne fonctionne que dans un ticket.", ephemeral=True)


@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot KFC connecte : {bot.user} ({bot.user.id})")
    cmds = await tree.fetch_commands()
    print(f"{len(cmds)} commandes synchronisees")


bot.run(TOKEN)
