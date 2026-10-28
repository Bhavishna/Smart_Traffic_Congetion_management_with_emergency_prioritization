import random
import time
import threading
from datetime import datetime

class TrafficEngine:
    def __init__(self, socketio, arduino_controller=None):
        self.socketio = socketio
        self.arduino = arduino_controller
        self.running = False
        self.paused = False
        self.cycle_number = 0
        self.current_green_lane = -1
        self.emergency_lane = -1
        self.emergency_active = False
        self.videos_uploaded = [False, False, False, False]
        self.video_paths = [None, None, None, None]
        self.processing_complete = [False, False, False, False]
        self.lane_names = ["North", "East", "South", "West"]
        self.vehicle_categories = ["Cars", "Buses", "Trucks", "Bikes", "Autos", "Cycles"]
        self.lane_densities = [{} for _ in range(4)]
        self.lane_total_density = [0, 0, 0, 0]
        self.signal_states = ["RED", "RED", "RED", "RED"]
        self.signal_timings = [0, 0, 0, 0]
        self.logs = []
        self.min_green = 10
        self.max_green = 60
        self.yellow_time = 3
        self.all_red_time = 2
        self.base_weights = {
            "Cars": 1.0,
            "Buses": 2.5,
            "Trucks": 3.0,
            "Bikes": 0.5,
            "Autos": 0.8,
            "Cycles": 0.3
        }
        self.previous_densities = [None, None, None, None]

    def generate_density(self, lane_index):
        density = {}
        prev = self.previous_densities[lane_index]

        for category in self.vehicle_categories:
            if category == "Cars":
                base = random.randint(8, 35)
            elif category == "Buses":
                base = random.randint(1, 8)
            elif category == "Trucks":
                base = random.randint(0, 6)
            elif category == "Bikes":
                base = random.randint(5, 30)
            elif category == "Autos":
                base = random.randint(3, 15)
            elif category == "Cycles":
                base = random.randint(0, 10)
            else:
                base = random.randint(0, 10)

            if prev and category in prev:
                prev_val = prev[category]
                max_change = max(3, int(prev_val * 0.4))
                delta = random.randint(-max_change, max_change)
                base = max(0, prev_val + delta)

            density[category] = base

        self.previous_densities[lane_index] = density.copy()
        return density

    def calculate_weighted_density(self, density):
        total = 0
        for cat, count in density.items():
            total += count * self.base_weights.get(cat, 1.0)
        return round(total, 2)

    def calculate_green_time(self, weighted_density, total_all_lanes):
        if total_all_lanes == 0:
            return self.min_green
        proportion = weighted_density / total_all_lanes
        green_time = int(self.min_green + proportion * (self.max_green - self.min_green) * 2)
        green_time = max(self.min_green, min(self.max_green, green_time))
        return green_time

    def add_log(self, message, log_type="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {
            "time": timestamp,
            "message": message,
            "type": log_type
        }
        self.logs.append(log_entry)
        if len(self.logs) > 200:
            self.logs = self.logs[-200:]
        self.socketio.emit('new_log', log_entry)

    def update_signals_on_arduino(self):
        if not self.arduino:
            return
        for i in range(4):
            state = self.signal_states[i]
            if state == "RED":
                self.arduino.send_command(i, 'R')
            elif state == "YELLOW":
                self.arduino.send_command(i, 'Y')
            elif state == "GREEN":
                self.arduino.send_command(i, 'G')

    def emit_state(self, countdown=0, phase=""):
        state = {
            "cycle": self.cycle_number,
            "signal_states": self.signal_states.copy(),
            "signal_timings": self.signal_timings.copy(),
            "lane_densities": self.lane_densities.copy(),
            "lane_total_density": self.lane_total_density.copy(),
            "lane_names": self.lane_names,
            "current_green_lane": self.current_green_lane,
            "emergency_active": self.emergency_active,
            "emergency_lane": self.emergency_lane,
            "countdown": countdown,
            "phase": phase,
            "videos_uploaded": self.videos_uploaded.copy(),
            "processing_complete": self.processing_complete.copy()
        }
        self.socketio.emit('traffic_update', state)

    def simulate_processing(self, lane_index):
        self.processing_complete[lane_index] = False
        self.socketio.emit('processing_status', {
            "lane": lane_index,
            "status": "processing",
            "message": f"Analyzing vehicle density for {self.lane_names[lane_index]} lane..."
        })
        steps = [
            "Extracting frames from video feed...",
            "Applying background subtraction...",
            "Running vehicle detection model...",
            "Classifying vehicle types...",
            "Computing density metrics...",
            "Finalizing count..."
        ]
        for step in steps:
            time.sleep(random.uniform(0.3, 0.7))
            self.socketio.emit('processing_status', {
                "lane": lane_index,
                "status": "processing",
                "message": step,
                "progress": int((steps.index(step) + 1) / len(steps) * 100)
            })
        self.processing_complete[lane_index] = True
        self.socketio.emit('processing_status', {
            "lane": lane_index,
            "status": "complete",
            "message": "Density calculation complete.",
            "progress": 100
        })

    def handle_emergency(self, lane_index):
        self.emergency_active = True
        self.emergency_lane = lane_index
        self.add_log(f"EMERGENCY: Ambulance detected in {self.lane_names[lane_index]} lane!", "EMERGENCY")

        for i in range(4):
            if i == lane_index:
                self.signal_states[i] = "GREEN"
            else:
                self.signal_states[i] = "RED"

        self.update_signals_on_arduino()
        self.emit_state(countdown=0, phase="EMERGENCY")

    def clear_emergency(self):
        self.add_log(f"Emergency cleared for {self.lane_names[self.emergency_lane]} lane.", "INFO")
        self.emergency_active = False
        self.emergency_lane = -1
        self.emit_state(countdown=0, phase="RESUMING")

    def run_cycle(self):
        self.cycle_number += 1
        self.add_log(f"--- Cycle {self.cycle_number} Started ---", "CYCLE")

        for i in range(4):
            if self.videos_uploaded[i]:
                self.simulate_processing(i)
            density = self.generate_density(i)
            self.lane_densities[i] = density
            weighted = self.calculate_weighted_density(density)
            self.lane_total_density[i] = weighted
            self.add_log(f"{self.lane_names[i]}: {density} | Weighted: {weighted}", "DENSITY")

        total_all = sum(self.lane_total_density)
        for i in range(4):
            gt = self.calculate_green_time(self.lane_total_density[i], total_all)
            self.signal_timings[i] = gt

        sorted_lanes = sorted(range(4), key=lambda x: self.lane_total_density[x], reverse=True)

        for lane in sorted_lanes:
            if not self.running:
                return
            if self.emergency_active:
                while self.emergency_active and self.running:
                    time.sleep(0.5)
                if not self.running:
                    return

            self.add_log(f"GREEN phase for {self.lane_names[lane]} ({self.signal_timings[lane]}s)", "SIGNAL")

            for i in range(4):
                self.signal_states[i] = "RED"
            self.signal_states[lane] = "GREEN"
            self.current_green_lane = lane
            self.update_signals_on_arduino()

            green_time = self.signal_timings[lane]
            for t in range(green_time, 0, -1):
                if not self.running:
                    return
                if self.emergency_active:
                    break
                self.emit_state(countdown=t, phase="GREEN")
                time.sleep(1)

            if self.emergency_active:
                continue

            self.signal_states[lane] = "YELLOW"
            self.update_signals_on_arduino()
            self.add_log(f"YELLOW phase for {self.lane_names[lane]} ({self.yellow_time}s)", "SIGNAL")
            for t in range(self.yellow_time, 0, -1):
                if not self.running:
                    return
                self.emit_state(countdown=t, phase="YELLOW")
                time.sleep(1)

            self.signal_states[lane] = "RED"
            self.current_green_lane = -1
            self.update_signals_on_arduino()
            self.emit_state(countdown=0, phase="ALL_RED")
            time.sleep(self.all_red_time)

        self.add_log(f"--- Cycle {self.cycle_number} Completed ---", "CYCLE")

    def start(self):
        self.running = True
        self.add_log("Traffic system started.", "SYSTEM")

        def run_loop():
            while self.running:
                self.run_cycle()
            self.add_log("Traffic system stopped.", "SYSTEM")

        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()

    def stop(self):
        self.running = False
        for i in range(4):
            self.signal_states[i] = "RED"
        self.update_signals_on_arduino()
        self.emit_state(countdown=0, phase="STOPPED")