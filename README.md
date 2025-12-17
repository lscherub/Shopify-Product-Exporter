# Shopify Product Exporter

A beginner-friendly Python desktop application to export Shopify products, including Product IDs and Variant IDs to Excel using the GraphQL Admin API.

## Features
- **User-Friendly Interface**: Simple GUI built with Tkinter.
- **GraphQL Integration**: Access the latest Shopify Admin API.
- **Excel Export**: Saves products and variants data into a formatted `.xlsx` file.
- **Filtering**: Filter by Status, Vendor, Date, and Sort Order.
  
<p align="center">
  <img src="https://github.com/user-attachments/assets/020db528-4127-43ae-beb6-53fcfca3ce2c" width="31.5%" alt="Screenshot 1" />
  <img src="https://github.com/user-attachments/assets/2f68d556-0e85-462b-93df-15794d7548bc" width="45%" alt="Screenshot 2" />
</p>


## Prerequisites
- Windows, macOS, or Linux.
- Python 3.10 or higher.
- A Shopify Store with Admin API access.

## Installation

1. **Install Python**: Download and install from [python.org](https://www.python.org/). checking "Add Python to PATH" during installation.
2. **Download Application**: Download this folder to your computer.
3. **Open Terminal**: 
   - On Windows: Press `Win + R`, type `cmd`, and press Enter. Navigate to this folder (e.g., `cd path\to\shopifyapp`).
4. **Install Dependencies**:
   Run the following command:
   ```bash
   pip install -r requirements.txt
   ```

## How to Get Shopify Credentials
1. Go to your Shopify Admin -> **Settings** -> **Apps and sales channels**.
2. Click **Develop apps** -> **Create an app**.
3. Name it "Product Exporter" and create it.
4. Click **Configure Admin API scopes**.
5. Enable `read_products` scope.
6. Click **Save** and then **Install app**.
7. Reveal and copy the **Admin API access token**. 
   (Note: Use the token starting with `shpat_...`).

## Usage
1. Run the application:
   ```bash
   python main.py
   ```
2. **Step 1: Authentication**
   - Enter your store domain (e.g., `mystore.myshopify.com`).
   - Paste your Access Token.
   - Click "Connect & Validate".
3. **Step 2: Filters (Optional)**
   - Select status, vendor, or date range if needed.
   - Choose sorting preference.
4. **Step 3: Export**
   - Click "Fetch & Export to Excel".
   - Choose where to save the file.
   - Watch the log window for progress.

## Troubleshooting
- **401 Authentication Error**: Check if your token is correct and has `read_products` permission.
- **Module not found**: Ensure you ran `pip install -r requirements.txt`.

<hr>

**SPECIAL THANKS TO GOOGLE ANTIGRAVITY**


