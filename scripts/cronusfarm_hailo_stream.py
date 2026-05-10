#!/usr/bin/env python3
import sys
import gi
import paho.mqtt.client as mqtt
import json
import time

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

try:
    import hailo
except ImportError:
    print("Error: hailo python module not found. Make sure python3-hailo-tappas is installed.")
    sys.exit(1)

# MQTT Settings
MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC = "cronusfarm/hailo/count"

mqtt_client = mqtt.Client()
try:
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.loop_start()
except Exception as e:
    print(f"Warning: Could not connect to MQTT broker: {e}")

last_publish_time = 0
PUBLISH_INTERVAL = 1.0 # Publish count every 1 second

def probe_callback(pad, info):
    global last_publish_time
    buffer = info.get_buffer()
    if not buffer:
        return Gst.PadProbeReturn.OK

    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)
    
    count = len(detections)
    
    current_time = time.time()
    if current_time - last_publish_time >= PUBLISH_INTERVAL:
        last_publish_time = current_time
        # In the future, you can filter detections by class name:
        # e.g. if det.get_label() == "lavender_petal":
        payload = json.dumps({"count": count, "timestamp": current_time})
        mqtt_client.publish(MQTT_TOPIC, payload)
        print(f"Objects detected: {count}")

    return Gst.PadProbeReturn.OK

def main():
    Gst.init(None)

    # Hailo YOLOv8 GStreamer pipeline
    # Note: For custom models, change the hef-path
    pipeline_str = (
        "v4l2src device=/dev/video0 ! "
        "videoscale ! "
        "videoconvert ! "
        "video/x-raw, format=RGB, width=640, height=640, framerate=15/1 ! "
        "hailonet hef-path=/usr/share/hailo-models/yolov8s_h8l.hef batch-size=1 ! "
        "hailofilter so-path=/usr/lib/aarch64-linux-gnu/hailo/tappas/post_processes/libyolo_post.so config-path=/usr/share/hailo-models/yolov8.json qos=false ! "
        "queue ! "
        "hailooverlay ! "
        "videoconvert ! "
        "jpegenc ! "
        "multipartmux ! "
        "tcpserversink host=0.0.0.0 port=8081"
    )

    pipeline = Gst.parse_launch(pipeline_str)

    # Attach probe to hailofilter src pad to get detections
    hailofilter = pipeline.get_by_name("hailofilter0")
    if hailofilter:
        srcpad = hailofilter.get_static_pad("src")
        srcpad.add_probe(Gst.PadProbeType.BUFFER, probe_callback)
    else:
        print("Warning: Could not find hailofilter element in pipeline to attach probe.")

    loop = GLib.MainLoop()
    pipeline.set_state(Gst.State.PLAYING)

    print("Hailo Streamer Started. Video at http://<pi-ip>:8081. Counts published to MQTT.")

    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    finally:
        pipeline.set_state(Gst.State.NULL)
        mqtt_client.loop_stop()

if __name__ == '__main__':
    main()
