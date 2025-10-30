import os
import sys
import argparse
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# --- CONFIGURATION ---
SCOPES = ['https://www.googleapis.com/auth/drive']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'

# --- FUNCTIONS ---

def print_setup_instructions():
    """Prints detailed instructions for setting up Google Drive API access with OAuth 2.0."""
    instructions = """
    --- Google Drive API Setup Instructions (OAuth 2.0) ---

    To use this script, you need to enable the Google Drive API and create an OAuth 2.0 Client ID.

    1. **Enable the Google Drive API:**
       - Go to the Google Cloud Console: https://console.cloud.google.com/
       - Create a new project or select an existing one.
       - In the navigation menu, go to "APIs & Services" > "Library".
       - Search for "Google Drive API" and click "Enable".

    2. **Configure the OAuth Consent Screen:**
       - In the navigation menu, go to "APIs & Services" > "OAuth consent screen".
       - Choose "External" and click "Create".
       - Fill in the required fields (App name, User support email, Developer contact information).
       - Click "SAVE AND CONTINUE" through the Scopes and Test users sections.
       - On the Summary page, click "BACK TO DASHBOARD" and then "PUBLISH APP" to make it available.

    3. **Create an OAuth 2.0 Client ID:**
       - In the navigation menu, go to "APIs & Services" > "Credentials".
       - Click "+ CREATE CREDENTIALS" > "OAuth client ID".
       - For "Application type", select "Desktop app".
       - Give the client ID a name (e.g., "gdrive-uploader-desktop").
       - Click "CREATE".
       - A window will appear with your client ID and secret. Click "DOWNLOAD JSON".
       - **Rename the downloaded file to `credentials.json` and place it in the same directory as this script.**

    4. **First Run and Authentication:**
       - The first time you run the script, it will open a web browser and ask you to log in to your Google account and grant permission to the script.
       - After you grant permission, a `token.json` file will be created in the same directory. This file stores your authentication tokens, so you won't have to log in every time.

    **IMPORTANT:** Do not share your `credentials.json` or `token.json` files with anyone.
    """
    print(instructions)

def get_drive_service():
    """Authenticates and returns a Google Drive service object using OAuth 2.0."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"Error: Credentials file '{CREDENTIALS_FILE}' not found.")
                print_setup_instructions()
                return None
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"Error creating Drive service: {e}")
        return None

def get_or_create_folder(service, folder_name):
    """Searches for a folder by name and creates it if it doesn't exist. Returns the folder ID."""
    try:
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        items = results.get('files', [])

        if items:
            folder_id = items[0]['id']
            print(f"Found folder '{folder_name}' with ID: {folder_id}")
            return folder_id
        else:
            print(f"Folder '{folder_name}' not found, creating it...")
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = service.files().create(body=file_metadata, fields='id').execute()
            folder_id = folder.get('id')
            print(f"Created folder '{folder_name}' with ID: {folder_id}")
            return folder_id
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None

def upload_file(service, file_path, folder_id):
    """Uploads a single file to the specified Google Drive folder."""
    if not os.path.exists(file_path):
        print(f"Error: File not found at '{file_path}'")
        return False

    try:
        file_name = os.path.basename(file_path)
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        media = MediaFileUpload(file_path)
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"Successfully uploaded '{file_name}' with ID: {file.get('id')}")
        return True
    except HttpError as error:
        print(f"An error occurred while uploading '{file_path}': {error}")
        return False

def main():
    """Main function to parse arguments and upload files."""
    if '--setup' in sys.argv:
        print_setup_instructions()
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="Upload one or more files to a Google Drive folder.",
        epilog="""
Example usage:
  python gdrive_uploader.py "My Drive Folder" /path/to/file1.txt
  python gdrive_uploader.py "My Drive Folder" /path/to/directory/
"""
    )
    parser.add_argument("folder_name", help="The name of the Google Drive folder to upload files to.")
    parser.add_argument("file_paths", nargs='+', help="One or more paths to files or a directory to upload.")
    parser.add_argument("--setup", action="store_true", help="Print detailed setup instructions for Google Drive API access.")

    args = parser.parse_args()

    service = get_drive_service()
    if not service:
        sys.exit(1)

    folder_id = get_or_create_folder(service, args.folder_name)
    if not folder_id:
        sys.exit(1)

    success_count = 0
    total_count = 0

    for path in args.file_paths:
        if os.path.isdir(path):
            for dirpath, _, filenames in os.walk(path):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    total_count += 1
                    if upload_file(service, file_path, folder_id):
                        success_count += 1
        elif os.path.isfile(path):
            total_count += 1
            if upload_file(service, path, folder_id):
                success_count += 1
        else:
            print(f"Error: Path '{path}' is not a valid file or directory.")
            total_count += 1

    print(f"\n--- Upload Complete ---")
    print(f"{success_count} of {total_count} files uploaded successfully.")

    if success_count == total_count:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()