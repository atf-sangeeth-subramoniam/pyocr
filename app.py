import os
import boto3
from flask import Flask, render_template, request

app = Flask(__name__)

# configure your bucket name
S3_BUCKET = 'my-flask-images'
IMAGES_FILE = 'images.txt'

# create S3 client

session = boto3.Session(
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
    region_name=os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-1")
)

s3_client = session.client("s3")


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file part'

        file = request.files['file']

        if file.filename == '':
            return 'No selected file'

        if file:
            # Upload file to S3
            s3_client.upload_fileobj(
                file,
                S3_BUCKET,
                file.filename,
                ExtraArgs={'ACL': 'public-read'}
            )

            # Generate the S3 URL
            image_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{file.filename}"

            # Save URL to text file
            with open(IMAGES_FILE, 'a') as f:
                f.write(image_url + '\n')_
