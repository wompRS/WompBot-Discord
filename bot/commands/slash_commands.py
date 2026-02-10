"""
Slash commands for WompBot Discord bot.

This module contains all slash commands (/ syntax using app_commands).
"""

import os
import asyncio
import logging
import discord
from discord import app_commands
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Literal
from collections import Counter
from features.admin_utils import is_bot_admin, is_bot_admin_interaction, is_super_admin, SUPER_ADMIN_IDS

logger = logging.getLogger(__name__)

import re

def register_slash_commands(bot, db, llm, claims_tracker, chat_stats, stats_viz,
                            debate_scorekeeper, yearly_wrapped, qotd, iracing,
                            iracing_viz, iracing_team_manager, help_system,
                            wompie_user_id, series_autocomplete_cache, trivia,
                            rag=None, dashboard=None, poll_system=None):
    """
    Register all slash commands with the bot.

    Args:
        bot: Discord bot instance
        db: Database instance
        llm: LLM client instance
        claims_tracker: Claims tracking system
        chat_stats: Chat statistics system
        stats_viz: Statistics visualization system
        debate_scorekeeper: Debate tracking system
        yearly_wrapped: Yearly wrapped stats system
        qotd: Quote of the day system
        iracing: iRacing API wrapper
        iracing_viz: iRacing visualization system
        iracing_team_manager: iRacing team management system
        help_system: Help system instance
        wompie_user_id: Wompie's Discord user ID (list ref)
        series_autocomplete_cache: iRacing series cache dict (mutable ref)
        trivia: Trivia system instance
    """

    # Unpack Wompie user ID
    WOMPIE_USER_ID = wompie_user_id[0] if isinstance(wompie_user_id, list) else wompie_user_id

    @bot.tree.command(name="help", description="Show all commands or get detailed help for a specific command or category")
    @app_commands.describe(command="Command or category: tools, stats, claims, debates, trivia, games, polls, reminders, analytics, iracing, admin, etc.")
    async def help_slash(interaction: discord.Interaction, command: str = None):
        """Show bot commands or detailed help for a specific command or category"""
        if command:
            command_lower = command.lower().strip()

            # First check if it's a category
            embed = help_system.get_category_help(command_lower)
            if embed:
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Then check for specific command
            embed = help_system.get_command_help(command_lower)
            if embed:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                # List available categories
                categories = help_system.get_available_categories()
                cat_list = ", ".join(f"`{c}`" for c in categories)
                await interaction.response.send_message(
                    f"No help found for `{command}`.\n\n"
                    f"**Categories:** {cat_list}\n\n"
                    f"Use `/help <category>` for commands in a category, or `/help` for the overview.",
                    ephemeral=True
                )
        else:
            # Show general help
            embed = help_system.get_general_help()
            await interaction.response.send_message(embed=embed)
    
    # CHAT STATISTICS SLASH COMMANDS
    
    @bot.tree.command(name="stats_server", description="Show server network graph and interaction statistics")
    @app_commands.describe(date_range="Days (e.g., '30') or date range (e.g., '01/15/2024-02/15/2024')")
    async def stats_server(interaction: discord.Interaction, date_range: str = "30"):
        """Show server network statistics and interaction graph"""
        await interaction.response.defer()
    
        try:
            # Parse date range
            start_date, end_date = chat_stats.parse_date_range(date_range)
    
            # Check cache
            scope = f"server:{interaction.guild.id}"
            cached = chat_stats.get_cached_stats('network', scope, start_date, end_date)
    
            if cached:
                results = cached
            else:
                # Get messages
                messages = chat_stats.get_messages_for_analysis(None, start_date, end_date, exclude_opted_out=True)
    
                if not messages:
                    await interaction.followup.send("No messages found in this time range.")
                    return
    
                # Build network graph
                network = chat_stats.build_network_graph(messages)
                results = network
    
                # Cache results
                chat_stats.cache_stats('network', scope, start_date, end_date, results, cache_hours=6)
    
            # Create visualization
            if stats_viz:
                nodes = results['nodes']
                top_users = sorted(nodes.items(), key=lambda x: x[1]['degree'], reverse=True)[:20]
    
                image_buffer = stats_viz.create_network_table(
                    top_users=top_users,
                    total_users=len(nodes),
                    start_date=start_date,
                    end_date=end_date
                )
    
                file = discord.File(fp=image_buffer, filename="network_stats.png")
                await interaction.followup.send(file=file)
            else:
                # Fallback to embed if visualizer not loaded
                embed = discord.Embed(
                    title="📊 Server Network Statistics",
                    description=f"Analysis from {start_date.strftime('%m/%d/%Y')} to {end_date.strftime('%m/%d/%Y')}",
                    color=discord.Color.blue()
                )
    
                nodes = results['nodes']
                top_users = sorted(nodes.items(), key=lambda x: x[1]['degree'], reverse=True)[:10]
    
                table_data = []
                for _, data in top_users:
                    table_data.append([data['username'][:15], str(data['messages']), str(data['degree'])])
    
                table = chat_stats.format_as_discord_table(
                    ['User', 'Messages', 'Connections'],
                    table_data
                )
    
                embed.add_field(name="Most Connected Users", value=table, inline=False)
                embed.set_footer(text=f"Total users analyzed: {len(nodes)} | Cached for 6 hours")
    
                await interaction.followup.send(embed=embed)
    
        except ValueError as e:
            await interaction.followup.send(f"❌ {str(e)}")
        except Exception as e:
            await interaction.followup.send(f"❌ Error generating stats: {str(e)}")
            print(f"❌ Stats error: {e}")
            import traceback
            traceback.print_exc()
    
    @bot.tree.command(name="stats_topics", description="Show trending topics and keywords")
    @app_commands.describe(date_range="Days (e.g., '30') or date range (e.g., '01/15/2024-02/15/2024')")
    async def stats_topics(interaction: discord.Interaction, date_range: str = "30"):
        """Show trending topics using TF-IDF keyword extraction"""
        await interaction.response.defer()
    
        try:
            # Parse date range
            start_date, end_date = chat_stats.parse_date_range(date_range)
    
            # Check cache
            scope = f"server:{interaction.guild.id}"
            cached = chat_stats.get_cached_stats('topics', scope, start_date, end_date)
    
            if cached:
                topics = cached
            else:
                # Get messages
                messages = chat_stats.get_messages_for_analysis(None, start_date, end_date, exclude_opted_out=True)
    
                if not messages:
                    await interaction.followup.send("No messages found in this time range.")
                    return
    
                # Extract topics
                topics = chat_stats.extract_topics_tfidf(messages, top_n=15)
    
                if not topics:
                    await interaction.followup.send("Could not extract topics from messages.")
                    return
    
                # Cache results
                chat_stats.cache_stats('topics', scope, start_date, end_date, topics, cache_hours=6)
    
            # Create visualization
            if stats_viz:
                image_buffer = stats_viz.create_topics_barchart(
                    topics=topics,
                    start_date=start_date,
                    end_date=end_date
                )
    
                file = discord.File(fp=image_buffer, filename="trending_topics.png")
                await interaction.followup.send(file=file)
            else:
                # Fallback to embed
                embed = discord.Embed(
                    title="🔥 Trending Topics",
                    description=f"Top keywords from {start_date.strftime('%m/%d/%Y')} to {end_date.strftime('%m/%d/%Y')}",
                    color=discord.Color.orange()
                )
    
                table_data = []
                for i, topic in enumerate(topics[:15], 1):
                    bar_length = int(topic['score'] * 20)
                    bar = "█" * bar_length
                    table_data.append([f"{i}.", topic['keyword'][:20], str(topic['count']), bar])
    
                table = chat_stats.format_as_discord_table(
                    ['#', 'Keyword', 'Count', 'Relevance'],
                    table_data
                )
    
                embed.add_field(name="Top Keywords (TF-IDF Analysis)", value=table, inline=False)
                embed.set_footer(text="Cached for 6 hours | Uses keyword extraction (no LLM)")
    
                await interaction.followup.send(embed=embed)
    
        except ValueError as e:
            await interaction.followup.send(f"❌ {str(e)}")
        except Exception as e:
            await interaction.followup.send(f"❌ Error generating topics: {str(e)}")
            print(f"❌ Topics error: {e}")
            import traceback
            traceback.print_exc()
    
    @bot.tree.command(name="stats_primetime", description="Show activity patterns and peak hours")
    @app_commands.describe(
        user="User to analyze (optional, defaults to server-wide)",
        date_range="Days (e.g., '30') or date range (e.g., '01/15/2024-02/15/2024')"
    )
    async def stats_primetime(interaction: discord.Interaction, user: discord.Member = None, date_range: str = "30"):
        """Show activity heatmap and peak hours"""
        await interaction.response.defer()
    
        try:
            # Parse date range
            start_date, end_date = chat_stats.parse_date_range(date_range)
    
            # Determine scope
            if user:
                scope = f"user:{user.id}"
            else:
                scope = f"server:{interaction.guild.id}"
    
            # Check cache
            cached = chat_stats.get_cached_stats('primetime', scope, start_date, end_date)
    
            if cached:
                results = cached
            else:
                # Get messages
                messages = chat_stats.get_messages_for_analysis(None, start_date, end_date, exclude_opted_out=True)
    
                # Filter by user if specified
                if user:
                    messages = [m for m in messages if m['user_id'] == user.id]
    
                if not messages:
                    await interaction.followup.send(f"No messages found for {user.display_name if user else 'server'} in this time range.")
                    return
    
                # Calculate primetime stats
                results = chat_stats.calculate_primetime(messages)
    
                # Cache results
                chat_stats.cache_stats('primetime', scope, start_date, end_date, results, cache_hours=6)
    
            # Create visualization
            target_name = user.display_name if user else "Server"
    
            if stats_viz:
                image_buffer = stats_viz.create_primetime_heatmap(
                    hourly=results['hourly'],
                    daily=results['daily'],
                    target_name=target_name,
                    start_date=start_date,
                    end_date=end_date
                )
    
                file = discord.File(fp=image_buffer, filename="primetime_analysis.png")
                await interaction.followup.send(file=file)
            else:
                # Fallback to embed
                embed = discord.Embed(
                    title=f"⏰ Prime Time Analysis - {target_name}",
                    description=f"Activity from {start_date.strftime('%m/%d/%Y')} to {end_date.strftime('%m/%d/%Y')}",
                    color=discord.Color.purple()
                )
    
                hourly = results['hourly']
                max_hour_count = max(hourly.values()) if hourly else 1
    
                hourly_viz = []
                for hour in range(24):
                    count = hourly.get(hour, 0)
                    bar_length = int((count / max_hour_count) * 15) if max_hour_count > 0 else 0
                    bar = "█" * bar_length
                    time_str = f"{hour:02d}:00"
                    hourly_viz.append([time_str, str(count), bar])
    
                hourly_table = chat_stats.format_as_discord_table(
                    ['Hour', 'Msgs', 'Activity'],
                    hourly_viz
                )
    
                embed.add_field(name="Hourly Activity", value=hourly_table, inline=False)
    
                day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
                daily = results['daily']
                max_day_count = max(daily.values()) if daily else 1
    
                daily_viz = []
                for day in range(7):
                    count = daily.get(day, 0)
                    bar_length = int((count / max_day_count) * 15) if max_day_count > 0 else 0
                    bar = "█" * bar_length
                    daily_viz.append([day_names[day], str(count), bar])
    
                daily_table = chat_stats.format_as_discord_table(
                    ['Day', 'Msgs', 'Activity'],
                    daily_viz
                )
    
                embed.add_field(name="Day of Week", value=daily_table, inline=False)
    
                peak_hour = results['peak_hour']
                peak_day = day_names[results['peak_day']]
                embed.set_footer(text=f"Peak hour: {peak_hour:02d}:00 | Peak day: {peak_day} | Total: {results['total_messages']} msgs")
    
                await interaction.followup.send(embed=embed)
    
        except ValueError as e:
            await interaction.followup.send(f"❌ {str(e)}")
        except Exception as e:
            await interaction.followup.send(f"❌ Error generating primetime stats: {str(e)}")
            print(f"❌ Primetime error: {e}")
            import traceback
            traceback.print_exc()
    
    @bot.tree.command(name="stats_engagement", description="Show engagement metrics and conversation patterns")
    @app_commands.describe(
        user="User to analyze (optional, defaults to server-wide)",
        date_range="Days (e.g., '30') or date range (e.g., '01/15/2024-02/15/2024')"
    )
    async def stats_engagement(interaction: discord.Interaction, user: discord.Member = None, date_range: str = "30"):
        """Show engagement metrics"""
        await interaction.response.defer()
    
        try:
            # Parse date range
            start_date, end_date = chat_stats.parse_date_range(date_range)
    
            # Determine scope
            if user:
                scope = f"user_engagement:{user.id}"
            else:
                scope = f"server_engagement:{interaction.guild.id}"
    
            # Check cache
            cached = chat_stats.get_cached_stats('engagement', scope, start_date, end_date)
    
            if cached:
                results = cached
            else:
                # Get messages
                messages = chat_stats.get_messages_for_analysis(None, start_date, end_date, exclude_opted_out=True)
    
                # Filter by user if specified
                if user:
                    messages = [m for m in messages if m['user_id'] == user.id]
    
                if not messages:
                    await interaction.followup.send(f"No messages found for {user.display_name if user else 'server'} in this time range.")
                    return
    
                # Calculate engagement
                results = chat_stats.calculate_engagement(messages)
    
                # Cache results
                chat_stats.cache_stats('engagement', scope, start_date, end_date, results, cache_hours=6)
    
            # Format output
            target_name = user.display_name if user else "Server"
    
            if stats_viz:
                image_buffer = stats_viz.create_engagement_dashboard(
                    stats=results,
                    top_responders=results.get('top_responders', []),
                    target_name=target_name,
                    start_date=start_date,
                    end_date=end_date
                )
    
                file = discord.File(fp=image_buffer, filename="engagement_metrics.png")
                await interaction.followup.send(file=file)
            else:
                # Fallback to embed if visualizer not loaded
                embed = discord.Embed(
                    title=f"📈 Engagement Metrics - {target_name}",
                    description=f"Analysis from {start_date.strftime('%m/%d/%Y')} to {end_date.strftime('%m/%d/%Y')}",
                    color=discord.Color.green()
                )
    
                # Summary stats
                embed.add_field(name="Total Messages", value=f"{results['total_messages']:,}", inline=True)
                embed.add_field(name="Unique Users", value=f"{results['unique_users']}", inline=True)
                embed.add_field(name="Avg Length", value=f"{results['avg_message_length']:.1f} chars", inline=True)
    
                if not user:
                    embed.add_field(name="Avg Msgs/User", value=f"{results['avg_messages_per_user']:.1f}", inline=True)
    
                # Top responders
                if results['top_responders']:
                    table_data = []
                    for username, count in results['top_responders'][:10]:
                        table_data.append([username[:15], str(count)])
    
                    table = chat_stats.format_as_discord_table(
                        ['User', 'Responses'],
                        table_data
                    )
    
                    embed.add_field(name="Most Responsive Users", value=table, inline=False)
    
                await interaction.followup.send(embed=embed)
    
        except ValueError as e:
            await interaction.followup.send(f"❌ {str(e)}")
        except Exception as e:
            await interaction.followup.send(f"❌ Error generating engagement stats: {str(e)}")
            print(f"❌ Engagement error: {e}")
            import traceback
            traceback.print_exc()

    @bot.tree.command(name="wrapped", description="View your yearly activity summary (Spotify Wrapped for Discord!)")
    @app_commands.describe(
        year="Year to get wrapped for (defaults to current year)",
        user="User to view wrapped for (defaults to yourself)"
    )
    async def wrapped(interaction: discord.Interaction, year: int = None, user: discord.Member = None):
        """Generate yearly wrapped statistics"""
        await interaction.response.defer()
    
        try:
            # Rate limiting for expensive wrapped generation
            wrapped_cooldown = int(os.getenv('WRAPPED_COOLDOWN', '60'))  # 60 seconds default
            rate_check = db.check_feature_rate_limit(
                interaction.user.id,
                'wrapped',
                cooldown_seconds=wrapped_cooldown
            )
    
            if not rate_check['allowed']:
                wait_seconds = rate_check.get('wait_seconds', 60)
                await interaction.followup.send(
                    f"⏱️ Wrapped cooldown! Please wait {wait_seconds} seconds before generating another wrapped."
                )
                return
    
            target_user = user if user else interaction.user
            target_year = year if year else datetime.now().year
    
            # Validate year
            current_year = datetime.now().year
            if target_year < 2020 or target_year > current_year:
                await interaction.followup.send(f"❌ Please choose a year between 2020 and {current_year}")
                return
    
            # Generate wrapped data
            wrapped_data = await yearly_wrapped.generate_wrapped(target_user.id, target_year)
    
            if not wrapped_data:
                await interaction.followup.send(
                    f"📊 No data found for {target_user.display_name} in {target_year}"
                )
                return
    
            if stats_viz:
                # Transform wrapped data into visualization format
                sections = []
    
                # Message Activity Section
                msg_stats = wrapped_data['message_stats']
                msg_metrics = [("Total Messages", f"{msg_stats['total_messages']:,}")]
                if msg_stats['server_rank']:
                    msg_metrics.append(("Server Rank", f"#{msg_stats['server_rank']}"))
                if msg_stats['most_active_month']:
                    month_name = yearly_wrapped.format_month_name(msg_stats['most_active_month'])
                    msg_metrics.append(("Most Active Month", month_name))
                if msg_stats['most_active_day_of_week'] is not None:
                    day_name = yearly_wrapped.format_day_name(msg_stats['most_active_day_of_week'])
                    msg_metrics.append(("Favorite Day", day_name))
                if msg_stats['most_active_hour'] is not None:
                    hour = msg_stats['most_active_hour']
                    period = 'AM' if hour < 12 else 'PM'
                    display_hour = hour if hour <= 12 else hour - 12
                    display_hour = 12 if display_hour == 0 else display_hour
                    msg_metrics.append(("Peak Hour", f"{display_hour} {period}"))
                sections.append({"title": "💬 Message Activity", "metrics": msg_metrics})
    
                # Social Stats Section
                social_stats = wrapped_data['social_stats']
                if social_stats['top_conversation_partner'] or social_stats['replies_sent'] > 0:
                    social_metrics = []
                    if social_stats['replies_sent'] > 0:
                        social_metrics.append(("Replies Sent", social_stats['replies_sent']))
                    if social_stats['replies_received'] > 0:
                        social_metrics.append(("Replies Received", social_stats['replies_received']))
                    if social_stats['top_conversation_partner']:
                        # Get username for partner ID
                        partner_id = social_stats['top_conversation_partner']
                        partner_user = interaction.guild.get_member(partner_id)
                        partner_name = partner_user.display_name if partner_user else f"User {partner_id}"
                        social_metrics.append(("Top Buddy", f"{partner_name} ({social_stats['top_partner_count']} replies)"))
                    if social_metrics:
                        sections.append({"title": "👥 Social Network", "metrics": social_metrics})
    
                # Claims & Hot Takes Section
                claims_stats = wrapped_data['claims_stats']
                if claims_stats['total_claims'] > 0 or claims_stats['hot_take_count'] > 0:
                    claims_metrics = []
                    if claims_stats['total_claims'] > 0:
                        claims_metrics.append(("Claims Tracked", claims_stats['total_claims']))
                    if claims_stats['hot_take_count'] > 0:
                        claims_metrics.append(("Hot Takes", claims_stats['hot_take_count']))
                        if claims_stats['avg_controversy_score'] > 0:
                            claims_metrics.append(("Avg Controversy", f"{claims_stats['avg_controversy_score']}/10"))
                        if claims_stats['vindicated'] > 0:
                            claims_metrics.append(("Vindicated ✅", claims_stats['vindicated']))
                        if claims_stats['wrong'] > 0:
                            claims_metrics.append(("Wrong ❌", claims_stats['wrong']))
                    if claims_metrics:
                        sections.append({"title": "🔥 Claims & Hot Takes", "metrics": claims_metrics})
    
                # Quotes Section
                quotes_stats = wrapped_data['quotes_stats']
                if quotes_stats['quotes_received'] > 0 or quotes_stats['quotes_saved'] > 0:
                    quotes_metrics = []
                    if quotes_stats['quotes_received'] > 0:
                        quotes_metrics.append(("Times Quoted", quotes_stats['quotes_received']))
                    if quotes_stats['quotes_saved'] > 0:
                        quotes_metrics.append(("Quotes Saved", quotes_stats['quotes_saved']))
                    if quotes_stats['most_quoted_person']:
                        quotee_id = quotes_stats['most_quoted_person']
                        quotee_user = interaction.guild.get_member(quotee_id)
                        quotee_name = quotee_user.display_name if quotee_user else f"User {quotee_id}"
                        quotes_metrics.append(("Favorite Quotee", quotee_name))
                    if quotes_metrics:
                        sections.append({"title": "☁️ Quotes", "metrics": quotes_metrics})
    
                # Personality Section
                personality = wrapped_data['personality']
                if personality['question_rate'] > 0 or personality['fact_checks_requested'] > 0:
                    personality_metrics = []
                    if personality['question_rate'] > 0:
                        personality_metrics.append(("Question Rate", f"{personality['question_rate']}%"))
                    if personality['profanity_score'] > 0:
                        personality_metrics.append(("Profanity Score", f"{personality['profanity_score']}/10"))
                    if personality['fact_checks_requested'] > 0:
                        personality_metrics.append(("Fact Checks", personality['fact_checks_requested']))
                    if personality_metrics:
                        sections.append({"title": "🎭 Personality", "metrics": personality_metrics})
    
                # Achievements Section
                achievements = wrapped_data['achievements']
                if achievements:
                    sections.append({"title": "🏆 Achievements", "metrics": [("", " ".join(achievements))]})
    
                image_buffer = stats_viz.create_wrapped_summary(
                    username=target_user.display_name,
                    year=target_year,
                    sections=sections
                )
    
                file = discord.File(fp=image_buffer, filename=f"wrapped_{target_year}.png")
                await interaction.followup.send(file=file)
                db.record_feature_usage(interaction.user.id, 'wrapped')
                print(f"📊 Generated {target_year} wrapped for {target_user.display_name}")
                return
    
            # Create beautiful embed (fallback)
            embed = discord.Embed(
                title=f"📊 {target_year} Wrapped",
                description=f"**{target_user.display_name}'s Year in Review**",
                color=discord.Color.gold()
            )
    
            # Set thumbnail
            embed.set_thumbnail(url=target_user.display_avatar.url)
    
            # Message Activity
            msg_stats = wrapped_data['message_stats']
            activity_text = f"**{msg_stats['total_messages']:,}** messages sent"
            if msg_stats['server_rank']:
                activity_text += f"\n🏆 **Rank #{msg_stats['server_rank']}** in server"
            if msg_stats['most_active_month']:
                month_name = yearly_wrapped.format_month_name(msg_stats['most_active_month'])
                activity_text += f"\n📅 Most active: **{month_name}**"
            if msg_stats['most_active_day_of_week'] is not None:
                day_name = yearly_wrapped.format_day_name(msg_stats['most_active_day_of_week'])
                activity_text += f"\n📆 Favorite day: **{day_name}**"
            if msg_stats['most_active_hour'] is not None:
                hour = msg_stats['most_active_hour']
                period = 'AM' if hour < 12 else 'PM'
                display_hour = hour if hour <= 12 else hour - 12
                display_hour = 12 if display_hour == 0 else display_hour
                activity_text += f"\n⏰ Peak hour: **{display_hour} {period}**"
    
            embed.add_field(
                name="💬 Message Activity",
                value=activity_text,
                inline=False
            )
    
            # Social Stats
            social_stats = wrapped_data['social_stats']
            if social_stats['top_conversation_partner'] or social_stats['replies_sent'] > 0:
                social_text = ""
                if social_stats['replies_sent'] > 0:
                    social_text += f"**{social_stats['replies_sent']}** replies sent\n"
                if social_stats['replies_received'] > 0:
                    social_text += f"**{social_stats['replies_received']}** replies received\n"
                if social_stats['top_conversation_partner']:
                    social_text += f"🗣️ Top buddy: <@{social_stats['top_conversation_partner']}> ({social_stats['top_partner_count']} replies)"
    
                if social_text:
                    embed.add_field(
                        name="👥 Social Network",
                        value=social_text,
                        inline=False
                    )
    
            # Claims & Hot Takes
            claims_stats = wrapped_data['claims_stats']
            if claims_stats['total_claims'] > 0 or claims_stats['hot_take_count'] > 0:
                claims_text = ""
                if claims_stats['total_claims'] > 0:
                    claims_text += f"📋 **{claims_stats['total_claims']}** claims tracked\n"
                if claims_stats['hot_take_count'] > 0:
                    claims_text += f"🔥 **{claims_stats['hot_take_count']}** hot takes\n"
                    if claims_stats['avg_controversy_score'] > 0:
                        claims_text += f"⚡ Controversy: **{claims_stats['avg_controversy_score']}/10**\n"
                    if claims_stats['vindicated'] > 0:
                        claims_text += f"✅ Vindicated: **{claims_stats['vindicated']}**\n"
                    if claims_stats['wrong'] > 0:
                        claims_text += f"❌ Wrong: **{claims_stats['wrong']}**"
    
                if claims_text:
                    embed.add_field(
                        name="🔥 Claims & Hot Takes",
                        value=claims_text,
                        inline=True
                    )
    
            # Quotes
            quotes_stats = wrapped_data['quotes_stats']
            if quotes_stats['quotes_received'] > 0 or quotes_stats['quotes_saved'] > 0:
                quotes_text = ""
                if quotes_stats['quotes_received'] > 0:
                    quotes_text += f"☁️ **{quotes_stats['quotes_received']}** times quoted\n"
                if quotes_stats['quotes_saved'] > 0:
                    quotes_text += f"💾 **{quotes_stats['quotes_saved']}** quotes saved\n"
                if quotes_stats['most_quoted_person']:
                    quotes_text += f"⭐ Favorite quotee: <@{quotes_stats['most_quoted_person']}>"
    
                if quotes_text:
                    embed.add_field(
                        name="☁️ Quotes",
                        value=quotes_text,
                        inline=True
                    )
    
            # Personality Insights
            personality = wrapped_data['personality']
            if personality['question_rate'] > 0 or personality['fact_checks_requested'] > 0:
                personality_text = ""
                if personality['question_rate'] > 0:
                    personality_text += f"❓ Question rate: **{personality['question_rate']}%**\n"
                if personality['profanity_score'] > 0:
                    personality_text += f"🤬 Profanity: **{personality['profanity_score']}/10**\n"
                if personality['fact_checks_requested'] > 0:
                    personality_text += f"⚠️ Fact checks: **{personality['fact_checks_requested']}**"
    
                if personality_text:
                    embed.add_field(
                        name="🎭 Personality",
                        value=personality_text,
                        inline=False
                    )
    
            # Achievements
            achievements = wrapped_data['achievements']
            if achievements:
                embed.add_field(
                    name="🏆 Achievements",
                    value=" ".join(achievements),
                    inline=False
                )
    
            # Footer
            embed.set_footer(text=f"Your {target_year} wrapped • Generated with ❤️")
            embed.timestamp = datetime.now()
    
            await interaction.followup.send(embed=embed)
            db.record_feature_usage(interaction.user.id, 'wrapped')
            print(f"📊 Generated {target_year} wrapped for {target_user.display_name}")
    
        except Exception as e:
            await interaction.followup.send(f"❌ Error generating wrapped: {str(e)}")
            print(f"❌ Wrapped error: {e}")
            import traceback
            traceback.print_exc()

    # ===== Debate Scorekeeper =====
    @bot.tree.command(name="debate_start", description="Start tracking a debate")
    @app_commands.describe(topic="What's being debated?")
    async def debate_start(interaction: discord.Interaction, topic: str):
        """Start tracking a debate in this channel"""
        success = await debate_scorekeeper.start_debate(
            interaction.channel.id,
            interaction.guild.id,
            topic,
            interaction.user.id,
            str(interaction.user)
        )
    
        if success:
            await interaction.response.send_message(
                f"⚔️ **Debate Started!**\n"
                f"Topic: **{topic}**\n\n"
                f"All messages in this channel are now being tracked.\n"
                f"Use `!debate_end` when finished to see analysis and results!"
            )
        else:
            await interaction.response.send_message(
                "❌ There's already an active debate in this channel!\n"
                f"Current topic: **{debate_scorekeeper.get_active_debate_topic(interaction.channel.id)}**"
            )

    # ===== iRacing Integration =====
    @bot.tree.command(name="iracing_link", description="Link your Discord account to your iRacing account")
    @app_commands.describe(iracing_id_or_name="Your iRacing Customer ID (numeric) or display name")
    async def iracing_link(interaction: discord.Interaction, iracing_id_or_name: str):
        """Link Discord account to iRacing"""
        if not iracing:
            await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
            return
    
        await interaction.response.defer()
    
        try:
            cust_id = None
            display_name = None
    
            # Check if input is a customer ID (all digits)
            if iracing_id_or_name.strip().isdigit():
                cust_id = int(iracing_id_or_name.strip())
    
                # Get profile to verify customer ID and get display name
                profile = await iracing.get_driver_profile(cust_id)
    
                if profile:
                    # Try to extract display name from profile
                    # The structure may vary, try different locations
                    if isinstance(profile, dict):
                        display_name = (
                            profile.get('display_name') or
                            profile.get('name') or
                            profile.get('member_info', {}).get('display_name') or
                            f"Driver {cust_id}"
                        )
                        # Log what we extracted for debugging
                        logger.debug("Link: Extracted display_name='%s' from profile for cust_id=%s", display_name, cust_id)
                        logger.debug("profile.get('display_name')='%s'", profile.get('display_name'))
                        logger.debug("profile.get('name')='%s'", profile.get('name'))
                    else:
                        display_name = f"Driver {cust_id}"
                        logger.warning("Link: Profile is not a dict, using fallback: %s", display_name)
                else:
                    await interaction.followup.send(
                        f"❌ Could not find iRacing profile for customer ID {cust_id}\n"
                        f"Make sure the ID is correct."
                    )
                    return
            else:
                # Search by name
                results = await iracing.search_driver(iracing_id_or_name)
    
                if not results or len(results) == 0:
                    await interaction.followup.send(
                        f"❌ No iRacing driver found with name '{iracing_id_or_name}'\n"
                        f"💡 **Tip**: Try using your iRacing Customer ID instead (just the numbers)\n"
                        f"Find it at: https://members.iracing.com/membersite/member/Home.do"
                    )
                    return
    
                # Take first result (exact match preferred)
                driver = results[0]
                cust_id = driver.get('cust_id')
                display_name = driver.get('display_name', iracing_id_or_name)
    
            # Link the account
            success = await iracing.link_discord_to_iracing(
                interaction.user.id,
                cust_id,
                display_name
            )
    
            if success:
                await interaction.followup.send(
                    f"✅ Linked your Discord account to iRacing driver **{display_name}**\n"
                    f"You can now use `/iracing_profile` without specifying a name!"
                )
            else:
                await interaction.followup.send("❌ Failed to link accounts")
    
        except Exception as e:
            logger.error("iRacing link error: %s", e, exc_info=True)
            await interaction.followup.send("❌ Error linking account. Please try again later.")
    
    @bot.tree.command(name="iracing_profile", description="View iRacing driver profile and stats")
    @app_commands.describe(driver_name="Driver display name, real name, or customer ID (optional if linked)")
    async def iracing_profile(interaction: discord.Interaction, driver_name: str = None):
        """View iRacing driver profile"""
        if not iracing:
            await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
            return
    
        await interaction.response.defer()
    
        try:
            cust_id = None
            display_name = driver_name
    
            # If no driver name provided, check for linked account
            if not driver_name:
                linked = await iracing.get_linked_iracing_id(interaction.user.id)
                if linked:
                    cust_id, display_name = linked
                else:
                    await interaction.followup.send(
                        "❌ No driver name provided and no linked account found.\n"
                        "Use `/iracing_link` to link your account or provide a driver name."
                    )
                    return
            else:
                # Search for driver
                results = await iracing.search_driver(driver_name)
                if not results or len(results) == 0:
                    await interaction.followup.send(
                        f"❌ No driver found with name '{driver_name}'\n"
                        f"💡 Tip: Try the driver's customer ID for reliable results"
                    )
                    return
                cust_id = results[0].get('cust_id')
                display_name = results[0].get('display_name', driver_name)
    
            # Get profile data
            profile = await iracing.get_driver_profile(cust_id)
    
            if not profile:
                await interaction.followup.send("❌ Failed to retrieve profile data")
                return
    
            # Extract actual display name from profile (not customer ID, not first/last name)
            # Prioritize fresh API data over cached database value
            fresh_display_name = (
                profile.get('display_name') or
                profile.get('name') or
                display_name or
                f"Driver {cust_id}"
            )
    
            # Update display_name for use in visualizations and embeds
            display_name = fresh_display_name
    
            # Update database if user has linked account and name differs
            if display_name and display_name != f"Driver {cust_id}":
                # Attempt to update linked account with fresh display name
                try:
                    await iracing.link_discord_to_iracing(interaction.user.id, cust_id, display_name)
                except Exception as e:
                    logger.debug("Non-critical: Failed to update iRacing link: %s", e)
    
            if not iracing_viz:
                # Fallback to simple embed if visualizer failed to load
                embed = discord.Embed(
                    title=f"🏁 {display_name}",
                    description=f"Member since {profile.get('member_since', 'Unknown')}",
                    color=discord.Color.blue()
                )
    
                licenses = profile.get('licenses', {})
                for key, name in [('oval', '🏁 Oval'), ('sports_car', '🏎️ Road')]:
                    if key in licenses:
                        lic = licenses[key]
                        irating = lic.get('irating', 0)
                        sr = lic.get('safety_rating', 0.0)
                        embed.add_field(name=name, value=f"iR: {irating}\nSR: {sr:.2f}", inline=True)
    
                await interaction.followup.send(embed=embed)
                return
    
            # Get licenses data
            licenses = profile.get('licenses', {})
    
            if not licenses:
                await interaction.followup.send("❌ No license data found")
                return
    
            # Generate professional license overview showing all 5 categories
            image_buffer = iracing_viz.create_driver_license_overview(display_name, licenses)
    
            # Send as Discord file attachment
            file = discord.File(fp=image_buffer, filename="licenses.png")
    
            # Fetch career stats and member summary in parallel for richer data
            client = await iracing._get_client()
            career_stats, member_summary = await asyncio.gather(
                iracing.get_driver_career_stats(cust_id),
                client.get_member_summary(cust_id=cust_id),
                return_exceptions=True,
            )

            # Handle exceptions from gather
            if isinstance(career_stats, Exception):
                logger.warning("Failed to get career stats: %s", career_stats)
                career_stats = None
            if isinstance(member_summary, Exception):
                logger.warning("Failed to get member summary: %s", member_summary)
                member_summary = None

            embed = discord.Embed(
                title=f"🏁 {display_name}",
                description=f"Member since {profile.get('member_since', 'Unknown')}",
                color=discord.Color.blue()
            )

            if career_stats:
                stats = career_stats.get('stats', [])
                if stats:
                    total_starts = sum(s.get('starts', 0) for s in stats)
                    total_wins = sum(s.get('wins', 0) for s in stats)
                    total_podiums = sum(s.get('top3', 0) for s in stats)
                    total_top5 = sum(s.get('top5', 0) for s in stats)
                    total_poles = sum(s.get('poles', 0) for s in stats)
                    total_laps = sum(s.get('total_laps', 0) for s in stats)
                    total_laps_led = sum(s.get('laps_led', 0) for s in stats)

                    career_text = (
                        f"**Starts:** {total_starts:,}\n"
                        f"**Wins:** {total_wins:,}\n"
                        f"**Podiums:** {total_podiums:,}\n"
                        f"**Top 5:** {total_top5:,}\n"
                        f"**Poles:** {total_poles:,}"
                    )
                    embed.add_field(name="Career Stats", value=career_text, inline=True)

                    if total_laps > 0:
                        laps_text = f"**Total Laps:** {total_laps:,}\n**Laps Led:** {total_laps_led:,}"
                        if total_starts > 0:
                            win_pct = (total_wins / total_starts) * 100
                            laps_text += f"\n**Win Rate:** {win_pct:.1f}%"
                        embed.add_field(name="Laps", value=laps_text, inline=True)

            # Add member summary data if available
            if member_summary and isinstance(member_summary, dict):
                summary_parts = []
                for key in ('this_year', 'recent'):
                    section = member_summary.get(key)
                    if section and isinstance(section, list):
                        for cat in section[:2]:
                            cat_name = cat.get('category', 'Unknown')
                            starts = cat.get('starts', 0)
                            avg_finish = cat.get('avg_finish', 0)
                            if starts > 0:
                                summary_parts.append(f"**{cat_name}:** {starts} races, avg P{avg_finish:.1f}")
                        break

                if summary_parts:
                    embed.add_field(name="Recent Activity", value="\n".join(summary_parts), inline=False)

            await interaction.followup.send(embed=embed, file=file)

        except Exception as e:
            await interaction.followup.send("❌ Error getting profile")
            logger.error("iRacing profile error: %s", e, exc_info=True)
    
    async def series_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete function for series names"""
        if not iracing:
            logger.warning("Series autocomplete: iRacing integration not available")
            return []

        try:
            import asyncio
            import time

            # Try to use cache first for performance
            if series_autocomplete_cache and series_autocomplete_cache.get('data'):
                all_series = series_autocomplete_cache['data']
                logger.debug("Series autocomplete: Using cached data (%d series)", len(all_series))
            else:
                # No cache - fetch with timeout close to Discord's 3-second limit
                try:
                    all_series = await asyncio.wait_for(iracing.get_current_series(), timeout=2.8)
                    if all_series:
                        series_autocomplete_cache['data'] = all_series
                        series_autocomplete_cache['time'] = time.time()
                        logger.debug("Series autocomplete: Loaded %d series (cache created)", len(all_series))
                    else:
                        logger.warning("Series autocomplete: No series data returned")
                        # Return helpful message instead of empty list
                        return [app_commands.Choice(name="No series data available - try again in a moment", value="")]
                except asyncio.TimeoutError:
                    logger.warning("Series autocomplete: Timeout fetching series data")
                    # Return helpful message instead of empty list
                    return [app_commands.Choice(name="Loading series data... please try again", value="")]
                except Exception as e:
                    logger.warning("Series autocomplete fetch error: %s", e)
                    # Return helpful message instead of empty list
                    return [app_commands.Choice(name="Error loading series - try again in a moment", value="")]
    
            # Filter by current input
            current_lower = current.lower()

            def normalize_for_search(text):
                """Normalize text for fuzzy matching (handle umlauts, etc.)"""
                import unicodedata
                # Normalize unicode and convert to ASCII-friendly form
                normalized = unicodedata.normalize('NFKD', text.lower())
                # Remove diacritics (accents, umlauts)
                ascii_text = ''.join(c for c in normalized if not unicodedata.combining(c))
                return ascii_text

            # If no input yet, return top 25 series
            if not current_lower:
                matches = all_series[:25]
            else:
                search_terms = current_lower.split()
                normalized_search = normalize_for_search(current)

                def series_matches(s):
                    name = s.get('series_name', '')
                    name_lower = name.lower()
                    name_normalized = normalize_for_search(name)

                    # Check if all search terms match (supports multi-word search)
                    for term in search_terms:
                        term_normalized = normalize_for_search(term)
                        if term not in name_lower and term_normalized not in name_normalized:
                            return False
                    return True

                matches = [s for s in all_series if series_matches(s)]
    
            # Return up to 25 choices (Discord limit)
            choices = [
                app_commands.Choice(
                    name=s.get('series_name', 'Unknown')[:100],  # Discord limit is 100 chars
                    value=s.get('series_name', 'Unknown')[:100]
                )
                for s in matches[:25]
            ]
    
            logger.debug("Series autocomplete: Returning %d choices for '%s'", len(choices), current)
            return choices

        except Exception as e:
            logger.error("Series autocomplete error: %s: %s", type(e).__name__, e, exc_info=True)
            return []
    
    @bot.tree.command(name="iracing_schedule", description="View iRacing race schedule for a series or category")
    @app_commands.describe(
        series="Series name (leave blank if using category)",
        category="Show all series in this category for current week",
        week="Which week to show: current/previous/upcoming/full or week number (1-12)"
    )
    @app_commands.choices(
        category=[
            app_commands.Choice(name="Oval", value="oval"),
            app_commands.Choice(name="Sports Car", value="sports_car"),
            app_commands.Choice(name="Formula Car", value="formula_car"),
            app_commands.Choice(name="Dirt Oval", value="dirt_oval"),
            app_commands.Choice(name="Dirt Road", value="dirt_road")
        ]
    )
    @app_commands.autocomplete(series=series_autocomplete)
    async def iracing_schedule(interaction: discord.Interaction, series: str = None, category: str = None, week: str = "full"):
        """View series race schedule or category overview"""
        if not iracing:
            await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
            return
    
        await interaction.response.defer()
    
        try:
            # Get all series
            all_series = await iracing.get_current_series()
            if not all_series:
                await interaction.followup.send("❌ Failed to retrieve series data")
                return
    
            # Handle series-based schedule (takes priority if both series and category are provided)
            if series:
                import unicodedata

                def normalize_for_search(text):
                    """Normalize text for fuzzy matching (handle umlauts, etc.)"""
                    normalized = unicodedata.normalize('NFKD', text.lower())
                    return ''.join(c for c in normalized if not unicodedata.combining(c))

                # Find matching series (supports multi-word search and special chars)
                search_terms = series.lower().split()
                series_match = None

                for s in all_series:
                    name = s.get('series_name', '')
                    name_lower = name.lower()
                    name_normalized = normalize_for_search(name)

                    # Check if all search terms match
                    all_match = True
                    for term in search_terms:
                        term_normalized = normalize_for_search(term)
                        if term not in name_lower and term_normalized not in name_normalized:
                            all_match = False
                            break

                    if all_match:
                        series_match = s
                        break

                if not series_match:
                    await interaction.followup.send(f"❌ Series not found: '{series}'")
                    return
    
                series_id = series_match.get('series_id')
                series_name = series_match.get('series_name')
                season_id = series_match.get('season_id')
    
                logger.debug("Schedule request: series_id=%s, season_id=%s, series_name=%s", series_id, season_id, series_name)

                # Get schedule for this series
                schedule = await iracing.get_series_schedule(series_id, season_id)

                logger.debug("Schedule API returned %d entries", len(schedule) if schedule else 0)
    
                if not schedule or len(schedule) == 0:
                    await interaction.followup.send(f"❌ No schedule found for {series_name}")
                    return
    
                # Create visualization
                image_buffer = iracing_viz.create_schedule_table(series_name, schedule, week)
    
                # Send image
                file = discord.File(fp=image_buffer, filename="schedule.png")
                await interaction.followup.send(file=file)
    
            # Handle category-based schedule
            elif category:
                # Filter series by category (category_id is a string, not a number)
                category_series = [s for s in all_series if s.get('category_id') == category]
    
                logger.debug("Looking for category_id='%s', found %d series (before dedup)", category, len(category_series))
    
                # Deduplicate by series_id - keep only one season per series (prefer active=True)
                series_dict = {}
                for s in category_series:
                    series_id = s.get('series_id')
                    # If we haven't seen this series, or this one is active, use it
                    if series_id not in series_dict or s.get('active'):
                        series_dict[series_id] = s
    
                category_series = list(series_dict.values())
                logger.debug("After deduplication: %d unique series", len(category_series))
    
                if not category_series:
                    await interaction.followup.send(f"❌ No series found for category: {category}")
                    return
    
                # Get current week track for each series (using cached data from get_current_series)
                series_tracks = []
    
                # Get all seasons data once (this contains schedules already)
                client = await iracing._get_client()
                all_seasons = await client.get_series_seasons()
    
                # Build a map of season_id -> season data for fast lookup
                seasons_map = {season.get('season_id'): season for season in all_seasons}
    
                for s in category_series:
                    series_name = s.get('series_name')
                    season_id = s.get('season_id')
    
                    # Get the full season data with schedules
                    season_data = seasons_map.get(season_id)
                    if not season_data:
                        continue
    
                    schedules = season_data.get('schedules', [])
                    if not schedules:
                        continue
    
                    # Calculate current week based on dates
                    now = datetime.now(timezone.utc)
                    current_week_num = 0
    
                    # Debug: check first schedule entry
                    if schedules and series_name == category_series[0].get('series_name'):
                        first_week = schedules[0]
                        logger.debug("First schedule entry keys for %s: %s", series_name, list(first_week.keys()))
                        logger.debug("First week start_date: %s, race_week_num: %s, total schedules: %d",
                                     first_week.get('start_date'), first_week.get('race_week_num'), len(schedules))
    
                    for week_data in schedules:
                        start_date = week_data.get('start_date')
                        if start_date:
                            try:
                                # Parse date string (format: "2025-10-28") and make it timezone-aware
                                week_start = datetime.fromisoformat(start_date)
                                # Make it timezone-aware (UTC)
                                week_start = week_start.replace(tzinfo=timezone.utc)
                                week_end = week_start + timedelta(days=7)
    
                                if week_start <= now < week_end:
                                    current_week_num = week_data.get('race_week_num', 0)
                                    logger.debug("Found current week %d for %s", current_week_num, series_name)
                                    break
                            except Exception as e:
                                logger.debug("Error parsing date %s: %s", start_date, e)

                    if current_week_num == 0 and series_name == category_series[0].get('series_name'):
                        logger.debug("No current week found for %s, defaulting to 0", series_name)
    
                    # Find the current week's track
                    for week_data in schedules:
                        if week_data.get('race_week_num') == current_week_num:
                            track = week_data.get('track', {})
                            track_name = track.get('track_name', 'Unknown') if isinstance(track, dict) else 'Unknown'
                            config_name = track.get('config_name', '') if isinstance(track, dict) else ''
    
                            if config_name and config_name not in track_name:
                                full_track_name = f"{track_name} - {config_name}"
                            else:
                                full_track_name = track_name
    
                            series_tracks.append({
                                'series_name': series_name,
                                'track_name': full_track_name,
                                'week_num': current_week_num + 1
                            })
                            break
    
                if not series_tracks:
                    await interaction.followup.send(f"❌ No schedule data found for {category} series")
                    return
    
                # Create category schedule visualization
                category_display_name = category.replace('_', ' ').title()
                image_buffer = iracing_viz.create_category_schedule_table(category_display_name, series_tracks)
    
                file = discord.File(fp=image_buffer, filename="category_schedule.png")
                await interaction.followup.send(file=file)
    
            else:
                await interaction.followup.send("❌ Please specify either a series name or a category")
    
        except Exception as e:
            logger.error("iRacing schedule error: %s", e, exc_info=True)
            await interaction.followup.send("❌ Error getting schedule. Please try again later.")

    async def week_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[int]]:
        """Autocomplete function for week numbers with track names"""
        if not iracing:
            return [app_commands.Choice(name=f"Week {w}", value=w) for w in range(0, 13)]
    
        try:
            # Get namespace to access series parameter
            namespace = interaction.namespace
            series_name = getattr(namespace, 'series', None)
    
            if series_name:
                # Try to get actual week schedules for the series
                import asyncio
                client = await asyncio.wait_for(iracing._get_client(), timeout=2.8)
                if client:
                    series_seasons = await client.get_series_seasons()
    
                    # Find matching series
                    for season in series_seasons:
                        schedules = season.get('schedules', [])
                        if not schedules:
                            continue
    
                        # Check if this season matches the selected series
                        first_schedule = schedules[0]
                        if series_name.lower() in first_schedule.get('series_name', '').lower():
                            # Build week choices with track names
                            week_choices = []
    
                            for week_schedule in schedules[:13]:  # Max 13 weeks
                                week_num = week_schedule.get('race_week_num')
                                track = week_schedule.get('track', {})
                                track_name = track.get('track_name', '')
                                track_config = track.get('config_name', '')
    
                                # Format: "Week 0: Daytona" or "Week 1: Spa - Grand Prix"
                                if track_config and track_config not in track_name:
                                    name = f"Week {week_num}: {track_name} - {track_config}"
                                else:
                                    name = f"Week {week_num}: {track_name}"
    
                                # Truncate if too long (Discord limit is 100 chars)
                                if len(name) > 100:
                                    name = name[:97] + "..."
    
                                week_choices.append(app_commands.Choice(name=name, value=week_num))
    
                            if week_choices:
                                # Filter by current input
                                if current:
                                    try:
                                        current_int = int(current)
                                        week_choices = [w for w in week_choices if w.value == current_int or str(current_int) in str(w.value)]
                                    except ValueError:
                                        # Search by track name
                                        week_choices = [w for w in week_choices if current.lower() in w.name.lower()]
    
                                return week_choices[:25]
    
                            break
    
        except Exception as e:
            logger.warning("Week autocomplete error: %s", e)
    
        # Fallback to simple week numbers
        weeks = list(range(0, 13))
        if current:
            try:
                current_int = int(current)
                weeks = [w for w in weeks if str(w).startswith(str(current_int))]
            except ValueError:
                pass
    
        return [
            app_commands.Choice(name=f"Week {w}", value=w)
            for w in weeks[:25]
        ]
    
    def season_id_to_year_quarter(season_id: int) -> str:
        """
        Convert iRacing season ID to year and quarter format.
        iRacing runs 4 seasons per year (quarters).
    
        Args:
            season_id: iRacing season ID
    
        Returns:
            String like "2025 S1" or "2024 S4"
        """
        # Reference point: Season 5513 = 2025 Season 1 (updated from actual API data)
        # Each season is +1, 4 seasons per year
        reference_season = 5513
        reference_year = 2025
        reference_quarter = 1
    
        # Calculate offset from reference (negative = past, positive = future)
        offset = season_id - reference_season
    
        # Calculate total quarters from reference point
        total_quarters = reference_quarter + offset
    
        # Calculate year and quarter
        # If offset is negative, we go backwards in time
        years_offset = 0
        quarter = total_quarters
    
        while quarter <= 0:
            years_offset -= 1
            quarter += 4
    
        while quarter > 4:
            years_offset += 1
            quarter -= 4
    
        year = reference_year + years_offset
    
        return f"{year} S{quarter}"
    
    def season_string_to_id(season_str: str) -> int:
        """
        Convert a human-friendly season label (e.g., "2025 S1") into the numeric season_id.
    
        Accepts forms like "2025 S1", "2025 season 1", or the raw numeric id.
        """
        if not season_str:
            raise ValueError("Season string cannot be empty")
    
        normalized = season_str.strip().upper()
    
        if normalized.isdigit():
            return int(normalized)
    
        normalized = normalized.replace("SEASON", "S")
        normalized = re.sub(r"\s+", "", normalized)
    
        match = re.match(r"^(\d{4})S([1-4])$", normalized)
        if not match:
            raise ValueError(f"Invalid season format '{season_str}'. Use values like '2025 S1'.")
    
        year = int(match.group(1))
        quarter = int(match.group(2))
    
        reference_season = 5513  # 2025 Season 1
        reference_year = 2025
        reference_quarter = 1
    
        years_offset = year - reference_year
        quarters_offset = quarter - reference_quarter
        total_offset = years_offset * 4 + quarters_offset
    
        return reference_season + total_offset
    
    async def season_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[int]]:
        """Autocomplete function for season numbers with year/quarter"""
        if not iracing:
            return []
    
        try:
            # Get namespace to access other parameters
            namespace = interaction.namespace
            series_name = getattr(namespace, 'series', None)
    
            season_choices = []
    
            logger.debug("Season autocomplete called with series='%s', current='%s'", series_name, current)
    
            if series_name:
                # Try to get seasons for the specific series
                import asyncio
                try:
                    client = await asyncio.wait_for(iracing._get_client(), timeout=2.8)
                    if client:
                        seasons_data = await asyncio.wait_for(client.get_series_seasons(), timeout=2.8)
    
                    # Find matching series and extract unique season info
                    seen_seasons = set()
                    for season in seasons_data:
                        season_id = season.get('season_id')
                        if season_id in seen_seasons:
                            continue
    
                        schedules = season.get('schedules', [])
                        for schedule in schedules:
                            if series_name.lower() in schedule.get('series_name', '').lower():
                                seen_seasons.add(season_id)
    
                                # Format: "2025 S1 (Active)" or "2024 S4"
                                year_quarter = season_id_to_year_quarter(season_id)
                                is_active = season.get('active', False)
                                name = f"{year_quarter}{' (Active)' if is_active else ''}"
    
                                season_choices.append(app_commands.Choice(name=name, value=season_id))
                                break
    
                        if season_choices:
                            # Sort by season ID descending (most recent first)
                            season_choices.sort(key=lambda x: x.value, reverse=True)
    
                            # Filter by current input
                            if current:
                                season_choices = [
                                    s for s in season_choices
                                    if current.lower() in s.name.lower() or current in str(s.value)
                                ]
    
                            logger.debug("Season autocomplete returning %d choices", len(season_choices))
                            return season_choices[:25]
                except Exception as e:
                    logger.warning("Season autocomplete error: %s", e)
    
            # Fallback: provide recent season IDs with year/quarter
            # Current season around 5516 (2025 S4), go back 20 seasons (5 years)
            base = 5516
            for season_id in range(base, base - 20, -1):
                year_quarter = season_id_to_year_quarter(season_id)
                is_current = (season_id == base)
                name = f"{year_quarter}{' (Current)' if is_current else ''}"
                season_choices.append(app_commands.Choice(name=name, value=season_id))
    
            # Filter by current input if provided
            if current:
                season_choices = [
                    s for s in season_choices
                    if current.lower() in s.name.lower() or current in str(s.value)
                ]
    
            return season_choices[:25]
    
        except Exception as e:
            logger.error("Season autocomplete error: %s", e, exc_info=True)
            # Fallback to basic season list with year/quarter
            base = 5760
            season_choices = []
            for season_id in range(base, base - 12, -1):  # 3 years worth
                year_quarter = season_id_to_year_quarter(season_id)
                season_choices.append(app_commands.Choice(name=year_quarter, value=season_id))
    
            return season_choices[:10]
    
    async def season_label_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """
        Wrapper around season_autocomplete that returns string labels (e.g., '2025 S1').
        Useful for commands that accept the human-readable label instead of the raw ID.
        """
        base_choices = await season_autocomplete(interaction, current)
    
        label_choices: list[app_commands.Choice[str]] = []
        seen_labels: set[str] = set()
    
        for choice in base_choices:
            season_id = choice.value
            try:
                label = season_id_to_year_quarter(season_id)
            except Exception:
                continue
    
            if label in seen_labels:
                continue
    
            label_choices.append(app_commands.Choice(name=choice.name, value=label))
            seen_labels.add(label)
    
        return label_choices[:25]
    
    async def track_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete function for track names"""
        if not iracing:
            return []
    
        try:
            # Get namespace to access series parameter
            namespace = interaction.namespace
            series_name = getattr(namespace, 'series', None)
    
            if series_name:
                # Get tracks used in this series
                import asyncio
                client = await asyncio.wait_for(iracing._get_client(), timeout=2.8)
                if client:
                    series_seasons = await client.get_series_seasons()
    
                    # Find matching series and extract tracks
                    track_set = set()
                    track_choices = []
    
                    for season in series_seasons:
                        schedules = season.get('schedules', [])
                        if not schedules:
                            continue
    
                        # Check if this season matches the selected series
                        first_schedule = schedules[0]
                        if series_name.lower() in first_schedule.get('series_name', '').lower():
                            # Extract all unique tracks from this series
                            for schedule in schedules:
                                track = schedule.get('track', {})
                                track_id = track.get('track_id')
                                track_name = track.get('track_name', '')
                                track_config = track.get('config_name', '')
    
                                if not track_id or track_id in track_set:
                                    continue
    
                                track_set.add(track_id)
    
                                # Format: "Spa-Francorchamps - Grand Prix"
                                if track_config and track_config not in track_name:
                                    display_name = f"{track_name} - {track_config}"
                                else:
                                    display_name = track_name
    
                                # Truncate if needed
                                if len(display_name) > 100:
                                    display_name = display_name[:97] + "..."
    
                                track_choices.append(app_commands.Choice(
                                    name=display_name,
                                    value=display_name[:100]
                                ))
    
                            if track_choices:
                                # Sort alphabetically
                                track_choices.sort(key=lambda x: x.name)
    
                                # Filter by current input
                                if current:
                                    track_choices = [
                                        t for t in track_choices
                                        if current.lower() in t.name.lower()
                                    ]
    
                                return track_choices[:25]
                            break

        except asyncio.TimeoutError:
            logger.warning("Track autocomplete: Timeout fetching track data")
            return [app_commands.Choice(name="Loading track data... please try again", value="")]
        except Exception as e:
            logger.warning("Track autocomplete error: %s", e)
            return [app_commands.Choice(name="Error loading tracks - try again in a moment", value="")]

        # If no series selected or no tracks found, return helpful message
        return [app_commands.Choice(name="Select a series first to see available tracks", value="")]
    
    async def category_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete function for license categories"""
        categories = [
            app_commands.Choice(name="Oval", value="oval"),
            app_commands.Choice(name="Sports Car (Road)", value="sports_car_road"),
            app_commands.Choice(name="Formula Car (Road)", value="formula_car_road"),
            app_commands.Choice(name="Dirt Oval", value="dirt_oval"),
            app_commands.Choice(name="Dirt Road", value="dirt_road")
        ]
    
        if not current:
            return categories
    
        # Filter based on user input
        current_lower = current.lower()
        return [c for c in categories if current_lower in c.name.lower() or current_lower in c.value.lower()][:25]
    
    @bot.tree.command(name="iracing_meta", description="View meta analysis for an iRacing series")
    @app_commands.describe(
        series="Series name to analyze",
        season="Season number (optional, defaults to current)",
        week="Week number (optional, defaults to current)",
        track="Track name (optional, analyzes all tracks if not specified)"
    )
    @app_commands.autocomplete(
        series=series_autocomplete,
        week=week_autocomplete,
        season=season_autocomplete,
        track=track_autocomplete
    )
    async def iracing_meta(interaction: discord.Interaction, series: str, season: int = None, week: int = None, track: str = None):
        """View meta chart showing best cars for a series"""
        if not iracing:
            await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
            return
    
        # Send initial response immediately
        await interaction.response.send_message("🔄 Analyzing race data... This may take up to 60 seconds for detailed performance statistics.")
    
        try:
            # Get meta chart data with performance analysis
            # This call will now wait for the full analysis to complete
            meta_data = await iracing.get_meta_chart_data(series, season_id=season, week_num=week, track_name=track, force_analysis=True)
    
            if not meta_data:
                await interaction.edit_original_response(content=f"❌ Could not find series '{series}' or no data available")
                return
    
            series_name = meta_data.get('series_name', series)
            series_id = meta_data.get('series_id')
            car_data = meta_data.get('cars', [])
            track_name_result = meta_data.get('track_name')
            track_config = meta_data.get('track_config')
            week_num = meta_data.get('week', week or 'Current')
            season_analyzed = meta_data.get('season_analyzed')
            has_performance_data = meta_data.get('has_performance_data', False)
    
            # If no cars found after analysis, show error
            if not car_data:
                await interaction.edit_original_response(content=f"❌ No race data available for {series_name}. No recent races found to analyze.")
                return
    
            # Always create a professional chart if we have car data
            if has_performance_data and any(car.get('avg_lap_time') for car in car_data):
                # Use iRacing visualizer to create meta chart
                from iracing_viz import iRacingVisualizer
                viz = iRacingVisualizer()
    
                # Prepare track name for display
                display_track = track_name_result or "All Tracks"
                if track_name_result and track_config and track_config not in track_name_result:
                    display_track = f"{track_name_result} - {track_config}"
    
                # Get total races analyzed
                total_races = meta_data.get('total_races_analyzed', 0)
    
                # Calculate total unique drivers across all cars
                # Just sum up the unique drivers per car (they're already counted)
                unique_drivers_count = sum(car.get('unique_drivers', 0) for car in car_data)
    
                # Get weather data if available
                weather_data = meta_data.get('weather', {})
    
                # Create the meta chart
                chart_image = await viz.create_meta_chart(
                    series_name=series_name,
                    track_name=display_track,
                    week_num=week_num,
                    car_data=car_data,
                    total_races=total_races,
                    unique_drivers=unique_drivers_count,
                    weather_data=weather_data
                )
    
                # Send as file attachment
                file = discord.File(fp=chart_image, filename=f"meta_{series_name.replace(' ', '_')}_week{week_num}.png")
    
                # Create minimal embed with just the image
                chart_embed = discord.Embed(
                    title=f"{series_name} - Meta Analysis",
                    color=discord.Color.blue()
                )

                chart_embed.set_image(url=f"attachment://meta_{series_name.replace(' ', '_')}_week{week_num}.png")

                # Add series logo as thumbnail if available
                if series_id:
                    series_logo_url = await iracing.get_series_image_url(series_id, 'logo')
                    if series_logo_url:
                        chart_embed.set_thumbnail(url=series_logo_url)

                # Replace the loading message with the chart
                await interaction.edit_original_response(content=None, embed=chart_embed, attachments=[file])
            else:
                # If still no performance data after waiting, show what cars are available
                embed = discord.Embed(
                    title=f"🏎️ {series_name}",
                    description=f"Week {week_num} - No race data available yet for this track/series combination.\n\nShowing available cars:",
                    color=discord.Color.orange()
                )
    
                if track_name_result:
                    track_text = f"{track_name_result}"
                    if track_config and track_config not in track_name_result:
                        track_text += f" - {track_config}"
                    embed.add_field(name="📍 Track", value=track_text, inline=False)
    
                # Show car list
                car_list = []
                for idx, car in enumerate(car_data, 1):
                    car_name = car.get('car_name', 'Unknown')
                    car_list.append(f"{idx}. **{car_name}**")
    
                # Split into chunks
                chunk_size = 15
                for i in range(0, len(car_list), chunk_size):
                    chunk = car_list[i:i+chunk_size]
                    field_name = "🚗 Available Cars" if i == 0 else "🚗 Available Cars (cont.)"
                    embed.add_field(name=field_name, value="\n".join(chunk), inline=False)
    
                embed.set_footer(text="No race results found for this series/track combination in recent seasons")
    
                await interaction.edit_original_response(content=None, embed=embed)
    
        except Exception as e:
            logger.error("iRacing meta error: %s", e, exc_info=True)
            try:
                await interaction.edit_original_response(content="❌ Error getting meta data. Please try again later.")
            except (discord.HTTPException, discord.NotFound):
                await interaction.followup.send("❌ Error getting meta data. Please try again later.")

    @bot.tree.command(name="iracing_results", description="View recent iRacing race results for a driver")
    @app_commands.describe(driver_name="Driver display name, real name, or customer ID (optional if linked)")
    async def iracing_results(interaction: discord.Interaction, driver_name: str = None):
        """View driver's recent race results"""
        if not iracing:
            await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
            return
    
        await interaction.response.defer()
    
        try:
            cust_id = None
            display_name = driver_name
    
            # If no driver name provided, check for linked account
            if not driver_name:
                linked = await iracing.get_linked_iracing_id(interaction.user.id)
                if linked:
                    cust_id, display_name = linked
                else:
                    await interaction.followup.send(
                        "❌ No driver name provided and no linked account found.\n"
                        "Use `/iracing_link` to link your account or provide a driver name."
                    )
                    return
            else:
                # Search for driver
                results = await iracing.search_driver(driver_name)
                if not results or len(results) == 0:
                    await interaction.followup.send(
                        f"❌ No driver found with name '{driver_name}'\n"
                        f"💡 Tip: Try the driver's customer ID for reliable results"
                    )
                    return
                cust_id = results[0].get('cust_id')
                display_name = results[0].get('display_name', driver_name)
    
            # Get recent races
            races = await iracing.get_driver_recent_races(cust_id, limit=10)
    
            if not races or len(races) == 0:
                await interaction.followup.send(f"❌ No recent races found for {display_name}")
                return
    
            # Look up track names for each race
            for race in races:
                # Track might be an object or a direct ID
                track_data = race.get('track')
                if isinstance(track_data, dict):
                    # Track is an object with track_id and track_name
                    track_id = track_data.get('track_id')
                    track_name = track_data.get('track_name', 'Unknown Track')
                    config_name = track_data.get('config_name', '')
    
                    # Append config if it exists and isn't already in the name
                    if config_name and config_name not in track_name:
                        track_name = f"{track_name} - {config_name}"
    
                    race['track_name'] = track_name
                else:
                    # Try to look up by track_id
                    track_id = race.get('track_id')
                    if track_id and (not race.get('track_name') or race.get('track_name') == 'Unknown Track'):
                        track_name = await iracing.get_track_name(track_id)
                        race['track_name'] = track_name
    
            # Generate visual table
            if not iracing_viz:
                # Fallback to simple embed if visualizer failed to load
                embed = discord.Embed(
                    title=f"🏁 Recent Races - {display_name}",
                    description=f"Last {len(races)} races",
                    color=discord.Color.blue()
                )
    
                for i, race in enumerate(races):
                    series_name = race.get('series_name', 'Unknown Series')
                    track_name = race.get('track_name', 'Unknown Track')
                    finish_pos = race.get('finish_position', 'N/A')
                    start_pos = race.get('start_position', 'N/A')
                    incidents = race.get('incidents', 'N/A')
    
                    embed.add_field(
                        name=f"{i+1}. {series_name}",
                        value=f"**Track:** {track_name}\n**Finish:** P{finish_pos} (started P{start_pos})\n**Incidents:** {incidents}",
                        inline=False
                    )
    
                await interaction.followup.send(embed=embed)
                return
    
            # Create visualization
            image_buffer = iracing_viz.create_recent_results_table(display_name, races)
    
            # Send as Discord file attachment
            file = discord.File(fp=image_buffer, filename="results.png")
            await interaction.followup.send(file=file)
    
        except Exception as e:
            logger.error("iRacing results error: %s", e, exc_info=True)
            await interaction.followup.send("❌ Error getting race results. Please try again later.")


    @bot.tree.command(name="iracing_season_schedule", description="View full season schedule for an iRacing series")
    @app_commands.describe(
        series_name="Series name",
        season="Season (e.g., '2025 S1', optional - uses current if not specified)"
    )
    @app_commands.autocomplete(
        series_name=series_autocomplete,
        season=season_label_autocomplete
    )
    async def iracing_season_schedule(interaction: discord.Interaction, series_name: str, season: str = None):
        """View complete season track rotation"""
        if not iracing:
            await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
            return
    
        await interaction.response.defer()
    
        try:
            # Get series info
            all_series = await iracing.get_current_series()
            if not all_series:
                await interaction.followup.send("❌ Failed to retrieve series data")
                return
    
            # Find matching series
            series_match = None
            for s in all_series:
                if series_name.lower() in s.get('series_name', '').lower():
                    series_match = s
                    break
    
            if not series_match:
                await interaction.followup.send(f"❌ Series not found: '{series_name}'")
                return
    
            series_id = series_match.get('series_id')
            series_full_name = series_match.get('series_name')
    
            # If season not specified, use current
            if season:
                try:
                    season_id = season_string_to_id(season)
                except ValueError as err:
                    await interaction.followup.send(f"❌ {err}")
                    return
            else:
                season_id = series_match.get('season_id')
    
            # Get schedule
            schedule = await iracing.get_series_schedule(series_id, season_id)
    
            if not schedule or len(schedule) == 0:
                await interaction.followup.send(f"❌ No schedule found for {series_full_name}")
                return
    
            # Sort schedule by race week to ensure consistent visualization
            schedule_sorted = sorted(schedule, key=lambda entry: entry.get('race_week_num', 0))
    
            # Human-friendly season label
            season_label = season if season else None
            if not season_label:
                try:
                    season_label = season_id_to_year_quarter(season_id)
                except Exception:
                    season_label = "Current Season"
    
            # Gather date range for summary (if available)
            start_dates = []
            for week in schedule_sorted:
                start_date_raw = (
                    week.get('start_date')
                    or week.get('start_time')
                    or week.get('start_date_time')
                )
                if start_date_raw:
                    try:
                        dt = datetime.fromisoformat(str(start_date_raw).replace('Z', '+00:00'))
                        start_dates.append(dt)
                    except Exception:
                        continue
    
            season_span = None
            if start_dates:
                season_span = f"{min(start_dates).strftime('%b %d, %Y')} - {max(start_dates).strftime('%b %d, %Y')}"
    
            if iracing_viz:
                try:
                    image_buffer = iracing_viz.create_schedule_table(series_full_name, schedule_sorted, "full")
    
                    safe_base = "".join(c if c.isalnum() else "_" for c in series_full_name.lower())
                    filename = f"{safe_base or 'schedule'}_{season_id}_schedule.png"
    
                    embed = discord.Embed(
                        title=f"📅 {series_full_name}",
                        description=f"{season_label} • {len(schedule_sorted)} weeks",
                        color=discord.Color.blue()
                    )
                    if season_span:
                        embed.add_field(name="Season Dates", value=season_span, inline=False)
    
                    embed.set_footer(text="Generated by WompBot iRacing Visualizer")
                    embed.set_image(url=f"attachment://{filename}")
    
                    file = discord.File(fp=image_buffer, filename=filename)
                    await interaction.followup.send(embed=embed, file=file)
                    return
                except Exception as viz_error:
                    logger.warning("Failed to render season schedule visualization: %s", viz_error, exc_info=True)
                    # Fallback to text embed below
    
            # Fallback text-based embed when visualizer unavailable
            embed = discord.Embed(
                title=f"📅 {series_full_name}",
                description=f"{season_label} • {len(schedule_sorted)} weeks",
                color=discord.Color.blue()
            )
    
            display_limit = min(len(schedule_sorted), 12)
    
            for i, week in enumerate(schedule_sorted[:display_limit]):
                week_num = week.get('race_week_num', i)
                track_name = week.get('track_name', 'Unknown Track')
                layout = week.get('track_layout', '')
    
                if layout and layout != track_name:
                    track_display = f"{track_name} - {layout}"
                else:
                    track_display = track_name
    
                embed.add_field(
                    name=f"Week {week_num + 1}",
                    value=track_display,
                    inline=True
                )
    
            if len(schedule_sorted) > display_limit:
                embed.set_footer(text=f"Showing first {display_limit} of {len(schedule_sorted)} weeks")
    
            await interaction.followup.send(embed=embed)
    
            if len(schedule_sorted) > display_limit:
                remaining_lines = []
                for i, week in enumerate(schedule_sorted[display_limit:], start=display_limit):
                    week_num = week.get('race_week_num', i)
                    track_name = week.get('track_name', 'Unknown Track')
                    layout = week.get('track_layout', '')
    
                    if layout and layout != track_name:
                        track_display = f"{track_name} - {layout}"
                    else:
                        track_display = track_name
    
                    remaining_lines.append(f"Week {week_num + 1}: {track_display}")
    
                if remaining_lines:
                    chunks = []
                    chunk = []
                    total_chars = 0
    
                    for line in remaining_lines:
                        if total_chars + len(line) + 1 > 1900:
                            chunks.append("\n".join(chunk))
                            chunk = [line]
                            total_chars = len(line)
                        else:
                            chunk.append(line)
                            total_chars += len(line) + 1
    
                    if chunk:
                        chunks.append("\n".join(chunk))
    
                    for text_chunk in chunks:
                        await interaction.followup.send(f"```\n{text_chunk}\n```")
    
        except Exception as e:
            logger.error("iRacing season schedule error: %s", e, exc_info=True)
            await interaction.followup.send("❌ Error getting schedule. Please try again later.")


    @bot.tree.command(name="iracing_server_leaderboard", description="Show iRating leaderboard for this Discord server")
    @app_commands.describe(category="License category (oval/sports_car_road/formula_car_road/dirt_oval/dirt_road)")
    @app_commands.autocomplete(category=category_autocomplete)
    async def iracing_server_leaderboard(interaction: discord.Interaction, category: str = "sports_car_road"):
        """Show server-wide iRating rankings"""
        if not iracing:
            await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
            return
    
        await interaction.response.defer()
    
        try:
            # Rate limiting for expensive server leaderboard
            iracing_leaderboard_cooldown = int(os.getenv('IRACING_LEADERBOARD_COOLDOWN', '60'))  # 60 seconds
            rate_check = db.check_feature_rate_limit(
                interaction.user.id,
                'iracing_leaderboard',
                cooldown_seconds=iracing_leaderboard_cooldown
            )
    
            if not rate_check['allowed']:
                wait_seconds = rate_check.get('wait_seconds', 60)
                await interaction.followup.send(
                    f"⏱️ Leaderboard cooldown! Please wait {wait_seconds} seconds before requesting another leaderboard."
                )
                return
    
            # Get all linked accounts in this guild
            guild_member_ids = [member.id for member in interaction.guild.members]
    
            if len(guild_member_ids) == 0:
                await interaction.followup.send("❌ No members in this server")
                return
    
            # Get linked iRacing accounts
            leaderboard_data = []
    
            for discord_id in guild_member_ids:
                linked = await iracing.get_linked_iracing_id(discord_id)
                if linked:
                    cust_id, display_name = linked
    
                    # Get profile to fetch current iRating
                    profile = await iracing.get_driver_profile(cust_id)
                    if profile:
                        licenses = profile.get('licenses', {})
    
                        # Map category names
                        category_map = {
                            'oval': 'oval',
                            'road': 'sports_car',
                            'dirt_oval': 'dirt_oval',
                            'dirt_road': 'dirt_road',
                            'formula_car': 'formula_car',
                            'formula': 'formula_car'
                        }
    
                        license_key = category_map.get(category.lower(), 'sports_car')
    
                        if license_key in licenses:
                            lic = licenses[license_key]
                            irating = lic.get('irating', 0)
                            sr = lic.get('safety_rating', 0.0)
    
                            # Get Discord member
                            member = interaction.guild.get_member(discord_id)
                            discord_name = member.display_name if member else "Unknown"
    
                            leaderboard_data.append({
                                'discord_name': discord_name,
                                'iracing_name': display_name,
                                'irating': irating,
                                'safety_rating': sr,
                                'cust_id': cust_id
                            })
    
            if len(leaderboard_data) == 0:
                await interaction.followup.send("❌ No linked iRacing accounts found in this server.\nUse `/iracing_link` to link your account!")
                return
    
            # Sort by iRating
            leaderboard_data.sort(key=lambda x: x['irating'], reverse=True)
    
            # Create visualization
            category_display = category.replace('_', ' ').title()
    
            if not iracing_viz:
                # Fallback to embed if visualizer not available
                embed = discord.Embed(
                    title=f"🏆 {interaction.guild.name} - {category_display} Leaderboard",
                    description=f"{len(leaderboard_data)} linked drivers",
                    color=discord.Color.gold()
                )
    
                for i, driver in enumerate(leaderboard_data[:10]):
                    rank_emoji = ["🥇", "🥈", "🥉"][i] if i < 3 else f"**{i+1}.**"
                    embed.add_field(
                        name=f"{rank_emoji} {driver['discord_name']}",
                        value=f"iR: {driver['irating']:,} | SR: {driver['safety_rating']:.2f}\n*{driver['iracing_name']}*",
                        inline=False
                    )
    
                if len(leaderboard_data) > 10:
                    embed.set_footer(text=f"Showing top 10 of {len(leaderboard_data)} drivers")
    
                await interaction.followup.send(embed=embed)
                db.record_feature_usage(interaction.user.id, 'iracing_leaderboard')
            else:
                # Use visualization
                image_buffer = iracing_viz.create_server_leaderboard_table(
                    interaction.guild.name,
                    category_display,
                    leaderboard_data
                )
    
                file = discord.File(fp=image_buffer, filename="server_leaderboard.png")
                await interaction.followup.send(file=file)
                db.record_feature_usage(interaction.user.id, 'iracing_leaderboard')
    
        except Exception as e:
            await interaction.followup.send(f"❌ Error generating leaderboard: {str(e)}")
            logger.error("Server leaderboard error: %s", e, exc_info=True)
    
    
    IRACING_HISTORY_TIMEFRAMES = {
        "day": ("Last 24 Hours", timedelta(days=1)),
        "week": ("Last 7 Days", timedelta(days=7)),
        "month": ("Last 30 Days", timedelta(days=30)),
        "season": ("Last Season", timedelta(weeks=12)),
        "year": ("Last Year", timedelta(days=365)),
        "all": ("Full Career", None),
    }
    
    IRACING_HISTORY_CACHE_TTLS = {
        "day": 0.5,
        "week": 2,
        "month": 6,
        "season": 12,
        "year": 24,
        "all": 24,
    }

    # iRacing chart_data category IDs
    IRACING_CHART_CATEGORIES = {
        "road": (2, "Road"),
        "oval": (1, "Oval"),
        "dirt_oval": (3, "Dirt Oval"),
        "dirt_road": (4, "Dirt Road"),
    }


    @bot.tree.command(
        name="iracing_history",
        description="Analyze rating and safety trends across your racing career",
    )
    @app_commands.describe(
        driver_name="iRacing display name (optional if you've linked your account)",
        timeframe="Time range to analyze (default: Last 30 Days)",
        category="License category (default: Road)",
    )
    @app_commands.choices(
        timeframe=[
            app_commands.Choice(name="Last 24 Hours", value="day"),
            app_commands.Choice(name="Last 7 Days", value="week"),
            app_commands.Choice(name="Last 30 Days", value="month"),
            app_commands.Choice(name="Last Season (~12 weeks)", value="season"),
            app_commands.Choice(name="Last Year", value="year"),
            app_commands.Choice(name="Full Career", value="all"),
        ],
        category=[
            app_commands.Choice(name="Road", value="road"),
            app_commands.Choice(name="Oval", value="oval"),
            app_commands.Choice(name="Dirt Oval", value="dirt_oval"),
            app_commands.Choice(name="Dirt Road", value="dirt_road"),
        ],
    )
    async def iracing_history(
        interaction: discord.Interaction,
        driver_name: str = None,
        timeframe: Optional[app_commands.Choice[str]] = None,
        category: Optional[app_commands.Choice[str]] = None,
    ):
        """Render a performance dashboard with iRating/Safety trends and key stats.

        Uses the native /data/member/chart_data endpoint for full career rating data
        and /data/stats/member_recent_races for summary statistics.
        """
        if not iracing or not iracing_viz:
            await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
            return
    
        await interaction.response.defer()
    
        try:
            cust_id = None
            display_name = driver_name
    
            timeframe_key = timeframe.value if timeframe else "month"
            timeframe_label, delta = IRACING_HISTORY_TIMEFRAMES.get(
                timeframe_key, IRACING_HISTORY_TIMEFRAMES["month"]
            )

            category_key = category.value if category else "road"
            category_id, category_name = IRACING_CHART_CATEGORIES.get(
                category_key, IRACING_CHART_CATEGORIES["road"]
            )

            # Resolve driver identity
            if not driver_name:
                linked = await iracing.get_linked_iracing_id(interaction.user.id)
                if linked:
                    cust_id, display_name = linked
                else:
                    await interaction.followup.send(
                        "❌ No driver name provided and no linked account found.\n"
                        "Use `/iracing_link` to link your account or provide a driver name."
                    )
                    return
            else:
                results = await iracing.search_driver(driver_name)
                if not results:
                    await interaction.followup.send(
                        f"❌ No driver found with name '{driver_name}'\n"
                        f"💡 Tip: Try the driver's customer ID for reliable results"
                    )
                    return
                cust_id = results[0].get('cust_id')
                display_name = results[0].get('display_name', driver_name)
    
            cache_hit = False
            rating_points: List[Dict] = []
            summary_stats: Dict = {}
    
            cache_key_suffix = f"{timeframe_key}_{category_key}"
            cache_payload = db.get_iracing_history_cache(cust_id, cache_key_suffix) if db else None
            if cache_payload:
                try:
                    rating_points = [
                        {
                            "date": datetime.fromisoformat(point["date"]),
                            "irating": point["irating"],
                            "safety_rating": point["safety_rating"],
                        }
                        for point in cache_payload.get("rating_points", [])
                    ]
    
                    summary_stats = cache_payload.get("summary_stats", {})
                    summary_stats["series_counts"] = [
                        (entry["name"], entry["count"])
                        for entry in summary_stats.get("series_counts", [])
                    ]
                    summary_stats["car_counts"] = [
                        (entry["name"], entry["count"])
                        for entry in summary_stats.get("car_counts", [])
                    ]
    
                    if rating_points and summary_stats:
                        timeframe_label = cache_payload.get("timeframe_label", timeframe_label)
                        display_name = cache_payload.get("display_name", display_name)
                        cache_hit = True
                        logger.debug("Using cached history for driver %s (%s)", cust_id, cache_key_suffix)
                except Exception as cache_error:
                    logger.warning("Failed to deserialize history cache: %s", cache_error)
                    cache_hit = False
    
            if not cache_hit:
                # Fetch chart data (iRating + SR) and recent races in parallel
                # chart_data: 2 API calls for full career rating history
                # recent_races: 1 API call for summary stats (wins, incidents, etc.)
                client = await iracing._get_client()

                ir_data, sr_data, races = await asyncio.gather(
                    client.get_member_chart_data(category_id, chart_type=1, cust_id=cust_id),
                    client.get_member_chart_data(category_id, chart_type=3, cust_id=cust_id),
                    iracing.get_driver_recent_races(cust_id, limit=200),
                )

                if not ir_data and not sr_data:
                    await interaction.followup.send(
                        f"❌ No {category_name} rating data found for {display_name}\n"
                        f"💡 They may not have raced in this category."
                    )
                    return

                # Parse chart_data into rating points
                now = datetime.now(timezone.utc)
                cutoff = now - delta if delta else None

                def _parse_chart_entries(data) -> Dict[datetime, float]:
                    """Parse chart_data response into {datetime: value} dict."""
                    lookup = {}
                    entries = data.get('data', []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                    for entry in entries:
                        when = entry.get('when')
                        value = entry.get('value')
                        if when and value is not None:
                            try:
                                dt = datetime.fromisoformat(str(when).replace("Z", "+00:00"))
                                if dt.tzinfo is None:
                                    dt = dt.replace(tzinfo=timezone.utc)
                                lookup[dt] = float(value)
                            except (ValueError, TypeError):
                                continue
                    return lookup

                ir_by_date = _parse_chart_entries(ir_data) if ir_data else {}
                sr_by_date = {}
                if sr_data:
                    raw_sr = _parse_chart_entries(sr_data)
                    # SR values from chart_data are sub_level (e.g. 345 = 3.45)
                    sr_by_date = {dt: val / 100.0 for dt, val in raw_sr.items()}

                # Merge iRating and SR by date, carrying forward last known values
                all_dates = sorted(set(list(ir_by_date.keys()) + list(sr_by_date.keys())))
                if cutoff:
                    all_dates = [d for d in all_dates if d >= cutoff]

                if not all_dates:
                    await interaction.followup.send(
                        f"❌ No {category_name} rating data for {display_name} in {timeframe_label}."
                    )
                    return

                last_ir = None
                last_sr = None
                rating_points = []

                for dt in all_dates:
                    ir_val = ir_by_date.get(dt, last_ir)
                    sr_val = sr_by_date.get(dt, last_sr)
                    if ir_val is not None:
                        last_ir = ir_val
                    if sr_val is not None:
                        last_sr = sr_val
                    if last_ir is not None:
                        rating_points.append({
                            "date": dt,
                            "irating": int(last_ir),
                            "safety_rating": last_sr if last_sr is not None else 0.0,
                        })

                if not rating_points:
                    await interaction.followup.send(
                        f"❌ Not enough rating data for {display_name} in {timeframe_label}."
                    )
                    return

                # Compute summary stats from recent races
                def _parse_race_start(race: Dict) -> Optional[datetime]:
                    for key in ("session_start_time", "start_time", "start_time_utc"):
                        raw = race.get(key)
                        if raw is None:
                            continue
                        if isinstance(raw, (int, float)):
                            return datetime.fromtimestamp(raw, tz=timezone.utc)
                        if isinstance(raw, str):
                            try:
                                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                            except ValueError:
                                try:
                                    dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
                                except ValueError:
                                    continue
                                dt = dt.replace(tzinfo=timezone.utc)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            else:
                                dt = dt.astimezone(timezone.utc)
                            return dt
                    return None

                def _to_int(value):
                    try:
                        return int(value)
                    except (TypeError, ValueError):
                        return None

                # Filter races by timeframe and category
                processed = []
                for race in (races or []):
                    start_dt = _parse_race_start(race)
                    if start_dt is None:
                        continue
                    if cutoff and start_dt < cutoff:
                        continue
                    # Filter by license category if available
                    race_cat = race.get('license_category_id') or race.get('category_id')
                    if race_cat is not None:
                        try:
                            if int(race_cat) != category_id:
                                continue
                        except (ValueError, TypeError):
                            pass
                    processed.append(race)

                total_races = len(processed)
                finish_values = []
                incident_values = []
                ir_changes = []
                sr_changes = []
                series_counter: Counter[str] = Counter()
                car_counter: Counter[str] = Counter()

                for race in processed:
                    finish = _to_int(race.get("finish_position"))
                    if finish is not None:
                        finish_values.append(finish)
                    incidents = _to_int(race.get("incidents"))
                    if incidents is not None:
                        incident_values.append(incidents)

                    old_ir = _to_int(race.get("oldi_rating"))
                    new_ir = _to_int(race.get("newi_rating"))
                    old_sr_raw = _to_int(race.get("old_sub_level"))
                    new_sr_raw = _to_int(race.get("new_sub_level"))

                    if new_ir is not None and old_ir is not None:
                        ir_changes.append(new_ir - old_ir)
                    if new_sr_raw is not None and old_sr_raw is not None:
                        sr_changes.append((new_sr_raw - old_sr_raw) / 100.0)

                    sn = (race.get("series_name") or race.get("series") or "Unknown Series").strip()
                    series_counter[sn] += 1
                    cn = (race.get("car_name") or race.get("display_car_name") or race.get("car") or "Unknown Car")
                    car_counter[str(cn).strip()] += 1

                wins = sum(1 for v in finish_values if v == 1)
                podiums = sum(1 for v in finish_values if v is not None and v <= 3)
                avg_finish = sum(finish_values) / len(finish_values) if finish_values else 0
                avg_incidents = sum(incident_values) / len(incident_values) if incident_values else 0
                total_ir_change = sum(ir_changes)
                total_sr_change = sum(sr_changes)

                # If chart data covers timeframe but no recent races match, derive change from chart
                if not ir_changes and len(rating_points) >= 2:
                    total_ir_change = rating_points[-1]["irating"] - rating_points[0]["irating"]
                if not sr_changes and len(rating_points) >= 2:
                    total_sr_change = rating_points[-1]["safety_rating"] - rating_points[0]["safety_rating"]

                series_counts = series_counter.most_common(5)
                car_counts = car_counter.most_common(5)

                summary_stats = {
                    "timeframe_label": timeframe_label,
                    "total_races": total_races,
                    "wins": wins,
                    "podiums": podiums,
                    "avg_finish": avg_finish,
                    "avg_incidents": avg_incidents,
                    "ir_change": total_ir_change,
                    "sr_change": total_sr_change,
                    "ir_per_race": total_ir_change / total_races if total_races else 0.0,
                    "sr_per_race": total_sr_change / total_races if total_races else 0.0,
                    "series_counts": series_counts,
                    "car_counts": car_counts,
                }

                # Cache the results
                if db:
                    serialized_points = [
                        {
                            "date": point["date"].isoformat(),
                            "irating": point["irating"],
                            "safety_rating": point["safety_rating"],
                        }
                        for point in rating_points
                    ]
                    serialized_summary = dict(summary_stats)
                    serialized_summary["series_counts"] = [
                        {"name": name, "count": count} for name, count in series_counts
                    ]
                    serialized_summary["car_counts"] = [
                        {"name": name, "count": count} for name, count in car_counts
                    ]

                    payload = {
                        "display_name": display_name,
                        "timeframe_label": timeframe_label,
                        "rating_points": serialized_points,
                        "summary_stats": serialized_summary,
                    }

                    ttl_hours = IRACING_HISTORY_CACHE_TTLS.get(timeframe_key, 2)
                    db.store_iracing_history_cache(cust_id, cache_key_suffix, payload, ttl_hours=ttl_hours)

            # Add category to the label for the dashboard
            full_label = f"{timeframe_label} \u2022 {category_name}"

            image_buffer = iracing_viz.create_rating_performance_dashboard(
                display_name,
                full_label,
                rating_points,
                summary_stats,
            )
    
            file = discord.File(fp=image_buffer, filename="rating_history.png")
            await interaction.followup.send(file=file)
    
        except Exception as e:
            await interaction.followup.send("❌ Error generating history dashboard")
            logger.error("iRacing history error for driver %s: %s", driver_name, e, exc_info=True)
    
    
    @bot.tree.command(
        name="iracing_bests",
        description="View personal best lap times across cars and tracks",
    )
    @app_commands.describe(
        driver_name="iRacing display name or customer ID (optional if linked)",
    )
    async def iracing_bests(
        interaction: discord.Interaction,
        driver_name: str = None,
    ):
        """Show a driver's personal best lap times from iRacing."""
        if not iracing:
            await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
            return

        await interaction.response.defer()

        try:
            cust_id = None
            display_name = driver_name

            # Resolve driver identity
            if not driver_name:
                linked = await iracing.get_linked_iracing_id(interaction.user.id)
                if linked:
                    cust_id, display_name = linked
                else:
                    await interaction.followup.send(
                        "❌ No driver name provided and no linked account found.\n"
                        "Use `/iracing_link` to link your account or provide a driver name."
                    )
                    return
            else:
                results = await iracing.search_driver(driver_name)
                if not results:
                    await interaction.followup.send(
                        f"❌ No driver found with name '{driver_name}'\n"
                        f"💡 Tip: Try the driver's customer ID for reliable results"
                    )
                    return
                cust_id = results[0].get('cust_id')
                display_name = results[0].get('display_name', driver_name)

            client = await iracing._get_client()
            bests_data = await client.get_member_bests(cust_id=cust_id)

            if not bests_data:
                await interaction.followup.send(f"❌ No personal best data found for {display_name}")
                return

            # Parse the bests response
            bests_list = bests_data.get('bests', [])
            if isinstance(bests_data, list):
                bests_list = bests_data

            if not bests_list:
                await interaction.followup.send(f"❌ No personal best records for {display_name}")
                return

            # Get car and track name lookups
            all_cars = await iracing.get_all_cars()
            all_tracks = await iracing.get_all_tracks()
            car_lookup = {c.get('car_id'): c.get('car_name', f"Car {c.get('car_id')}") for c in all_cars}
            track_lookup = {}
            for t in all_tracks:
                tid = t.get('track_id')
                if isinstance(tid, str) and tid.isdigit():
                    tid = int(tid)
                tname = t.get('track_name', '')
                config = t.get('config_name', '')
                if config and config not in tname:
                    tname = f"{tname} - {config}"
                track_lookup[tid] = tname

            def format_lap_time(tenths_of_seconds):
                """Format lap time from 10000ths of second to MM:SS.mmm"""
                if not tenths_of_seconds or tenths_of_seconds <= 0:
                    return "N/A"
                seconds = tenths_of_seconds / 10000.0
                minutes = int(seconds // 60)
                secs = seconds % 60
                return f"{minutes}:{secs:06.3f}"

            # Build embed with best laps
            embed = discord.Embed(
                title=f"🏁 Personal Bests — {display_name}",
                color=0x60a5fa,
            )

            # Group by event type if available, show top entries
            entries_shown = 0
            max_entries = 15

            for record in bests_list[:max_entries]:
                car_id = record.get('car_id')
                track_id = record.get('track_id')
                best_lap = record.get('best_lap_time', 0)
                event_type = record.get('event_type_name', 'Race')

                car_name = car_lookup.get(car_id, f"Car {car_id}")
                track_name = track_lookup.get(track_id, f"Track {track_id}")
                lap_str = format_lap_time(best_lap)

                embed.add_field(
                    name=f"{car_name}",
                    value=f"📍 {track_name}\n⏱️ {lap_str} ({event_type})",
                    inline=True,
                )
                entries_shown += 1

            if len(bests_list) > max_entries:
                embed.set_footer(text=f"Showing top {max_entries} of {len(bests_list)} records • WompBot")
            else:
                embed.set_footer(text=f"{entries_shown} personal best records • WompBot")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send("❌ Error fetching personal bests")
            logger.error("iRacing bests error: %s", e, exc_info=True)


    @bot.tree.command(name="iracing_win_rate", description="View win rate analysis for cars in a series")
    @app_commands.describe(
        series_name="Series name (autocomplete available)",
        season="Season (e.g., '2025 S1', optional)",
        week="Week number (optional, defaults to current week)",
        track="Track name filter (optional)"
    )
    async def iracing_win_rate(interaction: discord.Interaction, series_name: str,
                               season: str = None, week: int = None, track: str = None):
        """View win rate and podium rate analysis"""
        if not iracing or not iracing_viz:
            await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
            return
    
        await interaction.response.defer()
    
        try:
            # Get series list
            all_series = await iracing.get_current_series()
            if not all_series:
                await interaction.followup.send("❌ Failed to retrieve series data")
                return
    
            # Find series
            series_match = None
            for s in all_series:
                if series_name.lower() in s.get('series_name', '').lower():
                    series_match = s
                    break
    
            if not series_match:
                await interaction.followup.send(f"❌ Series not found: '{series_name}'")
                return
    
            series_id = series_match.get('series_id')
            series_full_name = series_match.get('series_name')
            season_id = series_match.get('season_id') if not season else season_string_to_id(season)
    
            # Determine week (current week if not specified)
            if week is None:
                week = series_match.get('race_week_num', 0)
    
            # Get meta analysis (with track filter if specified)
            track_id_filter = None
            if track:
                tracks = await iracing.get_all_tracks()
                for t in tracks:
                    if track.lower() in t.get('track_name', '').lower():
                        track_id_filter = t.get('track_id')
                        break
    
            # Get meta stats
            meta_stats = await iracing.get_meta_for_series(
                series_id,
                season_id,
                week,
                track_id=track_id_filter
            )
    
            if not meta_stats or 'cars' not in meta_stats or len(meta_stats['cars']) == 0:
                await interaction.followup.send(f"❌ No meta data available for {series_full_name}")
                return
    
            cars = meta_stats['cars']
    
            # Calculate win rates and podium rates
            car_data = []
            for car in cars:
                total_races = car.get('total_races', 0)
                wins = car.get('wins', 0)
                podiums = car.get('podiums', 0)
    
                if total_races > 0:
                    win_rate = (wins / total_races) * 100
                    podium_rate = (podiums / total_races) * 100
    
                    car_data.append({
                        'car_name': car.get('car_name', 'Unknown'),
                        'wins': wins,
                        'races': total_races,
                        'win_rate': win_rate,
                        'podium_rate': podium_rate
                    })
    
            if len(car_data) == 0:
                await interaction.followup.send("❌ Not enough data to calculate win rates")
                return
    
            # Generate chart
            track_name = meta_stats.get('track_name') if track_id_filter else None
            image_buffer = iracing_viz.create_win_rate_chart(series_full_name, car_data, track_name)
    
            # Send as Discord file attachment
            file = discord.File(fp=image_buffer, filename=f"win_rate_{series_id}.png")
    
            embed = discord.Embed(
                title=f"📊 Win Rate Analysis",
                description=f"{series_full_name}\nWeek {week + 1}",
                color=discord.Color.gold()
            )
            embed.add_field(name="Total Cars Analyzed", value=str(len(car_data)), inline=True)
            embed.add_field(name="Total Races", value=str(sum(c['races'] for c in car_data)), inline=True)
    
            await interaction.followup.send(embed=embed, file=file)
    
        except Exception as e:
            await interaction.followup.send(f"❌ Error generating win rate analysis: {str(e)}")
            logger.error("Win rate error: %s", e, exc_info=True)
    
    
    @bot.tree.command(name="iracing_compare_drivers", description="Compare two drivers side-by-side")
    @app_commands.describe(
        driver1="First driver (name or customer ID)",
        driver2="Second driver (name or customer ID)",
        category="License category to compare (oval/sports_car_road/formula_car_road/dirt_oval/dirt_road)"
    )
    @app_commands.autocomplete(category=category_autocomplete)
    async def iracing_compare_drivers(interaction: discord.Interaction, driver1: str, driver2: str, category: str = "sports_car_road"):
        """Compare two drivers side-by-side"""
        if not iracing or not iracing_viz:
            await interaction.response.send_message("❌ iRacing integration is not configured")
            return
    
        await interaction.response.defer()
    
        try:
            # Helper to resolve driver name or ID to customer ID
            async def resolve_driver(input_str: str) -> tuple:
                """Returns (cust_id, display_name) or (None, None)"""
                # Try as customer ID first
                if input_str.strip().isdigit():
                    cust_id = int(input_str.strip())
                    profile = await iracing.get_driver_profile(cust_id)
                    if profile:
                        return cust_id, profile.get('display_name', f'Driver {cust_id}')
                    return None, None
    
                # Search by name
                results = await iracing.search_driver(input_str)
                if results and len(results) > 0:
                    return results[0].get('cust_id'), results[0].get('display_name', input_str)
                return None, None
    
            # Get both drivers
            cust_id1, name1 = await resolve_driver(driver1)
            if not cust_id1:
                await interaction.followup.send(f"❌ Driver not found: '{driver1}'")
                return
    
            cust_id2, name2 = await resolve_driver(driver2)
            if not cust_id2:
                await interaction.followup.send(f"❌ Driver not found: '{driver2}'")
                return
    
            # Get full profiles
            profile1 = await iracing.get_driver_profile(cust_id1)
            profile2 = await iracing.get_driver_profile(cust_id2)
    
            if not profile1 or not profile2:
                await interaction.followup.send("❌ Failed to retrieve profile data")
                return
    
            # Get career stats
            stats1 = await iracing.get_driver_career_stats(cust_id1)
            stats2 = await iracing.get_driver_career_stats(cust_id2)
    
            logger.debug("Career stats for %s: %d stat entries", name1, len(stats1.get('stats', [])) if stats1 else 0)
            logger.debug("Career stats for %s: %d stat entries", name2, len(stats2.get('stats', [])) if stats2 else 0)
    
            # Build comparison data
            def build_data(profile, stats_data, name):
                stats_summary = {
                    'starts': 0,
                    'wins': 0,
                    'top3': 0,
                    'top5': 0,
                    'poles': 0,
                    'avg_finish': 0,
                    'avg_incidents': 0,
                    'win_rate': 0
                }
    
                if stats_data and 'stats' in stats_data and len(stats_data['stats']) > 0:
                    all_stats = stats_data['stats']
    
                    logger.debug("Stats for %s: %d categories", name, len(all_stats))
    
                    total_starts = sum(s.get('starts', 0) for s in all_stats)
    
                    stats_summary = {
                        'starts': total_starts,
                        'wins': sum(s.get('wins', 0) for s in all_stats),
                        'top3': sum(s.get('top3', 0) for s in all_stats),
                        'top5': sum(s.get('top5', 0) for s in all_stats),
                        'poles': sum(s.get('poles', 0) for s in all_stats),
                        'avg_finish': sum(s.get('avg_finish', 0) for s in all_stats) / len(all_stats) if len(all_stats) > 0 else 0,
                        'avg_incidents': sum(s.get('avg_incidents', 0) for s in all_stats) / len(all_stats) if len(all_stats) > 0 else 0,
                        'win_rate': (sum(s.get('wins', 0) for s in all_stats) / total_starts * 100) if total_starts > 0 else 0
                    }
    
                # Map license keys to match visualization expectations
                # Licenses is a list, need to convert to dict by category
                licenses_mapped = {}
    
                # Category ID to name mapping (based on iRacing API)
                # 1=Oval, 3=Dirt Road, 4=Dirt Oval
                # 5=Sports Car Road, 6=Formula Car Road
                # Note: Category 2 was removed - iRacing uses 5 & 6 for road racing categories
                category_id_to_name = {
                    1: 'oval',
                    3: 'dirt_road',
                    4: 'dirt_oval',
                    5: 'sports_car_road',  # Sports Car Road
                    6: 'formula_car_road'  # Formula Car Road
                }
    
                licenses_list = profile.get('licenses', [])
                if isinstance(licenses_list, list):
                    for lic_data in licenses_list:
                        # Get category identifier
                        cat_id = lic_data.get('category_id', lic_data.get('category'))
                        cat_name = category_id_to_name.get(cat_id, f'unknown_{cat_id}')
    
                        # Store both iRating and TT Rating separately
                        irating = lic_data.get('irating', 0)
                        tt_rating = lic_data.get('tt_rating', 0)
    
                        licenses_mapped[cat_name] = {
                            'irating': irating,
                            'tt_rating': tt_rating,
                            'safety_rating': lic_data.get('safety_rating', 0.0),
                            'license_class': lic_data.get('group_name', 'R')  # Use group_name (e.g., "Rookie", "Class A")
                        }
    
                        logger.debug("License: %s - iR:%s ttR:%s SR:%s class:%s",
                                     cat_name, irating, tt_rating,
                                     lic_data.get('safety_rating'), lic_data.get('group_name', 'N/A'))
    
                return {
                    'name': name,
                    'licenses': licenses_mapped,
                    'stats': stats_summary
                }
    
            driver1_data = build_data(profile1, stats1, name1)
            driver2_data = build_data(profile2, stats2, name2)
    
            # Generate comparison chart
            image_buffer = iracing_viz.create_driver_comparison(driver1_data, driver2_data, category)
            file = discord.File(fp=image_buffer, filename="comparison.png")
    
            await interaction.followup.send(file=file)
    
        except Exception as e:
            logger.error("Compare drivers error: %s", e, exc_info=True)
            await interaction.followup.send("❌ Error comparing drivers. Please try again later.")
    
    
    @bot.tree.command(name="iracing_series_popularity", description="View most popular series by participation")
    @app_commands.describe(
        time_range="Time period for popularity analysis"
    )
    @app_commands.choices(time_range=[
        app_commands.Choice(name="This Season", value="season"),
        app_commands.Choice(name="This Week", value="weekly"),
        app_commands.Choice(name="This Year", value="yearly"),
        app_commands.Choice(name="All Seasons", value="all_time")
    ])
    async def iracing_series_popularity(interaction: discord.Interaction, time_range: str = "season"):
        """Show series popularity rankings based on driver participation"""
        if not iracing:
            await interaction.response.send_message("❌ iRacing integration not configured")
            return
    
        await interaction.response.defer()
    
        try:
            # Get current time info
            now = datetime.now(timezone.utc)
            current_year = now.year
            current_quarter = (now.month - 1) // 3 + 1
    
            # Check if we have enough historical data for this time range
            availability_info = None
            if db:
                availability_info = db.get_data_availability_info(current_year, current_quarter)
    
            # Determine if we can show this time range
            can_show = True
            warning_message = None
    
            if availability_info and time_range != "season":
                quarter_days = availability_info.get('quarter_days', 0)
                total_days = availability_info.get('total_days', 0)
    
                if time_range == "yearly" and total_days < 30:
                    can_show = False
                    warning_message = (
                        f"📊 **Historical Data Not Yet Available**\n\n"
                        f"Yearly statistics require at least 30 days of data collection. "
                        f"Currently collected: **{total_days} days**\n\n"
                        f"The bot is collecting participation data daily. Check back in **{30 - total_days} days** "
                        f"to see yearly trends!\n\n"
                        f"*Showing current season data instead:*"
                    )
                    time_range = "season"  # Fall back to season
                elif time_range == "all_time" and total_days < 90:
                    can_show = False
                    warning_message = (
                        f"📊 **Historical Data Not Yet Available**\n\n"
                        f"All-time statistics require at least 90 days of data collection. "
                        f"Currently collected: **{total_days} days**\n\n"
                        f"The bot is collecting participation data daily. Check back in **{90 - total_days} days** "
                        f"to see all-time trends!\n\n"
                        f"*Showing current season data instead:*"
                    )
                    time_range = "season"
    
            # Check cache first
            if time_range in iracing_popularity_cache:
                cache_entry = iracing_popularity_cache[time_range]
                sorted_series = cache_entry['data']
                cache_age = (datetime.now() - cache_entry['timestamp']).total_seconds() / 3600
                logger.debug("Using cached %s popularity data (age: %.1f hours)", time_range, cache_age)
            else:
                # Compute if not cached
                logger.debug("Computing %s popularity (not in cache)", time_range)
                sorted_series = await compute_series_popularity(time_range)
                if sorted_series:
                    iracing_popularity_cache[time_range] = {
                        'data': sorted_series,
                        'timestamp': datetime.now()
                    }
    
            # Check if we have data
            if not sorted_series:
                await interaction.followup.send("❌ No participation data available")
                return
    
            logger.debug("Top %d series by participation", len(sorted_series))
    
            # Create visualization
            time_range_names = {
                "season": "This Season",
                "weekly": "This Week",
                "yearly": "This Year",
                "all_time": "All Seasons"
            }
    
            image_buffer = iracing_viz.create_popularity_chart(
                sorted_series,
                time_range_names.get(time_range, "This Season")
            )
    
            file = discord.File(fp=image_buffer, filename="series_popularity.png")
    
            # Send with warning message if applicable
            if warning_message:
                await interaction.followup.send(content=warning_message, file=file)
            else:
                await interaction.followup.send(file=file)
    
        except Exception as e:
            logger.error("Popularity error: %s", e, exc_info=True)
            await interaction.followup.send("❌ Error getting popularity data. Please try again later.")


    @bot.tree.command(name="iracing_timeslots", description="View race session times for a specific series")
    @app_commands.describe(
        series="Series name to look up",
        week="Race week number (leave blank for current week)"
    )
    @app_commands.autocomplete(series=series_autocomplete)
    async def iracing_timeslots(interaction: discord.Interaction, series: str, week: int = None):
        """
        Show race session start times for a specific series and week.
    
        For series with infrequent races (like Nurburgring Endurance), this extracts
        scheduled times from race_time_descriptors since the race_guide API only
        returns sessions starting in the next 24-48 hours.
    
        TODO: Optimize by caching season schedule data (TTL: 1 hour) to reduce
        redundant API calls. Currently makes 3-4 API calls per invocation.
        """
        if not iracing:
            await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
            return
    
        await interaction.response.defer()
    
        try:
            # Get all series to find the matching one
            # TODO: Cache this or add get_season_by_id() to avoid fetching all 147 seasons
            all_series = await iracing.get_current_series()
            if not all_series:
                await interaction.followup.send("❌ Failed to retrieve series data")
                return
    
            # Find matching series
            series_match = None
            for s in all_series:
                if series.lower() in s.get('series_name', '').lower():
                    series_match = s
                    break
    
            if not series_match:
                await interaction.followup.send(f"❌ Series not found: '{series}'")
                return
    
            series_id = series_match.get('series_id')
            series_name = series_match.get('series_name')
            season_id = series_match.get('season_id')
    
            logger.debug("Race times request: series_id=%s, season_id=%s, week=%s", series_id, season_id, week)
    
            # Get race times for this series
            sessions = await iracing.get_race_times(series_id, season_id, week)
    
            # Get track name and week info from schedule
            schedule = await iracing.get_series_schedule(series_id, season_id)
    
            # Get current week - use parameter, or first session week, or current week from series
            client = await iracing._get_client()
            all_seasons = await client.get_series_seasons()
            season_data = None
            for s in all_seasons:
                if s.get('season_id') == season_id:
                    season_data = s
                    break
    
            current_week = week
            if not current_week and sessions:
                current_week = sessions[0].get('race_week_num')
            elif not current_week and season_data:
                current_week = season_data.get('race_week', 0)
    
            track_name = "Unknown Track"
            if schedule and current_week is not None:
                for week_entry in schedule:
                    if week_entry.get('race_week_num') == current_week:
                        track_name = week_entry.get('track_name', 'Unknown Track')
                        break
    
            # If no upcoming sessions found, try to get exact times from schedule data
            if not sessions:
                # Look for session times in the schedule data
                week_schedule = None
                if schedule and current_week is not None:
                    for week_entry in schedule:
                        if week_entry.get('race_week_num') == current_week:
                            week_schedule = week_entry
                            break
    
                # Extract session times from race_time_descriptors
                # Note: There may be multiple descriptors for different session types
                if week_schedule:
                    race_time_descriptors = week_schedule.get('race_time_descriptors', [])
    
                    if race_time_descriptors:
                        # Iterate through ALL descriptors (not just first one)
                        # Some series may have multiple session types or time slots
                        sessions = []
                        for descriptor in race_time_descriptors:
                            session_times_list = descriptor.get('session_times', [])
    
                            for time_str in session_times_list:
                                sessions.append({
                                    'start_time': time_str,
                                    'series_id': series_id,
                                    'race_week_num': current_week
                                })
    
                        if sessions:
                            logger.debug("Using scheduled session times from race_time_descriptors: %d sessions", len(sessions))
    
                # Final fallback: show recurring pattern if we couldn't find exact times
                if not sessions:
                    schedule_desc = season_data.get('schedule_description', '') if season_data else ''
    
                    if schedule_desc:
                        embed = discord.Embed(
                            title=f"🏁 {series_name}",
                            description=f"**Week {current_week}** • {track_name}",
                            color=discord.Color.orange()
                        )
    
                        embed.add_field(
                            name="📅 Recurring Schedule",
                            value=schedule_desc,
                            inline=False
                        )
    
                        embed.add_field(
                            name="ℹ️ Note",
                            value="No live sessions in the next 24-48 hours. This series follows a recurring schedule as shown above.",
                            inline=False
                        )
    
                        embed.set_footer(text="Times are in GMT • Check iRacing for exact session times")
    
                        await interaction.followup.send(embed=embed)
                        return
                    else:
                        # Provide more informative error message
                        error_msg = (
                            f"❌ **No session times available for {series_name}**\n\n"
                            f"This can happen if:\n"
                            f"• No sessions are scheduled in the next 24-48 hours\n"
                            f"• Schedule data is unavailable for week {current_week}\n"
                            f"• The series is not currently active\n\n"
                            f"Try checking iRacing.com directly or contact support if you believe this is an error."
                        )
                        await interaction.followup.send(error_msg)
                        return
    
            # Prepare session data for visualization
            session_data = []
            for session in sessions[:50]:  # Limit to 50 sessions
                # Get session start time
                start_time_str = session.get('start_time') or session.get('session_start_time')
                if not start_time_str:
                    continue
    
                try:
                    # Parse the time
                    if isinstance(start_time_str, str):
                        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                    else:
                        start_time = datetime.fromtimestamp(start_time_str, tz=timezone.utc)
    
                    timestamp = int(start_time.timestamp())
    
                    session_data.append({
                        'start_time': start_time_str,
                        'timestamp': timestamp
                    })
    
                except Exception as e:
                    logger.debug("Error parsing session time: %s", e)
                    continue
    
            # Create visualization
            image_buffer = iracing_viz.create_timeslots_table(
                series_name=series_name,
                track_name=track_name,
                week_num=current_week,
                sessions=session_data
            )
    
            # Send as file attachment
            file = discord.File(fp=image_buffer, filename="iracing_timeslots.png")
            await interaction.followup.send(file=file)
    
        except Exception as e:
            logger.error("Race times error: %s", e, exc_info=True)
            await interaction.followup.send("❌ Error getting race times. Please try again later.")

    @bot.tree.command(name="trivia_start", description="Start a trivia session")
    @app_commands.describe(
        topic="Topic for trivia questions (e.g., 'science', 'history', 'gaming')",
        difficulty="Difficulty level",
        questions="Number of questions (1-20)",
        time_per_question="Seconds per question (10-60)"
    )
    @app_commands.choices(difficulty=[
        app_commands.Choice(name="Easy", value="easy"),
        app_commands.Choice(name="Medium", value="medium"),
        app_commands.Choice(name="Hard", value="hard")
    ])
    async def trivia_start(
        interaction: discord.Interaction,
        topic: str,
        difficulty: app_commands.Choice[str] = None,
        questions: int = 10,
        time_per_question: int = 30
    ):
        """Start a new trivia session"""
        await interaction.response.defer()

        try:
            # Validate parameters
            if questions < 1 or questions > 20:
                await interaction.followup.send("❌ Questions must be between 1 and 20")
                return

            if time_per_question < 10 or time_per_question > 60:
                await interaction.followup.send("❌ Time per question must be between 10 and 60 seconds")
                return

            diff_value = difficulty.value if difficulty else 'medium'

            # Check if session already active
            if trivia.is_session_active(interaction.channel_id):
                await interaction.followup.send("❌ A trivia session is already active in this channel")
                return

            # Start session (generates questions)
            await interaction.followup.send(f"🎲 Generating {questions} {diff_value} trivia questions about **{topic}**...")

            session_id = await trivia.start_session(
                interaction.guild_id,
                interaction.channel_id,
                interaction.user.id,
                str(interaction.user),
                topic,
                diff_value,
                questions,
                time_per_question
            )

            # Send start message
            embed = discord.Embed(
                title=f"🎲 Trivia: {topic.title()}",
                description=f"**{questions} questions** | **{diff_value.title()}** difficulty | **{time_per_question}s** per question",
                color=discord.Color.blue()
            )
            embed.add_field(name="How to Play", value="Type your answer in the chat when a question appears. First correct answer gets full points!", inline=False)
            embed.set_footer(text=f"Started by {interaction.user.display_name}")

            await interaction.channel.send(embed=embed)

            # Ask first question
            await asyncio.sleep(3)
            question = await trivia.ask_next_question(
                interaction.channel_id,
                lambda: trivia.handle_timeout(interaction.channel)
            )

            if question:
                embed = discord.Embed(
                    title=f"Question 1/{questions}",
                    description=question['question'],
                    color=discord.Color.green()
                )
                embed.set_footer(text=f"You have {time_per_question} seconds to answer")
                await interaction.channel.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"❌ Error starting trivia: {str(e)}")
            print(f"❌ Trivia start error: {e}")
            import traceback
            traceback.print_exc()

    print("✅ Trivia commands registered")

    # ===== Server Dashboard =====
    if dashboard:
        @bot.tree.command(name="dashboard", description="View server health dashboard with charts")
        @app_commands.describe(days="Time period in days (default: 7, max: 90)")
        async def dashboard_slash(interaction: discord.Interaction, days: int = 7):
            """Generate server-wide analytics dashboard"""
            await interaction.response.defer()

            try:
                days = min(max(days, 1), 90)
                data = await dashboard.generate_dashboard(interaction.guild_id, days)

                if not data:
                    await interaction.followup.send(
                        "📊 Not enough data to generate a dashboard. "
                        "The bot needs some message history first!"
                    )
                    return

                from plotly_charts import PlotlyCharts
                charts = PlotlyCharts()
                files = []

                # Chart 1: Activity trend (line chart)
                trend = data.get('activity_trend', {})
                if trend.get('values') and sum(trend['values']) > 0:
                    line_buf = charts.create_line_chart(
                        data={'Messages': trend['values']},
                        title=f"Message Activity (Last {days} Days)",
                        xlabel="Date",
                        ylabel="Messages",
                        x_labels=trend.get('labels')
                    )
                    files.append(discord.File(fp=line_buf, filename="activity_trend.png"))

                # Chart 2: Top users (horizontal bar)
                top_users = data.get('top_users', {})
                if top_users:
                    # Take top 10 and reverse for horizontal bar readability
                    bar_buf = charts.create_bar_chart(
                        data=dict(list(top_users.items())[:10]),
                        title=f"Top Messagers (Last {days} Days)",
                        xlabel="Messages",
                        horizontal=True
                    )
                    files.append(discord.File(fp=bar_buf, filename="top_users.png"))

                # Chart 3: Top topics (pie chart)
                topics = data.get('topics', {})
                if topics and len(topics) >= 2:
                    pie_buf = charts.create_pie_chart(
                        data=dict(list(topics.items())[:8]),
                        title=f"Discussion Topics (Last {days} Days)"
                    )
                    files.append(discord.File(fp=pie_buf, filename="topics.png"))

                # Summary embed
                engagement = data.get('engagement', {})
                primetime = data.get('primetime', {})
                cd_stats = data.get('claim_debate_stats', {})

                embed = discord.Embed(
                    title=f"📊 Server Dashboard — Last {days} Days",
                    color=discord.Color.teal()
                )

                # Activity summary
                total_msgs = data.get('total_messages', 0)
                unique_users = engagement.get('unique_users', 0)
                avg_len = engagement.get('avg_message_length', 0)
                embed.add_field(
                    name="📈 Activity",
                    value=(
                        f"**{total_msgs:,}** messages\n"
                        f"**{unique_users}** active users\n"
                        f"Avg length: **{avg_len:.0f}** chars"
                    ),
                    inline=True
                )

                # Peak times
                peak_hour = primetime.get('peak_hour', '?')
                peak_day_num = primetime.get('peak_day')
                day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
                peak_day = day_names[peak_day_num] if peak_day_num is not None and 0 <= peak_day_num <= 6 else '?'
                embed.add_field(
                    name="⏰ Peak Times",
                    value=(
                        f"Hour: **{peak_hour}:00**\n"
                        f"Day: **{peak_day}**"
                    ),
                    inline=True
                )

                # Community activity
                claims = cd_stats.get('claims', 0)
                debates = cd_stats.get('debates', 0)
                fact_checks = cd_stats.get('fact_checks', 0)
                if claims > 0 or debates > 0 or fact_checks > 0:
                    embed.add_field(
                        name="🎯 Community",
                        value=(
                            f"Claims: **{claims}**\n"
                            f"Debates: **{debates}**\n"
                            f"Fact checks: **{fact_checks}**"
                        ),
                        inline=True
                    )

                if files:
                    await interaction.followup.send(embed=embed, files=files)
                else:
                    await interaction.followup.send(embed=embed)

            except Exception as e:
                logger.error("Dashboard generation failed: %s", e, exc_info=True)
                await interaction.followup.send("❌ Error generating dashboard. Please try again.")

        print("✅ Dashboard commands registered")

    # ===== Conversation Flow =====
    @bot.tree.command(name="flow", description="Analyze topic transitions and who changes subjects")
    @app_commands.describe(days="Time period in days (default: 14, max: 60)")
    async def flow_slash(interaction: discord.Interaction, days: int = 14):
        """Show conversation flow analysis with Sankey diagram"""
        await interaction.response.defer()

        try:
            days = min(max(days, 1), 60)
            start_date = datetime.now() - timedelta(days=days)
            end_date = datetime.now()

            # Fetch messages
            messages = chat_stats.get_messages_for_analysis(
                None, start_date, end_date, exclude_opted_out=True
            )

            if not messages or len(messages) < 20:
                await interaction.followup.send(
                    "📊 Not enough messages to analyze conversation flow. "
                    "Try a longer time period."
                )
                return

            # Filter to this guild if possible
            guild_messages = [m for m in messages if m.get('guild_id') == interaction.guild_id] or messages

            # Analyze flow
            flow = chat_stats.analyze_conversation_flow(guild_messages, top_n=8, gap_minutes=10)

            if not flow['transitions']:
                await interaction.followup.send(
                    "📊 Not enough distinct topic transitions found. "
                    "Try a longer time period with more varied conversations."
                )
                return

            files = []

            # Sankey diagram of topic transitions
            from plotly_charts import PlotlyCharts
            charts = PlotlyCharts()

            labels = list(flow['top_topics'])
            if len(labels) >= 2 and flow['transitions']:
                # Build Sankey data
                label_to_idx = {l: i for i, l in enumerate(labels)}
                source = []
                target = []
                values = []
                for fr, to, cnt in flow['transitions']:
                    if fr in label_to_idx and to in label_to_idx:
                        source.append(label_to_idx[fr])
                        target.append(label_to_idx[to])
                        values.append(cnt)

                if source:
                    sankey_buf = charts.create_sankey(
                        labels=[l.title() for l in labels],
                        source=source,
                        target=target,
                        value=values,
                        title=f"Topic Flow (Last {days} Days)"
                    )
                    files.append(discord.File(fp=sankey_buf, filename="topic_flow.png"))

            # Topic changers bar chart
            if flow['topic_changers']:
                changers_data = {name: count for name, count in flow['topic_changers'][:10]}
                if changers_data:
                    bar_buf = charts.create_bar_chart(
                        data=changers_data,
                        title=f"Top Topic Changers (Last {days} Days)",
                        ylabel="Topic Changes",
                        horizontal=True
                    )
                    files.append(discord.File(fp=bar_buf, filename="topic_changers.png"))

            # Summary embed
            embed = discord.Embed(
                title=f"🔄 Conversation Flow — Last {days} Days",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="📊 Segments",
                value=f"**{flow['segment_count']}** conversation segments detected",
                inline=True
            )
            embed.add_field(
                name="🔀 Transitions",
                value=f"**{len(flow['transitions'])}** unique topic transitions",
                inline=True
            )

            # Top transitions as text
            if flow['transitions'][:5]:
                trans_text = "\n".join(
                    f"**{fr.title()}** → **{to.title()}** ({cnt}x)"
                    for fr, to, cnt in flow['transitions'][:5]
                )
                embed.add_field(
                    name="🔝 Top Transitions",
                    value=trans_text,
                    inline=False
                )

            if files:
                await interaction.followup.send(embed=embed, files=files)
            else:
                await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"❌ Error analyzing flow: {str(e)}")
            print(f"❌ Flow analysis error: {e}")
            import traceback
            traceback.print_exc()

    print("✅ Conversation flow commands registered")

    # ===== Polls =====
    if poll_system:
        @bot.tree.command(name="poll", description="Create a poll")
        @app_commands.describe(
            question="The poll question",
            options="Comma-separated options (e.g. 'Yes, No, Maybe')",
            duration="Duration in minutes before auto-close (optional)",
            anonymous="Hide voter names (default: False)",
            multi="Allow multiple votes per person (default: False)"
        )
        async def poll_create(interaction: discord.Interaction, question: str,
                              options: str, duration: int = None,
                              anonymous: bool = False, multi: bool = False):
            """Create a new poll with buttons"""
            await interaction.response.defer()

            try:
                option_list = [o.strip() for o in options.split(',') if o.strip()]
                poll_type = 'multi' if multi else 'single'

                result = await poll_system.create_poll(
                    guild_id=interaction.guild_id,
                    channel_id=interaction.channel_id,
                    created_by=interaction.user.id,
                    question=question,
                    options=option_list,
                    poll_type=poll_type,
                    anonymous=anonymous,
                    duration_minutes=duration
                )

                if result.get('error'):
                    await interaction.followup.send(f"❌ {result['error']}")
                    return

                poll_id = result['poll_id']

                # Create embed
                embed = discord.Embed(
                    title=f"📊 {question}",
                    color=discord.Color.gold()
                )

                option_text = "\n".join(f"**{i+1}.** {opt}" for i, opt in enumerate(option_list))
                embed.description = option_text

                vote_type = "Multiple choice" if multi else "Single choice"
                anon_text = " • Anonymous" if anonymous else ""
                dur_text = f" • Closes in {duration}min" if duration else ""
                embed.set_footer(text=f"Poll #{poll_id} • {vote_type}{anon_text}{dur_text}")

                # Create button view
                from features.polls import PollView
                timeout_seconds = duration * 60 if duration else 86400
                view = PollView(poll_system, poll_id, option_list, poll_type, timeout_seconds)

                msg = await interaction.followup.send(embed=embed, view=view)
                await poll_system.set_message_id(poll_id, msg.id)

            except Exception as e:
                await interaction.followup.send(f"❌ Error creating poll: {str(e)}")
                print(f"❌ Poll create error: {e}")
                import traceback
                traceback.print_exc()


        print("\u2705 Poll commands registered")

    # ===== Personal Analytics =====
    @bot.tree.command(name="mystats", description="View your personal analytics profile card")
    @app_commands.describe(
        user="User to view stats for (defaults to yourself)",
        days="Time period in days (default: all time, max: 365)"
    )
    async def mystats_slash(interaction: discord.Interaction,
                            user: discord.Member = None,
                            days: int = None):
        """View comprehensive personal analytics"""
        await interaction.response.defer()

        try:
            from psycopg2.extras import RealDictCursor
            target_user = user if user else interaction.user
            user_id = target_user.id
            guild_id = interaction.guild_id

            # Build time filter
            if days:
                days = min(max(days, 1), 365)
                start_date = datetime.now() - timedelta(days=days)
                end_date = datetime.now()
                time_filter = "AND m.timestamp BETWEEN %s AND %s"
                time_params = [start_date, end_date]
                time_label = f"Last {days} days"
            else:
                time_filter = ""
                time_params = []
                time_label = "All time"

            stats = {}

            with db.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # ── Activity stats ──
                    cur.execute(f"""
                        SELECT
                            COUNT(*) as total_messages,
                            COUNT(DISTINCT DATE(m.timestamp)) as active_days,
                            MIN(m.timestamp) as first_seen,
                            EXTRACT(HOUR FROM m.timestamp) as hour
                        FROM messages m
                        WHERE m.user_id = %s AND COALESCE(m.opted_out, FALSE) = FALSE
                            {time_filter}
                        GROUP BY EXTRACT(HOUR FROM m.timestamp)
                        ORDER BY COUNT(*) DESC
                        LIMIT 1
                    """, [user_id] + time_params)
                    activity_row = cur.fetchone()

                    if not activity_row or activity_row['total_messages'] == 0:
                        # Get total across all hours to check if any data exists
                        cur.execute(f"""
                            SELECT COUNT(*) as total
                            FROM messages m
                            WHERE m.user_id = %s AND COALESCE(m.opted_out, FALSE) = FALSE
                                {time_filter}
                        """, [user_id] + time_params)
                        total_check = cur.fetchone()
                        if not total_check or total_check['total'] == 0:
                            await interaction.followup.send(
                                f"📊 {target_user.display_name} doesn't have any tracked messages yet!"
                            )
                            return

                    # Full activity aggregation
                    cur.execute(f"""
                        SELECT
                            COUNT(*) as total_messages,
                            COUNT(DISTINCT DATE(m.timestamp)) as active_days,
                            MIN(m.timestamp) as first_seen
                        FROM messages m
                        WHERE m.user_id = %s AND COALESCE(m.opted_out, FALSE) = FALSE
                            {time_filter}
                    """, [user_id] + time_params)
                    total_row = cur.fetchone()
                    stats['total_messages'] = total_row['total_messages']
                    stats['active_days'] = total_row['active_days']

                    if total_row.get('first_seen'):
                        stats['member_since'] = total_row['first_seen'].strftime('%b %Y')

                    # Most active hour
                    stats['most_active_hour'] = int(activity_row['hour']) if activity_row else 12

                    # Server rank
                    cur.execute(f"""
                        SELECT rank FROM (
                            SELECT user_id,
                                   DENSE_RANK() OVER (ORDER BY COUNT(*) DESC) as rank
                            FROM messages m
                            WHERE COALESCE(m.opted_out, FALSE) = FALSE
                                {time_filter}
                            GROUP BY user_id
                        ) ranked
                        WHERE user_id = %s
                    """, time_params + [user_id])
                    rank_row = cur.fetchone()
                    stats['server_rank'] = rank_row['rank'] if rank_row else '?'

                    # ── Social stats ──
                    cur.execute(f"""
                        SELECT replied_to_user_id, COUNT(*) as cnt
                        FROM message_interactions mi
                        WHERE mi.user_id = %s
                            AND mi.replied_to_user_id IS NOT NULL
                            AND mi.replied_to_user_id != %s
                            {time_filter.replace('m.timestamp', 'mi.timestamp')}
                        GROUP BY replied_to_user_id
                        ORDER BY cnt DESC
                        LIMIT 1
                    """, [user_id, user_id] + time_params)
                    partner_row = cur.fetchone()
                    if partner_row:
                        # Look up username
                        cur.execute("SELECT username FROM user_profiles WHERE user_id = %s",
                                   (partner_row['replied_to_user_id'],))
                        partner_name = cur.fetchone()
                        stats['top_partner'] = partner_name['username'] if partner_name else 'Unknown'
                        stats['top_partner_count'] = partner_row['cnt']
                    else:
                        stats['top_partner'] = 'N/A'
                        stats['top_partner_count'] = 0

                    # Reply counts
                    cur.execute(f"""
                        SELECT
                            COUNT(*) FILTER (WHERE mi.user_id = %s AND mi.replied_to_user_id IS NOT NULL) as sent,
                            COUNT(*) FILTER (WHERE mi.replied_to_user_id = %s) as received
                        FROM message_interactions mi
                        WHERE (mi.user_id = %s OR mi.replied_to_user_id = %s)
                            {time_filter.replace('m.timestamp', 'mi.timestamp')}
                    """, [user_id, user_id, user_id, user_id] + time_params)
                    reply_row = cur.fetchone()
                    stats['replies_sent'] = reply_row['sent'] if reply_row else 0
                    stats['replies_received'] = reply_row['received'] if reply_row else 0

                    # ── Claims stats ──
                    cur.execute(f"""
                        SELECT
                            COUNT(*) as total_claims,
                            COUNT(*) FILTER (WHERE verification_status IN ('true', 'false')) as verified,
                            COUNT(*) FILTER (WHERE verification_status = 'true') as correct
                        FROM claims c
                        WHERE c.user_id = %s
                            {time_filter.replace('m.timestamp', 'c.timestamp')}
                    """, [user_id] + time_params)
                    claims_row = cur.fetchone()
                    stats['total_claims'] = claims_row['total_claims'] if claims_row else 0
                    if claims_row and claims_row['verified'] and claims_row['verified'] > 0:
                        stats['claims_accuracy'] = round(
                            claims_row['correct'] / claims_row['verified'] * 100
                        )
                    else:
                        stats['claims_accuracy'] = None

                    # Hot takes count
                    cur.execute(f"""
                        SELECT COUNT(*) as cnt
                        FROM hot_takes ht
                        JOIN claims c ON ht.claim_id = c.id
                        WHERE c.user_id = %s
                            {time_filter.replace('m.timestamp', 'c.timestamp')}
                    """, [user_id] + time_params)
                    ht_row = cur.fetchone()
                    stats['hot_takes_count'] = ht_row['cnt'] if ht_row else 0

                    # ── Debate stats ──
                    cur.execute("""
                        SELECT
                            COUNT(*) as total,
                            COUNT(*) FILTER (WHERE dp.is_winner = TRUE) as wins,
                            AVG(dp.score) as avg_score
                        FROM debate_participants dp
                        JOIN debates d ON dp.debate_id = d.id
                        WHERE dp.user_id = %s AND d.guild_id = %s
                    """, (user_id, guild_id))
                    debate_row = cur.fetchone()
                    if debate_row and debate_row['total'] > 0:
                        wins = debate_row['wins'] or 0
                        losses = debate_row['total'] - wins
                        stats['debate_record'] = f"{wins}W-{losses}L"
                        stats['debate_avg_score'] = round(debate_row['avg_score'], 1) if debate_row['avg_score'] else None
                        stats['debate_win_rate'] = round(wins / debate_row['total'] * 100) if debate_row['total'] > 0 else 0
                    else:
                        stats['debate_record'] = '0W-0L'
                        stats['debate_avg_score'] = None
                        stats['debate_win_rate'] = None

                    # ── Trivia stats ──
                    cur.execute("""
                        SELECT wins, total_points, total_correct, total_questions_answered
                        FROM trivia_stats
                        WHERE guild_id = %s AND user_id = %s
                    """, (guild_id, user_id))
                    trivia_row = cur.fetchone()
                    if trivia_row:
                        stats['trivia_wins'] = trivia_row['wins'] or 0
                        stats['trivia_points'] = trivia_row['total_points'] or 0
                        answered = trivia_row['total_questions_answered'] or 0
                        correct = trivia_row['total_correct'] or 0
                        stats['trivia_correct_pct'] = round(correct / answered * 100) if answered > 0 else None
                    else:
                        stats['trivia_wins'] = 0
                        stats['trivia_points'] = 0
                        stats['trivia_correct_pct'] = None

            # ── Topic expertise (from separate table) ──
            topics = db.get_user_expertise(user_id, guild_id, limit=5)
            stats['top_topics'] = [(t['topic'], t['quality_score']) for t in topics] if topics else []

            # ── Achievements ──
            achievements = []
            hour = stats.get('most_active_hour', 12)
            if 0 <= hour <= 5:
                achievements.append('Night Owl')
            elif 6 <= hour <= 9:
                achievements.append('Early Bird')
            if stats['total_messages'] >= 1000:
                achievements.append('Conversationalist')
            if stats.get('hot_takes_count', 0) >= 5:
                achievements.append('Debate Champion')
            if stats.get('trivia_wins', 0) >= 3:
                achievements.append('Trivia Wizard')
            if len(stats.get('top_topics', [])) >= 3:
                achievements.append('Topic Expert')
            stats['achievements'] = achievements

            # Generate the card
            from mystats_card import create_mystats_card
            image_buffer = create_mystats_card(
                f"{target_user.display_name}'s Stats ({time_label})",
                stats
            )

            file = discord.File(fp=image_buffer, filename="mystats.png")
            await interaction.followup.send(file=file)

        except Exception as e:
            await interaction.followup.send(f"❌ Error generating stats: {str(e)}")
            print(f"❌ MyStats error: {e}")
            import traceback
            traceback.print_exc()

    print("✅ Personal analytics commands registered")

    print("✅ Slash commands registered")
