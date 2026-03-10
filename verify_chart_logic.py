from datetime import datetime, timedelta
import os

def resample_data(data, interval):
    if not data or interval == 'D':
        return data

    resampled = []
    grouped_data = {}
    
    for row in data:
        date_str = row['date']
        price = row['close']
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            continue

        if interval == 'W':
            year, week, _ = date_obj.isocalendar()
            period_key = f"{year}-{week:02d}"
        elif interval == 'M':
            period_key = date_obj.strftime('%Y-%m')
        else:
            period_key = date_str

        if period_key not in grouped_data:
            grouped_data[period_key] = []
        
        grouped_data[period_key].append({'date': date_str, 'close': price})

    for key in sorted(grouped_data.keys()):
        period_items = grouped_data[key]
        last_item = period_items[-1]
        resampled.append(last_item)

    return resampled

# Generate 5 years of daily data
data = []
start_date = datetime(2020, 1, 1)
for i in range(365 * 5):
    d = start_date + timedelta(days=i)
    data.append({'date': d.strftime('%Y-%m-%d'), 'close': 100 + i})

print(f"Total daily points: {len(data)}")

# Test Monthly
monthly = resample_data(data, 'M')
print(f"Total monthly points: {len(monthly)}")
# Expected: ~60 months

# Test Slicing logic
width = 50
if len(monthly) > width:
    sliced = monthly[-width:]
else:
    sliced = monthly

print(f"Sliced monthly points (width={width}): {len(sliced)}")
print(f"First visible date: {sliced[0]['date']}")
print(f"Last visible date: {sliced[-1]['date']}")

# Test Weekly
weekly = resample_data(data, 'W')
print(f"Total weekly points: {len(weekly)}")
# Expected: ~260 weeks

if len(weekly) > width:
    sliced_w = weekly[-width:]
else:
    sliced_w = weekly

print(f"Sliced weekly points (width={width}): {len(sliced_w)}")
