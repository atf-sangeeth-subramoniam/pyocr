import os
import boto3
from flask import Flask, render_template, request

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

    # Read all stored keys
    image_keys = []
    if os.path.exists(IMAGES_FILE):
        with open(IMAGES_FILE, 'r') as f:
            image_keys = [line.strip() for line in f if line.strip()]

    images = [get_presigned_url(key) for key in image_keys]

    return render_template('index.html', images=images)

if __name__ == '__main__':
    app.run(debug=True)
