import boto3
from core.aws_config import AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION, COLLECTION_ID

rekognition = boto3.client(
    'rekognition',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

def create_collection():
    try:
        response = rekognition.create_collection(CollectionId=COLLECTION_ID)
        status = response['StatusCode']
        if status == 200:
            print(f"✅ Rekognition collection `{COLLECTION_ID}` created.")
        else:
            print(f"⚠️ Unexpected status: {status}")
    except rekognition.exceptions.ResourceAlreadyExistsException:
        print(f"ℹ️ Collection `{COLLECTION_ID}` already exists.")
    except Exception as e:
        print(f"❌ Failed to create collection: {e}")

if __name__ == '__main__':
    create_collection()
