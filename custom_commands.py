import discord
from discord.ext import commands
from discord import app_commands
import json
import asyncio
from datetime import datetime, timedelta

# Load config
def load_config():
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            # Convert string role IDs to integers for comparison
            for command_name, perms in config.get("command_permissions", {}).items():
                if "allowed_roles" in perms:
                    perms["allowed_roles"] = [int(role_id) for role_id in perms["allowed_roles"]]
            return config
    except FileNotFoundError:
        return {"command_permissions": {}}

CONFIG = load_config()

# Role check decorator for prefix commands
def has_required_roles(command_name):
    def predicate(ctx):
        # If no roles specified in config, everyone can use
        if command_name not in CONFIG["command_permissions"]:
            return True
        
        allowed_roles = CONFIG["command_permissions"][command_name].get("allowed_roles", [])
        
        # If no roles specified, everyone can use
        if not allowed_roles:
            return True
        
        # Check if user has any of the required roles
        user_roles = [role.id for role in ctx.author.roles]
        user_has_role = any(role_id in user_roles for role_id in allowed_roles)
        
        # Debug info
        print(f"Command: {command_name}")
        print(f"Allowed roles: {allowed_roles}")
        print(f"User roles: {user_roles}")
        print(f"User has required role: {user_has_role}")
        
        return user_has_role
    
    return commands.check(predicate)

# Role check for slash commands
async def slash_has_required_roles(interaction, command_name):
    # If no roles specified in config, everyone can use
    if command_name not in CONFIG["command_permissions"]:
        return True
    
    allowed_roles = CONFIG["command_permissions"][command_name].get("allowed_roles", [])
    
    # If no roles specified, everyone can use
    if not allowed_roles:
        return True
    
    # Check if user has any of the required roles
    user_roles = [role.id for role in interaction.user.roles]
    user_has_role = any(role_id in user_roles for role_id in allowed_roles)
    
    # Debug info
    print(f"Slash Command: {command_name}")
    print(f"Allowed roles: {allowed_roles}")
    print(f"User roles: {user_roles}")
    print(f"User has required role: {user_has_role}")
    
    return user_has_role

# Prefix command: !ping
@commands.command(name='ping')
@has_required_roles('ping')
async def ping_prefix(ctx):
    """Check bot latency with prefix command"""
    latency = round(ctx.bot.latency * 1000)
    await ctx.send(f'🏓 Pong! Latency: `{latency}ms`')

@ping_prefix.error
async def ping_prefix_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ You don't have permission to use this command!")

# Slash command: /ping
@app_commands.command(name="ping", description="Check bot latency")
async def ping_slash(interaction: discord.Interaction):
    """Check bot latency with slash command"""
    # Check roles for slash command
    if not await slash_has_required_roles(interaction, 'ping'):
        await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        return
    
    latency = round(interaction.client.latency * 1000)
    await interaction.response.send_message(f'🏓 Pong! Latency: `{latency}ms`')

# Prefix command: !rename
@commands.command(name='rename')
@has_required_roles('rename')
async def rename_prefix(ctx, *, new_name: str):
    """Rename the current channel"""
    try:
        # Check if the bot has permission to manage channels
        if not ctx.guild.me.guild_permissions.manage_channels:
            await ctx.send("❌ I don't have permission to manage channels!")
            return
        
        # Rename the channel
        old_name = ctx.channel.name
        await ctx.channel.edit(name=new_name)
        await ctx.send(f"✅ Channel renamed from `{old_name}` to `{new_name}`")
        
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to rename this channel!")
    except discord.HTTPException as e:
        await ctx.send(f"❌ Failed to rename channel: {e}")

@rename_prefix.error
async def rename_prefix_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ You don't have permission to use this command!")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Usage: `!rename <new_channel_name>`")

# Prefix command: !delete
@commands.command(name='delete')
@has_required_roles('channel')
async def delete_prefix(ctx, confirmation: str, channel: discord.TextChannel = None):
    """Delete a channel (requires confirmation)"""
    target_channel = channel or ctx.channel
    
    if confirmation.lower() != 'yes':
        await ctx.send("❌ Deletion cancelled. You must type `yes` to confirm.")
        return
    
    await handle_delete(ctx, target_channel, is_slash=False)

