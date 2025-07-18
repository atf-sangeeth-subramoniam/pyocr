import os
import boto3
from flask import Flask, render_template, request, jsonify
from google.cloud import vision
import google.auth

app = Flask(__name__)

# === Configuration ===
S3_BUCKET = 'san-ocr-bucket'
WIF_CREDENTIALS_PATH = 'credentials/wif-cred.json'
IMAGE_RECORD_FILE = 'images.txt'

# === AWS S3 client ===
s3_client = boto3.client('s3')


def get_presigned_url(key):
    return s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': S3_BUCKET, 'Key': key},
        ExpiresIn=3600
    )


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file part in request.'

        file = request.files['file']
        if file.filename == '':
            return 'No selected file.'

        if file:
            s3_client.upload_fileobj(file, S3_BUCKET, file.filename)

            with open(IMAGE_RECORD_FILE, 'a') as f:
                f.write(file.filename + '\n')

    image_keys = []
    if os.path.exists(IMAGE_RECORD_FILE):
        with open(IMAGE_RECORD_FILE, 'r') as f:
            image_keys = [line.strip() for line in f if line.strip()]

    images = [{"url": get_presigned_url(key), "key": key} for key in image_keys]
    return render_template('index.html', images=images)


@app.route('/ocr', methods=['POST'])
def ocr():
    try:
        filename = request.json.get('filename')
        if not filename:
            return jsonify({'error': 'Filename is required'}), 400

        # Load WIF credentials
        creds, _ = google.auth.load_credentials_from_file(
            WIF_CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

        # Download image from S3
        s3_response = s3_client.get_object(Bucket=S3_BUCKET, Key=filename)
        image_bytes = s3_response['Body'].read()

        # Vision API call using bytes
        client = vision.ImageAnnotatorClient(credentials=creds)
        image = vision.Image(content=image_bytes)
        response = client.text_detection(image=image)

        if response.error.message:
            return jsonify({'error': response.error.message}), 500

        text = response.full_text_annotation.text
        return jsonify({'text': text})

    except Exception as e:
        return jsonify({'error': f"Server error: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True)
