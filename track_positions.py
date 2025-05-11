import urllib.request
import json
import os

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:136.0) Gecko/20100101 Firefox/136.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.5",
    "device_brand": "Linux_Firefox_136.0",
    "device_id": "1aa7addb864747dcba31e2ed6c5c6bb2",
    "platformId": "30",
    "appSiteId": "0",
    "channel": "official",
    "reg_channel": "official",
    "app_version": "4.78.74",
    "lang": "en",
    "appId": "30004",
    "mainAppId": "10009",
    "timestamp": "1746876207231",
    "timeZone": "5.5",
    "traceId": "cba99669ed4a405096c9d88f457de4e0",
    "sign": "F8BBA431198DB11F8B4B838FFCAC3020ECF8F606F150909374758ED07891BDEC",
    "visitorId": "-1",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
    "Referer": "https://bingx.com/"
}


POSITION_URL = "https://api-app.we-api.com/api/copy-trade-facade/v2/real/trader/positions?uid=1265135796481568773&apiIdentity=1265549006658510853&pageId=0&pageSize=10&copyTradeLabelType=2"
HISTORY_URL = "https://api-app.we-api.com/api/v3/trader/orders/v3?uid=1265135796481568773&pageId=0&pageSize=10&apiIdentity=1265549006658510853&copyTradeLabelType=2"

POSITION_FILE = "active_positions.json"

def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())

def load_previous_positions(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []

def save_positions(positions, path):
    with open(path, "w") as f:
        json.dump(positions, f, indent=2)

def get_position_ids(positions):
    return set(p["positionNo"] for p in positions)

def get_position_symbols(positions):
    return set(p["symbol"] for p in positions)

def send_telegram_message(message):
    import urllib.parse
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    base_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    })
    urllib.request.urlopen(f"{base_url}?{params}")

def main():
    print("Fetching current positions...")
    current_data = fetch_json(POSITION_URL)
    current_positions = current_data.get("data", {}).get("positions", [])
    current_positions = []
    current_ids = get_position_ids(current_positions)
    current_symbols = get_position_symbols(current_positions)

    print("Loading previously stored positions...")
    previous_positions = load_previous_positions(POSITION_FILE)
    prev_ids = get_position_ids(previous_positions)
    prev_symbols = get_position_symbols(previous_positions)

    new_positions = [p for p in current_positions if p["positionNo"] not in prev_ids]
    closed_positions = [p for p in previous_positions if p["positionNo"] not in current_ids]

    print(f"🆕 New positions: {len(new_positions)}")
    for p in new_positions:
        message = (
            f"🆕 *New Position Detected*\n"
            f"Symbol: `{p['symbol']}`\n"
            f"Side: `{p['positionSide']}`\n"
            f"Leverage: `{p['leverage']}x`\n"
            f"Avg Price: `{p['avgPrice']}`\n"
            f"Volume: `{p['volume']}`\n"
            f"Unrealized PnL: `{p['unrealizedPnl']:.2f}`\n"
            f"Earning Rate: `{p['positionEarningRate'] * 100:.2f}`\n"
            f"Liquidation Price: `{p['liquidatedPrice']}`\n"
            f"Position No: `{p['positionNo']}`"
        )
        send_telegram_message(message)
        print(f"  → {p['symbol']} (ID: {p['positionNo']})")

    if closed_positions:
        print(f"❌ Closed positions: {len(closed_positions)}")
        print("Fetching trade history to match closed positions by symbol...")
        history_data = fetch_json(HISTORY_URL)
        trade_orders = history_data.get("data", {}).get("result", [])

        for closed in closed_positions:
            symbol = closed["symbol"]
            match = next((order for order in trade_orders if order["name"] == symbol), None)
            order_info = f"Matched Order: `{match['orderNo']}`" if match else "No match in recent history"
            if match:
                print(f"  → {symbol} closed → {order_info}")
                message = (
                    f"❌ *Position Closed*\n"
                    f"Symbol: `{match['name']}`\n"
                    f"Side: `{'SHORT' if match['orderType'] else 'LONG'}`\n"
                    f"Leverage: `{match['leverTimes']}x`\n"
                    f"Avg Open Price: `{match['displayPrice']}`\n"
                    f"Avg Close Price: `{match['displayClosePrice']}`\n"
                    f"PnL: `{match['grossEarnings']:.2f}`\n"
                    f"Earning Rate: `{match['grossProfitRate'] * 100:.2%}`\n"
                    f"{order_info}"
                )
                send_telegram_message(message)

    # Save current state
    save_positions(current_positions, POSITION_FILE)
    print("✅ Updated active positions stored in:", POSITION_FILE)

if __name__ == "__main__":
    main()
