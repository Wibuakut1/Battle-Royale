import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import random
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

players = {}
game_mode = "Solo"
zones = ["Pochinki", "School", "Military Base", "Rozhok", "Georgopol"]
current_zone = random.choice(zones)
airdrop_items = ["Bazooka", "AWM", "M4A1", "AK47", "Armor Lv.3", "Armor Lv.2", "Armor Lv.1"]
status_channel = None

@tasks.loop(minutes=2)
async def shrink_zone():
    global current_zone
    current_zone = random.choice(zones)
    summary = f"**Zone is shrinking! New zone:** {current_zone}\n"
    for player_id, player in players.items():
        if player["zone"] != current_zone:
            player["hp"] -= 25
            summary += f"<@{player_id}> took 25 zone damage. "
            if player["hp"] <= 0:
                player["status"] = "knocked" if player["mode"] == "Squad" else "dead"
                summary += f"and is now **{player['status']}**\n"
            else:
                summary += f"(HP: {player['hp']})\n"
    await send_embed("Zone Shrinking", summary)

@tasks.loop(seconds=30)
async def handle_battle():
    zone_map = {}
    logs = ""
    for pid, p in players.items():
        if p["status"] != "alive": continue
        zone_map.setdefault(p["zone"], []).append(pid)

    for zone, pids in zone_map.items():
        if len(pids) < 2: continue
        p1_id, p2_id = random.sample(pids, 2)
        p1, p2 = players[p1_id], players[p2_id]

        for attacker, defender, atk_id, def_id in [(p1, p2, p1_id, p2_id), (p2, p1, p2_id, p1_id)]:
            if defender["status"] != "alive": continue
            weapon = attacker.get("weapon")
            headshot = random.random() < 0.1

            if weapon == "Bazooka":
                defender["status"] = "knocked" if defender["mode"] == "Squad" else "dead"
                logs += f"💥 <@{atk_id}> used **Bazooka** on <@{def_id}> — **{defender['status']}**!\n"
                continue

            damage = 0
            if weapon == "M4A1" or weapon == "AK47":
                damage = random.randint(45, 55)
            elif weapon == "AWM":
                damage = random.randint(60, 100)
            elif weapon == "Grenade":
                damage = 60
            elif weapon == "Vehicle":
                damage = 95
            else:
                damage = random.randint(20, 35)

            armor = defender.get("armor", 0)
            if armor == 1:
                damage -= 15
            elif armor == 2:
                damage -= 22
            elif armor == 3:
                damage -= 30

            if headshot:
                defender["status"] = "knocked" if defender["mode"] == "Squad" else "dead"
                logs += f"🎯 <@{atk_id}> got a **headshot** on <@{def_id}> — **{defender['status']}**!\n"
                continue

            defender["hp"] -= max(0, damage)
            if defender["hp"] <= 0:
                defender["status"] = "knocked" if defender["mode"] == "Squad" else "dead"
            logs += f"🔫 <@{atk_id}> hit <@{def_id}> with **{weapon}** for {damage} damage (HP: {max(0, defender['hp'])})\n"
    if logs:
        await send_embed("Zone Battle", logs)

@tasks.loop(minutes=1)
async def red_zone():
    zone = random.choice(zones)
    logs = f"☢️ **Red Zone hits**: {zone}\n"
    for pid, p in players.items():
        if p["zone"] == zone and p["status"] == "alive":
            dmg = random.randint(20, 60)
            p["hp"] -= dmg
            if p["hp"] <= 0:
                p["status"] = "knocked" if p["mode"] == "Squad" else "dead"
                logs += f"<@{pid}> took {dmg} damage and is now **{p['status']}**\n"
            else:
                logs += f"<@{pid}> took {dmg} damage (HP: {p['hp']})\n"
    await send_embed("Red Zone Event", logs)

async def send_embed(title, description):
    if status_channel:
        embed = discord.Embed(title=title, description=description, color=discord.Color.red())
        await status_channel.send(embed=embed)

@tree.command(name="start")
async def start_game(interaction: discord.Interaction):
    global status_channel
    status_channel = interaction.channel
    view = ModeSelect()
    await interaction.response.send_message("Select game mode:", view=view, ephemeral=True)

class ModeSelect(discord.ui.View):
    @discord.ui.button(label="Solo", style=discord.ButtonStyle.primary)
    async def solo(self, interaction: discord.Interaction, button: discord.ui.Button):
        await setup_game(interaction, "Solo")

    @discord.ui.button(label="Squad", style=discord.ButtonStyle.success)
    async def squad(self, interaction: discord.Interaction, button: discord.ui.Button):
        await setup_game(interaction, "Squad")

async def setup_game(interaction, mode):
    global game_mode
    game_mode = mode
    players.clear()
    await interaction.followup.send(f"Game starting in **{mode}** mode. React ✅ to join!", ephemeral=True)
    await asyncio.sleep(15)
    for member in interaction.guild.members:
        if not member.bot:
            players[member.id] = {
                "hp": 100,
                "weapon": random.choices(["M4A1", "AK47", "AWM", "Bazooka", "Grenade", "Vehicle"], [0.2, 0.2, 0.1, 0.005, 0.2, 0.1])[0],
                "armor": random.choices([0,1,2,3], [0.5,0.2,0.2,0.1])[0],
                "zone": random.choice(zones),
                "status": "alive",
                "mode": mode
            }
    shrink_zone.start()
    handle_battle.start()
    red_zone.start()

bot.run(TOKEN)
    
