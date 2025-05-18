import os
import cv2
import streamlit as st
from datetime import datetime
from tempfile import NamedTemporaryFile
from ultralytics import YOLO
import time
import mysql.connector # For MySQL
from mysql.connector import Error # For MySQL error handling

# --- Streamlit Page Configuration (MUST BE FIRST STREAMLIT COMMAND) ---
st.set_page_config(layout="wide", page_title="Weapon Detection System")

# --- Database Configuration ---
# REPLACE THESE WITH YOUR ACTUAL MYSQL CREDENTIALS FOR LOCAL DEVELOPMENT
# FOR DEPLOYMENT, USE STREAMLIT SECRETS (secrets.toml)
# Example secrets.toml:
# [mysql]
# host = "your_deployed_mysql_host"
# user = "your_deployed_mysql_user"
# password = "your_deployed_mysql_password"
# database = "your_deployed_mysql_database"

DB_CONFIG = {
    'host': st.secrets.get("mysql.host", "localhost"), # e.g., "localhost"
    'user': st.secrets.get("mysql.user", "root"),   # e.g., "root"
    'password': st.secrets.get("mysql.password", ""), # e.g., "yourpassword"
    'database': st.secrets.get("mysql.database", "") # e.g., "weapon_detection_db"
}

# --- Database Connection Function & Table Creation ---
@st.cache_resource # Cache the connection across reruns
def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        if conn.is_connected():
            print("Successfully connected to MySQL database")
            return conn
    except Error as e:
        st.error(f"DB Connection Error: {e}")
        print(f"DB Connection Error: {e}")
        return None
    return None

