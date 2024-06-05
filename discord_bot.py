import os
import sys
import time
import asyncio
import discord
import requests
import traceback
from io import StringIO
from lxml import etree
from discord import app_commands
from typing import Literal
from datetime import datetime
from pprint import pprint

token = ""
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


# -- Get username from UUID --

parser = etree.HTMLParser()

def get_uuid_for_username(username):
    res = requests.get(f"https://mcuuid.net/?q={username}")
    t = etree.parse(StringIO(res.text), parser)
    uuid = t.xpath("//input[@id='results_id']/@value")
    return uuid[0]

# ------

# -- Keep track of wins/losses/streaks --

modes = ["classic", "potion", "combo", "sumo", "bridge", "uhc", "sw", "blitz", "mw", "boxing", "op"]
stats = {"overall": {}}
for mode in modes:
    stats[mode] = {}
uuids = []

async def get_game_stats_for_uuid(uuid):
    headers = {
        "API-Key": ""
    }

    base_url = "https://api.hypixel.net/v2"

    res = requests.get(f"{base_url}/player?uuid={uuid}", headers=headers)
    if res.status_code == 200:
        #print(res.headers)
        j = res.json()
        username = j["player"]["displayname"]
        duels_stats = j["player"]["stats"]["Duels"]
        overall_wins = duels_stats["wins"]
        overall_losses = duels_stats["losses"]

        print(f"[{username}] WINS: {overall_wins} LOSSES: {overall_losses}")
        #pprint(stats)
        now = int(datetime.now().timestamp())

        if uuid in stats["overall"]:
            if overall_wins > stats["overall"][uuid]["last_win"]:
                streak_orig = stats["overall"][uuid]["last_win"] - stats["overall"][uuid]["wins"]
                stats["overall"][uuid]["last_win"] = overall_wins
                streak = stats["overall"][uuid]["last_win"] - stats["overall"][uuid]["wins"]
                print(f"WINS STREAK! {username} on a streak {streak}")

                win_mode = None
                for mode in modes:
                    if f"{mode}_duel_wins" in duels_stats and f"{mode}_duel_losses" in duels_stats:
                        if duels_stats[f"{mode}_duel_wins"] > stats[mode][uuid]["last_win"]:
                            mode_streak_orig = stats[mode][uuid]["last_win"] - stats[mode][uuid]["wins"]
                            stats[mode][uuid]["last_win"] = duels_stats[f"{mode}_duel_wins"]
                            mode_streak = stats[mode][uuid]["last_win"] - stats[mode][uuid]["wins"]
                            win_mode = mode
                            break

                channel = discord.utils.get(client.get_all_channels(), name="bot-test")
                await channel.send(f":green_circle: **{username}** winstreak changed: **{streak_orig} -> {streak}** ({win_mode.title()}: **{mode_streak_orig} -> {mode_streak}**) <t:{now}:R>")

            if overall_losses > stats["overall"][uuid]["losses"]:
                # Wah wah
                # Streak has ended.
                # Tell discord this player's streak is over.
                wins_orig = stats["overall"][uuid]["last_win"]
                streak = stats["overall"][uuid]["last_win"] - stats["overall"][uuid]["wins"]
                stats["overall"][uuid] = {"wins": overall_wins, "last_win": overall_wins, "losses": overall_losses}

                duel_mode = "None"
                mode_streak = -1
                for mode in modes:
                    if f"{mode}_duel_wins" in duels_stats and f"{mode}_duel_losses" in duels_stats:
                        if duels_stats[f"{mode}_duel_losses"] > stats[mode][uuid]["losses"]:
                            duel_mode = mode
                            mode_streak = stats[mode][uuid]["last_win"] - stats[mode][uuid]["wins"]
                            stats[mode][uuid] = {"wins": duels_stats[f"{mode}_duel_wins"], "last_win": duels_stats[f"{mode}_duel_wins"], "losses": duels_stats[f"{mode}_duel_losses"]}
                            break

                channel = discord.utils.get(client.get_all_channels(), name="bot-test")
                await channel.send(f":red_circle: **{username}** lost their winstreak: **{streak} -> 0** ({duel_mode.title()}: **{mode_streak} -> 0**) <t:{now}:R>")
        else:
            stats["overall"][uuid] = {"wins": overall_wins, "last_win": overall_wins, "losses": overall_losses}
            for mode in modes:
                if f"{mode}_duel_wins" in duels_stats and f"{mode}_duel_losses" in duels_stats:
                    stats[mode][uuid] = {"wins": duels_stats[f"{mode}_duel_wins"], "last_win": duels_stats[f"{mode}_duel_wins"], "losses": duels_stats[f"{mode}_duel_losses"]}

# ------

# -- Discord stuff --

@tree.command(description="Track a HyPixel user for win streaks")
@app_commands.describe(username="The HyPixel username of the user to track")
async def track(interaction: discord.Interaction, username: str):
    uuid = get_uuid_for_username(username)
    uuids.append(uuid)
    await interaction.response.send_message(f"Added {username}.")

@tree.command(description="Remove a user from the tracker")
@app_commands.describe(username="The HyPixel username of the user to stop track")
async def untrack(interaction: discord.Interaction, username: str):
    uuid = get_uuid_for_username(username)
    if uuid in uuids:
        uuids.remove(uuid)
    await interaction.response.send_message(f"Removed {username}.")

@tree.command(description="Update a user's winstreak")
@app_commands.describe(username="The HyPixel username of the user to track", streak="The streak they're on.")
async def winstreak(interaction: discord.Interaction, mode:Literal["overall", "classic", "potion", "combo", "sumo", "bridge", "uhc", "sw", "blitz", "mw", "boxing", "op"], username: str, streak: int):
    uuid = get_uuid_for_username(username)
    stats[mode][uuid]["wins"] = stats[mode][uuid]["last_win"] - streak
    await interaction.response.send_message(f"Updated {mode} streak for {username} to {streak}.")

@client.event
async def on_ready():
    for guild in client.guilds:
        print(f"Guild: {guild.name} : {guild.id}")
    commands = await tree.sync()
    pprint(commands)
    print("Bot is ready")

    while True:
        for uuid in uuids:
            try:
                await get_game_stats_for_uuid(uuid)
            except Exception as e:
                print(f"Failed to get game stats for {uuid}: {e}")
                traceback.print_exc(file=sys.stdout)
                #pprint(stats)

        await asyncio.sleep(5)

client.run(token)
