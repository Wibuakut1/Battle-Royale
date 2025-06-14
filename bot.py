import discord
from discord.ext import commands, tasks
import asyncio
import random
import os
from flask import Flask
from threading import Thread
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
players = {}
zone_loot = {}
stats = {}
game_running = False
join_message_id = None
damage_multiplier = 1
last_zone_started = False
last_zone_timer = 300  # 5 menit

loot_pool = [
    "AKM", "M4A1", "AWM", "Pistol",
    "Peluru 5.56mm", "Peluru 7.62mm", "Peluru .300 Magnum", "Peluru 9mm",
    "Bandage", "Medkit", "Armor Level 1", "Flare Gun",
    "Granat", "Kendaraan"
]

weapon_damage = {
    "M4A1": 35,
    "AKM": 42,
    "AWM": 90,
    "Pistol": 20,
    "Bazooka": 999,
    "Granat": 60,
    "Kendaraan": 95,
    "Tinju": 10
}

weapon_ammo_type = {
    "M4A1": "Peluru 5.56mm",
    "AKM": "Peluru 7.62mm",
    "AWM": "Peluru .300 Magnum",
    "Pistol": "Peluru 9mm",
    "Bazooka": "Bazooka Ammo",
    "Granat": None,
    "Kendaraan": None,
    "Tinju": None
}

armor_protection = {
    "Armor Level 1": 15,
    "Ghillie Suit": 25
}
def generate_loot():
    loot = random.sample(loot_pool, k=random.randint(1, 3))
    if random.random() < 0.05:
        loot.append("Bazooka")
        loot.append("Bazooka Ammo")
    return loot

