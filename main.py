import discord
from discord.ext import commands
from discord.ext import tasks
import logging
from dotenv import load_dotenv
import os
import yfinance as yf


load_dotenv()
token = os.getenv("Discord_Token")

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

alerts = {}

# Event for proof the bot is online
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    check_alerts.start()

# Command to allow users to check the price of a certain stock, etf, or cryptocurrency (!price [stock]) make sure to check if the stock exists and send an error message if it doesn't
@bot.command()
async def price(ctx, stock: str):
    try:
        stock_data = yf.Ticker(stock)
        current_price = stock_data.info['regularMarketPrice']
        currency = stock_data.info['currency']

        if current_price:
            await ctx.send(f"The current price of {stock} is {current_price} {currency}.")
        else:
            await ctx.send(f"Could not retrieve the price for {stock}. Please check the stock symbol and try again.")
    except Exception as e:
        await ctx.send(f"An error occurred while retrieving the price for {stock}: {e}")

# Command to allow a user to set an alert when a stock hits a low price that will send them a dm when its at that price 
# (!setlowalert [stock] [price]) make sure to check if the price is already lower than the alert price and send an alert if it is
@bot.command()
async def setlowalert(ctx, stock: str, price: float):
    try:
        user_id = ctx.author.id
        stock = stock.upper()
        # Ensure user exists
        if user_id not in alerts:
            alerts[user_id] = {}
        # Ensure stock exists for this user
        if stock not in alerts[user_id]:
            alerts[user_id][stock] = []
        # Add alert
        alerts[user_id][stock].append({'price': price, 'type': 'low'})
        await ctx.send(f"Low price alert set for {stock} at {price}. You will receive a DM when the price hits this level.")
    except Exception as e:
        await ctx.send(f"An error occurred while setting the low price alert for {stock}: {e}")
        
# Command to allow a user to set an alert when a stock hits a high price (!sethighalert [stock] [price]) make sure to check if the price is already higher than the alert price and send an alert if it is
@bot.command()
async def sethighalert(ctx, stock: str, price: float):
    try:
        user_id = ctx.author.id
        stock = stock.upper()
        # Ensure user exists
        if user_id not in alerts:
            alerts[user_id] = {}

        # Ensure stock exists for this user
        if stock not in alerts[user_id]:
            alerts[user_id][stock] = []
        # Add alert
        alerts[user_id][stock].append({'price': price, 'type': 'high'})
        await ctx.send(f"High price alert set for {stock} at {price}. You will receive a DM when the price hits this level.")
    except Exception as e:
        await ctx.send(f"An error occurred while setting the high price alert for {stock}: {e}")

# Task to check the stock prices every minute and send alerts if necessary
@tasks.loop(seconds=5)
async def check_alerts():
    try:
        # Loop through each user safely
        for user_id, stocks in list(alerts.items()):
            try:
                # Loop through each stock the user is watching
                for stock, alert_list in list(stocks.items()):
                    try:
                        stock_data = yf.Ticker(stock)
                        current_price = stock_data.info.get('regularMarketPrice')
                        if current_price is None:
                            continue
                        # Loop through each alert for this stock
                        for alert in list(alert_list):
                            price = alert['price']
                            alert_type = alert['type']
                            # Check alert condition
                            if (alert_type == 'low' and current_price <= price) or \
                               (alert_type == 'high' and current_price >= price):
                                try:
                                    user = await bot.fetch_user(user_id)
                                    await user.send(
                                        f"Alert: {stock} has hit your "
                                        f"{'low' if alert_type == 'low' else 'high'} price of {price}. "
                                        f"Current price: {current_price}."
                                    )
                                except Exception as dm_error:
                                    print(f"Error sending DM to {user_id}: {dm_error}")
                                # Remove the alert after sending
                                alert_list.remove(alert)
                        # If no alerts left for this stock, remove it
                        if not alert_list:
                            del stocks[stock]
                    except Exception as stock_error:
                        print(f"Error checking stock {stock}: {stock_error}")
                # If user has no stocks left, remove user entry
                if not stocks:
                    del alerts[user_id]
            except Exception as user_error:
                print(f"Error processing alerts for user {user_id}: {user_error}")
    except Exception as main_error:
        print(f"General error in check_alerts loop: {main_error}")

