import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Base URL with a placeholder for the changing ID numbers
base_url = "https://www.nccn.org/guidelines/guidelines-detail?category=patients&id={}"


# Counter to track consecutive 404 errors
max_consecutive_errors = 5
consecutive_errors = 0
current_id = 0  # Start from ID 0

def download_pdf(pdf_url, output_directory):
    """Downloads a PDF from a given URL and saves it locally."""
    pdf_name = pdf_url.split("/")[-1]  # Extract filename from URL
    pdf_path = os.path.join(output_directory, pdf_name)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }  # Add User-Agent header

    try:
        print(f"Downloading: {pdf_url}")
        pdf_response = requests.get(pdf_url, headers=headers, stream=True)
        if pdf_response.status_code == 200:
            with open(pdf_path, 'wb') as pdf_file:
                for chunk in pdf_response.iter_content(chunk_size=1024):
                    pdf_file.write(chunk)
            print(f"Saved: {pdf_path}")
        else:
            print(f"Failed to download {pdf_url}: HTTP {pdf_response.status_code}")
    except Exception as e:
        print(f"Error downloading {pdf_url}: {e}")

def scrape_and_download_pdfs(output_directory):
    """Iterates through IDs until encountering max consecutive 404 errors."""
    global consecutive_errors, current_id
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }  # Add User-Agent header

    while consecutive_errors < max_consecutive_errors:
        url = base_url.format(current_id)
        print(f"Checking URL: {url}")

        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 404:
                consecutive_errors += 1
                print(f"Page not found for ID {current_id}, skipping. ({consecutive_errors} consecutive 404s)")
                current_id += 1
                continue
            elif response.status_code != 200:
                print(f"Unexpected error for ID {current_id}: HTTP {response.status_code}")
                consecutive_errors += 1
                current_id += 1
                continue

            consecutive_errors = 0  # Reset 404 counter if a valid page is found

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find PDF links on the page
            pdf_found = False
            for link in soup.find_all('a', href=True):
                href = link['href']
                if href.lower().endswith('.pdf'):
                    pdf_url = urljoin(url, href)
                    download_pdf(pdf_url, output_directory)
                    pdf_found = True

            if not pdf_found:
                print(f"No PDF found on page {current_id}")

        except Exception as e:
            print(f"Error processing ID {current_id}: {e}")

        current_id += 1


if __name__ == "__main__":
    # Output directory to store the downloaded PDFs
    output_directory = "documents"
    os.makedirs(output_directory, exist_ok=True)

    # Run the scraper and downloader
    scrape_and_download_pdfs(output_directory)

    print(f"All available PDFs have been saved to the directory: {output_directory}")

