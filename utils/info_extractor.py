from discord import Guild, Member, User
from discord.abc import GuildChannel


def get_guild_info(guild: Guild):
    return {
        "name": guild.name,
        "id": guild.id,
        "icon": getattr(guild.icon, "url", ""),
        "members": [get_member_info(member) for member in guild.members],
        "channels": [get_channel_info(channel) for channel in guild.channels]
    }


def get_member_info(member: Member):
    return {
        "name": member.name,
        "global_name": member.global_name,
        "id": member.id,
        "avatar": getattr(member.avatar, "url", "")
    }


def get_channel_info(channel: GuildChannel):
    return {
        "name": channel.name,
        "id": channel.id,
        "type": channel.type.name
    }


def get_user_info(user: User):
    return {
        "name": user.name,
        "global_name": user.global_name,
        "id": user.id,
        "avatar": getattr(user.avatar, "url", "")
    }
