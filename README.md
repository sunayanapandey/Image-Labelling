# Automated Image Labeling with AWS Rekognition and S3

This project provides a beginner-friendly guide and Python script to build an automated system for image analysis. It leverages Amazon S3 for image storage and Amazon Rekognition for detecting objects, scenes (labels), confidence levels, and bounding box information. This project is ideal for those new to cloud computing and looking for hands-on experience with AWS services (S3, Rekognition, IAM) and the AWS CLI.


## 🚀 Project Goals

* Implement an automated workflow for handling images with Amazon S3.
* Utilize Amazon Rekognition to analyze images and detect relevant labels with confidence scores and bounding boxes.
* Develop a Python script (`image_analyzer.py`) to manage the image analysis process.
* Securely manage access to AWS services using AWS IAM and the AWS CLI, following the principle of least privilege.
* Display analysis results, including labels, confidence scores, and a visual pop-up of the image with bounding boxes.
* Gain hands-on experience with AWS AI/ML services, storage, and security best practices.

---

## ⚙️ How It Works: The System Flow

1.  **Image Upload**: You (or an automated process) upload an image file to your designated Amazon S3 bucket.
2.  **Execution Trigger**: You run the Python script (`image_analyzer.py` provided in this repository), providing the S3 bucket name and the image's S3 key (its "filename" in the bucket).
3.  **Authentication & Authorization**: The Python script, via the Boto3 library, uses the AWS credentials configured in your CLI environment. AWS IAM validates that your user has the necessary permissions (defined in the policies you'll create) to access the S3 object and the Rekognition service.
4.  **Image Referencing**: The script tells Amazon Rekognition where to find the image in S3.
5.  **Analysis Request**: The script calls the `detect_labels` operation in Amazon Rekognition.
6.  **Result Processing**: Rekognition analyzes the image and sends back a JSON response containing detected labels, confidence scores, bounding box coordinates for object instances, and other metadata.
7.  **Output Generation**:
    * Your Python script parses this JSON.
    * It prints the requested labels and their confidence scores to your console.
    * The script then retrieves the original image from S3 (using the `s3:GetObject` permission) and uses a library like Pillow to draw the bounding boxes onto this image.
8.  **Visual Display**: A pop-up window appears on your screen, showing the analyzed image with the bounding boxes neatly overlaid!

---
