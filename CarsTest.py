import time
import requests
from bs4 import BeautifulSoup
import gspread
import os
from google.oauth2.service_account import Credentials

def authenticate_google_sheets():
    # Define the scope and credentials
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    
    # Get the service account credentials from environment variables
    credentials_dict = {
        "type": os.environ.get("GOOGLE_SHEETS_TYPE"),
        "project_id": os.environ.get("GOOGLE_SHEETS_PROJECT_ID"),
        "private_key_id": os.environ.get("GOOGLE_SHEETS_PRIVATE_KEY_ID"),
        "private_key": os.environ.get("GOOGLE_SHEETS_PRIVATE_KEY"),
        "client_email": os.environ.get("GOOGLE_SHEETS_CLIENT_EMAIL"),
        "client_id": os.environ.get("GOOGLE_SHEETS_CLIENT_ID"),
        "auth_uri": os.environ.get("GOOGLE_SHEETS_AUTH_URI"),
        "token_uri": os.environ.get("GOOGLE_SHEETS_TOKEN_URI"),
        "auth_provider_x509_cert_url": os.environ.get("GOOGLE_SHEETS_AUTH_PROVIDER_CERT_URL"),
        "client_x509_cert_url": os.environ.get("GOOGLE_SHEETS_CLIENT_CERT_URL")
    }

    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scope)

    # Authorize and get the Google Sheets client
    client = gspread.authorize(credentials)
    return client

def scrape_cars(url, sheet):
    page_number = 1
    processed_links = set()

    while True:
        # Send a GET request to the URL
        response = requests.get(f"{url}&page={page_number}")

        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all car listings on the page
        listings = soup.find_all('div', class_='vehicle-card-main js-gallery-click-card')

        # If no listings are found, exit the loop
        if not listings:
            break

        # Process each listing
        for listing in listings:
            # Extract relevant information from the listing
            title = listing.find('h2', class_='title').text.strip()
            price = listing.find('span', class_='primary-price').text.strip()
            name = listing.find('div', class_='dealer-name').text.strip()

            # Check if the mileage element exists
            mileage_element = listing.find('div', class_='mileage')
            if mileage_element:
                mileage = mileage_element.text.strip()
            else:
                mileage = 'N/A'

            miles_from = listing.find('div', class_='miles-from').text.strip()

            # Extract the link to the vehicle listing page
            link = listing.find('a', class_='vehicle-card-link')['href']
            vehicle_link = f"https://www.cars.com{link}"

            # Check for duplicate link
            if vehicle_link in processed_links:
                continue

            # Extract the vehicle history report links from the vehicle detail page
            try:
                vehicle_response = requests.get(vehicle_link)
                vehicle_soup = BeautifulSoup(vehicle_response.content, 'html.parser')
                external_links = vehicle_soup.find_all('div', class_='vehicle-deeplink')

                history_report = 'N/A'

                for link in external_links:
                    if 'carfax' in link.text.lower() or 'autocheck' in link.text.lower():
                        history_report = f"https://www.cars.com{link.find('a')['href']}"
                        break
            except (TypeError, KeyError):
                history_report = 'N/A'

            # Extract the color information from the vehicle detail page
            try:
                color_element = vehicle_soup.find('dt', string='Exterior color')
                color = color_element.find_next('dd').text.strip()
            except AttributeError:
                color = 'N/A'

            # Extract the interior color information from the vehicle detail page
            try:
                interior_color_element = vehicle_soup.find('dt', string='Interior color')
                interior_color = interior_color_element.find_next('dd').text.strip()
            except AttributeError:
                interior_color = 'N/A'

            # Extract the phone number from the vehicle detail page
            try:
                phone_element = vehicle_soup.find('a', id='mobile-call-button')
                phone = phone_element['href'][4:]if phone_element else 'N/A'  # Extract the phone number from the href attribute
            except AttributeError:
                phone = 'N/A'
            
            # Extract the VIN from the vehicle detail page
            try:
                vin_element = vehicle_soup.find('dt', string='VIN')
                vin = vin_element.find_next('dd').text.strip()
            except AttributeError:
                vin = 'N/A'
            
            # Extract the Stock # from the vehicle detail page
            try:
                stock_element = vehicle_soup.find('dt', string='Stock #')
                stock = stock_element.find_next('dd').text.strip()
            except AttributeError:
                stock = 'N/A'

            # Append the data to the Google Sheet
            row_data = [title, price, name, mileage, miles_from, vehicle_link, history_report, color, interior_color, phone, vin, stock]
            sheet.append_row(row_data)

            # Add the link to the processed links set
            processed_links.add(vehicle_link)

            # Delay between each record
            time.sleep(2)

        # Move to the next page
        page_number += 1

        # Delay the scraping process for a few seconds
        time.sleep(5)

# Authenticate Google Sheets API
client = authenticate_google_sheets()

# Open the Results sheet
results_sheet = client.open('CarSearch').worksheet('results')

# Add headers to the Results sheet if not already present
header_row = results_sheet.row_values(1)
if 'Color' not in header_row:
    results_sheet.update_cell(1, len(header_row) + 1, 'Color')
if 'Interior Color' not in header_row:
    results_sheet.update_cell(1, len(header_row) + 1, 'Interior Color')
if 'Phone' not in header_row:
    results_sheet.update_cell(1, len(header_row) + 1, 'Phone')
if 'VIN' not in header_row:
    results_sheet.update_cell(1, len(header_row) + 1, 'VIN')
if 'Stock #' not in header_row:
    results_sheet.update_cell(1, len(header_row) + 1, 'Stock #')

# Open the Criteria sheet
criteria_sheet = client.open('CarSearch').worksheet('Criteria')

# Verify that the criteria values are present
if criteria_sheet.row_count < 11:
    print("Insufficient criteria values. Please make sure all criteria are provided.")
    exit()

# Extract the criteria values from the sheet
maximum_distance = criteria_sheet.cell(2, 2).value
zip_code = criteria_sheet.cell(3, 2).value
stock_type = criteria_sheet.cell(4, 2).value
makes = criteria_sheet.cell(5, 2).value.split(',')
models = criteria_sheet.cell(6, 2).value.split(',')
minimum_year = criteria_sheet.cell(7, 2).value
maximum_year = criteria_sheet.cell(8, 2).value
minimum_price = criteria_sheet.cell(9, 2).value
maximum_price = criteria_sheet.cell(10, 2).value
maximum_mileage = criteria_sheet.cell(11, 2).value

# Construct the URL with the fetched criteria values
base_url = f"https://www.cars.com/shopping/results/?maximum_distance={maximum_distance}&zip={zip_code}&stock_type={stock_type}&makes%5B%5D={','.join(makes)}&models%5B%5D={','.join(models)}&year_min={minimum_year}&year_max={maximum_year}&list_price_min={minimum_price}&list_price_max={maximum_price}&mileage_max={maximum_mileage}"

# Scrape the search results from multiple pages and store in the Results sheet
scrape_cars(base_url, results_sheet)
