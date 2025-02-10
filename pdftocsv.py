import requests
from bs4 import BeautifulSoup
import pdfplumber
import re
import csv
import os
from datetime import datetime
import io


#Endpoint to Auction Website
BASE_URL = "https://www.nyc.gov"
AUCTION_PAGE_URL = "https://www.nyc.gov/site/finance/vehicles/auctions.page"

# Custom headers to mimic a standard browser request
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/108.0.0.0 Safari/537.36"
    )
}

def get_pdf_links():
    """
    Fetch the NYC auctions page and return a list of tuples:
    [(pdf_url, link_text), ...] for each PDF link found.
    """
    print(f"Fetching main auction page: {AUCTION_PAGE_URL}")
    response = requests.get(AUCTION_PAGE_URL, headers=HEADERS)
    if not response.ok:
        print(f"Failed to fetch {AUCTION_PAGE_URL}. Status code: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    pdf_links = []
    # Naive approach: find all <a> tags whose 'href' contains '.pdf'
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        link_text = a_tag.get_text(strip=True)
        if ".pdf" in href.lower():
            # Some PDF links might be relative, so we join with BASE_URL if needed
            if href.lower().startswith("http"):
                pdf_url = href
            else:
                pdf_url = BASE_URL + href
            pdf_links.append((pdf_url, link_text))

    print(f"Found {len(pdf_links)} PDF link(s).")
    return pdf_links

def parse_auction_pdf(pdf_bytes):
    """
    Given the PDF bytes, extract text using pdfplumber,
    then parse out the needed info.
    """
    results = {
        "auction_date": None,
        "location": None,
        "auctioneer": None,
        "vehicles": []
    }

    try:
        # Wrap bytes in BytesIO so pdfplumber can .seek() on it
        pdf_file = io.BytesIO(pdf_bytes)

        with pdfplumber.open(pdf_file) as pdf:
            full_text = ""
            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                if not page_text.strip():
                    print(f"Warning: No text extracted from page {page_num}. (Might be scanned?)")
                full_text += page_text + "\n"

        # If there's no text at all, return None
        if not full_text.strip():
            print("No textual content found in PDF (it may be a scanned PDF).")
            return None

        # --- 1) Parse Auction Info (date, location, auctioneer) ---
        # Demo pattern for date (over-simplified).
        date_match = re.search(
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}",
            full_text, 
            re.IGNORECASE
        )
        if date_match:
            results["auction_date"] = date_match.group(0).strip()

        # Auctioneer pattern example: "by XXX, Auctioneer"
        auc_match = re.search(r"by\s+([A-Za-z\s\.]+),\s*Auctioneer", full_text, re.IGNORECASE)
        if auc_match:
            results["auctioneer"] = auc_match.group(1).strip()

        # Location pattern example: "morning at <some text>"
        loc_match = re.search(r"morning at (.*)", full_text, re.IGNORECASE)
        if loc_match:
            line_fragment = loc_match.group(1).split("\n")[0]
            results["location"] = line_fragment.strip()

        # --- 2) Parse Vehicles Table ---
        lines = full_text.splitlines()
        table_started = False
        table_lines = []

        for ln in lines:
            if re.search(r"#\s*YEAR\s*MAKE", ln, re.IGNORECASE):
                # found the header row, start collecting
                table_started = True
                continue
            if table_started:
                # If we reach an empty line or something that indicates table is over, 
                # you might need extra logic. But let's just collect non-empty lines for now.
                if ln.strip() == "":
                    continue
                table_lines.append(ln)

        # Merge lines where lienholder data might wrap
        merged_table_lines = []
        current_line = ""
        for ln in table_lines:
            # If the line starts with a digit (#), assume new row
            if re.match(r"^\d+\s", ln):
                if current_line.strip():
                    merged_table_lines.append(current_line)
                current_line = ln
            else:
                current_line += " " + ln
        if current_line.strip():
            merged_table_lines.append(current_line)

        # Regex for each row (very naive). Adjust as needed.
        row_pattern = re.compile(
            r"^(\d+)\s+"                # item number
            r"(\d{4})\s+"               # year
            r"([A-Za-z0-9\-/]+)\s+"     # make (Naive; real PDFs might be more complex)
            r"([A-Za-z0-9]+)\s+"        # plate
            r"([A-Za-z]{2,3})\s+"       # state
            r"([A-Za-z0-9]+)\s+"        # vehicle_id
            r"(.*)$"                    # lienholder
        )

        for row_text in merged_table_lines:
            match = row_pattern.match(row_text.strip())
            if match:
                vehicle_data = {
                    "#": match.group(1).strip(),
                    "YEAR": match.group(2).strip(),
                    "MAKE": match.group(3).strip(),
                    "PLATE#": match.group(4).strip(),
                    "ST": match.group(5).strip(),
                    "VEHICLE_ID": match.group(6).strip(),
                    "LIENHOLDER": match.group(7).strip()
                }
                results["vehicles"].append(vehicle_data)

        return results

    except Exception as e:
        print(f"Error parsing PDF: {e}")
        return None

