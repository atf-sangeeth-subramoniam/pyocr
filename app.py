import os
import boto3
import json
from flask import Flask, render_template, request, jsonify
from google.auth import default
from google.auth.transport.requests import Request as GoogleRequest
from google.cloud import vision

app = Flask(__name__)

S3_BUCKET = 'san-ocr-bucket'
IMAGES_FILE = 'images.txt'

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
            s3_client.upload_fileobj(
                file,
                S3_BUCKET,
                file.filename
            )
            with open(IMAGES_FILE, 'a') as f:
                f.write(file.filename + '\n')

    image_keys = []
    if os.path.exists(IMAGES_FILE):
        with open(IMAGES_FILE, 'r') as f:
            image_keys = [line.strip() for line in f if line.strip()]

    images = []
    for key in image_keys:
        images.append({
            "url": get_presigned_url(key),
            "key": key
        })

    return render_template('index.html', images=images)

@app.route('/ocr', methods=['POST'])
def ocr_image():
    try:
        from google.auth import impersonated_credentials
        from google.auth.transport.requests import Request as GoogleRequest
        from google.auth import aws
        from google.cloud import vision

        data = request.get_json()
        key = data.get('key')

        if not key:
            return jsonify({"error": "Missing 'key' in request."}), 400

        # Download image from S3
        image_bytes = s3_client.get_object(Bucket=S3_BUCKET, Key=key)['Body'].read()

        # Create AWS credentials adapter for Workload Identity Federation
        credentials = aws.Credentials(
            identity_pool_provider="arn:aws:sts::458575205268:assumed-role/san-ocr-s3-bucket-access",  # This is the AWS role on EC2
            subject_token_type="urn:ietf:params:aws:token-type:aws4_request",
            audience="//iam.googleapis.com/projects/180272852791/locations/global/workloadIdentityPools/ocr-aws-to-google-vision/providers/ocr-aws-provider"
        )
        credentials.refresh(GoogleRequest())

        # Vision client with federated credentials
        client = vision.ImageAnnotatorClient(credentials=credentials)

        image = vision.Image(content=image_bytes)
        response = client.text_detection(image=image)

        text = ''
        if response.text_annotations:
            text = response.text_annotations[0].description

        return jsonify({"ocr_text": text.strip()})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
