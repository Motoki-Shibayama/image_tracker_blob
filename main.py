from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from azure.cognitiveservices.vision.computervision.models import VisualFeatureTypes
from azure.storage.blob import BlobServiceClient, generate_account_sas, ResourceTypes, AccountSasPermissions
from msrest.authentication import CognitiveServicesCredentials

from array import array
from datetime import datetime, timedelta
import json
import os
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
import streamlit as st
import sys
import time

# Read credentials
with open("secret.json") as f:
    secret = json.load(f)

STORAGE_ACCOUNT_NAME = secret["STORAGE_ACCOUNT_NAME"]
STORAGE_ACCOUNT_URL = secret["STORAGE_ACCOUNT_URL"]
ACCOUNT_KEY = secret["ACCOUNT_KEY"]
CONNECTION_STRING = secret["CONNECTION_STRING"]
SUBSCRIPTION_KEY = secret["SUBSCRIPTION_KEY"]
ENDPOINT = secret["ENDPOINT"]

# container name
CONTAINER_NAME = "img"

# client authentication for computer vision
computervision_client = ComputerVisionClient(ENDPOINT, CognitiveServicesCredentials(SUBSCRIPTION_KEY))

# download image data from azure storage
download_path = f"download/download_image.jpg"


def detect_image(image_path):
    local_image = open(image_path, "rb")
    detect_objects_results = computervision_client.detect_objects_in_stream(local_image)
    objects = detect_objects_results.objects
    return objects


def get_tags(image_path):
    local_image = open(image_path, "rb")
    tags_result = computervision_client.tag_image_in_stream(local_image)
    tags = tags_result.tags
    tags_name = []
    for tag in tags:
        tags_name.append(tag.name)
    return tags_name


def getBlobServiceClient():
    # Generate SAS token
    sas_token = generate_account_sas(
        account_name = STORAGE_ACCOUNT_NAME,
        account_key = ACCOUNT_KEY,
        resource_types = ResourceTypes(service=True, container=True, object=True),
        permission = AccountSasPermissions(read=True, write=True, list=True, create=True),
        expiry = datetime.utcnow() + timedelta(minutes=5)
    )

    blob_service_client = BlobServiceClient(account_url=STORAGE_ACCOUNT_URL, credential=sas_token)
    return blob_service_client


def getContainerClient(blob_service_client, container_name):
    return blob_service_client.get_container_client(container_name)


def isContainerExists(blob_service_client, container_name):
    isExists = False
    all_containers = blob_service_client.list_containers()
    # check if designated container exists
    for container in all_containers:
        if container.name == container_name:
            return True
        else:
            isExists = False
    return isExists

def isBlobExists(container_client,  blob_name):
    isExists = False
    blob_list = container_client.list_blobs()
    for blob in blob_list:
        if blob.name == blob_name:
            return True
        else:
            isExists = False
    return isExists


def main():
    # remove download file if there is
    if os.path.exists(download_path):
        os.remove(download_path)

    blob_service_client = getBlobServiceClient()

    isExists = isContainerExists(blob_service_client, CONTAINER_NAME)
    if not isExists:
        # Create container
        try:
            blob_service_client.create_container(CONTAINER_NAME)
        except Exception as e:
            print(e)

    # create UI with streamlit
    st.title("Image Analysis")
    # upload image to blob container
    uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "png"])

    if uploaded_file is not None:
        uploaded_image = Image.open(uploaded_file)
        # save image under tmp folder in order to get file path
        img_path = f"tmp/{uploaded_file.name}"
        uploaded_image.save(img_path)

        # upload image file to blob container if there are not
        container_client = getContainerClient(blob_service_client, CONTAINER_NAME)
        if not isBlobExists(container_client, uploaded_file.name):
            with open(img_path, "rb") as data:
                blob_client = container_client.upload_blob(name=uploaded_file.name, data=data)

        # delete image data in tmp folder
        os.remove(img_path)

        with open(download_path, "wb") as image:
            blob_data = blob_client.download_blob()
            blob_data.readinto(image)

        # detect image object
        objects = detect_image(download_path)

        # draw image
        img = Image.open(download_path)
        draw = ImageDraw.Draw(img)
        for object in objects:
            # get coordinate points
            x = object.rectangle.x
            y = object.rectangle.y
            w = object.rectangle.w
            h = object.rectangle.h

            # get object propertoes of image
            caption = object.object_property
            # define font property
            font = ImageFont.truetype(font="./arial.ttf", size=50)
            # get text size in the rectangle
            text_w, text_h = draw.textsize(caption, font)

            # draw a rectangle for object
            draw.rectangle([(x,y), (x+w, y+h)], fill=None, outline="green", width=5)
            # draw a rectangle for text and fill
            draw.rectangle([(x,y), (x+text_w+5, y+text_h+5)], fill="green")
            # write text for describing object
            draw.text((x,y), caption, fill="white", font=font)

        # show image
        st.image(img)

        # get tag information
        tags_name = get_tags(download_path)
        # join tags with ", " as separator
        tags_name = ", ".join(tags_name)
        # show tags with markdown
        st.markdown("*** contents tag ***")
        st.markdown(f"> {tags_name}")


if __name__ == "__main__":
    main()
