import os
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from arduino_controller import ArduinoController
from traffic_engine import TrafficEngine

app = Flask(__name__)
app.config['SECRET_KEY'] = 'traffic_secret_key_2024'
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs('uploads', exist_ok=True)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

arduino = ArduinoController(port='COM5')
arduino.connect()

engine = TrafficEngine(socketio, arduino if arduino.connected else None)

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/upload_video', methods=['POST'])
def upload_video():
    lane = int(request.form.get('lane', 0))
    if 'video' not in request.files:
        return jsonify({"status": "error", "message": "No video file provided"}), 400
    file = request.files['video']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No file selected"}), 400
    filename = f"lane_{lane}_{file.filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    engine.videos_uploaded[lane] = True
    engine.video_paths[lane] = filepath
    engine.add_log(f"Video uploaded for {engine.lane_names[lane]} lane: {file.filename}", "UPLOAD")
    return jsonify({"status": "success", "message": f"Video uploaded for {engine.lane_names[lane]} lane"})

@app.route('/start_system', methods=['POST'])
def start_system():
    if not engine.running:
        engine.start()
        return jsonify({"status": "success", "message": "System started"})
    return jsonify({"status": "info", "message": "System already running"})

@app.route('/stop_system', methods=['POST'])
def stop_system():
    engine.stop()
    return jsonify({"status": "success", "message": "System stopped"})

@app.route('/trigger_emergency', methods=['POST'])
def trigger_emergency():
    data = request.get_json()
    lane = int(data.get('lane', 0))
    engine.handle_emergency(lane)
    return jsonify({"status": "success", "message": f"Emergency triggered for {engine.lane_names[lane]}"})

@app.route('/clear_emergency', methods=['POST'])
def clear_emergency():
    engine.clear_emergency()
    return jsonify({"status": "success", "message": "Emergency cleared"})

@app.route('/get_logs', methods=['GET'])
def get_logs():
    return jsonify(engine.logs)

@app.route('/get_state', methods=['GET'])
def get_state():
    return jsonify({
        "cycle": engine.cycle_number,
        "signal_states": engine.signal_states,
        "signal_timings": engine.signal_timings,
        "lane_densities": engine.lane_densities,
        "lane_total_density": engine.lane_total_density,
        "lane_names": engine.lane_names,
        "current_green_lane": engine.current_green_lane,
        "emergency_active": engine.emergency_active,
        "emergency_lane": engine.emergency_lane,
        "videos_uploaded": engine.videos_uploaded,
        "processing_complete": engine.processing_complete,
        "arduino_connected": arduino.connected
    })

if __name__ == '__main__':
    socketio.run(app, debug=False, host='0.0.0.0', port=5000)