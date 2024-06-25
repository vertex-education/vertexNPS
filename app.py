import os
import getpass
from datetime import datetime
from flask import Flask, jsonify, redirect, render_template, request, url_for
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
import json
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
import uuid
import pandas as pd

app = Flask(__name__)

# Retrieve the connection string from environment variable
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

# Initialize Azure Blob Service Client
blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
container_name = "surveydata"
container_client = blob_service_client.get_container_client(container_name)

# Load the CSV file
def load_username_mapping():
    csv_path = os.path.join(os.path.dirname(__file__), 'data', 'NPS+Survey+Data.csv')
    df = pd.read_csv(csv_path)
    return df.set_index('Computer Name')['Last Logon User'].to_dict()

username_mapping = load_username_mapping()

@app.route('/')
def index():
    # Get the username from the request parameter
    machine_name = request.args.get('username', default='Guest') 
     # Check if the machine name starts with 'VTX-' and map to actual username if true
    if machine_name.startswith('VTX-'):
        username = username_mapping.get(machine_name, 'Guest')
    else:
        username = machine_name
    question = "How likely are you to recommend Vertex Education to a friend?"
    return render_template('index.html', question=question, username=username)



@app.route('/initialize_default_data', methods=['POST'])
def initialize_default_data():
    # Get the username from the request parameter
    username = request.json.get('username')     

    default_survey_data = {
        "id": str(uuid.uuid4()),  # Generate a unique ID
        "rating": "",
        "closedWithoutResponse": True,
        "username": username,
        "timestamp": str(datetime.now()),
    }
    
    # Read existing data from blob
    existing_data = read_from_blob()
    
    # If existing_data is not a list, initialize it as an empty list
    if not isinstance(existing_data, list):
        existing_data = []
    
    # Append the new survey data to existing data
    existing_data.append(default_survey_data)
    
    # Upload the updated data back to blob
    save_to_blob(existing_data)
    
    print("Default data initialized successfully")
    return jsonify({'message': 'Default data initialized successfully'}), 200



@app.route('/submit_rating', methods=['POST'])
def submit_rating():
    # Get the username from the request parameter
    username = request.json.get('username')     
    selected_rating = request.json.get('rating')
    submit_survey_data = {
        "id": str(uuid.uuid4()),  # Generate a unique ID
        "rating": selected_rating,
        "closedWithoutResponse": False,
        "username": username,
        "timestamp": str(datetime.now()),
    }
    overwrite_last_blob_entry(submit_survey_data)
    return redirect(url_for('thankyou'))

def save_to_blob(data):
    blob_client = container_client.get_blob_client("survey_data.json")
    blob_client.upload_blob(json.dumps(data), overwrite=True)

def read_from_blob():
    try:
        blob_client = container_client.get_blob_client("survey_data.json")
        data = blob_client.download_blob()
        return json.loads(data.readall())
    except ResourceNotFoundError:
        print("Blob 'survey_data.json' not found. Creating...")
        # Create the blob with an empty list as initial data
        blob_client.upload_blob("[]")
        return []

def overwrite_last_blob_entry(updated_data):
    existing_data = read_from_blob()
    
    # If existing_data is not in the expected format, handle it
    if not isinstance(existing_data, list):
        print("Error: Existing data is not in expected format")
        return
    
    # Find the JSON object with the highest timestamp
    max_timestamp_obj = max(existing_data, key=lambda x: x.get('timestamp', ''))
    
    # Update the JSON object with the highest timestamp with the updated_data
    if max_timestamp_obj:
        max_timestamp_obj.update(updated_data)
    else:
        # If no JSON object exists, append the updated_data
        existing_data.append(updated_data)
    
    # Save the updated data to Blob Storage
    save_to_blob(existing_data)


@app.route('/thankyou')
def thankyou():
    return render_template('thankyou.html')

if __name__ == '__main__':
   app.run()
