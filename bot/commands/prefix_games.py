"""
Prefix game commands for WompBot Discord bot.

This module contains prefix (!) commands for debate extras, trivia extras,
and game commands (polls, Who Said It?, Devil's Advocate, Jeopardy).
"""

import asyncio
import discord
from discord.ext import commands


def register_prefix_game_commands(bot, db, llm=None, debate_scorekeeper=None,
                                  trivia=None, poll_system=None, who_said_it=None,
                                  devils_advocate=None, jeopardy=None,
                                  iracing_viz=None, chat_stats=None, stats_viz=None):
    """
    Register prefix game commands with the bot.

    Args:
        bot: Discord bot instance
        db: Database instance
        llm: LLM client instance
        debate_scorekeeper: DebateScorekeeper instance
        trivia: Trivia instance
        poll_system: PollSystem instance
        who_said_it: WhoSaidItGame instance
        devils_advocate: DevilsAdvocate instance
        jeopardy: JeopardyGame instance
        iracing_viz: iRacing visualizer instance
        chat_stats: ChatStats instance
        stats_viz: Stats visualizer instance
    """

    # ==================== GROUP 4: DEBATE EXTRAS ====================
    if debate_scorekeeper:

        @bot.command(name='debate_end', aliases=['de'])
        async def debate_end_cmd(ctx):
            """End debate and show LLM analysis"""
            async with ctx.typing():
                try:
                    result = await debate_scorekeeper.end_debate(ctx.channel.id)

                    if not result:
                        await ctx.send("No active debate in this channel!")
                        return

                    if 'error' in result:
                        await ctx.send(f"{result['message']}")
                        return

                    # Create results embed
                    embed = discord.Embed(
                        title=f"Debate Results: {result['topic']}",
                        description=result['analysis'].get('summary', 'Debate concluded'),
                        color=discord.Color.red()
                    )

                    duration_mins = int(result['duration_minutes'])
                    embed.add_field(
                        name="Stats",
                        value=f"Duration: {duration_mins} min\nParticipants: {result['participant_count']}\nMessages: {result['message_count']}",
                        inline=True
                    )

                    # Winner
                    if 'winner' in result['analysis']:
                        winner = result['analysis']['winner']
                        reason = result['analysis'].get('winner_reason', 'Superior arguments')
                        embed.add_field(
                            name="Winner",
                            value=f"**{winner}**\n{reason[:100]}",
                            inline=True
                        )

                    # Participant scores
                    if 'participants' in result['analysis']:
                        for username, data in result['analysis']['participants'].items():
                            score = data.get('score', '?')
                            strengths = data.get('strengths', 'N/A')[:150]
                            fallacies = data.get('fallacies', [])

                            field_value = f"**Score:** {score}/10\n**Strengths:** {strengths}"
                            if fallacies:
                                field_value += f"\n**Fallacies:** {', '.join(fallacies[:2])}"

                            embed.add_field(
                                name=f"{username}",
                                value=field_value,
                                inline=False
                            )

                    embed.set_footer(text=f"Debate #{result['debate_id']}")
                    await ctx.send(embed=embed)

                except Exception as e:
                    await ctx.send(f"Error ending debate: {str(e)}")
                    print(f"Debate end error: {e}")
                    import traceback
                    traceback.print_exc()

        @bot.command(name='debate_stats', aliases=['ds'])
        async def debate_stats_cmd(ctx, user: discord.Member = None):
            """View debate statistics for a user"""
            async with ctx.typing():
                try:
                    target_user = user if user else ctx.author
                    stats = await debate_scorekeeper.get_debate_stats(target_user.id)

                    if not stats:
                        await ctx.send(
                            f"{target_user.display_name} hasn't participated in any debates yet!"
                        )
                        return

                    if stats_viz:
                        # Format metrics for visualization
                        metrics = [
                            ("Record", f"{stats['wins']}W - {stats['losses']}L", 'primary'),
                            ("Win Rate", f"{stats['win_rate']}%", 'success'),
                            ("Total Debates", stats['total_debates'], 'info'),
                        ]

                        if stats['avg_score']:
                            metrics.append(("Average Score", f"{stats['avg_score']}/10", 'warning'))

                        if stats['favorite_topic']:
                            metrics.append(("Favorite Topic", stats['favorite_topic'][:50], 'purple'))

                        image_buffer = stats_viz.create_personal_stats_dashboard(
                            username=f"{target_user.display_name}'s Debate Stats",
                            metrics=metrics
                        )

                        file = discord.File(fp=image_buffer, filename="debate_stats.png")
                        await ctx.send(file=file)
                    else:
                        # Fallback to embed if visualizer not loaded
                        embed = discord.Embed(
                            title=f"Debate Stats: {target_user.display_name}",
                            color=discord.Color.blue()
                        )
                        embed.set_thumbnail(url=target_user.display_avatar.url)

                        embed.add_field(
                            name="Record",
                            value=f"**{stats['wins']}W - {stats['losses']}L**\nWin Rate: {stats['win_rate']}%",
                            inline=True
                        )

                        if stats['avg_score']:
                            embed.add_field(
                                name="Average Score",
                                value=f"**{stats['avg_score']}/10**",
                                inline=True
                            )

                        embed.add_field(
                            name="Total Debates",
                            value=f"**{stats['total_debates']}**",
                            inline=True
                        )

                        if stats['favorite_topic']:
                            embed.add_field(
                                name="Favorite Topic",
                                value=stats['favorite_topic'][:100],
                                inline=False
                            )

                        await ctx.send(embed=embed)

                except Exception as e:
                    await ctx.send(f"Error getting stats: {str(e)}")
                    print(f"Debate stats error: {e}")

        @bot.command(name='debate_lb', aliases=['dlb'])
        async def debate_leaderboard_cmd(ctx):
            """Show debate leaderboard"""
            async with ctx.typing():
                try:
                    leaderboard = await debate_scorekeeper.get_leaderboard(ctx.guild.id)

                    if not leaderboard:
                        await ctx.send("No debate data yet! Start a debate with `/debate_start`")
                        return

                    if stats_viz:
                        # Define value formatter for debate leaderboard
                        def format_debate_value(entry):
                            return f"{entry['wins']}W ({entry['win_rate']}%) - Avg: {entry['avg_score']}/10 - {entry['total_debates']} debates"

                        image_buffer = stats_viz.create_leaderboard(
                            entries=leaderboard[:10],
                            title="Debate Leaderboard",
                            subtitle="Top debaters by wins and average score",
                            value_formatter=format_debate_value
                        )

                        file = discord.File(fp=image_buffer, filename="debate_leaderboard.png")
                        await ctx.send(file=file)
                    else:
                        # Fallback to embed if visualizer not loaded
                        embed = discord.Embed(
                            title="Debate Leaderboard",
                            description="Top debaters by wins and average score",
                            color=discord.Color.gold()
                        )

                        for i, entry in enumerate(leaderboard[:10], 1):
                            medal = {1: '1.', 2: '2.', 3: '3.'}.get(i, f'{i}.')
                            value = f"**{entry['wins']}W** ({entry['win_rate']}%) - Avg: {entry['avg_score']}/10 - {entry['total_debates']} debates"
                            embed.add_field(
                                name=f"{medal} {entry['username']}",
                                value=value,
                                inline=False
                            )

                        await ctx.send(embed=embed)

                except Exception as e:
                    await ctx.send(f"Error getting leaderboard: {str(e)}")
                    print(f"Debate leaderboard error: {e}")

        @bot.command(name='debate_review')
        async def debate_review_cmd(ctx, *, topic: str = None):
            """Analyze a debate from uploaded text file. Attach a .txt/.log/.md file."""
            async with ctx.typing():
                try:
                    # Check for file attachment
                    if not ctx.message.attachments:
                        await ctx.send(
                            "Please attach a text file with the debate transcript.\n\n"
                            "**Expected format:**\n"
                            "```\n"
                            "Username1: First argument here\n"
                            "Username2: Counter argument\n"
                            "Username1: Response to counter\n"
                            "...\n"
                            "```\n\n"
                            "Usage: `!debate_review [topic]` with a .txt file attached"
                        )
                        return

                    attachment = ctx.message.attachments[0]

                    # Validate file type
                    if not attachment.filename.endswith(('.txt', '.log', '.md')):
                        await ctx.send(
                            "**Invalid file type**\n\n"
                            "Please upload a text file (.txt, .log, or .md)\n\n"
                            "**Expected format:**\n"
                            "```\n"
                            "Username1: First argument here\n"
                            "Username2: Counter argument\n"
                            "Username1: Response to counter\n"
                            "...\n"
                            "```"
                        )
                        return

                    # Check file size (max 1MB)
                    if attachment.size > 1024 * 1024:
                        await ctx.send("File too large. Maximum size is 1MB.")
                        return

                    # Download and read file content
                    transcript_bytes = await attachment.read()
                    try:
                        transcript_text = transcript_bytes.decode('utf-8')
                    except UnicodeDecodeError:
                        await ctx.send("File must be UTF-8 encoded text.")
                        return

                    # Use filename as topic if not provided
                    if not topic:
                        topic = attachment.filename.rsplit('.', 1)[0]  # Remove extension

                    # Analyze the debate
                    result = await debate_scorekeeper.analyze_uploaded_debate(transcript_text, topic)

                    # Handle errors
                    if 'error' in result:
                        error_messages = {
                            'insufficient_participants': result['message'],
                            'insufficient_messages': result['message'],
                            'analysis_failed': f"Analysis failed: {result['message']}"
                        }
                        error_msg = error_messages.get(result['error'], f"Error: {result.get('message', 'Unknown error')}")
                        await ctx.send(f"{error_msg}")
                        return

                    # Format successful analysis
                    analysis = result['analysis']

                    # Check if analysis failed
                    if 'error' in analysis:
                        error_msg = analysis.get('raw_analysis', analysis.get('message', 'Unknown error'))
                        # Truncate to fit Discord's 2000 char limit (with room for formatting)
                        if len(error_msg) > 1800:
                            error_msg = error_msg[:1800] + "...\n(truncated)"

                        await ctx.send(
                            f"**Analysis Error**\n\n"
                            f"The LLM analysis encountered an issue:\n"
                            f"```\n{error_msg}\n```"
                        )
                        return

                    # Build embed with results
                    embed = discord.Embed(
                        title=f"Comprehensive Debate Analysis: {result['topic']}",
                        description=analysis.get('summary', 'Analysis complete'),
                        color=discord.Color.purple()
                    )

                    # Add participant scores
                    if 'participants' in analysis:
                        for username, data in analysis['participants'].items():
                            overall_score = data.get('overall_score', data.get('score', 'N/A'))

                            field_value = f"**Overall: {overall_score}/10**\n\n"

                            # Rhetorical scores
                            logos = data.get('logos', {})
                            ethos = data.get('ethos', {})
                            pathos = data.get('pathos', {})
                            factual = data.get('factual_accuracy', {})

                            # Show scores with indicators
                            logos_score = logos.get('score', 'N/A') if isinstance(logos, dict) else 'N/A'
                            ethos_score = ethos.get('score', 'N/A') if isinstance(ethos, dict) else 'N/A'
                            pathos_score = pathos.get('score', 'N/A') if isinstance(pathos, dict) else 'N/A'
                            factual_score = factual.get('score', 'N/A') if isinstance(factual, dict) else 'N/A'

                            field_value += f"**Scores:**\n"
                            field_value += f"Logos (Logic): {logos_score}/10\n"
                            field_value += f"Ethos (Credibility): {ethos_score}/10\n"
                            field_value += f"Pathos (Emotion): {pathos_score}/10\n"
                            field_value += f"Factual Accuracy: {factual_score}/10\n\n"

                            # Logos details (fallacies)
                            if isinstance(logos, dict) and logos.get('fallacies'):
                                fallacies = logos['fallacies']
                                if fallacies and len(fallacies) > 0:
                                    field_value += f"**Logical Fallacies:**\n"
                                    for fallacy in fallacies[:2]:
                                        field_value += f"- {fallacy}\n"
                                    if len(fallacies) > 2:
                                        field_value += f"- _(+{len(fallacies) - 2} more)_\n"
                                    field_value += "\n"

                            # Factual accuracy details
                            if isinstance(factual, dict):
                                correct = factual.get('correct_points', [])
                                errors = factual.get('major_errors', [])

                                if correct and len(correct) > 0:
                                    field_value += f"**Key Facts Right:**\n"
                                    for point in correct[:2]:
                                        field_value += f"- {point[:60]}...\n" if len(point) > 60 else f"- {point}\n"

                                if errors and len(errors) > 0:
                                    field_value += f"\n**Key Errors:**\n"
                                    for error in errors[:2]:
                                        field_value += f"- {error[:60]}...\n" if len(error) > 60 else f"- {error}\n"

                            embed.add_field(
                                name=f"{username}",
                                value=field_value[:1024],  # Discord field value limit
                                inline=False
                            )

                    # Add winner
                    winner = analysis.get('winner', 'N/A')
                    winner_reason = analysis.get('winner_reason', 'N/A')
                    embed.add_field(
                        name="Winner",
                        value=f"**{winner}**\n{winner_reason}",
                        inline=False
                    )

                    # Add metadata
                    embed.set_footer(text=f"{result['participant_count']} participants - {result['message_count']} messages")

                    await ctx.send(embed=embed)

                except Exception as e:
                    await ctx.send(f"Error analyzing debate: {str(e)}")
                    print(f"Debate review error: {e}")
                    import traceback
                    traceback.print_exc()

        @bot.command(name='debate_profile', aliases=['dp'])
        async def debate_profile_cmd(ctx, user: discord.Member = None):
            """View detailed argumentation profile with radar chart and rhetorical breakdown"""
            async with ctx.typing():
                try:
                    target_user = user if user else ctx.author
                    profile = await debate_scorekeeper.get_argumentation_profile(
                        target_user.id, ctx.guild.id
                    )

                    if not profile or profile['total_debates'] == 0:
                        await ctx.send(
                            f"{target_user.display_name} hasn't participated in any debates yet! "
                            f"Use `/debate_start` to begin tracking a debate."
                        )
                        return

                    # Generate the PIL profile card
                    from debate_card import create_debate_profile_card
                    image_buffer = create_debate_profile_card(
                        target_user.display_name, profile
                    )

                    file = discord.File(fp=image_buffer, filename="debate_profile.png")

                    # Add a brief summary embed alongside the card
                    embed = discord.Embed(
                        title=f"{target_user.display_name}'s Argumentation Profile",
                        color=discord.Color.purple()
                    )
                    embed.set_image(url="attachment://debate_profile.png")

                    style = profile.get('argumentation_style', 'Unknown')
                    embed.description = (
                        f"**Style:** {style}\n"
                        f"**Record:** {profile['wins']}W - {profile['losses']}L "
                        f"({profile['win_rate']}% win rate)\n"
                        f"**Avg Score:** {profile['avg_score']}/10 across "
                        f"{profile['total_debates']} debates"
                    )

                    if profile.get('best_topic'):
                        embed.add_field(
                            name="Best Topic",
                            value=profile['best_topic'][:50],
                            inline=True
                        )
                    if profile.get('worst_topic'):
                        embed.add_field(
                            name="Weakest Topic",
                            value=profile['worst_topic'][:50],
                            inline=True
                        )

                    await ctx.send(file=file, embed=embed)

                except Exception as e:
                    await ctx.send(f"Error generating profile: {str(e)}")
                    print(f"Debate profile error: {e}")
                    import traceback
                    traceback.print_exc()

        print("  Prefix debate extra commands registered")

    # ==================== GROUP 5: TRIVIA EXTRAS ====================
    if trivia:

        @bot.command(name='triviastop')
        async def trivia_stop_cmd(ctx):
            """Stop the current trivia session"""
            async with ctx.typing():
                try:
                    if not trivia.is_session_active(ctx.channel.id):
                        await ctx.send("No active trivia session in this channel")
                        return

                    # End session
                    result = await trivia.end_session(ctx.channel.id)

                    if result:
                        # Show final scores
                        embed = discord.Embed(
                            title="Trivia Ended",
                            description=f"**{result['topic'].title()}** - {result['difficulty'].title()} - {result['question_count']} questions",
                            color=discord.Color.red()
                        )

                        if result['leaderboard']:
                            # Winner announcement with overall stats
                            winner_id, winner_data = result['leaderboard'][0]
                            winner_stats = result.get('winner_overall_stats')

                            if winner_stats:
                                accuracy = (winner_stats['total_correct'] / winner_stats['total_questions_answered'] * 100) if winner_stats['total_questions_answered'] > 0 else 0

                                winner_text = (
                                    f"**{winner_data['username']}** wins with **{winner_data['score']} points** this session!\n\n"
                                    f"**Overall Stats:**\n"
                                    f"- Total Points: **{winner_stats['total_points']:,}** across all sessions\n"
                                    f"- Total Wins: **{winner_stats['wins']}**\n"
                                    f"- Accuracy: **{accuracy:.1f}%** ({winner_stats['total_correct']}/{winner_stats['total_questions_answered']} correct)\n"
                                    f"- Best Streak: **{winner_stats['best_streak']}**"
                                )
                                embed.add_field(name="Champion", value=winner_text, inline=False)
                            else:
                                embed.add_field(
                                    name="Champion",
                                    value=f"**{winner_data['username']}** wins with **{winner_data['score']} points**!",
                                    inline=False
                                )

                            # Session leaderboard
                            leaderboard_text = ""
                            for i, (user_id, data) in enumerate(result['leaderboard'][:10]):
                                rank_emoji = ["1.", "2.", "3."][i] if i < 3 else f"{i+1}."
                                leaderboard_text += f"{rank_emoji} **{data['username']}** - {data['score']} points\n"

                            embed.add_field(name="Session Leaderboard", value=leaderboard_text, inline=False)

                        await ctx.send(embed=embed)

                except Exception as e:
                    await ctx.send(f"Error stopping trivia: {str(e)}")

        @bot.command(name='triviastats')
        async def trivia_stats_cmd(ctx, user: discord.Member = None):
            """View trivia stats for a user"""
            async with ctx.typing():
                try:
                    target = user or ctx.author
                    stats = await trivia.get_user_stats(ctx.guild.id, target.id)

                    if not stats:
                        await ctx.send(f"{target.display_name} hasn't played trivia yet")
                        return

                    # Get rank data
                    rank_data = await trivia.get_user_rank(ctx.guild.id, target.id)

                    accuracy = (stats['total_correct'] / stats['total_questions_answered'] * 100) if stats['total_questions_answered'] > 0 else 0

                    # Build title with rank if available
                    if rank_data:
                        rank = rank_data['rank']
                        if rank == 1:
                            rank_display = "#1"
                        elif rank == 2:
                            rank_display = "#2"
                        elif rank == 3:
                            rank_display = "#3"
                        else:
                            rank_display = f"#{rank}"
                        title = f"{target.display_name} - {rank_display} of {rank_data['total_players']}"
                        color = discord.Color.gold() if rank <= 3 else discord.Color.blue()
                    else:
                        title = f"Trivia Stats - {target.display_name}"
                        color = discord.Color.blue()

                    embed = discord.Embed(title=title, color=color)
                    embed.add_field(name="Total Sessions", value=f"{stats['total_sessions']}", inline=True)
                    embed.add_field(name="Questions Answered", value=f"{stats['total_questions_answered']}", inline=True)
                    embed.add_field(name="Wins", value=f"{stats['wins']}", inline=True)
                    embed.add_field(name="Accuracy", value=f"{accuracy:.1f}%", inline=True)
                    embed.add_field(name="Total Points", value=f"{stats['total_points']:,}", inline=True)
                    embed.add_field(name="Avg Time/Question", value=f"{stats['avg_time_per_question']:.1f}s", inline=True)

                    if stats.get('favorite_topic'):
                        embed.add_field(name="Favorite Topic", value=stats['favorite_topic'], inline=False)

                    embed.add_field(name="Best Streak", value=f"{stats['best_streak']} correct in a row", inline=False)

                    await ctx.send(embed=embed)

                except Exception as e:
                    await ctx.send(f"Error fetching stats: {str(e)}")

        @bot.command(name='trivialeaderboard', aliases=['tlb'])
        async def trivia_leaderboard_cmd(ctx, days: int = 30):
            """View server trivia leaderboard"""
            async with ctx.typing():
                try:
                    leaderboard = await trivia.get_leaderboard(ctx.guild.id, days=days, limit=10)

                    if not leaderboard:
                        await ctx.send("No trivia stats available for this server yet")
                        return

                    embed = discord.Embed(
                        title=f"Trivia Leaderboard (Last {days} days)",
                        color=discord.Color.gold()
                    )

                    leaderboard_text = ""
                    for i, entry in enumerate(leaderboard):
                        rank_emoji = ["1.", "2.", "3."][i] if i < 3 else f"{i+1}."
                        leaderboard_text += f"{rank_emoji} **{entry['username']}** - {entry['total_points']:,} pts ({entry['total_correct']}/{entry['total_questions_answered']} correct)\n"

                    embed.description = leaderboard_text

                    await ctx.send(embed=embed)

                except Exception as e:
                    await ctx.send(f"Error fetching leaderboard: {str(e)}")

        print("  Prefix trivia extra commands registered")

    # ==================== GROUP 6: GAME COMMANDS ====================

    # ===== Poll Commands =====
    if poll_system:

        @bot.command(name='pollresults')
        async def poll_results_cmd(ctx, poll_id: int):
            """View results for a poll"""
            async with ctx.typing():
                try:
                    results = await poll_system.get_results(poll_id)

                    if results.get('error'):
                        await ctx.send(f"{results['error']}")
                        return

                    # Generate PIL results card
                    from poll_card import create_poll_results_card
                    image_buffer = create_poll_results_card(results)
                    file = discord.File(fp=image_buffer, filename="poll_results.png")

                    embed = discord.Embed(
                        title=f"Poll Results -- #{poll_id}",
                        color=discord.Color.gold()
                    )
                    embed.set_image(url="attachment://poll_results.png")

                    status = "Closed" if results['is_closed'] else "Live"
                    embed.set_footer(text=f"{status} - {results['total_voters']} voters")

                    await ctx.send(file=file, embed=embed)

                except Exception as e:
                    await ctx.send(f"Error getting results: {str(e)}")
                    print(f"Poll results error: {e}")

        @bot.command(name='pollclose')
        async def poll_close_cmd(ctx, poll_id: int):
            """Close a poll you created and show final results"""
            async with ctx.typing():
                try:
                    results = await poll_system.close_poll(poll_id, ctx.author.id)

                    if results.get('error'):
                        await ctx.send(f"{results['error']}")
                        return

                    # Generate results card
                    from poll_card import create_poll_results_card
                    image_buffer = create_poll_results_card(results)
                    file = discord.File(fp=image_buffer, filename="poll_results.png")

                    winner = results.get('winner', {})
                    embed = discord.Embed(
                        title=f"Poll #{poll_id} -- Final Results",
                        description=f"Winner: **{winner.get('option', 'N/A')}** ({winner.get('percentage', 0)}%)",
                        color=discord.Color.green()
                    )
                    embed.set_image(url="attachment://poll_results.png")
                    embed.set_footer(text=f"{results['total_voters']} total voters")

                    await ctx.send(file=file, embed=embed)

                except Exception as e:
                    await ctx.send(f"Error closing poll: {str(e)}")
                    print(f"Poll close error: {e}")

        print("  Prefix poll commands registered")

    # ===== Who Said It? Commands =====
    if who_said_it:

        @bot.command(name='whosaidit')
        async def whosaidit_start_cmd(ctx, rounds: int = 5):
            """Start a 'Who Said It?' guessing game"""
            async with ctx.typing():
                try:
                    result = await who_said_it.start_game(
                        ctx.channel.id,
                        ctx.guild.id,
                        ctx.author.id,
                        rounds
                    )

                    if result.get('error'):
                        await ctx.send(f"{result['error']}")
                        return

                    embed = discord.Embed(
                        title="Who Said It?",
                        description="Guess which server member said each quote!\nType your guess in chat.",
                        color=discord.Color.blue()
                    )
                    embed.add_field(
                        name=f"Round {result['round']}/{result['total_rounds']}",
                        value=f">>> {result['quote']}",
                        inline=False
                    )
                    embed.set_footer(text="Type a username to guess! Use !wsisskip to skip. !wsisend to stop.")
                    await ctx.send(embed=embed)

                except Exception as e:
                    await ctx.send(f"Error: {str(e)}")
                    print(f"Who Said It start error: {e}")

        @bot.command(name='wsisskip')
        async def whosaidit_skip_cmd(ctx):
            """Skip the current round and reveal answer"""
            try:
                result = await who_said_it.skip_round(ctx.channel.id)
                if not result:
                    await ctx.send("No active game in this channel!")
                    return

                msg = f"Skipped! The answer was **{result['correct_answer']}**"
                await ctx.send(msg)

                if result.get('game_over'):
                    embed = discord.Embed(
                        title="Who Said It? -- Game Over!",
                        color=discord.Color.gold()
                    )
                    scores = result.get('final_scores', [])
                    if scores:
                        board = "\n".join(
                            f"{i+1}. **{s['username']}** -- {s['correct']} correct"
                            for i, s in enumerate(scores)
                        )
                        embed.description = board
                    else:
                        embed.description = "No one scored any points!"
                    await ctx.send(embed=embed)
                elif result.get('next_quote'):
                    await asyncio.sleep(1)
                    embed = discord.Embed(
                        title=f"Round {result['next_round']}/{result['total_rounds']}",
                        description=f">>> {result['next_quote']}",
                        color=discord.Color.blue()
                    )
                    embed.set_footer(text="Who said this? Type your guess!")
                    await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"Error: {str(e)}")

        @bot.command(name='wsisend')
        async def whosaidit_end_cmd(ctx):
            """End the Who Said It? game"""
            try:
                result = await who_said_it.end_game(ctx.channel.id)
                if not result:
                    await ctx.send("No active game in this channel!")
                    return

                embed = discord.Embed(
                    title="Who Said It? -- Game Ended!",
                    color=discord.Color.gold()
                )
                scores = result.get('final_scores', [])
                if scores:
                    board = "\n".join(
                        f"{i+1}. **{s['username']}** -- {s['correct']}/{result['total_rounds']} correct"
                        for i, s in enumerate(scores)
                    )
                    embed.description = board
                else:
                    embed.description = "No one scored any points!"

                await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"Error: {str(e)}")

        print("  Prefix Who Said It? commands registered")

    # ===== Devil's Advocate Commands =====
    if devils_advocate:

        @bot.command(name='da')
        async def devils_advocate_cmd(ctx, *, topic: str):
            """Start a devil's advocate debate on any topic"""
            try:
                if devils_advocate.is_session_active(ctx.channel.id):
                    await ctx.send(
                        "A devil's advocate session is already active in this channel!\n"
                        "Use `!daend` to end it first."
                    )
                    return

                async with ctx.typing():
                    result = await devils_advocate.start_session(
                        channel_id=ctx.channel.id,
                        guild_id=ctx.guild.id,
                        topic=topic,
                        user_id=ctx.author.id
                    )

                    if result.get('error'):
                        await ctx.send(f"{result['error']}")
                        return

                    embed = discord.Embed(
                        title=f"Devil's Advocate -- {topic}",
                        description=result['response'],
                        color=discord.Color.red()
                    )
                    embed.set_footer(text=f"Started by {ctx.author.display_name} - Reply to debate - !daend to stop")
                    await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"Error: {str(e)}")

        @bot.command(name='daend')
        async def devils_advocate_end_cmd(ctx):
            """End the current devil's advocate session"""
            try:
                result = await devils_advocate.end_session(ctx.channel.id)
                if not result:
                    await ctx.send("No active devil's advocate session in this channel!")
                    return

                embed = discord.Embed(
                    title="Devil's Advocate -- Session Ended",
                    color=discord.Color.red()
                )
                embed.add_field(name="Topic", value=result['topic'], inline=False)
                embed.add_field(name="Exchanges", value=str(result['exchange_count']), inline=True)
                embed.add_field(name="Duration", value=f"{result['duration_minutes']} minutes", inline=True)
                await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"Error: {str(e)}")

        print("  Prefix Devil's Advocate commands registered")

    # ===== Jeopardy Commands =====
    if jeopardy:

        @bot.command(name='jeopardy')
        async def jeopardy_start_cmd(ctx, categories: int = 4, clues_per: int = 5):
            """Start a Jeopardy game with server-inspired categories"""
            try:
                if jeopardy.is_session_active(ctx.channel.id):
                    await ctx.send(
                        "A Jeopardy game is already active in this channel!\n"
                        "Use `!jend` to end it first."
                    )
                    return

                async with ctx.typing():
                    result = await jeopardy.start_game(
                        channel_id=ctx.channel.id,
                        guild_id=ctx.guild.id,
                        started_by=ctx.author.id,
                        num_categories=categories,
                        clues_per=clues_per
                    )

                    if result.get('error'):
                        await ctx.send(f"{result['error']}")
                        return

                    # Build the game board display
                    board = result['board']
                    cat_names = result['categories']
                    values = result['point_values']

                    embed = discord.Embed(
                        title="JEOPARDY!",
                        description=f"Started by {ctx.author.display_name}\n\n"
                                    f"**Categories:**\n" +
                                    "\n".join(f"**{name}**" for name in cat_names),
                        color=discord.Color.blue()
                    )
                    embed.add_field(
                        name="Point Values",
                        value=" | ".join(f"${v}" for v in values),
                        inline=False
                    )
                    embed.add_field(
                        name="How to Play",
                        value=(
                            "1. Use `!jpick [category] [value]` to select a clue\n"
                            "2. Type your answer in chat (e.g. \"What is Python?\")\n"
                            "3. Correct = earn points, Wrong = lose points!\n"
                            "4. `!jpass` to skip a clue"
                        ),
                        inline=False
                    )
                    embed.set_footer(text=f"{result['clues_remaining']} clues to play")
                    await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"Error: {str(e)}")

        @bot.command(name='jpick')
        async def jeopardy_pick_cmd(ctx, *, args: str):
            """Pick a category and point value. Usage: !jpick Science 400"""
            try:
                # Parse: last word is value, everything before is category
                parts = args.rsplit(' ', 1)
                if len(parts) < 2:
                    await ctx.send("Usage: `!jpick <category> <value>` e.g. `!jpick Science 400`")
                    return
                category = parts[0]
                try:
                    value = int(parts[1])
                except ValueError:
                    await ctx.send("Value must be a number. Usage: `!jpick Science 400`")
                    return

                result = await jeopardy.select_clue(
                    ctx.channel.id, category, value
                )

                if not result:
                    await ctx.send("No active Jeopardy game!")
                    return

                if result.get('error'):
                    await ctx.send(f"{result['error']}")
                    return

                embed = discord.Embed(
                    title=f"{result['category']} -- ${result['value']}",
                    description=f"**{result['clue']}**",
                    color=discord.Color.gold()
                )
                embed.set_footer(text="Type your answer! (e.g. \"What is...?\")")
                await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"Error: {str(e)}")

        @bot.command(name='jpass')
        async def jeopardy_pass_cmd(ctx):
            """Pass on the current clue and reveal the answer"""
            try:
                result = await jeopardy.pass_clue(ctx.channel.id)

                if not result:
                    await ctx.send("No active clue to skip!")
                    return

                msg = f"Passed! The answer was: **{result['correct_answer']}**"

                if result.get('game_over'):
                    msg += "\n\n**GAME OVER!**"
                    scores = result.get('final_scores', [])
                    if scores:
                        board = "\n".join(
                            f"{i+1}. **{s['username']}** -- ${s['score']}"
                            for i, s in enumerate(scores)
                        )
                        msg += f"\n\n**Final Scores:**\n{board}"
                else:
                    msg += f"\n{result['clues_remaining']} clues remaining. Use `!jpick` to continue!"

                await ctx.send(msg)

            except Exception as e:
                await ctx.send(f"Error: {str(e)}")

        @bot.command(name='jend')
        async def jeopardy_end_cmd(ctx):
            """End the current Jeopardy game"""
            try:
                result = await jeopardy.end_game(ctx.channel.id)
                if not result:
                    await ctx.send("No active Jeopardy game!")
                    return

                embed = discord.Embed(
                    title="JEOPARDY! -- Game Over!",
                    color=discord.Color.blue()
                )

                scores = result.get('final_scores', [])
                if scores:
                    board = "\n".join(
                        f"{i+1}. **{s['username']}** -- ${s['score']}"
                        for i, s in enumerate(scores)
                    )
                    embed.description = board
                else:
                    embed.description = "No one scored any points!"

                answered = result['total_clues'] - result['clues_remaining']
                embed.set_footer(text=f"{answered}/{result['total_clues']} clues answered")

                await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"Error: {str(e)}")

        print("  Prefix Jeopardy commands registered")

    print("Prefix game commands registered")
