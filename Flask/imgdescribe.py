# image_description.py
from google.cloud import vision
import io

def convert_image_to_description(image_bytes):
    """Converts an image to a description using Google Cloud Vision API."""
    client = vision.ImageAnnotatorClient()

    image = vision.Image(content=image_bytes)
    response = client.label_detection(image=image)
    labels = response.label_annotations

    description = ", ".join([label.description for label in labels])
    return description if description else "No description available"
