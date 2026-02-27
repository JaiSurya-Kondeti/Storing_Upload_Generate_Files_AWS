import uuid
import boto3
import io
import numpy as np

from fastapi import FastAPI, UploadFile, File, HTTPException
from mangum import Mangum
from PIL import Image

app = FastAPI()

s3 = boto3.client("s3")

BUCKET_NAME = "api-upload-create-s3-bucket-12345-unique--1"

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):

    allowed_types = (".jpg", ".jpeg", ".png")

    if not file.filename.lower().endswith(allowed_types):
        raise HTTPException(
            status_code=400,
            detail="Only .jpg, .jpeg, .png files allowed"
        )

    if not BUCKET_NAME:
        raise HTTPException(
            status_code=500,
            detail="Bucket name not configured"
        )

    image_id = str(uuid.uuid4())
    key = f"images/{image_id}.jpg"

    contents = await file.read()

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=contents,
        ContentType=file.content_type
    )

    return {
        "id": image_id,
        "image_url": f"https://{BUCKET_NAME}.s3.amazonaws.com/{key}"
    }


@app.post("/generate-gif")
def generate_gif():

    response = s3.list_objects_v2(
        Bucket=BUCKET_NAME,
        Prefix="images/"
    )

    image_arrays = []
    target_size = None

    for obj in response.get("Contents", []):
        key = obj["Key"]

        if key.lower().endswith((".jpg", ".jpeg", ".png")):

            s3_object = s3.get_object(Bucket=BUCKET_NAME, Key=key)
            image_bytes = s3_object["Body"].read()

            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

            if target_size is None:
                target_size = image.size

            image = image.resize(target_size)

            image_arrays.append(np.array(image))

    if not image_arrays:
        return {"message": "No images found"}

    pil_images = [Image.fromarray(img) for img in image_arrays]

    gif_buffer = io.BytesIO()

    pil_images[0].save(
        gif_buffer,
        format="GIF",
        save_all=True,
        append_images=pil_images[1:],
        duration=5000,
        loop=0
    )

    gif_buffer.seek(0)
    gif_bytes = gif_buffer.read()

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key="output/output.gif",
        Body=gif_bytes,
        ContentType="image/gif"
    )

    return {
        "gif_url": f"https://{BUCKET_NAME}.s3.amazonaws.com/output/output.gif"
    }

handler = Mangum(app)