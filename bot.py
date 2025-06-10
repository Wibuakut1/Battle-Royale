import discord
from discord.ext import commands, tasks
import random
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True
bot = commands.Bot(command_prefix='/', intents=intents)

zones = ["A", "B", "C", "D", "E"]
active_zones = zones.copy()

players = {}  # user_id: {...}
zone_loot = {}

loot_pool = [
    "AKM", "M4A1", "AWM", "Pistol",
    "Peluru 5.56mm", "Peluru 7.62mm", "Bandage", "Medkit", "Armor Level 1"
]

weapon_damage = {
    "M4A1": 35,
    "AKM": 42,
    "AWM": 90,
    "Pistol": 20
}

armor_protection = {
    "Armor Level 1": 15
}

join_message_id = None

stats = {}  # user_id: {"kills": 0, "games_played": 0, "wins": 0}

def generate_loot():
    return random.sample(loot_pool, k=random.randint(1, 3))


@bot.event
async def on_ready():
    print(f'Bot connected as {bot.user}')
    channel = bot.get_channel(1344370197351366697)
    if channel:
        msg = await channel.send("🎮 Klik ✅ untuk bergabung dalam Battle Royale!")
        await msg.add_reaction("✅")
        global join_message_id
        join_message_id = msg.id
    else:
        print("Channel ID 1344370197351366697 tidak ditemukan.")
    game_loop.start()


@bot.event
async def on_raw_reaction_add(payload):
    if payload.message_id == join_message_id and str(payload.emoji) == "✅":
        user_id = payload.user_id
        if user_id == bot.user.id:
            return
        if user_id not in players:
            zone = random.choice(active_zones)
            players[user_id] = {"zone": zone, "hp": 100, "inventory": [], "armor": 0, "kill_streak": 0, "kills": 0}
            stats.setdefault(user_id, {"kills": 0, "games_played": 0, "wins": 0})
            stats[user_id]["games_played"] += 1
            channel = bot.get_channel(payload.channel_id)
            if channel:
                await channel.send(f"<@{user_id}> bergabung di zona {zone}!")
        else:
            channel = bot.get_channel(payload.channel_id)
            if channel:
                await channel.send(f"<@{user_id}> kamu sudah bergabung!")


@bot.command()
async def status(ctx):
    user_id = ctx.author.id
    if user_id in players:
        player = players[user_id]
        await ctx.send(
            f"{ctx.author.mention} | Zona: {player['zone']} | HP: {player['hp']} | Armor: {player['armor']} | Inventory: {player['inventory']} | Kill Streak: {player['kill_streak']} | Kills: {player['kills']}"
        )
    else:
        await ctx.send("Kamu belum join. Klik ✅ pada pesan join untuk bergabung.")


@bot.command()
async def stats(ctx):
    user_id = ctx.author.id
    if user_id in stats:
        s = stats[user_id]
        await ctx.send(
            f"{ctx.author.mention} Statistik:\n"
            f"🗡️ Kill: {s['kills']}\n"
            f"🎮 Game Played: {s['games_played']}\n"
            f"🏆 Win: {s['wins']}"
        )
    else:
        await ctx.send("Kamu belum memiliki statistik. Mulai dengan join game dulu ya.")


@tasks.loop(seconds=30)
async def game_loop():
    channel = bot.get_channel(1344370197351366697)
    if not channel:
        print("Channel ID 1344370197351366697 tidak ditemukan.")
        return

    global active_zones
    if len(active_zones) > 1:
        active_zones = random.sample(active_zones, len(active_zones) - 1)
        await channel.send(f"🌀 Zona mengecil! Zona aman: {', '.join(active_zones)}")

        for user_id, info in players.items():
            if info["zone"] not in active_zones:
                new_zone = random.choice(active_zones)
                info["zone"] = new_zone
                await channel.send(f"🚶 <@{user_id}> dipindahkan ke zona {new_zone} agar aman.")

    for z in active_zones:
        zone_loot[z] = generate_loot()

    for user_id, info in players.items():
        zone = info["zone"]
        if zone in zone_loot and zone_loot[zone]:
            loot_given = random.choice(zone_loot[zone])
            info["inventory"].append(loot_given)
            if loot_given in armor_protection:
                info["armor"] += armor_protection[loot_given]
                await channel.send(f"🛡️ <@{user_id}> mendapatkan {loot_given} (+{armor_protection[loot_given]} armor)")
            else:
                await channel.send(f"🎁 <@{user_id}> menemukan: {loot_given} di zona {zone}")

    zone_players = {}
    for uid, info in players.items():
        if info["hp"] > 0:
            zone_players.setdefault(info["zone"], []).append(uid)

    for zona, user_ids in zone_players.items():
        if len(user_ids) >= 2:
            await channel.send(f"💥 Pertempuran di zona {zona}!")
            random.shuffle(user_ids)
            for i in range(0, len(user_ids) - 1, 2):
                attacker = user_ids[i]
                defender = user_ids[i + 1]

                atk_inv = players[attacker]["inventory"]
                weapon = next((w for w in atk_inv if w in weapon_damage), None)
                base_damage = weapon_damage.get(weapon, 10)

                defender_armor = players[defender]["armor"]
                damage = max(base_damage - defender_armor, 1)

                players[defender]["hp"] -= damage
                await channel.send(f"🔫 <@{attacker}> menembak <@{defender}> dengan {weapon or 'tinju'} ({damage} damage)")

                if players[defender]["hp"] <= 0:
                    await channel.send(f"☠️ <@{defender}> telah dieliminasi!")
                    players[attacker]["kill_streak"] += 1
                    players[attacker]["kills"] += 1
                    stats[attacker]["kills"] += 1
                    players[defender]["kill_streak"] = 0

    for user_id, info in players.items():
        if info["hp"] > 0:
            healing_items = [item for item in info["inventory"] if item in ["Bandage", "Medkit"]]
            if healing_items:
                heal_item = healing_items[0]
                heal_amount = 20 if heal_item == "Medkit" else 10
                info["hp"] = min(info["hp"] + heal_amount, 100)
                info["inventory"].remove(heal_item)
                await channel.send(f"❤️ <@{user_id}> menggunakan {heal_item} dan pulih {heal_amount} HP (HP sekarang: {info['hp']})")

    alive = [uid for uid, p in players.items() if p["hp"] > 0]
    if len(alive) == 1 and len(players) > 0:
        winner = alive[0]
        stats[winner]["wins"] += 1

        leaderboard = sorted(players.items(), key=lambda x: x[1].get("kills", 0), reverse=True)
        leaderboard_text = "🏅 **Leaderboard Kill Sementara:**\n"
        for rank, (uid, pdata) in enumerate(leaderboard, start=1):
            user = await bot.fetch_user(uid)
            leaderboard_text += f"{rank}. {user.name} - Kill: {pdata.get('kills', 0)}\n"

        await channel.send(f"🏆 <@{winner}> menang! Game selesai.\n\n{leaderboard_text}")
        players.clear()
        active_zones = zones.copy()

bot.run(TOKEN)
                
