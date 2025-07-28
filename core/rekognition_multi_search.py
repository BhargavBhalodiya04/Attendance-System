import boto3
from PIL import Image
import os

rekognition = boto3.client('rekognition')
s3 = boto3.client('s3')

def get_face_crops(bucket_name, image_key):
    # Detect faces
    response = rekognition.detect_faces(
        Image={'S3Object': {'Bucket': bucket_name, 'Name': image_key}},
        Attributes=['DEFAULT']
    )

    face_details = response['FaceDetails']

    # Download original image
    local_path = f'/tmp/{os.path.basename(image_key)}'
    s3.download_file(bucket_name, image_key, local_path)
    original = Image.open(local_path)
    width, height = original.size

    # Crop each face
    cropped_paths = []
    for i, face in enumerate(face_details):
        box = face['BoundingBox']
        left = int(box['Left'] * width)
        top = int(box['Top'] * height)
        w = int(box['Width'] * width)
        h = int(box['Height'] * height)

        cropped_img = original.crop((left, top, left + w, top + h))
        crop_path = f"/tmp/face_crop_{i}.jpg"
        cropped_img.save(crop_path)
        cropped_paths.append(crop_path)

    return cropped_paths

def recognize_faces_in_image(bucket_name, image_key, collection_id):
    face_crops = get_face_crops(bucket_name, image_key)
    matched_ids = []

    for face_path in face_crops:
        with open(face_path, 'rb') as image_data:
            response = rekognition.search_faces_by_image(
                CollectionId=collection_id,
                Image={'Bytes': image_data.read()},
                MaxFaces=1,
                FaceMatchThreshold=90
            )
        
        matches = response.get('FaceMatches', [])
        if matches:
            matched_id = matches[0]['Face']['ExternalImageId']
            matched_ids.append(matched_id)

    return list(set(matched_ids))  # Remove duplicates
