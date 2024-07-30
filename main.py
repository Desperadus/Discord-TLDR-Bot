import os
import discord
from discord.ext import commands
import ollama
from datetime import datetime, timedelta
import asyncio
from dotenv import load_dotenv
import logging
import httpx

logging.basicConfig(level=logging.INFO, filename="bot_logs.log")

load_dotenv()
TOKEN = os.getenv("DC_TLDR_BOT_TOKEN")
LANGUAGE = os.getenv("LANGUAGE")
if not TOKEN:
    raise ValueError("DC_TLDR_BOT_TOKEN environment variable is not set")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

ollama_client = ollama.Client(timeout=httpx.Timeout(120.0, connect=60.0))


async def generate_tldr(channel, hours, custom_message, model):
    after_time = datetime.utcnow() - timedelta(hours=hours)
    messages = []
    async for message in channel.history(limit=None, after=after_time):
        messages.append(f"{message.author.name}: {message.content}")

    # messages.reverse()

    if os.getenv("LANGUAGE") == "CZ":
        prompt = f"Shrň následující konverzaci mezi uživateli na Discordu, buď stručný, řekni hlavní věci co se řešily a jaký názor zastával:\n\n"
    else:
        prompt = f"Summarize the following conversation in a concise TLDR format:\n\n"
    prompt += "\n".join(messages)
    logging.info(prompt)

    if custom_message:
        if os.getenv("LANGUAGE") == "CZ":
            prompt += f"\n\nDoplňující kontext: {custom_message}"
        else:
            prompt += f"\n\nAdditional context: {custom_message}"

    # Generate TLDR using Ollama with streaming
    try:
        return ollama_client.generate(model=model, prompt=prompt, stream=True)
    except Exception as e:
        logging.error(f"{str(e)}")
        return f"Error generating TLDR: {str(e)}"



@bot.command(name="tldr")
async def tldr(ctx, hours: int = 1, *, custom: str = ""):
    try:
        # Send initial message to user's DM
        user_dm = await ctx.author.create_dm()
        initial_message = await user_dm.send(
            "Generating TLDR... This may take a moment."
        )

        # Start generating TLDR
        stream = await generate_tldr(ctx.channel, hours, custom, "llama3.1")

        if isinstance(stream, str):  # Error occurred
            await initial_message.edit(content=stream)
            return

        generated_content = ""

        # Stream the response and update the message
        for chunk in stream:
            generated_content += chunk["response"]
            if len(generated_content) % 10 == 0:  # Update every 20 characters
                await initial_message.edit(
                    content=f"TLDR of the last {hours} hour(s):\n\n{generated_content}"
                )
                # Add a small delay to avoid rate limiting
                await asyncio.sleep(2)

        # Send the final message
        await initial_message.edit(
            content=f"TLDR of the last {hours} hour(s):\n\n{generated_content}"
        )

    except Exception as e:
        await user_dm.send(f"An error occurred: {str(e)}")
        logging.error(f"{str(e)}")


@bot.command(name="models")
async def list_models(ctx):
    try:
        models = await asyncio.to_thread(ollama_client.list)
        model_names = [model["name"] for model in models["models"]]
        await ctx.author.send(f"Available Ollama models:\n{', '.join(model_names)}")
    except Exception as e:
        await ctx.author.send(f"Error listing models: {str(e)}")


@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")


bot.run(TOKEN)
