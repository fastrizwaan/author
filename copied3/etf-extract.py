import csv
import re

# File path to the CSV
file_path = './MW-ETF-24-Oct-2024.csv'

# Step 1: Read the CSV file and clean column names with BOM handling
with open(file_path, 'r', encoding='utf-8-sig') as file:
    reader = csv.DictReader(file)
    data = [row for row in reader]

# Debugging step to inspect the column names
if data:
    print(f"Column names in the CSV: {list(data[0].keys())}")
else:
    print("The CSV file is empty or not read properly.")

# Step 2: Clean the column names by stripping leading/trailing spaces and handling NoneType
for i, row in enumerate(data):
    data[i] = {key.strip() if key is not None else key: value for key, value in row.items()}

# Step 3: Convert 'Underlying Asset' to Title Case immediately after loading
for row in data:
    row['UNDERLYING ASSET'] = row['UNDERLYING ASSET'].strip().title()

# Step 4: Initial replacements in 'Underlying Asset'

# Replace 'ETF', 'TRI', and 'Total Return Index' at the end with 'Index'
for row in data:
    asset = row['UNDERLYING ASSET'].strip()
    # Insert a space between an alphabet and number (e.g., 'midsmall400' -> 'midsmall 400')
    asset = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', asset) 
    if "Cpse" in asset:
        asset = asset.replace("Cpse", "Nifty Pse")
    if asset.endswith('Etf'):
        asset = asset[:-3] + 'Index'
    elif asset.endswith('Tri'):
        asset = asset[:-3] + 'Index'
    elif "Total Return Index" in asset:
        asset = asset.replace("Total Return Index", "Index")
    asset = asset.strip()
    # Remove 'Index' from the end if it's the last word
    if asset.endswith('Index'):
        asset = asset[:-5].strip()  # Removes the trailing 'Index' and extra spaces
    asset = asset.strip()
    if asset.endswith('Index-'):
        asset = asset[:-6].strip()  # Removes the trailing 'Index' and extra spaces

    row['UNDERLYING ASSET'] = asset

# Use regex to replace the prefix before "Nifty" with "Nifty", case-insensitive,
# and ensure there is a space after "Nifty" if followed by other characters
def replace_nifty(asset):
    return re.sub(r'^.*?\bNifty\b', 'Nifty', re.sub(r'(?i)(Nifty)(\S)', r'Nifty \2', asset), flags=re.IGNORECASE)

# Apply the replacement to 'UNDERLYING ASSET'
for row in data:
    row['UNDERLYING ASSET'] = replace_nifty(row['UNDERLYING ASSET'].strip())

# Use regex to remove text before "S&P", case-insensitive
def replace_s_and_p(asset):
    return re.sub(r'^.*?\bS&P\b', 'S&P', asset, flags=re.IGNORECASE)

# Apply the replacement to 'UNDERLYING ASSET' for "S&P"
for row in data:
    row['UNDERLYING ASSET'] = replace_s_and_p(row['UNDERLYING ASSET'].strip())

# Step 5: Convert 'Volume' and 'Price' columns to numeric by removing commas and handling errors
def clean_numeric(value):
    try:
        return float(value.replace(',', ''))
    except (ValueError, AttributeError):
        return None

# Track the volumes for debugging
volumes = []

# Use the actual column names for 'Volume' and 'Price' once identified
for row in data:
    row['Volume'] = clean_numeric(row.get('VOLUME', ''))  # Adjust 'VOLUME' if necessary after inspecting the column names
    row['Price'] = clean_numeric(row.get('LTP', ''))      # Adjust 'LTP' if necessary after inspecting the column names
    volumes.append(row['Volume'])

# Debugging step: print some of the volumes for inspection
print(f"Sample of Volume values: {volumes[:20]}")  # Show the first 20 volume values

# Step 6: Filter rows where volume is greater than 100,000
filtered_data = [row for row in data if row['Volume'] and row['Volume'] > 100000]
print(f"Rows after filtering by volume: {len(filtered_data)}")

# Step 7: Remove rows where 'Underlying Asset' contains unwanted keywords
unwanted_keywords = ['LIQUID', 'GILT', 'Government', 'G-Sec', 'Rate', 'SDL', 'Hang Seng']

def contains_unwanted_keywords(asset):
    return any(keyword.lower() in asset.lower() for keyword in unwanted_keywords)

filtered_data = [row for row in filtered_data if not contains_unwanted_keywords(row['UNDERLYING ASSET'])]
print(f"Rows after removing unwanted keywords: {len(filtered_data)}")

# Step 7.1: Remove rows with specific symbols (case insensitive)
symbols_to_remove = ['GROWWGOLD', 'HNGSNGBEES', 'MAHKTECH']

filtered_data = [row for row in filtered_data if row['SYMBOL'].upper() not in symbols_to_remove]
print(f"Rows after removing specific symbols: {len(filtered_data)}")

# Step 8: Remove rows containing "silver" or "gold" except for symbols "Silverbees" and "Goldbees"
filtered_data = [row for row in filtered_data if not (('silver' in row['UNDERLYING ASSET'].lower() or 'gold' in row['UNDERLYING ASSET'].lower()) 
                     and row['SYMBOL'].lower() not in ['Silverbees', 'Goldbees'])]
print(f"Rows after removing 'silver' and 'gold' rows: {len(filtered_data)}")

# Step 9: Select the row with the maximum volume for each unique 'Underlying Asset'
max_volume_per_asset = {}
for row in filtered_data:
    asset = row['UNDERLYING ASSET']
    volume = row['Volume']
    if asset not in max_volume_per_asset or volume > max_volume_per_asset[asset]['Volume']:
        max_volume_per_asset[asset] = row

# Convert the max volume dictionary back to a list of rows
unique_filtered_data = list(max_volume_per_asset.values())
print(f"Rows after selecting max volume for each asset: {len(unique_filtered_data)}")

# Step 10: Sort by 'Underlying Asset' before writing to the file
sorted_data = sorted(unique_filtered_data, key=lambda x: x['UNDERLYING ASSET'])
print(f"Rows after sorting by 'Underlying Asset': {len(sorted_data)}")

# Step 11: Save the final sorted data to a new CSV file
if sorted_data:
    output_file = 'filtered_sorted_by_underlying_etf_data.csv'
    with open(output_file, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=sorted_data[0].keys())
        writer.writeheader()
        writer.writerows(sorted_data)
    print(f"Data has been filtered, cleaned, and saved to '{output_file}'.")
else:
    print("No data to write. Please check your filters and input.")