def create_logs_table_if_not_exists(_conn):
    if _conn is None or not _conn.is_connected():
        st.warning("DB not connected, cannot create/check logs table.")
        return
    cursor = None
    try:
        cursor = _conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS detection_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                timestamp DATETIME NOT NULL,
                log_level VARCHAR(20) NOT NULL,
                message TEXT NOT NULL,
                video_source VARCHAR(255) NULL,
                clip_path VARCHAR(255) NULL
            );
        """)
        _conn.commit()
        print("detection_logs table checked/created successfully.")
    except Error as e:
        st.error(f"DB Table Creation Error: {e}")
        print(f"DB Table Creation Error: {e}")
    finally:
        if cursor:
            cursor.close()

# Attempt to connect and create table on app startup
db_connection_global = get_db_connection() # Store the initial connection attempt
if db_connection_global:
    create_logs_table_if_not_exists(db_connection_global)
else:
    st.warning("DATABASE ALERT: Could not connect to MySQL. Logs will NOT be saved to the database for this session.")

# --- Initialize YOLO models ---
@st.cache_resource
def load_models():
    try:
        weapon_model = YOLO("best.pt")
        effect_model = YOLO("yolov8n.pt")
        print("YOLO Models loaded successfully.")
        return weapon_model, effect_model
    except Exception as e:
        st.error(f"Error loading YOLO models: {e}")
        print(f"Error loading YOLO models: {e}")
        return None, None

weapon_model, effect_model = load_models()
if weapon_model is None or effect_model is None:
    st.error("CRITICAL ERROR: YOLO models could not be loaded. The application cannot continue. Check model paths.")
    st.stop()

# --- COCO Labels, Output Folder, Sample Videos ---
coco_labels = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light",
    "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "TV", "laptop", "mouse", "remote", "keyboard",
    "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
    "scissors", "teddy bear", "hair drier", "toothbrush"
]
output_folder = "detected_clips"
os.makedirs(output_folder, exist_ok=True)
SAMPLE_VIDEOS = {
    "CriminalThreatens (Example)": "sample/CriminalThreatens.mp4", # Replace with your actual file name
    "Person with a Gun (Example)": "sample/Shutter.mp4",       # Replace with your actual file name
    "Person with Knife (Example)": "sample/WithGuns.mp4" # Replace
    # Add more sample video paths heres
}

# --- Custom CSS ---
st.markdown("""
<style>
    .log-container .stTextArea textarea { color: #FFA500 !important; font-family: 'Consolas', 'Monaco', monospace !important; }
    .latest-log-info .stAlert { font-size: 0.95rem; }
</style>
""", unsafe_allow_html=True)

# --- Session State Variables ---
if "log" not in st.session_state: st.session_state.log = ""
if "stop_camera" not in st.session_state: st.session_state.stop_camera = False
if "is_processing" not in st.session_state: st.session_state.is_processing = False
if "current_video_source" not in st.session_state: st.session_state.current_video_source = None
if "current_video_path" not in st.session_state: st.session_state.current_video_path = None

# --- Helper Function: write_log_to_db ---
def write_log_to_db(level, message, video_source=None, clip_path=None):
    conn = get_db_connection() # Use the cached connection
    if conn is None or not conn.is_connected():
        # Try to re-establish if initial connection failed or was lost
        global db_connection_global
        if not db_connection_global or not db_connection_global.is_connected():
            print("Attempting to reconnect to DB for logging...")
            db_connection_global = get_db_connection()
            if db_connection_global: create_logs_table_if_not_exists(db_connection_global)
        
        conn = db_connection_global # Use the (potentially) re-established global connection

        if conn is None or not conn.is_connected():
            print(f"DB LOG SKIP (No Connection): {level} - {message}")
            return

    cursor = None
    try:
        cursor = conn.cursor()
        sql = """
            INSERT INTO detection_logs (timestamp, log_level, message, video_source, clip_path)
            VALUES (%s, %s, %s, %s, %s)
        """
        val = (datetime.now(), str(level).upper(), str(message),
               str(video_source) if video_source else None,
               str(clip_path) if clip_path else None)
        cursor.execute(sql, val)
        conn.commit()
    except Error as e:
        print(f"DB LOG WRITE ERROR: {e} for message: '{message}'") # Log to console, not st.error
        if conn: conn.rollback()
    finally:
        if cursor: cursor.close()

# --- MODIFIED Helper Function: write_log ---
def write_log(message, placeholder_to_update=None, is_error=False,
              log_level_for_db="INFO", db_video_source=None, db_clip_path=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ui_prefix = "⚡"
    actual_db_log_level = str(log_level_for_db).upper()

    if is_error or "error" in message.lower():
        ui_prefix = "🔴"; actual_db_log_level = "ERROR"
    elif "detected" in message.lower():
        ui_prefix = "⚠️"; actual_db_log_level = "DETECTION"
    elif "recording started" in message.lower(): ui_prefix = "🔴"
    elif "recording stopped" in message.lower() or "finalized" in message.lower(): ui_prefix = "💾"
    elif "initiated" in message.lower() or "selected" in message.lower() or "uploaded" in message.lower():
        ui_prefix = "🚦"; actual_db_log_level = "SYSTEM_EVENT"
    elif "stop" in message.lower() and "user" in message.lower():
         ui_prefix = "⏹️"; actual_db_log_level = "USER_ACTION"
    elif "opened successfully" in message.lower(): ui_prefix = "✅"
    elif "loop finished" in message.lower(): ui_prefix = "🏁"


    new_session_log_entry = f"[{timestamp}] {ui_prefix} {message}"
    st.session_state.log = new_session_log_entry + "\n" + st.session_state.log
    max_log_lines = 100
    log_lines = st.session_state.log.splitlines()
    if len(log_lines) > max_log_lines: st.session_state.log = "\n".join(log_lines[:max_log_lines])

    if placeholder_to_update:
        if actual_db_log_level == "ERROR": placeholder_to_update.error(f"🔴 Latest: {message}")
        else: placeholder_to_update.info(f"{ui_prefix} Latest: {message}")

    final_db_video_source = db_video_source
    if final_db_video_source is None and st.session_state.get("current_video_source"):
        current_src_state = st.session_state.current_video_source
        if current_src_state == "webcam": final_db_video_source = "webcam"
        elif current_src_state in ["file", "sample"] and st.session_state.get("current_video_path"):
            final_db_video_source = os.path.basename(st.session_state.current_video_path)
        elif isinstance(current_src_state, str): final_db_video_source = current_src_state

    write_log_to_db(level=actual_db_log_level, message=message,
                    video_source=final_db_video_source, clip_path=db_clip_path)

# --- UI Definition ---
with st.sidebar:
    st.title("🛡️ Controls & Log")
    st.markdown("Upload video, use webcam, or select sample.")
    st.markdown("---")
    uploaded_file_sidebar = st.file_uploader("📂 Upload Video", type=["mp4", "avi", "mov"], key="uploader",
                                           disabled=st.session_state.is_processing)
    if st.button("📸 Start Webcam", key="start_cam", disabled=st.session_state.is_processing, use_container_width=True):
        if not st.session_state.is_processing:
            st.session_state.is_processing = True; st.session_state.stop_camera = False
            st.session_state.current_video_source = "webcam"; st.session_state.current_video_path = None
            write_log("Webcam feed initiated...", log_level_for_db="SYSTEM_EVENT")
            st.rerun()
    st.markdown("---")
    st.subheader("🧪 Sample Videos")
    sample_options = ["None"] + list(SAMPLE_VIDEOS.keys())
    selected_sample = st.selectbox("Select sample:", options=sample_options, index=0, key="sample_select",
                                   disabled=st.session_state.is_processing)
    if selected_sample != "None":
        sample_p = SAMPLE_VIDEOS[selected_sample]
        if not os.path.exists(sample_p): st.warning(f"Sample missing: {sample_p}")
        elif st.button(f"Process: {selected_sample}", key=f"proc_samp_{selected_sample.replace(' ','_')}",
                       disabled=st.session_state.is_processing, use_container_width=True):
            if not st.session_state.is_processing:
                st.session_state.is_processing = True; st.session_state.stop_camera = False
                st.session_state.current_video_source = "sample"; st.session_state.current_video_path = sample_p
                write_log(f"Sample '{selected_sample}' selected.", log_level_for_db="SYSTEM_EVENT")
                st.rerun()
    st.markdown("---")
    st.subheader("📝 Session Log")
    st.markdown('<div class="log-container">', unsafe_allow_html=True)
    st.text_area("LogView", value=st.session_state.log, height=250, disabled=True, key="session_log_area", label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

# Main Area
st.title("🔫 Weapon & Object Detection System 👀")
st.markdown("Real-time weapon and object detection. Detected weapon clips are saved.")
st.markdown("---")
frame_placeholder = st.empty()
st.markdown('<div class="latest-log-info">', unsafe_allow_html=True)
status_placeholder = st.empty()
st.markdown('</div>', unsafe_allow_html=True)

# --- Core Processing Function ---
def process_video_feed(video_input, status_ph): # video_input is path or 0 for webcam
    cap = None
    ui_source_name = "Webcam"; db_source_name = "webcam"

    if isinstance(video_input, str):
        if not os.path.exists(video_input):
            msg = f"Video file not found: {video_input}"
            st.error(msg); write_log(msg, status_ph, is_error=True, db_video_source=video_input)
            st.session_state.is_processing = False; st.session_state.stop_camera = True; return
        cap = cv2.VideoCapture(video_input)
        ui_source_name = os.path.basename(video_input); db_source_name = ui_source_name
        write_log(f"Processing video: {ui_source_name}...", status_ph, db_video_source=db_source_name)
    else:
        cap = cv2.VideoCapture(video_input) # 0 for webcam
        write_log("Attempting to start webcam...", status_ph, db_video_source=db_source_name)

    if not cap or not cap.isOpened():
        msg = "Error opening video source."
        st.error(msg); write_log(msg, status_ph, is_error=True, db_video_source=db_source_name)
        st.session_state.is_processing = False; st.session_state.stop_camera = True
        if cap: cap.release(); return

    status_ph.info(f"⏳ Processing {ui_source_name}...")
    write_log("Video source opened.", None, db_video_source=db_source_name) # Log to sidebar, not overwriting status_ph

    recording = False; out = None; current_clip_path = ""
    fps = cap.get(cv2.CAP_PROP_FPS)
    fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if fps <= 0 or fps > 120: fps = 20.0 # Default FPS

    try:
        while not st.session_state.stop_camera:
            ret, frame = cap.read()
            if not ret:
                write_log("End of video or stream error.", status_ph, db_video_source=db_source_name)
                break

            weapon_res = weapon_model(frame, verbose=False, half=True)
            effect_res = effect_model(frame, verbose=False, half=True)
            annot_frame = frame.copy()
            weapon_detected_this_frame = False
            detected_weapon_name = "Weapon" # Default, can be model.names[cls]
            now_time = datetime.now()

            for r in weapon_res:
                if r.boxes is not None:
                    for box in r.boxes:
                        cls = int(box.cls.item()); conf = float(box.conf.item())
                        if cls == 0 and conf > 0.5: # Assuming class 0 is weapon
                            weapon_detected_this_frame = True
                            x1,y1,x2,y2 = map(int, box.xyxy[0].tolist())
                            cv2.rectangle(annot_frame, (x1,y1),(x2,y2), (0,0,255),2)
                            cv2.putText(annot_frame, f"{detected_weapon_name} ({conf:.2f})", (x1,y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,(0,0,255),2)
            for r in effect_res:
                if r.boxes is not None:
                    for box in r.boxes:
                        cls = int(box.cls.item()); conf = float(box.conf.item())
                        if conf > 0.5:
                            obj_name = coco_labels[cls] if cls < len(coco_labels) else f"Obj-{cls}"
                            x1,y1,x2,y2 = map(int, box.xyxy[0].tolist())
                            cv2.rectangle(annot_frame, (x1,y1),(x2,y2), (255,0,0),2)
                            cv2.putText(annot_frame, f"{obj_name} ({conf:.2f})", (x1,y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,(255,0,0),2)

            if weapon_detected_this_frame:
                if not recording:
                    ts_date = now_time.strftime("%d-%m-%y"); ts_time = now_time.strftime("%H-%M-%S")
                    vid_fname = f"{detected_weapon_name}_{ts_date}_{ts_time}.mp4"
                    current_clip_path = os.path.join(output_folder, vid_fname)
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    out = cv2.VideoWriter(current_clip_path, fourcc, fps, (fw,fh))
                    if not out.isOpened():
                        msg = f"Error opening VideoWriter: {current_clip_path}"
                        st.error(msg); write_log(msg, status_ph, is_error=True, db_video_source=db_source_name)
                        st.session_state.stop_camera=True; break
                    recording = True
                    write_log(f"REC Start: {vid_fname}", status_ph, log_level_for_db="RECORDING_EVENT", db_clip_path=current_clip_path)
                if recording and out: out.write(frame) # Original frame
                log_ts = now_time.strftime("%I:%M:%S %p")
                write_log(f"{detected_weapon_name} detected @{log_ts}", status_ph, log_level_for_db="DETECTION", db_clip_path=current_clip_path if recording else None)
            else: # No weapon
                if recording:
                    recording=False
                    if out: out.release(); out=None
                    write_log(f"REC Stop: {os.path.basename(current_clip_path)}", status_ph, log_level_for_db="RECORDING_EVENT", db_clip_path=current_clip_path)
                    current_clip_path = ""
            
            rgb_frame = cv2.cvtColor(annot_frame, cv2.COLOR_BGR2RGB)
            frame_placeholder.image(rgb_frame, channels="RGB", use_container_width=True)
    finally:
        if cap: cap.release()
        if recording and out: # If loop/app stops while recording
            out.release()
            write_log(f"REC Finalized (incomplete?): {os.path.basename(current_clip_path)}", status_ph, log_level_for_db="RECORDING_EVENT", db_clip_path=current_clip_path)
        write_log("Processing loop ended.", status_ph, db_video_source=db_source_name)
        st.session_state.is_processing = False
        st.session_state.stop_camera = True # Ensure stop is true

# --- Main Control Logic ---
if uploaded_file_sidebar and not st.session_state.is_processing:
    if st.session_state.current_video_source != "file_processed_marker":
        st.session_state.is_processing = True; st.session_state.stop_camera = False
        st.session_state.current_video_source = "file"
        with NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_f:
            tmp_f.write(uploaded_file_sidebar.read())
            st.session_state.current_video_path = tmp_f.name
        write_log(f"File '{uploaded_file_sidebar.name}' uploaded.", status_placeholder, log_level_for_db="SYSTEM_EVENT", db_video_source=uploaded_file_sidebar.name)
        st.rerun()

if st.session_state.is_processing:
    if st.button("🛑 Stop Processing", key="stop_main_btn", use_container_width=False):
        write_log("User stopped processing.", status_placeholder, log_level_for_db="USER_ACTION")
        st.session_state.stop_camera = True
        st.session_state.is_processing = False # Crucial: mark as not processing now
        st.rerun()
else: # Not processing
    if not st.session_state.current_video_source and not uploaded_file_sidebar and selected_sample == "None":
         frame_placeholder.info("✨ Welcome! Upload a video, start webcam, or select a sample. ✨")

if st.session_state.is_processing and not st.session_state.stop_camera:
    frame_placeholder.empty()
    input_src = None
    if st.session_state.current_video_source == "webcam": input_src = 0
    elif st.session_state.current_video_source in ["file", "sample"]: input_src = st.session_state.current_video_path
    
    if input_src is not None:
        process_video_feed(input_src, status_placeholder)
        # After process_video_feed, is_processing is False, stop_camera is True
        # The script will then fall through to the cleanup block below on the same run
    else: # Should not happen if UI logic is correct
        write_log("Error: Invalid video source for processing.", status_placeholder, is_error=True)
        st.session_state.is_processing = False; st.session_state.stop_camera = True; st.rerun()

# Cleanup and final state update happens if not processing (either finished naturally or stopped)
if not st.session_state.is_processing:
    # This ensures cleanup runs once after processing is done or stopped.
    # current_video_source being not None indicates a process was active.
    if st.session_state.current_video_source is not None and \
       st.session_state.current_video_source != "file_processed_marker": # Avoid multiple cleanups for same stop
        
        if st.session_state.current_video_source == "file" and st.session_state.current_video_path:
            if os.path.exists(st.session_state.current_video_path):
                try:
                    os.unlink(st.session_state.current_video_path)
                    write_log(f"Temp file deleted: {os.path.basename(st.session_state.current_video_path)}", status_placeholder, log_level_for_db="SYSTEM_EVENT")
                except Exception as e:
                    write_log(f"Error deleting temp file: {e}", status_placeholder, is_error=True)
            st.session_state.current_video_path = None
        
        status_placeholder.success("✅ Processing finished or stopped. Ready for new input.")
        st.session_state.current_video_source = "file_processed_marker" # Mark as idle/processed
        # A final rerun might be needed if the process ended naturally to update UI to idle state.
        # The stop button already does a rerun.
        # If a natural end (video finishes) doesn't update UI, add st.rerun() here.
        # For now, let's assume the flow handles it.
        if not st.session_state.get("stop_button_pressed_this_run", False): # Avoid double rerun if stop button caused this
             st.rerun() # Rerun if process finished naturally
    st.session_state.pop("stop_button_pressed_this_run", None) # Clear the flag