![{48098C77-4DA8-45E6-9D79-DE8AA0525CC9}](https://github.com/user-attachments/assets/9bf88c21-866d-448d-a2ce-acea216f66b3)
# Real-Time Weapon & Object Detection System


This project implements a real-time weapon detection and general object recognition system using YOLOv8 models, built with a Streamlit web interface. It can process live webcam feeds, uploaded video files, or pre-defined sample videos. Detections are visually annotated on the video frames, and logs (including paths to clips where weapons are detected) are stored in a MySQL database.

## Features

*   **Real-Time Detection:** Processes video streams for immediate object identification.
*   **Dual Model System:**
    *   Custom-trained YOLOv8 model (`best.pt`) for specific weapon detection.
    *   Pre-trained YOLOv8n model for general object recognition (COCO dataset).
*   **Multiple Input Sources:**
    *   Live Webcam Feed
    *   Uploaded Video Files (MP4, AVI, MOV)
    *   Pre-configured Sample Videos
*   **Visual Annotations:** Bounding boxes and labels are drawn on frames for detected objects.
    *   Weapons: Red bounding boxes.
    *   General Objects: Blue bounding boxes.
*   **Automatic Clip Recording:** When a weapon is detected, the system automatically records a video clip of the event.
    *   Clips are saved to the `detected_clips/` folder with a timestamp and weapon name.
*   **MySQL Log Persistence:**
    *   Detection events, system events, and errors are logged to a MySQL database.
    *   Includes timestamp, log level, message, video source, and path to recorded clip (if applicable).
*   **Interactive Web Interface:** Built with Streamlit for easy user interaction.
    *   Controls for starting/stopping video processing.
    *   Sidebar for input selection and viewing a session log.
    *   Main area for video display and status messages.

## Demo / Screenshots
Homepage: 

![-2025-05-18T18_32_55 351Z](https://github.com/user-attachments/assets/eac6bdc4-ebae-4882-9fe7-6d94efa4cf57)

Detected Clips:

![2025-05-18T18_33_53 940Z](https://github.com/user-attachments/assets/aaf517b2-429c-4358-a665-e2ccfb9d5553)

Detected Logs in MySQL:

![2025-05-18T18_57_47 544Z](https://github.com/user-attachments/assets/e955d395-67ec-4293-9903-7928c6449268)






 
## Tech Stack

*   **Python**
*   **Streamlit**
*   **OpenCV (cv2)**
*   **Ultralytics YOLOv8**
*   **MySQL**
*   **`mysql-connector-python`**

## Project Structure

```
weapon-detection-system/
├── .streamlit/
│   └── secrets.toml         # Stores MySQL credentials
├── sample_videos/
│   └── people_walking.mp4   # Example
│   └── traffic.mp4          # Example
├── detected_clips/          # Auto-created for recorded clips
├── app.py                   # Main Streamlit application script
├── best.pt                  # Custom weapon detection YOLOv8 model
├── yolov8n.pt               # Pre-trained YOLOv8n model (auto-downloaded if missing)
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

## Setup and Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/SageMurphy/Automatic-Weapon-Detection-System
    cd [YOUR_REPOSITORY_DIRECTORY_NAME]
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # On Windows: venv\Scripts\activate
    # On macOS/Linux: source venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **YOLOv8 Models:**
    *   Ensure `best.pt` (your custom weapon model) is in the project root.
    *   `yolov8n.pt` will be downloaded automatically by Ultralytics if not present.

5.  **MySQL Database Setup:**
    *   Have a MySQL server running.
    *   Create a database (e.g., `[YOUR_DATABASE_NAME]`).
    *   Ensure your MySQL user (e.g., `[YOUR_MYSQL_USER]`) has permissions for this database.

6.  **Configure Database Secrets:**
    *   Create a directory: `.streamlit` in the project root.
    *   Inside `.streamlit/`, create `secrets.toml` with:
        ```toml
        [mysql]
        host = "[YOUR_MYSQL_HOST]"         # e.g., "localhost"
        user = "[YOUR_MYSQL_USER]"         # e.g., "root"
        password = "[YOUR_MYSQL_PASSWORD]" # Your MySQL password
        database = "[YOUR_DATABASE_NAME]"    # e.g., "weapon_detection_db"
        ```
   

7.  **(Optional) Sample Videos:**
    *   Create `sample_videos/` folder in the project root.
    *   Place your sample video files (e.g., `people_walking.mp4`, `traffic.mp4`) inside.
    *   Verify paths in the `SAMPLE_VIDEOS` dictionary in `app.py`.

## `requirements.txt`

Ensure this file exists in your project root:
```txt
streamlit
opencv-python
ultralytics
mysql-connector-python

``` 

## Usage

1.  **Activate virtual environment.**
2.  **Run the Streamlit Application:**
    ```bash
    streamlit run app.py
    ```
3.  Open the provided URL (e.g., `http://localhost:8501`) in your browser.
4.  **Interact:** Use the sidebar to choose video input (upload, webcam, sample) and start processing.
5.  **Outputs:**
    *   Recorded clips appear in `detected_clips/`.
    *   Logs are stored in your MySQL `detection_logs` table.

## How It Works

The system uses Streamlit for the UI. OpenCV handles video input. Each frame is processed by two YOLOv8 models: one custom (`best.pt`) for weapons, and `yolov8n.pt` for general objects. Detections are annotated on-screen. If a weapon is found, a video clip is recorded. All significant events, detections, and errors are logged to a MySQL database for persistence and analysis.

## Future Enhancements

*   [ ] UI-configurable detection thresholds.
*   [ ] Advanced log querying/display within the app.
*   [ ] Alerting for critical detections.
*   [ ] Performance optimizations.

## Contributing

Contributions are welcome! Please fork the repository, create a feature branch, commit your changes, and open a pull request.

## License

 MIT License

## Acknowledgements

*   Ultralytics YOLOv8
*   Streamlit Team
*   OpenCV Community

## Atuhor 
Abhishek Shrimali
