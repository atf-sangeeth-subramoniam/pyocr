import os
import uuid
import boto3
from flask import Flask, render_template, request, jsonify

from google.cloud import vision
import google.auth

# === Flask app setup ===
app = Flask(__name__)

# === Configuration ===
S3_BUCKET = 'san-ocr-bucket'
WIF_CREDENTIALS_PATH = 'credentials/wif-cred.json'
IMAGE_RECORD_FILE = 'images.txt'

# === AWS S3 client ===
s3_client = boto3.client('s3')


# === Helper: Generate presigned S3 URL ===
def get_presigned_url(key):
    return s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': S3_BUCKET, 'Key': key},
        ExpiresIn=3600
    )


# === Route: Home page with upload form and image previews ===
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file part in request.'

        file = request.files['file']
        if file.filename == '':
            return 'No selected file.'

        if file:
            # Save file to S3
            s3_client.upload_fileobj(file, S3_BUCKET, file.filename)

            # Log the filename
            with open(IMAGE_RECORD_FILE, 'a') as f:
                f.write(file.filename + '\n')

    # List all image URLs
    image_keys = []
    if os.path.exists(IMAGE_RECORD_FILE):
        with open(IMAGE_RECORD_FILE, 'r') as f:
            image_keys = [line.strip() for line in f if line.strip()]

    images = [{"url": get_presigned_url(key), "key": key} for key in image_keys]

    return render_template('index.html', images=images)


# === Route: OCR via Google Vision API ===
@app.route('/ocr', methods=['POST'])
def ocr():
    try:
        filename = request.json.get('filename')
        if not filename:
            return jsonify({'error': 'Filename is required'}), 400

        # GCS URI used by Google Vision API
        image_uri = f"gs://{S3_BUCKET}/{filename}"

        # Load credentials using Workload Identity Federation
        creds, _ = google.auth.load_credentials_from_file(
            WIF_CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

        # Initialize Vision client
        client = vision.ImageAnnotatorClient(credentials=creds)

        # Prepare image for OCR
        image = vision.Image()
        image.source.image_uri = image_uri

        # Perform OCR
        response = client.text_detection(image=image)

        if response.error.message:
            return jsonify({'error': response.error.message}), 500

        text = response.full_text_annotation.text
        return jsonify({'text': text})

    except Exception as e:
        return jsonify({'error': f"Server error: {str(e)}"}), 500


# === Run Flask app ===
if __name__ == '__main__':
    app.run(debug=True)
