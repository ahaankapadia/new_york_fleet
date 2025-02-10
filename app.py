import subprocess
from time import sleep

def main():
    print("Running app.py to scrape auction PDFs and generate auction_data.csv...")
    # Run the existing PDF scraping and data collection logic
    subprocess.run(["python", "pdftocsv.py"])  # Step 1: Run pdftocsv.py
    #sleep(10)
    print("\nAuction data collection complete. Now running VIN decoding (vin.py)...")
    # Run the VIN decoding logic
    subprocess.run(["python", "vin.py"])  # Step 2: Run vin.py

    print("\nVIN decoding complete. Process finished.")

if __name__ == "__main__":
    main()
