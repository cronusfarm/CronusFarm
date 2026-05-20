import json
import os

FILE_PATH = "nodered/merged-deploy.json"

def patch_dashboard():
    if not os.path.exists(FILE_PATH):
        print(f"File not found: {FILE_PATH}")
        return

    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Check if AI Camera group already exists
    existing = [n for n in data if n.get('id') == "ui_grp_ai_camera"]
    if existing:
        print("AI Camera UI group already exists.")
        return

    # 1. Create a UI Group for the AI Camera
    ui_group = {
        "id": "ui_grp_ai_camera",
        "type": "ui_group",
        "z": "",
        "name": "AI 작물 관측 (카메라)",
        "tab": "ui_tab_monitor",
        "order": 1,
        "disp": True,
        "width": "12",
        "collapse": False
    }

    # 2. MQTT In Node
    mqtt_in = {
        "id": "nr_node_mqtt_ai_count",
        "type": "mqtt in",
        "z": "1a7c50b697ef67ff", # Using an existing flow ID or dummy
        "name": "AI Count (MQTT)",
        "topic": "cronusfarm/camera/ai_count",
        "qos": "0",
        "datatype": "json",
        "broker": "b548b81.16ff048", # This is usually local mosquitto. We might need to guess the broker ID or create one.
        "nl": False,
        "rap": True,
        "rh": 0,
        "inputs": 0,
        "x": 200,
        "y": 1000,
        "wires": [["nr_node_ai_count_func"]]
    }
    
    # Let's find an existing MQTT broker in the flows to use
    broker_id = "b548b81.16ff048"
    for n in data:
        if n.get("type") == "mqtt-broker":
            broker_id = n.get("id")
            break
            
    mqtt_in["broker"] = broker_id

    # 3. Function to format count
    func_node = {
        "id": "nr_node_ai_count_func",
        "type": "function",
        "z": "1a7c50b697ef67ff",
        "name": "Extract Count",
        "func": "msg.payload = msg.payload.count + ' 개';\nreturn msg;",
        "outputs": 1,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 400,
        "y": 1000,
        "wires": [["nr_node_ui_ai_count"]]
    }

    # 4. UI Text Node for Count
    ui_text = {
        "id": "nr_node_ui_ai_count",
        "type": "ui_text",
        "z": "1a7c50b697ef67ff",
        "group": "ui_grp_ai_camera",
        "order": 2,
        "width": 0,
        "height": 0,
        "name": "방울토마토 개수",
        "label": "현재 방울토마토 개수",
        "format": "{{msg.payload}}",
        "layout": "row-spread",
        "x": 600,
        "y": 1000,
        "wires": []
    }

    # 5. UI Template Node for MJPEG Stream
    ui_template = {
        "id": "nr_node_ui_ai_stream",
        "type": "ui_template",
        "z": "1a7c50b697ef67ff",
        "group": "ui_grp_ai_camera",
        "name": "AI 카메라 피드",
        "order": 1,
        "width": "12",
        "height": "9",
        "format": "<div style=\"display: flex; justify-content: center; align-items: center; width: 100%; height: 100%;\">\n    <img src=\"http://ida.mango-larch.ts.net:8081/video_feed\" style=\"max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 8px;\" alt=\"AI Camera Stream Offline\">\n</div>",
        "storeOutMessages": True,
        "fwdInMessages": True,
        "resendOnRefresh": True,
        "templateScope": "local",
        "x": 600,
        "y": 1060,
        "wires": [[]]
    }

    # Add Z ID (use the first tab's ID)
    tabs = [n for n in data if n.get("type") == "tab"]
    if tabs:
        target_z = tabs[0]["id"]
        mqtt_in["z"] = target_z
        func_node["z"] = target_z
        ui_text["z"] = target_z
        ui_template["z"] = target_z

    data.extend([ui_group, mqtt_in, func_node, ui_text, ui_template])

    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print("Successfully patched Node-RED flows with AI Camera Dashboard.")

if __name__ == "__main__":
    patch_dashboard()
