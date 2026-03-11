import sqlite3
import sys
import os
import math
import random
from datetime import datetime, timedelta

DB_PATH = 'data/bist_model_ready.db'

def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)

def init_portfolio_table(conn):
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                symbol TEXT PRIMARY KEY,
                shares REAL NOT NULL,
                cost_per_share REAL NOT NULL,
                purchase_date TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute("PRAGMA table_info(portfolio)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'shares' not in columns:
            cursor.execute("ALTER TABLE portfolio ADD COLUMN shares REAL NOT NULL DEFAULT 0")
        if 'cost_per_share' not in columns:
            cursor.execute("ALTER TABLE portfolio ADD COLUMN cost_per_share REAL NOT NULL DEFAULT 0")
        if 'purchase_date' not in columns:
            cursor.execute("ALTER TABLE portfolio ADD COLUMN purchase_date TEXT")
            cursor.execute("UPDATE portfolio SET purchase_date = substr(added_at, 1, 10) WHERE purchase_date IS NULL")
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error creating portfolio table: {e}")

def color_text(text, color_code):
    return f"\033[{color_code}m{text}\033[0m"

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def main_menu():
    while True:
        clear_screen()
        print("=== BIST Stock Tracker CLI ===")
        print("1. List Stocks (Paginated)")
        print("2. View Portfolio")
        print("3. Add Stock to Portfolio")
        print("4. Trading Game")
        print("5. Exit")

        choice = input("\nEnter your choice (1-5): ")

        if choice == '1':
            list_stocks_menu()
        elif choice == '2':
            view_portfolio()
        elif choice == '3':
            add_to_portfolio()
        elif choice == '4':
            trading_game()
        elif choice == '5':
            print("Goodbye!")
            sys.exit(0)
        else:
            input("Invalid choice. Press Enter to try again...")

def list_stocks_menu():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get total count of unique stocks
    cursor.execute("SELECT COUNT(DISTINCT symbol) FROM model_data")
    total_stocks = cursor.fetchone()[0]
    
    page_size = 10
    total_pages = math.ceil(total_stocks / page_size)
    current_page = 1
    
    while True:
        clear_screen()
        print(f"=== Stock List (Page {current_page}/{total_pages}) ===")
        print("--------------------------------------------------")
        print(f"{'Symbol':<15}")
        print("--------------------------------------------------")
        
        offset = (current_page - 1) * page_size
        cursor.execute("SELECT DISTINCT symbol FROM model_data ORDER BY symbol LIMIT ? OFFSET ?", (page_size, offset))
        stocks = cursor.fetchall()
        
        for stock in stocks:
            print(f"{stock['symbol']:<15}")
            
        print("--------------------------------------------------")
        print("Commands: [N]ext, [P]revious, [S]elect, [B]ack")
        
        choice = input("\nEnter command: ").lower()
        
        if choice == 'n':
            if current_page < total_pages:
                current_page += 1
            else:
                input("You are on the last page. Press Enter to continue...")
        elif choice == 'p':
            if current_page > 1:
                current_page -= 1
            else:
                input("You are on the first page. Press Enter to continue...")
        elif choice == 's':
            symbol = input("Enter stock symbol to select: ").upper()
            cursor.execute("SELECT 1 FROM model_data WHERE symbol = ?", (symbol,))
            if cursor.fetchone():
                display_stock_chart(conn, symbol)
            else:
                input(f"Stock '{symbol}' not found. Press Enter to continue...")
        elif choice == 'b':
            break
        else:
            input("Invalid choice. Press Enter to try again...")
    
    conn.close()

def resample_data(data, interval):
    if not data or interval == 'D':
        return data

    resampled = []
    
    # Group data by period
    grouped_data = {}
    
    for row in data:
        date_str = row['date']
        price = row['close']
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            continue

        if interval == 'W':
            # ISO calendar year and week number
            year, week, _ = date_obj.isocalendar()
            period_key = f"{year}-{week:02d}"
        elif interval == 'M':
            period_key = date_obj.strftime('%Y-%m')
        else:
            period_key = date_str

        if period_key not in grouped_data:
            grouped_data[period_key] = []
        
        grouped_data[period_key].append({'date': date_str, 'close': price})

    # Create resampled list using the last close price of each period
    for key in sorted(grouped_data.keys()):
        period_items = grouped_data[key]
        # Taking the last item's close price as the close price for the period
        last_item = period_items[-1]
        resampled.append(last_item)

    return resampled

def display_stock_chart(conn, symbol):
    interval = 'D'  # Default to Daily
    
    while True:
        clear_screen()
        cursor = conn.cursor()
        
        # Fetch price data sorted by date
        try:
            cursor.execute("SELECT date, close FROM model_data WHERE symbol = ? ORDER BY date", (symbol,))
            raw_data = cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            input("Press Enter to continue...")
            return
        
        if not raw_data:
            print(f"No data available for {symbol}.")
            input("Press Enter to continue...")
            return

        # Resample data based on selected interval
        data = resample_data(raw_data, interval)
        
        if not data:
             print("Not enough data for this interval.")
             input("Press Enter to continue...")
             return

        # Chart dimensions
        try:
            terminal_width = os.get_terminal_size().columns
        except OSError:
            terminal_width = 80
            
        width = terminal_width - 15  # Reserve space for Y-axis labels and padding
        height = 20
        
        # Slice data to fit width
        # We want to show the LAST 'width' data points
        if len(data) > width:
            data = data[-width:]
            
        # Extract prices
        prices = [row['close'] for row in data]
        dates = [row['date'] for row in data]
        
        min_price = min(prices)
        max_price = max(prices)
        price_range = max_price - min_price
        
        if price_range == 0:
            price_range = 1  # Avoid division by zero
            
        interval_name = "Daily"
        if interval == 'W':
            interval_name = "Weekly"
        elif interval == 'M':
            interval_name = "Monthly"

        print(f"\n=== {symbol} Price Chart ({interval_name}) ===")
        print(f"Range: {min_price:.2f} - {max_price:.2f}")
        print(f"Displaying last {len(prices)} periods")
        print("-" * (width + 12))
        
        # Create empty chart grid
        grid = [[' ' for _ in range(width)] for _ in range(height)]
        
        # Populate chart
        num_points = len(prices)
        if num_points < 2:
            print("Not enough data points to display chart.")
            input("Press Enter to continue...")
            return

        # Map prices to grid coordinates
        # Since we sliced the data to fit the width, we map 1:1 or less
        for x in range(num_points):
            price = prices[x]
            normalized_price = (price - min_price) / price_range
            y = int(normalized_price * (height - 1))
            
            # Invert y because terminal prints top-to-bottom (0 is top)
            # But we want 0 to be bottom price (min_price)
            # So row index = height - 1 - y
            row_idx = height - 1 - y
            
            if 0 <= row_idx < height:
                grid[row_idx][x] = '*'
                
        # Print chart with Y-axis labels
        for i in range(height):
            # Calculate price corresponding to this row
            # Row 0 corresponds to max_price
            # Row height-1 corresponds to min_price
            y_val = max_price - (i / (height - 1)) * price_range
            row_str = "".join(grid[i])
            print(f"{y_val:8.2f} | {row_str}")
            
        print(" " * 9 + "-" * width)
        
        # Print X-axis labels (start and end date)
        start_date = str(dates[0])
        end_date = str(dates[-1])
        
        # Ensure date strings fit
        date_line = f"{' ' * 9}{start_date}"
        padding = width - len(start_date) - len(end_date)
        if padding > 0:
            date_line += f"{' ' * padding}{end_date}"
        else:
            date_line += f" {end_date}"
            
        print(date_line)
        
        print("\nIntervals: [D]aily  [W]eekly  [M]onthly")
        print("[B]ack to List")
        
        choice = input("\nEnter choice: ").upper()
        
        if choice == 'D':
            interval = 'D'
        elif choice == 'W':
            interval = 'W'
        elif choice == 'M':
            interval = 'M'
        elif choice == 'B':
            break

def build_portfolio_timeseries(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT symbol, shares, purchase_date FROM portfolio")
    portfolio = cursor.fetchall()

    if not portfolio:
        return []

    purchase_dates = {}
    earliest_purchase_date = None
    for item in portfolio:
        purchase_date = item['purchase_date']
        if purchase_date:
            purchase_dates[item['symbol']] = purchase_date
            if earliest_purchase_date is None or purchase_date < earliest_purchase_date:
                earliest_purchase_date = purchase_date

    # Get all dates where there is data for any symbol in the portfolio
    symbols = [item['symbol'] for item in portfolio]
    placeholders = ','.join('?' for _ in symbols)
    cursor.execute(
        f"SELECT DISTINCT date FROM model_data WHERE symbol IN ({placeholders}) ORDER BY date",
        symbols
    )
    dates = [row['date'] for row in cursor.fetchall()]

    # If purchase dates are after the available data, fall back to using the latest available window
    if earliest_purchase_date and dates and earliest_purchase_date > dates[-1]:
        earliest_purchase_date = None

    if earliest_purchase_date:
        dates = [date for date in dates if date >= earliest_purchase_date]

    timeseries = []

    # Cache price data per symbol
    price_cache = {}
    for item in portfolio:
        symbol = item['symbol']
        cursor.execute("SELECT date, close FROM model_data WHERE symbol = ? ORDER BY date", (symbol,))
        rows = cursor.fetchall()
        price_cache[symbol] = {row['date']: row['close'] for row in rows}

    for date in dates:
        total_value = 0
        for item in portfolio:
            symbol = item['symbol']
            shares = item['shares']
            purchase_date = purchase_dates.get(symbol)
            if purchase_date and date < purchase_date:
                continue

            price = price_cache.get(symbol, {}).get(date)
            if price is not None:
                total_value += price * shares
        
        timeseries.append({'date': date, 'close': total_value})

    return timeseries


def display_portfolio_chart(conn):
    interval = 'D'

    while True:
        clear_screen()
        data = build_portfolio_timeseries(conn)
        if not data:
            print("Portfolio is empty or no data available.")
            input("Press Enter to continue...")
            return

        if all(item['close'] == 0 for item in data):
            print("Portfolio data is outside the available market history.")
            print("Update purchase dates to be within the available price history.")
            input("Press Enter to continue...")
            return

        data = resample_data(data, interval)
        if not data:
            print("Not enough data for this interval.")
            input("Press Enter to continue...")
            return

        try:
            terminal_width = os.get_terminal_size().columns
        except OSError:
            terminal_width = 80

        width = terminal_width - 15
        height = 20

        if len(data) > width:
            data = data[-width:]

        prices = [row['close'] for row in data]
        dates = [row['date'] for row in data]

        min_price = min(prices)
        max_price = max(prices)
        price_range = max_price - min_price
        if price_range == 0:
            price_range = 1

        interval_name = "Daily"
        if interval == 'W':
            interval_name = "Weekly"
        elif interval == 'M':
            interval_name = "Monthly"

        print(f"\n=== Portfolio Value Chart ({interval_name}) ===")
        print(f"Range: {min_price:.2f} - {max_price:.2f}")
        print(f"Displaying last {len(prices)} periods")
        
        if prices:
            total_gain = prices[-1] - prices[0]
            gain_pct = (total_gain / prices[0]) * 100 if prices[0] else 0
            print(f"Gain: {total_gain:.2f} ({gain_pct:.2f}%)")
        
        print("-" * (width + 12))

        grid = [[' ' for _ in range(width)] for _ in range(height)]
        num_points = len(prices)
        if num_points < 2:
            print("Not enough data points to display chart.")
            input("Press Enter to continue...")
            return

        for x in range(num_points):
            price = prices[x]
            normalized_price = (price - min_price) / price_range
            y = int(normalized_price * (height - 1))
            row_idx = height - 1 - y
            if 0 <= row_idx < height:
                grid[row_idx][x] = '*'

        for i in range(height):
            y_val = max_price - (i / (height - 1)) * price_range
            row_str = "".join(grid[i])
            print(f"{y_val:8.2f} | {row_str}")

        print(" " * 9 + "-" * width)
        start_date = str(dates[0])
        end_date = str(dates[-1])
        date_line = f"{' ' * 9}{start_date}"
        padding = width - len(start_date) - len(end_date)
        if padding > 0:
            date_line += f"{' ' * padding}{end_date}"
        else:
            date_line += f" {end_date}"
        print(date_line)

        print("\nIntervals: [D]aily  [W]eekly  [M]onthly")
        print("[B]ack to Portfolio")
        choice = input("\nEnter choice: ").upper()

        if choice == 'D':
            interval = 'D'
        elif choice == 'W':
            interval = 'W'
        elif choice == 'M':
            interval = 'M'
        elif choice == 'B':
            break


def view_portfolio():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT symbol, shares, cost_per_share, purchase_date, added_at FROM portfolio ORDER BY added_at DESC")
        portfolio = cursor.fetchall()
        
        clear_screen()
        print("=== My Portfolio ===")
        print("------------------------------------------------------------------------------------------------------------------------------------------------------")
        print(f"{'Symbol':<10} {'Shares':<10} {'Cost/Share':<12} {'Current':<12} {'Value':<12} {'Cost':<12} {'P/L':<12} {'P/L %':<10} {'Purchased':<12} {'Added At':<12}")
        print("------------------------------------------------------------------------------------------------------------------------------------------------------")
        
        total_value = 0
        total_cost = 0
        
        if not portfolio:
            print("Your portfolio is empty.")
        else:
            for item in portfolio:
                symbol = item['symbol']
                shares = item['shares']
                cost_per_share = item['cost_per_share']
                purchase_date = item['purchase_date']
                added_at = item['added_at']
                
                # Get latest price
                cursor.execute("SELECT close FROM model_data WHERE symbol = ? ORDER BY date DESC LIMIT 1", (symbol,))
                price_row = cursor.fetchone()
                current_price = price_row['close'] if price_row else None
                
                if current_price is not None and shares > 0 and cost_per_share > 0:
                    current_value = current_price * shares
                    item_cost = cost_per_share * shares
                    pnl = current_value - item_cost
                    pnl_pct = (pnl / item_cost) * 100 if item_cost else 0
                    current_price_str = f"{current_price:.2f}"
                    current_value_str = f"{current_value:.2f}"
                    item_cost_str = f"{item_cost:.2f}"
                    pnl_str = f"{pnl:.2f}"
                    pnl_pct_str = f"{pnl_pct:.2f}%"

                    if pnl > 0:
                        pnl_str = color_text(pnl_str, '32')
                        pnl_pct_str = color_text(pnl_pct_str, '32')
                    elif pnl < 0:
                        pnl_str = color_text(pnl_str, '31')
                        pnl_pct_str = color_text(pnl_pct_str, '31')

                    total_value += current_value
                    total_cost += item_cost
                else:
                    current_price_str = f"{current_price:.2f}" if current_price is not None else "N/A"
                    current_value_str = "N/A"
                    item_cost_str = "N/A"
                    pnl_str = "N/A"
                    pnl_pct_str = "N/A"
                
                purchase_date_str = str(purchase_date) if purchase_date else "N/A"
                added_at_str = str(added_at).split(' ')[0] if added_at else "N/A"

                if pnl_str != "N/A":
                    pnl_str = f"{pnl_str:<12}"
                if pnl_pct_str != "N/A":
                    pnl_pct_str = f"{pnl_pct_str:<10}"

                # If we have ANSI color codes, avoid padding issues by ensuring the base columns align
                if pnl_str == "N/A":
                    pnl_str = f"{pnl_str:<12}"
                if pnl_pct_str == "N/A":
                    pnl_pct_str = f"{pnl_pct_str:<10}"
                
                print(
                    f"{symbol:<10} {shares:<10.2f} {cost_per_share:<12.2f} {current_price_str:<12} "
                    f"{current_value_str:<12} {item_cost_str:<12} {pnl_str} {pnl_pct_str} {purchase_date_str:<12} {added_at_str:<12}"
                )
                
        if total_cost > 0:
            total_pnl = total_value - total_cost
            total_pnl_pct = (total_pnl / total_cost) * 100
            total_pnl_str = f"{total_pnl:.2f}"
            total_pnl_pct_str = f"{total_pnl_pct:.2f}%"
        else:
            total_pnl_str = "N/A"
            total_pnl_pct_str = "N/A"

        print("------------------------------------------------------------------------------------------------------------------------------------------------------")
        if total_cost > 0:
            total_pnl = total_value - total_cost
            total_pnl_pct = (total_pnl / total_cost) * 100
            total_pnl_str = f"{total_pnl:.2f}"
            total_pnl_pct_str = f"{total_pnl_pct:.2f}%"

            if total_pnl > 0:
                total_pnl_str = color_text(total_pnl_str, '32')
                total_pnl_pct_str = color_text(total_pnl_pct_str, '32')
            elif total_pnl < 0:
                total_pnl_str = color_text(total_pnl_str, '31')
                total_pnl_pct_str = color_text(total_pnl_pct_str, '31')
        else:
            total_pnl_str = "N/A"
            total_pnl_pct_str = "N/A"

        print(
            f"TOTAL{'':<6} {'':<10} {'':<12} {'':<12} {total_value:>12.2f} {total_cost:>12.2f} {total_pnl_str:>12} {total_pnl_pct_str:>10} {'':<12} {'':<12}"
        )
        print("------------------------------------------------------------------------------------------------------------------------------------------------------")
        print("[A]dd Stock  [R]emove Stock  [U]pdate Shares/Cost  [S]elect Stock  [C]hart  [B]ack")
        
        choice = input("\nEnter your choice: ").lower()
        
        if choice == 'a':
            add_to_portfolio()
        elif choice == 'r':
            remove_from_portfolio()
        elif choice == 'u':
            update_portfolio_entry()
        elif choice == 's':
            symbol = input("Enter stock symbol to select: ").upper()
            cursor.execute("SELECT 1 FROM model_data WHERE symbol = ?", (symbol,))
            if cursor.fetchone():
                display_stock_chart(conn, symbol)
            else:
                input(f"Stock '{symbol}' not found. Press Enter to continue...")
        elif choice == 'c':
            display_portfolio_chart(conn)
        elif choice == 'b':
            pass
        else:
            input("Invalid choice. Press Enter to try again...")
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        input("Press Enter to continue...")
    finally:
        conn.close()

def add_to_portfolio():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    clear_screen()
    print("=== Add to Portfolio ===")
    symbol = input("Enter stock symbol to add: ").upper()
    
    if not symbol:
        return

    try:
        # Check if symbol exists in model_data
        cursor.execute("SELECT 1 FROM model_data WHERE symbol = ? LIMIT 1", (symbol,))
        if not cursor.fetchone():
            print(f"Error: Stock '{symbol}' does not exist in the database.")
            input("Press Enter to continue...")
            return

        shares_input = input("Enter number of shares: ")
        cost_input = input("Enter cost per share: ")
        purchase_date_input = input("Enter purchase date (YYYY-MM-DD): ")
        
        try:
            shares = float(shares_input)
            cost_per_share = float(cost_input)
        except ValueError:
            print("Invalid input. Shares and cost must be numeric.")
            input("Press Enter to continue...")
            return

        if shares <= 0 or cost_per_share <= 0:
            print("Shares and cost must be positive values.")
            input("Press Enter to continue...")
            return

        try:
            purchase_date = datetime.strptime(purchase_date_input, '%Y-%m-%d').strftime('%Y-%m-%d')
        except ValueError:
            print("Invalid purchase date. Use YYYY-MM-DD.")
            input("Press Enter to continue...")
            return

        # Add to portfolio
        cursor.execute(
            "INSERT INTO portfolio (symbol, shares, cost_per_share, purchase_date) VALUES (?, ?, ?, ?)",
            (symbol, shares, cost_per_share, purchase_date)
        )
        conn.commit()
        print(f"Successfully added {symbol} to portfolio.")
        input("Press Enter to continue...")
        
    except sqlite3.IntegrityError:
        print(f"Stock '{symbol}' is already in your portfolio. Use the update option in the portfolio view to adjust shares or cost.")
        input("Press Enter to continue...")
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        input("Press Enter to continue...")
    finally:
        conn.close()

def update_portfolio_entry():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    clear_screen()
    print("=== Update Portfolio Entry ===")
    symbol = input("Enter stock symbol to update: ").upper()
    
    if not symbol:
        return

    try:
        cursor.execute("SELECT shares, cost_per_share, purchase_date FROM portfolio WHERE symbol = ?", (symbol,))
        entry = cursor.fetchone()
        if not entry:
            print(f"Stock '{symbol}' not found in portfolio.")
            input("Press Enter to continue...")
            return

        current_shares = entry['shares']
        current_cost = entry['cost_per_share']
        current_purchase_date = entry['purchase_date']
        print(f"Current shares: {current_shares}")
        print(f"Current cost per share: {current_cost}")
        print(f"Current purchase date: {current_purchase_date}")

        shares_input = input("Enter new number of shares (leave blank to keep current): ")
        cost_input = input("Enter new cost per share (leave blank to keep current): ")
        purchase_date_input = input("Enter new purchase date (YYYY-MM-DD, leave blank to keep current): ")

        new_shares = current_shares
        new_cost = current_cost
        new_purchase_date = current_purchase_date

        if shares_input.strip():
            try:
                new_shares = float(shares_input)
            except ValueError:
                print("Invalid shares value. Update cancelled.")
                input("Press Enter to continue...")
                return

        if cost_input.strip():
            try:
                new_cost = float(cost_input)
            except ValueError:
                print("Invalid cost value. Update cancelled.")
                input("Press Enter to continue...")
                return

        if purchase_date_input.strip():
            try:
                new_purchase_date = datetime.strptime(purchase_date_input, '%Y-%m-%d').strftime('%Y-%m-%d')
            except ValueError:
                print("Invalid purchase date. Update cancelled.")
                input("Press Enter to continue...")
                return

        if new_shares <= 0 or new_cost <= 0:
            print("Shares and cost must be positive values.")
            input("Press Enter to continue...")
            return

        cursor.execute(
            "UPDATE portfolio SET shares = ?, cost_per_share = ?, purchase_date = ? WHERE symbol = ?",
            (new_shares, new_cost, new_purchase_date, symbol)
        )
        conn.commit()
        print(f"Updated {symbol} in portfolio.")
        input("Press Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        input("Press Enter to continue...")
    finally:
        conn.close()


def remove_from_portfolio():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    clear_screen()
    print("=== Remove from Portfolio ===")
    symbol = input("Enter stock symbol to remove: ").upper()
    
    if not symbol:
        return

    try:
        cursor.execute("DELETE FROM portfolio WHERE symbol = ?", (symbol,))
        if cursor.rowcount > 0:
            conn.commit()
            print(f"Successfully removed {symbol} from portfolio.")
        else:
            print(f"Stock '{symbol}' not found in portfolio.")
        input("Press Enter to continue...")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        input("Press Enter to continue...")
    finally:
        conn.close()


def display_game_chart(prices, interval_name="Day", width=60, height=15):
    """Display a simple ASCII chart for the trading game without dates."""
    if len(prices) < 2:
        return

    min_price = min(prices)
    max_price = max(prices)
    price_range = max_price - min_price
    if price_range == 0:
        price_range = 1

    # Create grid
    grid = [[' ' for _ in range(width)] for _ in range(height)]

    # Map prices to grid
    num_points = min(len(prices), width)
    for x in range(num_points):
        price = prices[x]
        normalized_price = (price - min_price) / price_range
        y = int(normalized_price * (height - 1))
        row_idx = height - 1 - y
        if 0 <= row_idx < height:
            grid[row_idx][x] = '*'

    # Draw connecting line between points
    for i in range(num_points - 1):
        x1, x2 = i, i + 1
        price1, price2 = prices[x1], prices[x2]
        y1 = int(((price1 - min_price) / price_range) * (height - 1))
        y2 = int(((price2 - min_price) / price_range) * (height - 1))
        row1 = height - 1 - y1
        row2 = height - 1 - y2

        # Simple line drawing
        if abs(row2 - row1) > 1:
            step = 1 if row2 > row1 else -1
            for r in range(row1 + step, row2, step):
                if 0 <= r < height and x1 < width:
                    grid[r][x1] = '|'

    # Print chart
    period_label = "30-period"
    print(f"\n{f'Price Chart ({period_label})':^{width + 12}}")
    print(f"Range: {min_price:.2f} - {max_price:.2f}")
    print("-" * (width + 12))

    for i in range(height):
        y_val = max_price - (i / (height - 1)) * price_range
        row_str = "".join(grid[i])
        print(f"{y_val:8.2f} | {row_str}")

    print(" " * 9 + "-" * width)
    print(" " * 9 + f"{interval_name} 1" + " " * (width - 12) + f"{interval_name} {num_points}")


def generate_random_chart_options(conn, interval='D', num_options=3):
    """Generate random stock chart options for the trading game."""
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT symbol FROM model_data")
    all_symbols = [row[0] for row in cursor.fetchall()]

    options = []
    attempts = 0
    max_attempts = 100

    while len(options) < num_options and attempts < max_attempts:
        attempts += 1
        symbol = random.choice(all_symbols)

        # Get data for this symbol
        cursor.execute("SELECT date, close FROM model_data WHERE symbol = ? ORDER BY date", (symbol,))
        raw_data = cursor.fetchall()
        
        # Resample data if needed
        # We need to convert sqlite.Row to dict for resample_data
        formatted_data = [{'date': row['date'], 'close': row['close']} for row in raw_data]
        data = resample_data(formatted_data, interval)

        if not data or len(data) < 31:
            continue

        # Select a random 30-period window
        max_start_index = len(data) - 31
        start_index = random.randint(0, max_start_index)
        end_index = start_index + 30

        period_data = data[start_index:end_index]
        next_period_data = data[end_index]

        prices = [row['close'] for row in period_data]

        # Check if this exact chart is already in options
        is_duplicate = False
        for opt in options:
            if opt['symbol'] == symbol and opt['prices'] == prices:
                is_duplicate = True
                break

        if not is_duplicate:
            options.append({
                'symbol': symbol,
                'prices': prices,
                'next_price': next_period_data['close'],
                'last_price': prices[-1]
            })

    return options


def display_trading_history(trade_history, virtual_balance):
    """Display trading history for the current session."""
    clear_screen()
    print("=== Trading Game History ===")
    print(f"Current balance: ${virtual_balance:,.2f}\n")

    if not trade_history:
        print("No trades yet.")
        input("Press Enter to continue...")
        return

    header = f"{'#':<4} {'Symbol':<8} {'Int':<5} {'Guess':<6} {'Invested':<12} {'Result':<10} {'P/L':<12} {'Balance':<12}"
    print(header)
    print("-" * len(header))

    for index, trade in enumerate(trade_history, 1):
        pnl = trade['pnl']
        pnl_str = f"{pnl:,.2f}"
        if pnl > 0:
            pnl_str = color_text(pnl_str, '32')
        elif pnl < 0:
            pnl_str = color_text(pnl_str, '31')

        interval_code = trade.get('interval', 'D')
        
        print(
            f"{index:<4} {trade['symbol']:<8} {interval_code:<5} {trade['guess']:<6} "
            f"${trade['investment']:<11,.2f} {trade['result']:<10} {pnl_str:<12} "
            f"${trade['balance']:<11,.2f}"
        )

    input("\nPress Enter to continue...")


def trading_game():
    """Trading game where user guesses price direction."""
    virtual_balance = 10000.0
    trade_history = []
    interval = 'D'  # Default interval

    while True:
        clear_screen()
        
        interval_name = "Daily"
        if interval == 'W':
            interval_name = "Weekly"
        elif interval == 'M':
            interval_name = "Monthly"
            
        print(f"=== Trading Game ({interval_name}) ===")
        print(f"Your virtual balance: ${virtual_balance:,.2f}")
        print("\nLoading chart options...")

        conn = get_db_connection()

        # Generate random chart options based on selected interval
        chart_options = generate_random_chart_options(conn, interval)

        if not chart_options:
            print(f"\nError generating chart options for {interval_name} interval. Trying Daily...")
            interval = 'D'
            chart_options = generate_random_chart_options(conn, 'D')
            if not chart_options:
                print("Error generating chart options. Please try again.")
                input("Press Enter to continue...")
                conn.close()
                continue

        # Display chart options
        clear_screen()
        print(f"=== Trading Game ({interval_name}) ===")
        print(f"Your virtual balance: ${virtual_balance:,.2f}")
        print(f"\nChoose a chart to trade for the NEXT {interval_name.upper().rstrip('LY')}:\n")

        period_unit = "Day"
        if interval == 'W':
            period_unit = "Week"
        elif interval == 'M':
            period_unit = "Month"

        for i, option in enumerate(chart_options, 1):
            print(f"--- Option {i}: {option['symbol']} ---")
            display_game_chart(option['prices'], interval_name=period_unit, width=50, height=12)
            print(f"Current price: ${option['last_price']:.2f}\n")

        print("[1-3] Select Chart  [R]efresh  [H]istory  [I]nterval  [B]ack")
        choice = input("Choice: ").upper()

        if choice == 'B':
            conn.close()
            return
            
        if choice == 'I':
            conn.close()
            print("\nSelect Time Interval:")
            print("1. Daily (Predict next day)")
            print("2. Weekly (Predict next week)")
            print("3. Monthly (Predict next month)")
            int_choice = input("Choice (1-3): ")
            if int_choice == '2':
                interval = 'W'
            elif int_choice == '3':
                interval = 'M'
            else:
                interval = 'D'
            continue

        if choice == 'R':
            conn.close()
            continue

        if choice == 'H':
            conn.close()
            display_trading_history(trade_history, virtual_balance)
            continue

        try:
            chart_index = int(choice) - 1
            if chart_index < 0 or chart_index >= len(chart_options):
                print("Invalid choice.")
                input("Press Enter to continue...")
                conn.close()
                continue
        except ValueError:
            print("Invalid choice.")
            input("Press Enter to continue...")
            conn.close()
            continue

        selected = chart_options[chart_index]
        symbol = selected['symbol']
        prices = selected['prices']
        last_price = selected['last_price']
        next_price = selected['next_price']

        # Ask for direction
        clear_screen()
        print(f"=== Trading Game: {symbol} ({interval_name}) ===")
        print(f"Your virtual balance: ${virtual_balance:,.2f}")
        display_game_chart(prices, interval_name=period_unit)
        print(f"\nCurrent price (end of period): ${last_price:.2f}")
        print(f"\nWill the price go UP or DOWN in the next {period_unit.lower()}?")

        direction = input("Enter [U]P or [D]OWN: ").upper()
        while direction not in ['U', 'D', 'UP', 'DOWN']:
            direction = input("Invalid choice. Enter [U]P or [D]OWN: ").upper()

        if direction in ['U', 'UP']:
            direction = 'UP'
        else:
            direction = 'DOWN'

        # Get investment amount
        print(f"\nHow much do you want to invest? (Available: ${virtual_balance:,.2f})")
        while True:
            try:
                investment_input = input("Investment amount: $").strip()
                investment = float(investment_input)
                if investment <= 0:
                    print("Investment must be positive.")
                    continue
                if investment > virtual_balance:
                    print(f"You cannot invest more than your balance (${virtual_balance:,.2f}).")
                    continue
                break
            except ValueError:
                print("Invalid amount. Please enter a number.")

        # Reveal result
        clear_screen()
        print(f"=== Trading Game Result ({interval_name}) ===")
        print(f"\nSymbol: {symbol}")
        print(f"Your guess: {direction}")
        print(f"Investment: ${investment:,.2f}")
        print(f"\nLast {period_unit.lower()} price: ${last_price:.2f}")
        print(f"Next {period_unit.lower()} price: ${next_price:.2f}")

        actual_direction = 'UP' if next_price > last_price else 'DOWN'
        price_change = abs(next_price - last_price)
        price_change_pct = (price_change / last_price) * 100

        print(f"\nActual direction: {actual_direction}")
        print(f"Price change: ${price_change:.2f} ({price_change_pct:.2f}%)")

        # Calculate result
        result_amount = investment * (price_change_pct / 100)
        if direction == actual_direction:
            # Win
            virtual_balance += result_amount
            result_label = "WIN"
            pnl_amount = result_amount
            print(f"\n🎉 CORRECT! You won ${result_amount:,.2f}!")
            print(f"New balance: ${virtual_balance:,.2f}")
        else:
            # Lose
            virtual_balance -= result_amount
            result_label = "LOSS"
            pnl_amount = -result_amount
            print(f"\n😞 Wrong! You lost ${result_amount:,.2f}.")
            print(f"New balance: ${virtual_balance:,.2f}")

        trade_history.append({
            'symbol': symbol,
            'guess': direction,
            'investment': investment,
            'result': result_label,
            'pnl': pnl_amount,
            'balance': virtual_balance,
            'interval': interval
        })

        if virtual_balance <= 0:
            print("\n💸 You've run out of money! Game over.")
            input("Press Enter to return to the main menu...")
            conn.close()
            return

        print("\n[P]lay again  [H]istory  [I]nterval  [B]ack to menu")
        choice = input("Choice: ").upper()
        
        conn.close()

        if choice == 'H':
            display_trading_history(trade_history, virtual_balance)
            # Re-open connection handled at start of loop
            continue
            
        if choice == 'I':
            print("\nSelect Time Interval:")
            print("1. Daily (Predict next day)")
            print("2. Weekly (Predict next week)")
            print("3. Monthly (Predict next month)")
            int_choice = input("Choice (1-3): ")
            if int_choice == '2':
                interval = 'W'
            elif int_choice == '3':
                interval = 'M'
            else:
                interval = 'D'
            continue

        if choice == 'B':
            return


if __name__ == "__main__":
    conn = get_db_connection()
    init_portfolio_table(conn)
    conn.close()
    main_menu()
