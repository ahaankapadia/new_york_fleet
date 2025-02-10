import requests
import pandas as pd

# List of VIN numbers to fetch details for
df = pd.read_csv('Data/auction_data.csv')
vin_numbers = df['VIN'].tolist()

def fetch_vin_details(vin):
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVin/{vin}?format=json"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        decoded_vin = {item['Variable']: item['Value'] for item in data['Results'] if item['Value']}
        decoded_vin['VIN'] = vin  # Add the VIN number as a key-value pair
        return decoded_vin
    else:
        return {"VIN": vin, "Error": "Unable to fetch data"}

# Fetch VIN details and store in a list
vin_data = [fetch_vin_details(vin) for vin in vin_numbers]

# Create a DataFrame to view results
df = pd.DataFrame(vin_data)

# Move the 'VIN' column (or VEHICLE_ID) to the front
columns = ['VIN'] + [col for col in df.columns if col != 'VIN']
df = df[columns]  # Rearrange columns

# Display DataFrame
print(df)

# Save the results to an Excel or CSV file
df.to_csv("Data/VIN_Details.csv", index=False)