# Command to allow a user to remove an alert (!removealert [stock])
@bot.command()
async def removealert(ctx, stock: str):
    try:
        user_id = ctx.author.id
        stock = stock.upper()

        if user_id in alerts:
            alerts[user_id] = [alert for alert in alerts[user_id] if alert['stock'] != stock]
            await ctx.send(f"Alerts for {stock} have been removed.")
        else:
            await ctx.send(f"You have no alerts set for {stock}.")
    except Exception as e:
        await ctx.send(f"An error occurred while removing the alert for {stock}: {e}")

# Command to allow a user to list all their current alerts (!listalerts)
@bot.command()
async def listalerts(ctx):
    try:
        user_id = ctx.author.id

        if user_id in alerts and alerts[user_id]:
            alert_messages = []
            for alert in alerts[user_id]:
                alert_messages.append(f"{alert['type'].capitalize()} alert for {alert['stock']} at {alert['price']}")
            await ctx.send("Your current alerts:\n" + "\n".join(alert_messages))
        else:
            await ctx.send("You have no alerts set.")
    except Exception as e:
        await ctx.send(f"An error occurred while listing your alerts: {e}")

# Command to allow a user to clear all their alerts (!clearalerts)
@bot.command()
async def clearalerts(ctx):
    try:
        user_id = ctx.author.id

        if user_id in alerts:
            del alerts[user_id]
            await ctx.send("All your alerts have been cleared.")
        else:
            await ctx.send("You have no alerts to clear.")
    except Exception as e:
        await ctx.send(f"An error occurred while clearing your alerts: {e}")

# Command to allow a user to check the price history of a stock (!history [stock] [period])
@bot.command()
async def history(ctx, stock: str, period: str):
    try:
        stock_data = yf.Ticker(stock)
        hist = stock_data.history(period=period)

        if not hist.empty:
            history_message = f"Price history for {stock} over the last {period}:\n"
            for index, row in hist.iterrows():
                history_message += f"{index.date()}: Open: {row['Open']}, High: {row['High']}, Low: {row['Low']}, Close: {row['Close']}\n"
            
            chunks = [history_message[i:i+1900] for i in range(0, len(history_message), 1900)]
            for chunk in chunks:
                await ctx.send(chunk)

        else:
            await ctx.send(f"No historical data found for {stock} over the last {period}. Please check the stock symbol and period and try again.")
    except Exception as e:
        await ctx.send(f"An error occurred while retrieving the price history for {stock}: {e}")

@history.error
async def history_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Please provide both the stock symbol and the period. Usage: !history [stock] [period]")
    else:
        await ctx.send(f"An error occurred while processing your request: {error}")
# Command to allow a user to check the news related to a stock (!news [stock])
@bot.command()
async def news(ctx, stock: str):
    try:
        stock_data = yf.Ticker(stock)
        news_items = stock_data.news

        if news_items:
            news_message = f"News related to {stock}:\n"
            for item in news_items[:5]:  # Show only the top 5 news items
                title = item.get('title', 'No title')
                link = item.get('link', 'No link')
                publisher = item.get('publisher', 'Unknown publisher')
                timestamp = item.get('providerPublishTime', 'Unknown time')
                news_message += f"Title: {title}\nPublisher: {publisher}\nPublished at: {timestamp}\nLink: {link}\n\n"

            chunks = [news_message[i:i+1900] for i in range(0, len(news_message), 1900)]
            for chunk in chunks:
                await ctx.send(chunk)

        else:
            await ctx.send(f"No news found for {stock}. Please check the stock symbol and try again.")
    except Exception as e:
        await ctx.send(f"An error occurred while retrieving news for {stock}: {e}")

@news.error
async def news_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Please provide the stock symbol. Usage: !news [stock]")
    else:
        await ctx.send(f"An error occurred while processing your request: {error}")

# makes the bot run with the token from the .env file
bot.run(token)