import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
from PIL import Image, ImageDraw # ImageFont could be added here if you want to use specific fonts
import io
import argparse
import traceback # For more detailed error logging

def analyze_image(bucket_name, image_key, max_labels, min_confidence, aws_profile_name=None, region_name=None):
    """
    Analyzes an image in S3 using Amazon Rekognition to detect labels and bounding boxes.

    Args:
        bucket_name (str): Name of the S3 bucket.
        image_key (str): Key (filename) of the image in the S3 bucket.
        max_labels (int): Maximum number of labels to return.
        min_confidence (float): Minimum confidence level for labels to be considered.
        aws_profile_name (str, optional): AWS CLI profile name. Defaults to None (uses default profile).
        region_name (str, optional): AWS region name. Defaults to None (uses region from profile or default).
    """
    try:
        # Initialize Boto3 session and clients
        session_kwargs = {}
        if aws_profile_name:
            session_kwargs["profile_name"] = aws_profile_name
        if region_name:
            session_kwargs["region_name"] = region_name
        session = boto3.Session(**session_kwargs)

        # Determine effective region for logging
        effective_region = session.region_name
        if not region_name and not effective_region: # If region wasn't passed and session doesn't have one (e.g. no default in config)
            print("Warning: AWS Region not specified and not found in profile/default. Rekognition might use a default region or fail if region is required.")
            # Forcing a default region for rekognition client if none is found can be an option,
            # but it's better if the user or their config provides it.
            # Example: rekognition_client = session.client('rekognition', region_name='us-east-1')
            # However, S3 client might also need a region if bucket is not in us-east-1 and path-style access is used.
            # For now, we'll let it try and potentially fail if region is crucial and missing.
            pass


        s3_client = session.client('s3') # s3 client can often work without explicit region for global operations like list_buckets,
                                         # but for get_object, it's best if the region matches the bucket or is configured.
        rekognition_client = session.client('rekognition') # Rekognition client strongly benefits from an explicit region.

        print(f"Attempting to access image: s3://{bucket_name}/{image_key}")
        print(f"Using AWS Profile: {aws_profile_name if aws_profile_name else 'default'}")
        if region_name:
            print(f"Using AWS Region (specified): {region_name}")
        elif effective_region:
            print(f"Using AWS Region (from profile/default): {effective_region}")
        else:
            print("AWS Region: Not explicitly specified, relying on SDK defaults (potentially us-east-1 for some services).")


        # Call Rekognition's detect_labels API
        print(f"\nRequesting label detection from Amazon Rekognition for {image_key}...")
        response = rekognition_client.detect_labels(
            Image={
                'S3Object': {
                    'Bucket': bucket_name,
                    'Name': image_key
                }
            },
            MaxLabels=max_labels,
            MinConfidence=min_confidence
        )

        labels = response.get('Labels', [])

        if not labels:
            print("No labels detected or labels did not meet the minimum confidence level.")
            return

        print(f"\n--- Detected Labels (Top {max_labels} or fewer, Min Confidence: {min_confidence}%) ---")
        for label in labels:
            print(f"- Label: {label['Name']}")
            print(f"  Confidence: {label['Confidence']:.2f}%")
            if label.get('Instances'):
                print(f"  Instances: {len(label['Instances'])}")
        print("--- End of Labels ---")


        # Retrieve image from S3 to draw bounding boxes
        print("\nRetrieving image from S3 for drawing bounding boxes...")
        s3_object = s3_client.get_object(Bucket=bucket_name, Key=image_key)
        image_data = s3_object['Body'].read()

        image = Image.open(io.BytesIO(image_data))
        img_width, img_height = image.size
        draw = ImageDraw.Draw(image)

        print("\nDrawing bounding boxes for detected instances...")
        colors = ["red", "blue", "green", "yellow", "purple", "orange", "cyan", "magenta", "lime", "pink", "teal", "brown", "navy", "olive"]
        color_index = 0

        found_boxes = False
        for label in labels:
            if label.get('Instances'):
                current_color = colors[color_index % len(colors)]
                color_index += 1
                for instance in label['Instances']:
                    if 'BoundingBox' in instance:
                        found_boxes = True
                        box = instance['BoundingBox']
                        left = img_width * box['Left']
                        top = img_height * box['Top']
                        width = img_width * box['Width']
                        height = img_height * box['Height']

                        points = (
                            (left, top),
                            (left + width, top),
                            (left + width, top + height),
                            (left, top + height),
                            (left, top) # Close the box
                        )
                        draw.line(points, fill=current_color, width=3)

                        # Add label text near the box
                        text_y_position = top + 5
                        if top < 15 : # If box is too close to the top, put text below
                            text_y_position = top + height + 5
                        elif top + height + 20 > img_height : # If box is too close to bottom, try to put text above if space
                            if top > 15:
                                text_y_position = top - 15 # Rough estimate for text height

                        text_position = (left + 5, text_y_position)

                        try:
                            # For better readability, you might want to load a font:
                            # from PIL import ImageFont
                            # font = ImageFont.truetype("arial.ttf", 15) # Adjust font and size
                            # draw.text(text_position, f"{label['Name']} ({instance['Confidence']:.1f}%)", fill=current_color, font=font)
                            text_to_draw = f"{label['Name']} ({instance['Confidence']:.1f}%)"

                            # Simple text background for better visibility
                            # Pillow's default font size is roughly 10px.
                            # For textbbox, Pillow 9.2.0+ is needed. Using estimation.
                            text_width_estimate = len(text_to_draw) * 6 # Adjusted rough estimate
                            text_height_estimate = 10 # Adjusted rough estimate

                            bg_left = text_position[0] - 2
                            bg_top = text_position[1] - 2
                            bg_right = text_position[0] + text_width_estimate + 2
                            bg_bottom = text_position[1] + text_height_estimate + 2

                            draw.rectangle([bg_left, bg_top, bg_right, bg_bottom], fill="black")
                            draw.text(text_position, text_to_draw, fill=current_color) # Using default font

                        except ImportError: # If ImageFont was attempted but not available
                            print("Warning: ImageFont not available or font file issue. Drawing text without custom font.")
                            draw.text(text_position, f"{label['Name']}", fill=current_color)
                        except Exception as e:
                             print(f"Warning: Could not draw text with confidence, falling back. Error: {e}")
                             draw.text(text_position, f"{label['Name']}", fill=current_color)


                        print(f"  Drew box for: {label['Name']} (Confidence: {instance['Confidence']:.2f}%) at [{left:.0f},{top:.0f},{width:.0f},{height:.0f}] with color {current_color}")

        if not found_boxes:
            print("No bounding boxes were generated as no instances with bounding box data were found.")

        # Display the image with bounding boxes
        print("\nDisplaying image with bounding boxes in a pop-up window...")
        image.show(title=f"Analyzed: {image_key}")
        print("Pop-up window initiated. Close the window to end the script.")

    except NoCredentialsError:
        print("AWS credentials not found. Configure AWS CLI or ensure your environment has credentials.")
        print("Try: `aws configure --profile <your-profile-name>` if using a named profile.")
    except PartialCredentialsError:
        print("Incomplete AWS credentials. Ensure Access Key ID and Secret Access Key are correctly configured.")
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        if error_code == 'NoSuchKey':
            print(f"Error: The image key '{image_key}' was not found in bucket '{bucket_name}'.")
        elif error_code == 'NoSuchBucket':
            print(f"Error: The S3 bucket '{bucket_name}' does not exist.")
        elif error_code == 'AccessDenied':
            print(f"Error: Access Denied. Check IAM permissions for S3 or Rekognition for profile '{aws_profile_name or 'default'}'.")
            print(f"Details: {error_message}")
        elif error_code == 'InvalidS3ObjectException' or ('Rekognition' in str(e) and ('Unable to get image' in str(e) or 'Unable to access S3 object' in str(e))):
             print(f"Error: Rekognition could not access or process the image in S3. This could be due to S3 permissions for Rekognition service role, the image not being accessible, or an unsupported image format.")
             print(f"Details: {error_message}")
        elif error_code == 'ExpiredToken': # Or similar for credentials issues
            print(f"Error: AWS credentials have expired or are invalid. Please reconfigure or refresh your credentials.")
            print(f"Details: {error_message}")
        else:
            print(f"An AWS ClientError occurred: {error_code} - {error_message}")
            # print(f"Full error: {e}") # Uncomment for more details if needed
    except FileNotFoundError: # If a local font file was specified (and uncommented) but not found
        print(f"Error: Font file not found. Ensure your specified font (e.g., 'arial.ttf') is accessible.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze an image stored in S3 using AWS Rekognition to detect labels and draw bounding boxes.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter # Shows default values in help
    )
    parser.add_argument("--bucket", required=True, help="Name of the S3 bucket containing the image.")
    parser.add_argument("--image", required=True, help="Image key (filename including any prefixes) in the S3 bucket.")
    parser.add_argument("--profile", help="AWS CLI profile name to use (optional). If not provided, the default profile is used.")
    parser.add_argument("--region", help="AWS region to use (optional). Overrides region from profile or default AWS configuration.")
    parser.add_argument("--max_labels", type=int, default=10, help="Maximum number of labels to detect.")
    parser.add_argument("--min_confidence", type=float, default=75.0, help="Minimum confidence level for labels (0-100). Labels below this will be ignored.")

    args = parser.parse_args()


    analyze_image(
        bucket_name=args.bucket,
        image_key=args.image,
        max_labels=args.max_labels,
        min_confidence=args.min_confidence,
        aws_profile_name=args.profile,
        region_name=args.region
    )