@delete_prefix.error
async def delete_prefix_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ You don't have permission to use this command!")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Usage: `!delete <yes> [#channel]`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Please mention a valid channel!")

# Slash command group for channel operations
class ChannelCommands(app_commands.Group):
    """Channel management commands"""
    
    @app_commands.command(name="rename", description="Rename the current channel")
    @app_commands.describe(name="New name for the channel")
    async def channel_rename(self, interaction: discord.Interaction, name: str):
        """Rename the current channel"""
        # Check roles for slash command
        if not await slash_has_required_roles(interaction, 'channel'):
            await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
            return
        
        try:
            # Check if the bot has permission to manage channels
            if not interaction.guild.me.guild_permissions.manage_channels:
                await interaction.response.send_message("❌ I don't have permission to manage channels!", ephemeral=True)
                return
            
            # Rename the channel
            old_name = interaction.channel.name
            await interaction.channel.edit(name=name)
            await interaction.response.send_message(f"✅ Channel renamed from `{old_name}` to `{name}`")
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to rename this channel!", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"❌ Failed to rename channel: {e}", ephemeral=True)

    @app_commands.command(name="delete", description="Delete a channel (requires confirmation)")
    @app_commands.describe(
        confirmation="Type 'yes' to confirm deletion",
        channel="Channel to delete (defaults to current channel)"
    )
    async def channel_delete(self, interaction: discord.Interaction, confirmation: str, channel: discord.TextChannel = None):
        """Delete a channel with confirmation"""
        if not await slash_has_required_roles(interaction, 'channel'):
            await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
            return
    
        target_channel = channel or interaction.channel
    
        if confirmation.lower() != 'yes':
            await interaction.response.send_message("❌ Deletion cancelled. You must type `yes` to confirm.", ephemeral=True)
            return
    
        await handle_delete(interaction, target_channel, is_slash=True)

# Prefix command: !sync
@commands.command(name='sync')
@has_required_roles('sync')
async def sync_prefix(ctx, channel: discord.TextChannel = None):
    """Sync channel permissions with its category"""
    target_channel = channel or ctx.channel
    await handle_sync(ctx, target_channel, is_slash=False)

@sync_prefix.error
async def sync_prefix_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ You don't have permission to use this command!")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Please mention a valid channel!")

# Slash command: /sync
@app_commands.command(name="sync", description="Sync channel permissions with its category")
@app_commands.describe(channel="Channel to sync (optional, defaults to current channel)")
async def sync_slash(interaction: discord.Interaction, channel: discord.TextChannel = None):
    """Sync channel permissions with its category"""
    if not await slash_has_required_roles(interaction, 'sync'):
        await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        return
    
    target_channel = channel or interaction.channel
    await handle_sync(interaction, target_channel, is_slash=True)

async def handle_sync(ctx_or_interaction, channel: discord.TextChannel, is_slash: bool):
    """Common sync handling logic"""
    try:
        # Check if bot has manage_channels permission
        if not ctx_or_interaction.guild.me.guild_permissions.manage_channels:
            message = "❌ I don't have permission to manage channels!"
            if is_slash:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
            else:
                await ctx_or_interaction.send(message)
            return
        
        # Check if channel has a category
        if not channel.category:
            message = "❌ This channel is not in a category!"
            if is_slash:
                if ctx_or_interaction.response.is_done():
                    await ctx_or_interaction.followup.send(message, ephemeral=True)
                else:
                    await ctx_or_interaction.response.send_message(message, ephemeral=True)
            else:
                await ctx_or_interaction.send(message)
            return
        
        # Sync permissions with category
        await channel.edit(sync_permissions=True)
        message = f"✅ **{channel.mention}** permissions synced with category **{channel.category.name}**"
        
        if is_slash:
            if ctx_or_interaction.response.is_done():
                await ctx_or_interaction.followup.send(message)
            else:
                await ctx_or_interaction.response.send_message(message)
        else:
            await ctx_or_interaction.send(message)
            
    except discord.Forbidden:
        message = "❌ I don't have permission to sync this channel!"
        if is_slash:
            if ctx_or_interaction.response.is_done():
                await ctx_or_interaction.followup.send(message, ephemeral=True)
            else:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
        else:
            await ctx_or_interaction.send(message)
    except Exception as e:
        message = f"❌ Failed to sync channel: {e}"
        if is_slash:
            if ctx_or_interaction.response.is_done():
                await ctx_or_interaction.followup.send(message, ephemeral=True)
            else:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
        else:
            await ctx_or_interaction.send(message)