def main():
    print("Starting PDF scraping...")
    pdf_links = get_pdf_links()
    if not pdf_links:
        print("No PDF links found. Exiting.")
        return

    # CSV files to store data + log
    data_csv_file = "Data/auction_data.csv"
    log_csv_file = "Data/auction_log.csv"

    # Write headers for the data CSV if it doesn't exist
    if not os.path.exists(data_csv_file):
        with open(data_csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "auction_date",
                "auctioneer",
                "location",
                "pdf_filename",  # <-- new column for PDF file name
                "#",
                "YEAR",
                "MAKE",
                "PLATE#",
                "ST",
                "VIN",
                "LIENHOLDER"
            ])

    # Write headers for the log CSV if it doesn't exist
    if not os.path.exists(log_csv_file):
        with open(log_csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
                "pdf_url",
                "pdf_filename",  # <-- new column for PDF file name
                "link_text",
                "status",
                "rows_extracted"
            ])

    # Process each PDF link
    for pdf_url, link_text in pdf_links:
        print(f"\nProcessing PDF: {pdf_url}")
        # Extract just the filename from the URL
        # e.g. "auction-010325-brooklyn.pdf"
        pdf_filename = os.path.basename(pdf_url)

        try:
            # Attempt to download the PDF
            pdf_response = requests.get(pdf_url, headers=HEADERS, stream=True)
            if pdf_response.ok:
                # Check content type to ensure it's PDF
                content_type = pdf_response.headers.get('Content-Type', '').lower()
                if "pdf" not in content_type:
                    # Not actually a PDF
                    print(f"Warning: Content-Type is '{content_type}', not a PDF. Skipping.")
                    status = "NOT_A_PDF"
                    rows_extracted = 0
                else:
                    # Parse PDF
                    results = parse_auction_pdf(pdf_response.content)
                    if results:
                        vehicles = results["vehicles"]
                        rows_extracted = len(vehicles)

                        # Write vehicle rows to data CSV
                        with open(data_csv_file, "a", newline="", encoding="utf-8") as f_data:
                            writer_data = csv.writer(f_data)
                            for v in vehicles:
                                writer_data.writerow([
                                    results["auction_date"] or "",
                                    results["auctioneer"] or "",
                                    results["location"] or "",
                                    pdf_filename,           # Write the PDF file name here
                                    v.get("#", ""),
                                    v.get("YEAR", ""),
                                    v.get("MAKE", ""),
                                    v.get("PLATE#", ""),
                                    v.get("ST", ""),
                                    v.get("VEHICLE_ID", ""),
                                    v.get("LIENHOLDER", ""),
                                ])

                        if rows_extracted > 0:
                            status = "SUCCESS"
                        else:
                            status = "PARSE_FAILED"
                    else:
                        status = "PARSE_FAILED"
                        rows_extracted = 0
            else:
                print(f"Failed to download PDF. Status code: {pdf_response.status_code}")
                status = "DOWNLOAD_FAILED"
                rows_extracted = 0

            # Log the result
            with open(log_csv_file, "a", newline="", encoding="utf-8") as f_log:
                writer_log = csv.writer(f_log)
                writer_log.writerow([
                    datetime.now().isoformat(),
                    pdf_url,
                    pdf_filename,  # <-- log the PDF file name here
                    link_text,
                    status,
                    rows_extracted
                ])

        except Exception as e:
            print(f"Error processing {pdf_url}: {e}")
            # Log the exception
            with open(log_csv_file, "a", newline="", encoding="utf-8") as f_log:
                writer_log = csv.writer(f_log)
                writer_log.writerow([
                    datetime.now().isoformat(),
                    pdf_url,
                    pdf_filename,
                    link_text,
                    f"ERROR_{str(e)}",
                    0
                ])

if __name__ == "__main__":
    main()