@bot.event
async def on_ready():
    print(f'✅ Bot aktif sebagai {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"🔁 Slash commands disinkronisasi: {len(synced)}")
    except Exception as e:
        print(f"❌ Gagal sync: {e}")

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot or not game_running or reaction.message.id != join_message_id:
        return
    uid = user.id
    if uid in players:
        return
    players[uid] = {
        "hp": 100, "zone": random.choice(active_zones),
        "inventory": [], "armor": 0, "kills": 0, "kill_streak": 0
    }
    stats[uid] = stats.get(uid, {"kills": 0, "wins": 0})
    await reaction.message.channel.send(f"✅ <@{uid}> bergabung ke dalam game!")

async def start_game_countdown(channel: discord.TextChannel):
    global game_running
    delay = random.randint(120)  # 2 menit
    await channel.send(embed=discord.Embed(
        description=f"⏳ Game akan dimulai dalam {delay // 120} menit...",
        color=discord.Color.blue()
    ))
    await asyncio.sleep(delay)

    if len(players) < 2:
        await channel.send(embed=discord.Embed(
            description="❌ Tidak cukup pemain untuk memulai game.",
            color=discord.Color.red()
        ))
        game_running = False
        return

    await channel.send(embed=discord.Embed(
        title="🚀 Game Dimulai!",
        description=f"{len(players)} pemain siap bertarung!",
        color=discord.Color.green()
    ))
    zone_loop.start()
    pvp_loop.start()
    event_loop.start()
@bot.tree.command(name="start", description="Mulai game & buka pendaftaran lewat reaksi")
async def start_game(interaction: discord.Interaction):
    global game_running, players, stats, active_zones, join_message_id, damage_multiplier
    if game_running:
        await interaction.response.send_message("⚠️ Game sedang berjalan!", ephemeral=True)
        return

    game_running = True
    players.clear()
    stats.clear()
    active_zones = zones.copy()
    damage_multiplier = 1

    msg = await interaction.channel.send(embed=discord.Embed(
        title="🎮 Game Baru Dimulai!",
        description="React dengan ✅ atau gunakan `/begin` untuk bergabung.",
        color=discord.Color.green()
    ))
    await msg.add_reaction("✅")
    join_message_id = msg.id

    await interaction.response.send_message("Game setup selesai! Menunggu pemain bergabung...", ephemeral=True)

    await start_game_countdown(interaction.channel)

@bot.tree.command(name="begin", description="Bergabung ke game yang sedang dimulai")
async def begin(interaction: discord.Interaction):
    if not game_running:
        await interaction.response.send_message("❌ Tidak ada game yang aktif.", ephemeral=True)
        return
    uid = interaction.user.id
    if uid in players:
        await interaction.response.send_message("⚠️ Kamu sudah bergabung!", ephemeral=True)
        return
    players[uid] = {
        "hp": 100,
        "zone": random.choice(active_zones),
        "inventory": [],
        "armor": 0,
        "kills": 0,
        "kill_streak": 0
    }
    stats[uid] = stats.get(uid, {"kills": 0, "wins": 0})
    await interaction.response.send_message(f"✅ <@{uid}> bergabung ke dalam game!")

@bot.tree.command(name="status", description="Lihat statusmu dalam game")
async def status(interaction: discord.Interaction):
    uid = interaction.user.id
    if uid not in players:
        await interaction.response.send_message("❌ Kamu belum bergabung dalam game.", ephemeral=True)
        return
    p = players[uid]
    embed = discord.Embed(title="📊 Status Kamu", color=discord.Color.blurple())
    embed.add_field(name="HP", value=str(p["hp"]))
    embed.add_field(name="Armor", value=str(p["armor"]))
    embed.add_field(name="Zona", value=p["zone"])
    embed.add_field(name="Inventory", value=", ".join(p["inventory"]) if p["inventory"] else "Kosong", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="stats", description="Lihat statistik permanentmu")
async def show_stats(interaction: discord.Interaction):
    uid = interaction.user.id
    s = stats.get(uid)
    if not s:
        await interaction.response.send_message("❌ Tidak ada statistik tersedia.", ephemeral=True)
        return
    embed = discord.Embed(title="📈 Statistik", color=discord.Color.purple())
    embed.add_field(name="Total Kills", value=str(s["kills"]))
    embed.add_field(name="Total Wins", value=str(s["wins"]))
    await interaction.response.send_message(embed=embed, ephemeral=True)
    
@tasks.loop(minutes=2)
async def zone_loop():
    channel = discord.utils.get(bot.get_all_channels(), id=1378788825731694732)
    global active_zones, damage_multiplier, last_zone_started, last_zone_timer, game_running

    if not game_running or not channel:
        return

    if len(active_zones) > 1:
        active_zones = random.sample(active_zones, len(active_zones) - 1)
        damage_multiplier += 0.2
        await channel.send(embed=discord.Embed(
            title="🌀 Zona menyusut!",
            description=f"Zona aman sekarang: {', '.join(active_zones)}",
            color=discord.Color.orange()
        ))

        for uid, p in players.items():
            if p["hp"] <= 0:
                continue
            if p["zone"] not in active_zones:
                p["zone"] = random.choice(active_zones)
                await channel.send(embed=discord.Embed(
                    description=f"🚶 <@{uid}> dipindahkan ke zona {p['zone']} karena zona menyusut.",
                    color=discord.Color.light_grey()
                ))
    elif len(active_zones) == 1:
        if not last_zone_started:
            last_zone_started = True
            last_zone_timer = 300  # 5 menit zona terakhir
            await channel.send(embed=discord.Embed(
                title="⚠️ Zona terakhir!",
                description="Zona terakhir dimulai. Bertahanlah!",
                color=discord.Color.red()
            ))
        else:
            last_zone_timer -= 120
            if last_zone_timer <= 0:
                for uid, p in players.items():
                    if p["hp"] > 0:
                        p["hp"] -= 50
                        await channel.send(embed=discord.Embed(
                            description=f"🔥 <@{uid}> terkena damage zona terakhir! (-50 HP)",
                            color=discord.Color.dark_red()
                        ))
                        if p["hp"] <= 0:
                            await channel.send(embed=discord.Embed(
                                description=f"☠️ <@{uid}> mati karena zona!",
                                color=discord.Color.red()
                            ))

@tasks.loop(seconds=30)
async def pvp_loop():
    channel = discord.utils.get(bot.get_all_channels(), id=1378788825731694732)
    if not channel or not game_running:
        return

    # Update loot dan flare gun
    for z in active_zones:
        zone_loot[z] = generate_loot()

    for uid, p in players.items():
        if p["hp"] <= 0:
            continue
        zone = p["zone"]
        if zone in zone_loot and zone_loot[zone]:
            loot = random.choice(zone_loot[zone])
            if loot == "Flare Gun":
                if "Flare Gun" not in p["inventory"] and random.random() < 0.1:
                    p["inventory"].append("Flare Gun")
            else:
                p["inventory"].append(loot)
            msg = f"🎁 <@{uid}> menemukan: {loot}"
            if loot in armor_protection:
                p["armor"] += armor_protection[loot]
                msg += f" (+{armor_protection[loot]} armor)"
            await channel.send(embed=discord.Embed(description=msg, color=discord.Color.green()))

    # Flare Gun usage
    for uid, p in players.items():
        if "Flare Gun" in p["inventory"]:
            if random.random() < 0.5:
                p["inventory"].remove("Flare Gun")
                p["inventory"].append("Ghillie Suit")
                p["armor"] += armor_protection["Ghillie Suit"]
                await channel.send(embed=discord.Embed(
                    description=f"🎯 <@{uid}> menggunakan Flare Gun dan mendapatkan Ghillie Suit!",
                    color=discord.Color.gold()
                ))

    # Pertempuran otomatis antar pemain dalam zona yang sama
    zone_players = {}
    for uid, p in players.items():
        if p["hp"] > 0:
            zone_players.setdefault(p["zone"], []).append(uid)

    for zone, user_ids in zone_players.items():
        if len(user_ids) >= 2:
            await channel.send(embed=discord.Embed(
                title="💥 Pertempuran dimulai!",
                description=f"Zona {zone}",
                color=discord.Color.red()
            ))
            random.shuffle(user_ids)
            for i in range(0, len(user_ids) - 1, 2):
                atk, dfn = user_ids[i], user_ids[i + 1]
                atk_p, dfn_p = players[atk], players[dfn]
                inv = atk_p["inventory"]
                weapon = next((w for w in inv if w in weapon_damage), None)
                ammo = weapon_ammo_type.get(weapon)

                if not weapon:
                    # Gunakan tinju jika tidak punya senjata
                    weapon = "Tinju"
                    base = 10
                else:
                    base = weapon_damage[weapon]

                # Hitung damage
                final_dmg = int(base * damage_multiplier)
                armor_block = random.randint(15, 20) if dfn_p["armor"] > 0 else 0
                dmg = max(final_dmg - armor_block, 1)
                dfn_p["hp"] -= dmg

                if weapon in inv and ammo and ammo in inv:
                    inv.remove(ammo)
                if weapon in ["Bazooka", "Granat", "Kendaraan"]:
                    inv.remove(weapon)

                await channel.send(embed=discord.Embed(
                    description=f"⚔️ <@{atk}> menyerang <@{dfn}> dengan **{weapon}** ({dmg} dmg)",
                    color=discord.Color.red()
                ))

                if dfn_p["hp"] <= 0:
                    await channel.send(embed=discord.Embed(
                        description=f"☠️ <@{dfn}> telah dieliminasi!",
                        color=discord.Color.dark_red()
                    ))
                    atk_p["kills"] += 1
                    atk_p["kill_streak"] += 1
                    stats[atk]["kills"] += 1
                    dfn_p["kill_streak"] = 0

    # Healing otomatis
    for uid, p in players.items():
        if p["hp"] > 0 and p["hp"] < 100:
            heals = [i for i in p["inventory"] if i in ["Bandage", "Medkit"]]
            if heals:
                item = heals[0]
                amt = 20 if item == "Medkit" else 10
                p["hp"] = min(100, p["hp"] + amt)
                p["inventory"].remove(item)
                await channel.send(embed=discord.Embed(
                    description=f"❤️ <@{uid}> menggunakan {item}, +{amt} HP",
                    color=discord.Color.green()
                ))

    # Cek pemenang
    alive = [uid for uid, p in players.items() if p["hp"] > 0]
    if len(alive) == 1:
        winner = alive[0]
        stats[winner]["wins"] += 1
        lb = sorted(players.items(), key=lambda x: x[1]["kills"], reverse=True)
        embed = discord.Embed(title="🏆 Game Selesai",
                              description=f"Pemenang: <@{winner}>",
                              color=discord.Color.gold())
        for i, (uid, p) in enumerate(lb, start=1):
            user = await bot.fetch_user(uid)
            embed.add_field(name=f"{i}. {user.name}", value=f"Kills: {p['kills']}", inline=False)
        await channel.send(embed=embed)
players.clear()
active_zones = zones.copy()
damage_multiplier = 1
game_running = False
pvp_loop.stop()
zone_loop.stop()

async def start_game_countdown(interaction):
    global game_running
    game_running = True
    await interaction.response.defer()
    await interaction.followup.send("Game akan dimulai dalam 5 detik...")  # ← Diperbaiki indentasinya

    await asyncio.sleep(5)

    # Penempatan awal dan reset stats
    for user_id, p in players.items():
        p["zone"] = random.choice(active_zones)
        p["hp"] = 100
        p["armor"] = 0
        p["inventory"] = []
        p["kills"] = 0
        p["kill_streak"] = 0
        stats[user_id] = stats.get(user_id, {"kills": 0, "wins": 0})

    channel = interaction.channel
    await channel.send(embed=discord.Embed(
        title="🎮 Game Dimulai!",
        description="Zona aktif: " + ', '.join(active_zones),
        color=discord.Color.green()
    ))

    # Mulai loop zona dan pertempuran
    pvp_loop.start()
    zone_loop.start()
app = Flask('')


@app.route('/')
def home():
    return "Bot is alive!"


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()


keep_alive()

bot.run(TOKEN)
