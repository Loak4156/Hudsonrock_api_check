
# Domain API Checker

This script processes a list of domains and checks them via a remote API for matches (e.g., employee or client presence). It supports multithreading, rate-limiting retries, graceful shutdown, and logs all activity to a file.

---

## ✨ Features

- Reads domains from a `domains.json` file
- Cleans and validates domain names (removes `www.`, trailing dots, and invalid formats)
- Multithreaded (processes domains in batches of 50 using up to 4 threads)
- Graceful shutdown via `Ctrl+C` (SIGINT) with signal handling
- Retry logic with exponential backoff (up to 5 attempts per batch)
- Logs output to `script.log`
- Results saved to `results.txt`

---

## 📁 File Structure

```
domain-checker/
├── name_script.py        # Main script
├── config.ini            # API URL and headers
├── domains.json          # Input domains file (array of strings)
├── results.txt           # Output file (written only with valid matches)
├── script.log            # Log file (auto-generated)
├── requirements.txt      # Python dependencies
├── README.md             # Project documentation
```

---

## 🔧 Configuration

Create a `config.ini` file in the same folder:

```ini
[API]
api_url_template = https://cavalier.hudsonrock.com/api/json/v2/search-by-domain?compromised_since={}&compromised_until={}  # URL with two placeholders for dates
api_key = YOUR_API_KEY
content_type = application/json
```

- The script will automatically replace `{}` with dates: one month ago and today.
- You can configure additional parameters in the `params` dictionary in the code.

---

## 📦 Dependencies

Install the required packages:

```bash
pip install -r requirements.txt
```

`requirements.txt`:
```
requests
tqdm
```

---

## 🚀 Usage

Run the script:
```bash
python3 name_script.py
```

- The script will read and clean the domains from `domains.json`
- Submit requests to the specified API in batches
- Save results to `results.txt` (only matched domains)
- Write logs to `script.log`

You can safely interrupt the process with `Ctrl+C`, and it will shutdown cleanly.

---

## 📌 Notes

- Each batch processes up to 50 domains
- If a domain returns in either `employeeAt` or `clientAt`, it's saved
- The script uses a fixed thread pool (`max_workers = 4`) for parallel processing

---
