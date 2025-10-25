import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
from keep_alive import keep_alive
from custom_commands import setup_commands
from dotenv import load_dotenv
load_dotenv()

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
    
    async def setup_hook(self):
        # Sync slash commands globally
        await self.tree.sync()
        print("Slash commands synced globally!")

bot = MyBot()

@bot.event
async def on_ready():
    print(f'{bot.user} has logged in successfully!')
    print(f'Bot ID: {bot.user.id}')
    print(f'Connected to {len(bot.guilds)} server(s)')
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="the game"
        )
    )

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        pass
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
    else:
        print(f"Error: {error}")
        await ctx.send("An error occurred while executing the command.")

# Start the Flask keep_alive server
keep_alive()

# Run the bot
if __name__ == "__main__":
    try:
        # Set up commands
        setup_commands(bot)
        
        # Get token from environment variable for security
        token = os.environ.get('DISCORD_BOT_TOKEN')
        if not token:
            raise ValueError("No DISCORD_BOT_TOKEN found in environment variables")
        
        bot.run(token)
    except Exception as e:
        print(f"Failed to start bot: {e}")