# Helper function to convert role input to Role object
async def get_role_from_input(guild, role_input):
    """Convert role input (mention, ID, or name) to Role object"""
    try:
        # Try to get by mention or ID
        if role_input.startswith('<@&') and role_input.endswith('>'):
            role_id = int(role_input[3:-1])
        else:
            role_id = int(role_input)
        
        role = guild.get_role(role_id)
        if role:
            return role
    except ValueError:
        pass
    
    # Try to get by name
    role = discord.utils.get(guild.roles, name=role_input)
    if role:
        return role
    
    return None

# Prefix command: !viewlock
@commands.command(name='viewlock')
@has_required_roles('viewlock')
async def viewlock_prefix(ctx, *roles_input):
    """Lock channel viewing to specific roles"""
    await handle_viewlock(ctx, list(roles_input), is_slash=False)

@viewlock_prefix.error
async def viewlock_prefix_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ You don't have permission to use this command!")

# Slash command: /viewlock
@app_commands.command(name="viewlock", description="Lock channel viewing to specific roles")
@app_commands.describe(roles="Roles that can view the channel (optional)")
async def viewlock_slash(interaction: discord.Interaction, roles: str = None):
    """Lock channel viewing to specific roles"""
    if not await slash_has_required_roles(interaction, 'viewlock'):
        await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        return
    
    roles_list = [roles] if roles else []
    await handle_viewlock(interaction, roles_list, is_slash=True)

async def handle_viewlock(ctx_or_interaction, roles_input, is_slash: bool):
    """Common viewlock handling logic"""
    try:
        # Check if bot has manage_channels permission
        if not ctx_or_interaction.guild.me.guild_permissions.manage_channels:
            message = "❌ I don't have permission to manage channels!"
            if is_slash:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
            else:
                await ctx_or_interaction.send(message)
            return
        
        channel = ctx_or_interaction.channel
        everyone_role = ctx_or_interaction.guild.default_role
        
        # Set View Channel to False for @everyone
        overwrites = channel.overwrites_for(everyone_role)
        overwrites.view_channel = False
        await channel.set_permissions(everyone_role, overwrite=overwrites)
        
        allowed_roles = []
        
        # Process role inputs
        for role_input in roles_input:
            if role_input:  # Skip empty inputs
                role = await get_role_from_input(ctx_or_interaction.guild, role_input)
                if role:
                    role_overwrites = channel.overwrites_for(role)
                    role_overwrites.view_channel = True
                    await channel.set_permissions(role, overwrite=role_overwrites)
                    allowed_roles.append(role)
                else:
                    message = f"⚠️ Role `{role_input}` not found, skipping..."
                    if is_slash:
                        if ctx_or_interaction.response.is_done():
                            await ctx_or_interaction.followup.send(message, ephemeral=True)
                        else:
                            await ctx_or_interaction.response.send_message(message, ephemeral=True)
                    else:
                        await ctx_or_interaction.send(message)
        
        # Create success message
        if allowed_roles:
            role_names = [role.name for role in allowed_roles]
            message = f"✅ **{channel.mention}** is now locked. Only **{'**,** '.join(role_names)}** can view this channel."
        else:
            message = f"✅ **{channel.mention}** is now locked. No one can view this channel."
        
        if is_slash:
            if ctx_or_interaction.response.is_done():
                await ctx_or_interaction.followup.send(message)
            else:
                await ctx_or_interaction.response.send_message(message)
        else:
            await ctx_or_interaction.send(message)
            
    except discord.Forbidden:
        message = "❌ I don't have permission to modify channel permissions!"
        if is_slash:
            if ctx_or_interaction.response.is_done():
                await ctx_or_interaction.followup.send(message, ephemeral=True)
            else:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
        else:
            await ctx_or_interaction.send(message)
    except Exception as e:
        message = f"❌ Failed to lock channel: {e}"
        if is_slash:
            if ctx_or_interaction.response.is_done():
                await ctx_or_interaction.followup.send(message, ephemeral=True)
            else:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
        else:
            await ctx_or_interaction.send(message)

