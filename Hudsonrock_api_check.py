import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import re
import configparser
import sys
from datetime import datetime, timedelta
import signal
import threading
import logging

# --------------------------
# Logging Configuration
# --------------------------
# This will write logs to 'script.log' at INFO level and above.
logging.basicConfig(
    filename='script.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --------------------------
# Flag to handle shutdown
# --------------------------
shutdown_flag = threading.Event()

# --------------------------
# Signal handler for interruption
# --------------------------
def signal_handler(signum, frame):
    """Signal handler for graceful shutdown."""
    logging.info("Interruption detected (SIGINT). Shutting down gracefully...")
    shutdown_flag.set()

# Register the signal handler for Ctrl+C
signal.signal(signal.SIGINT, signal_handler)

# --------------------------
# Domain cleaning
# --------------------------
def clean_domain(domain):
    """Cleans the domain by removing 'www.' and trailing dot."""
    if domain.startswith('www.'):
        domain = domain[4:]
    if domain.endswith('.'):
        domain = domain[:-1]
    return domain

# --------------------------
# Domain validation (updated regex)
# --------------------------
def is_valid_domain(domain):
    """
    Checks if the domain format is valid.
    Updated to allow longer TLDs (2–15 characters).
    """
    pattern = re.compile(
        r'^(?!:\/\/)([a-zA-Z0-9-_]+\.)+[a-zA-Z]{2,15}$',
        re.IGNORECASE
    )
    return re.match(pattern, domain) is not None

# --------------------------
# Date handling
# --------------------------
def get_past_date(months):
    """Returns the date that was a certain number of months ago."""
    return datetime.now() - timedelta(days=30 * months)

# --------------------------
# Load configuration from config.ini
# --------------------------
config = configparser.ConfigParser()
config_file = 'config.ini'
try:
    config.read(config_file)
except Exception as e:
    logging.error(f"Failed to read config file '{config_file}': {e}")
    sys.exit(1)

# Dates for the last month
one_month_ago = get_past_date(1).strftime('%Y-%m-%d')
current_date = datetime.now().strftime('%Y-%m-%d')

# --------------------------
# Load domains from file
# --------------------------
domains_file = 'domains.json'
try:
    with open(domains_file, 'r', encoding='utf-8') as f:
        original_domains = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    logging.error(f"Error loading domains file '{domains_file}': {e}")
    sys.exit(1)

# Clean and filter domains
cleaned_domains = []
for domain in original_domains:
    if isinstance(domain, str):
        cleaned_domains.append(clean_domain(domain))
    else:
        logging.warning(f"Non-string domain skipped: {domain}")

input_domains = set(filter(is_valid_domain, cleaned_domains))
logging.info(f"Total valid domains: {len(input_domains)}")

# --------------------------
# Use API configuration from config.ini
# --------------------------
try:
    api_url = config['API']['api_url_template'].format(one_month_ago, current_date)
    headers = {
        'api-key': config['API']['api_key'],
        'Content-Type': config['API']['content_type']
    }
    params = {
        'type': 'employees',
        'third_party_domains': 'true'
    }
    # You can adjust this timeout as needed
    REQUEST_TIMEOUT = 10
except KeyError as e:
    logging.error(f"Error in configuration file: missing key {e}")
    sys.exit(1)

# --------------------------
# Fetch data function
# --------------------------
def fetch_data(batch, index, api_url, headers, params, pbar):
    """Process a batch of domains with interruption handling."""
    if shutdown_flag.is_set():
        return None

    for attempt in range(5):
        if shutdown_flag.is_set():
            return None

        try:
            response = requests.post(
                api_url,
                headers=headers,
                params=params,
                json={'domains': batch},
                timeout=REQUEST_TIMEOUT  # <--- Timeout added here
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logging.warning(
                f"[Batch {index+1}] Attempt {attempt+1} failed: {e}. "
                "Will retry with exponential backoff."
            )
            # If this was the last attempt, log error and return None
            if attempt == 4:
                logging.error(
                    f"[ERROR] [Batch {index+1}] All 5 attempts failed. "
                    f"Error: {e}"
                )
                return None
            time.sleep((2 ** attempt) * 2)

# --------------------------
# Main function
# --------------------------
def main():
    # Split domains into batches of 50
    batches = [list(input_domains)[i:i + 50] for i in range(0, len(input_domains), 50)]
    total_batches = len(batches)

    results = set()
    logging.info(f"Starting processing with {total_batches} batch(es).")

    with tqdm(total=total_batches, desc="Processing batches", unit="batch") as pbar:
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(fetch_data, batch, i, api_url, headers, params, pbar): i
                for i, batch in enumerate(batches)
            }

            try:
                for future in as_completed(futures):
                    if shutdown_flag.is_set():
                        break
                    data = future.result()
                    if data:
                        for item in data:
                            # Each item can contain 'employeeAt' or 'clientAt'
                            if 'employeeAt' in item and item['employeeAt']:
                                results.update(
                                    d for d in item['employeeAt'] if d in input_domains
                                )
                            elif 'clientAt' in item and item['clientAt']:
                                results.update(
                                    d for d in item['clientAt'] if d in input_domains
                                )
                    pbar.update(1)

            except KeyboardInterrupt:
                logging.info("KeyboardInterrupt detected. Stopping all threads...")

            finally:
                executor.shutdown(wait=False)
                logging.info("All threads have been signaled to stop.")

    # Save results to a file results.txt
    results_file = 'results.txt'
    try:
        with open(results_file, 'w', encoding='utf-8') as f:
            for domain in results:
                f.write(domain + '\n')
        logging.info(f"Results successfully saved to '{results_file}'.")
    except Exception as e:
        logging.error(f"Failed to save results to '{results_file}': {e}")

# --------------------------
# Entry point
# --------------------------
if __name__ == "__main__":
    main()