async def handle_delete(ctx_or_interaction, channel: discord.TextChannel, is_slash: bool):
    """Common channel deletion logic with 10-second timer"""
    try:
        # Check if bot has manage_channels permission
        if not ctx_or_interaction.guild.me.guild_permissions.manage_channels:
            message = "❌ I don't have permission to manage channels!"
            if is_slash:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
            else:
                await ctx_or_interaction.send(message)
            return
        
        channel_name = channel.name
        channel_mention = channel.mention
        
        # Send warning message
        warning_message = f"⚠️ **{channel_mention}** will be deleted in **10 seconds**. Send any message in this channel to cancel deletion."
        
        if is_slash:
            if ctx_or_interaction.response.is_done():
                await ctx_or_interaction.followup.send(warning_message)
            else:
                await ctx_or_interaction.response.send_message(warning_message)
        else:
            await ctx_or_interaction.send(warning_message)
        
        # Define a check function to detect messages in the channel
        def check_message(message):
            return message.channel.id == channel.id and not message.author.bot
        
        # Wait for 10 seconds or until a message is sent in the channel
        try:
            # Wait for a message in the target channel
            await ctx_or_interaction.bot.wait_for('message', timeout=10.0, check=check_message)
            
            # If we get here, a message was sent in the channel
            cancel_message = f"✅ Deletion of **{channel_name}** has been cancelled."
            
            if is_slash:
                if ctx_or_interaction.response.is_done():
                    await ctx_or_interaction.followup.send(cancel_message)
                else:
                    await ctx_or_interaction.response.send_message(cancel_message)
            else:
                await ctx_or_interaction.send(cancel_message)
                
        except asyncio.TimeoutError:
            # No message was sent in 10 seconds, proceed with deletion
            await channel.delete()
            
            # Send success message (in the channel that executed the command, not the deleted one)
            success_message = f"✅ Channel **{channel_name}** has been deleted."
            
            if is_slash:
                if ctx_or_interaction.response.is_done():
                    await ctx_or_interaction.followup.send(success_message)
                else:
                    await ctx_or_interaction.response.send_message(success_message)
            else:
                await ctx_or_interaction.send(success_message)
            
    except discord.Forbidden:
        message = "❌ I don't have permission to delete this channel!"
        if is_slash:
            if ctx_or_interaction.response.is_done():
                await ctx_or_interaction.followup.send(message, ephemeral=True)
            else:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
        else:
            await ctx_or_interaction.send(message)
    except Exception as e:
        message = f"❌ Failed to delete channel: {e}"
        if is_slash:
            if ctx_or_interaction.response.is_done():
                await ctx_or_interaction.followup.send(message, ephemeral=True)
            else:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
        else:
            await ctx_or_interaction.send(message)

# Setup function to register commands with the bot
# Setup function to register commands with the bot
def setup_commands(bot_instance):
    # Add prefix commands
    bot_instance.add_command(ping_prefix)
    bot_instance.add_command(rename_prefix)
    bot_instance.add_command(sync_prefix)
    bot_instance.add_command(viewlock_prefix)
    bot_instance.add_command(delete_prefix)
    
    # Add slash commands
    bot_instance.tree.add_command(ping_slash)
    bot_instance.tree.add_command(ChannelCommands(name="channel", description="Channel management commands"))
    bot_instance.tree.add_command(sync_slash)
    bot_instance.tree.add_command(viewlock_slash)