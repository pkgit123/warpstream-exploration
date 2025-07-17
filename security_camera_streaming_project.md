# Security Camera Streaming Project

Real-time processing and analytics for Tapo and Arlo security cameras using WarpStream.

## Project Overview

Build a real-time security monitoring system that processes camera feeds, detects events, and provides intelligent insights using streaming data processing.

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Security    │───▶│ WarpStream  │───▶│ Event       │───▶│ Real-time   │
│ Cameras     │    │   Events    │    │ Processor   │    │ Dashboard   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │                   │
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Tapo RTSP   │    │ Local       │    │ Motion      │    │ Web App     │
│ Streams     │    │ Development │    │ Detection   │    │ (Vercel)    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │                   │
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Arlo API    │    │ Free Tier   │    │ Alerting    │    │ Mobile      │
│ Events      │    │ Production  │    │ System      │    │ App         │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## Camera Integration

### Tapo Camera Setup

#### 1. Enable RTSP Stream
```bash
# Access camera settings via Tapo app
# Enable RTSP stream and note credentials
# Default RTSP URL format: rtsp://username:password@camera_ip:554/stream1
```

#### 2. Python RTSP Processor
```python
# tapo_stream_processor.py
import cv2
import numpy as np
import json
import time
from datetime import datetime
from kafka import KafkaProducer
import threading

class TapoStreamProcessor:
    def __init__(self, camera_config):
        self.camera_config = camera_config
        self.producer = KafkaProducer(
            bootstrap_servers='localhost:9092',
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.running = False
        
    def start_streaming(self):
        """Start processing RTSP stream"""
        self.running = True
        thread = threading.Thread(target=self._process_stream)
        thread.daemon = True
        thread.start()
        return thread
    
    def _process_stream(self):
        """Process RTSP stream and detect events"""
        rtsp_url = self.camera_config['rtsp_url']
        cap = cv2.VideoCapture(rtsp_url)
        
        # Motion detection setup
        motion_detector = cv2.createBackgroundSubtractorMOG2(
            history=100, varThreshold=40, detectShadows=True
        )
        
        frame_count = 0
        
        while self.running:
            ret, frame = cap.read()
            if not ret:
                print(f"Failed to read frame from {self.camera_config['name']}")
                time.sleep(5)
                continue
            
            frame_count += 1
            
            # Process every 5th frame to reduce load
            if frame_count % 5 == 0:
                # Motion detection
                motion_mask = motion_detector.apply(frame)
                motion_score = np.sum(motion_mask) / (motion_mask.shape[0] * motion_mask.shape[1])
                
                # Send motion data
                if motion_score > 1000:  # Threshold for motion detection
                    event = {
                        'camera_id': self.camera_config['id'],
                        'camera_name': self.camera_config['name'],
                        'event_type': 'motion_detected',
                        'motion_score': float(motion_score),
                        'timestamp': datetime.now().isoformat(),
                        'location': self.camera_config['location']
                    }
                    self.producer.send('security_events', value=event)
                
                # Send periodic status update
                if frame_count % 300 == 0:  # Every 300 frames
                    status_event = {
                        'camera_id': self.camera_config['id'],
                        'camera_name': self.camera_config['name'],
                        'event_type': 'status_update',
                        'status': 'online',
                        'frame_count': frame_count,
                        'timestamp': datetime.now().isoformat()
                    }
                    self.producer.send('camera_status', value=status_event)
            
            time.sleep(0.1)  # 10 FPS processing
        
        cap.release()
    
    def stop_streaming(self):
        """Stop processing stream"""
        self.running = False
```

### Arlo Camera Setup

#### 1. API Authentication
```python
# arlo_api_client.py
import requests
import json
from datetime import datetime, timedelta

class ArloAPI:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.base_url = "https://arlo.netgear.com/hmsweb"
        self.session = requests.Session()
        self.authenticate()
    
    def authenticate(self):
        """Authenticate with Arlo API"""
        auth_data = {
            'email': self.email,
            'password': self.password
        }
        
        response = self.session.post(f"{self.base_url}/login", json=auth_data)
        if response.status_code == 200:
            data = response.json()
            self.auth_token = data['data']['token']
            self.session.headers.update({'Authorization': f'Bearer {self.auth_token}'})
            print("✅ Arlo authentication successful")
        else:
            raise Exception("Arlo authentication failed")
    
    def get_devices(self):
        """Get list of Arlo devices"""
        response = self.session.get(f"{self.base_url}/users/devices")
        if response.status_code == 200:
            return response.json()['data']
        return []
    
    def get_motion_events(self, device_id, hours_back=1):
        """Get motion events for a device"""
        from_date = (datetime.now() - timedelta(hours=hours_back)).isoformat()
        to_date = datetime.now().isoformat()
        
        params = {
            'deviceId': device_id,
            'fromDate': from_date,
            'toDate': to_date
        }
        
        response = self.session.get(f"{self.base_url}/users/devices/events", params=params)
        if response.status_code == 200:
            return response.json()['data']
        return []
```

#### 2. Arlo Event Processor
```python
# arlo_event_processor.py
import time
import json
from datetime import datetime
from kafka import KafkaProducer
from arlo_api_client import ArloAPI

class ArloEventProcessor:
    def __init__(self, arlo_config):
        self.arlo = ArloAPI(arlo_config['email'], arlo_config['password'])
        self.producer = KafkaProducer(
            bootstrap_servers='localhost:9092',
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.processed_events = set()
    
    def process_events(self):
        """Process Arlo motion events"""
        devices = self.arlo.get_devices()
        
        for device in devices:
            if device['deviceType'] == 'camera':
                events = self.arlo.get_motion_events(device['deviceId'])
                
                for event in events:
                    event_id = event.get('uniqueId')
                    
                    # Avoid processing duplicate events
                    if event_id not in self.processed_events:
                        self.processed_events.add(event_id)
                        
                        # Send to WarpStream
                        stream_event = {
                            'camera_id': device['deviceId'],
                            'camera_name': device.get('deviceName', 'Unknown'),
                            'event_type': 'motion_detected',
                            'event_id': event_id,
                            'timestamp': event.get('timestamp'),
                            'location': device.get('location', {}),
                            'media_url': event.get('presignedContentUrl'),
                            'source': 'arlo_api'
                        }
                        
                        self.producer.send('security_events', value=stream_event)
                        print(f"📹 Arlo event processed: {device.get('deviceName')}")
    
    def run_continuous(self, interval_seconds=30):
        """Run continuous event processing"""
        print("🚀 Starting Arlo event processing...")
        
        while True:
            try:
                self.process_events()
                time.sleep(interval_seconds)
            except Exception as e:
                print(f"❌ Error processing Arlo events: {e}")
                time.sleep(60)  # Wait longer on error
```

## Stream Processing Pipeline

### 1. Event Aggregator
```python
# event_aggregator.py
from kafka import KafkaConsumer, KafkaProducer
import json
from collections import defaultdict
from datetime import datetime, timedelta

class SecurityEventAggregator:
    def __init__(self):
        self.consumer = KafkaConsumer(
            'security_events',
            group_id='security_aggregator',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            bootstrap_servers='localhost:9092'
        )
        
        self.producer = KafkaProducer(
            bootstrap_servers='localhost:9092',
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        # In-memory state for aggregations
        self.hourly_stats = defaultdict(lambda: {
            'motion_events': 0,
            'cameras_active': set(),
            'locations': defaultdict(int)
        })
    
    def process_events(self):
        """Process and aggregate security events"""
        for message in self.consumer:
            event = message.value
            timestamp = datetime.fromisoformat(event['timestamp'])
            hour_key = timestamp.strftime('%Y-%m-%d %H:00')
            
            # Update hourly statistics
            if event['event_type'] == 'motion_detected':
                self.hourly_stats[hour_key]['motion_events'] += 1
                self.hourly_stats[hour_key]['cameras_active'].add(event['camera_id'])
                self.hourly_stats[hour_key]['locations'][event.get('location', 'unknown')] += 1
            
            # Generate insights
            insights = self.generate_insights(hour_key)
            if insights:
                self.producer.send('security_insights', value=insights)
    
    def generate_insights(self, hour_key):
        """Generate insights from aggregated data"""
        stats = self.hourly_stats[hour_key]
        
        # Calculate activity level
        activity_level = 'low'
        if stats['motion_events'] > 10:
            activity_level = 'high'
        elif stats['motion_events'] > 5:
            activity_level = 'medium'
        
        # Find most active location
        most_active_location = max(stats['locations'].items(), key=lambda x: x[1])[0] if stats['locations'] else 'none'
        
        insights = {
            'hour': hour_key,
            'activity_level': activity_level,
            'total_motion_events': stats['motion_events'],
            'active_cameras': len(stats['cameras_active']),
            'most_active_location': most_active_location,
            'location_breakdown': dict(stats['locations']),
            'timestamp': datetime.now().isoformat()
        }
        
        return insights
```

### 2. Alert System
```python
# alert_system.py
from kafka import KafkaConsumer
import json
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

class SecurityAlertSystem:
    def __init__(self, alert_config):
        self.alert_config = alert_config
        self.consumer = KafkaConsumer(
            'security_events',
            group_id='alert_system',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            bootstrap_servers='localhost:9092'
        )
        
        # Alert thresholds
        self.motion_threshold = 5  # Events per minute
        self.recent_events = []
    
    def process_alerts(self):
        """Process events and generate alerts"""
        for message in self.consumer:
            event = message.value
            timestamp = datetime.fromisoformat(event['timestamp'])
            
            # Add to recent events
            self.recent_events.append({
                'timestamp': timestamp,
                'camera': event['camera_name'],
                'location': event.get('location', 'unknown')
            })
            
            # Remove old events (older than 1 minute)
            cutoff_time = datetime.now() - timedelta(minutes=1)
            self.recent_events = [
                e for e in self.recent_events 
                if e['timestamp'] > cutoff_time
            ]
            
            # Check for high activity
            if len(self.recent_events) >= self.motion_threshold:
                self.send_alert('high_activity', {
                    'event_count': len(self.recent_events),
                    'time_window': '1 minute',
                    'locations': list(set(e['location'] for e in self.recent_events))
                })
            
            # Check for unusual patterns
            if self.detect_unusual_pattern(event):
                self.send_alert('unusual_activity', {
                    'camera': event['camera_name'],
                    'location': event.get('location', 'unknown'),
                    'event_type': event['event_type']
                })
    
    def detect_unusual_pattern(self, event):
        """Detect unusual activity patterns"""
        # Example: Detect activity during unusual hours (2 AM - 6 AM)
        timestamp = datetime.fromisoformat(event['timestamp'])
        if 2 <= timestamp.hour <= 6:
            return True
        return False
    
    def send_alert(self, alert_type, data):
        """Send alert via email/SMS"""
        if alert_type == 'high_activity':
            subject = f"🚨 High Security Activity Detected"
            body = f"""
            High activity detected in your security system:
            
            - Events: {data['event_count']} in {data['time_window']}
            - Locations: {', '.join(data['locations'])}
            - Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
            Check your security dashboard for details.
            """
        else:
            subject = f"⚠️ Unusual Activity Detected"
            body = f"""
            Unusual activity detected:
            
            - Camera: {data['camera']}
            - Location: {data['location']}
            - Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
            Check your security dashboard for details.
            """
        
        # Send email alert
        self.send_email_alert(subject, body)
        print(f"📧 Alert sent: {alert_type}")
    
    def send_email_alert(self, subject, body):
        """Send email alert"""
        # Implementation depends on your email service
        # Example using Gmail SMTP
        pass
```

## Real-time Dashboard

### 1. Web Dashboard
```python
# dashboard_app.py
from flask import Flask, render_template, jsonify
from kafka import KafkaConsumer
import json
import threading
import time

app = Flask(__name__)

# Global state for dashboard
dashboard_data = {
    'recent_events': [],
    'hourly_stats': {},
    'camera_status': {},
    'alerts': []
}

class DashboardDataCollector:
    def __init__(self):
        self.consumer = KafkaConsumer(
            'security_events',
            'security_insights',
            'camera_status',
            group_id='dashboard_collector',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            bootstrap_servers='localhost:9092'
        )
    
    def collect_data(self):
        """Collect data for dashboard"""
        for message in self.consumer:
            event = message.value
            
            if message.topic == 'security_events':
                dashboard_data['recent_events'].append(event)
                # Keep only last 50 events
                if len(dashboard_data['recent_events']) > 50:
                    dashboard_data['recent_events'].pop(0)
            
            elif message.topic == 'security_insights':
                dashboard_data['hourly_stats'] = event
            
            elif message.topic == 'camera_status':
                dashboard_data['camera_status'][event['camera_id']] = event

# Start data collection
collector = DashboardDataCollector()
collector_thread = threading.Thread(target=collector.collect_data)
collector_thread.daemon = True
collector_thread.start()

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/events')
def get_events():
    return jsonify(dashboard_data['recent_events'])

@app.route('/api/stats')
def get_stats():
    return jsonify(dashboard_data['hourly_stats'])

@app.route('/api/cameras')
def get_cameras():
    return jsonify(dashboard_data['camera_status'])

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

### 2. Dashboard HTML
```html
<!-- templates/dashboard.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Security Camera Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .dashboard { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .card { border: 1px solid #ddd; padding: 20px; border-radius: 8px; }
        .event { background: #f5f5f5; padding: 10px; margin: 5px 0; border-radius: 4px; }
        .alert { background: #ffebee; border-left: 4px solid #f44336; }
    </style>
</head>
<body>
    <h1>🏠 Security Camera Dashboard</h1>
    
    <div class="dashboard">
        <div class="card">
            <h2>Recent Events</h2>
            <div id="events"></div>
        </div>
        
        <div class="card">
            <h2>Activity Statistics</h2>
            <div id="stats"></div>
        </div>
        
        <div class="card">
            <h2>Camera Status</h2>
            <div id="cameras"></div>
        </div>
        
        <div class="card">
            <h2>Activity Chart</h2>
            <div id="chart"></div>
        </div>
    </div>
    
    <script>
        // Update dashboard every 5 seconds
        setInterval(updateDashboard, 5000);
        
        function updateDashboard() {
            // Fetch and update events
            fetch('/api/events')
                .then(response => response.json())
                .then(events => {
                    const eventsDiv = document.getElementById('events');
                    eventsDiv.innerHTML = events.map(event => `
                        <div class="event">
                            <strong>${event.camera_name}</strong> - ${event.event_type}<br>
                            <small>${new Date(event.timestamp).toLocaleString()}</small>
                        </div>
                    `).join('');
                });
            
            // Fetch and update stats
            fetch('/api/stats')
                .then(response => response.json())
                .then(stats => {
                    const statsDiv = document.getElementById('stats');
                    statsDiv.innerHTML = `
                        <p><strong>Activity Level:</strong> ${stats.activity_level}</p>
                        <p><strong>Total Events:</strong> ${stats.total_motion_events}</p>
                        <p><strong>Active Cameras:</strong> ${stats.active_cameras}</p>
                        <p><strong>Most Active Location:</strong> ${stats.most_active_location}</p>
                    `;
                });
        }
        
        // Initial load
        updateDashboard();
    </script>
</body>
</html>
```

## Cost Breakdown

### Development Phase (Month 1)
- **Local Development**: $0
- **Camera APIs**: $0 (using existing cameras)
- **Processing**: Local machine
- **Total**: $0

### Production Phase (Month 2+)
- **WarpStream**: $0-10/month (free tier + minimal usage)
- **Vercel Hosting**: $0 (free tier)
- **Email Alerts**: $0 (Gmail SMTP)
- **Total**: $0-10/month

### Advanced Features (Month 3+)
- **Cloud Processing**: $5-15/month (if needed)
- **Storage**: $5-10/month (for video clips)
- **Total**: $10-25/month

## Getting Started

1. **Set up local environment** with Docker Kafka
2. **Configure camera access** (RTSP for Tapo, API for Arlo)
3. **Build basic event processing** pipeline
4. **Create simple dashboard** to view events
5. **Add alerting system** for notifications
6. **Deploy to production** with WarpStream

This project gives you hands-on experience with:
- **IoT data processing**
- **Real-time streaming**
- **Computer vision** (motion detection)
- **API integration**
- **Real-time dashboards**
- **Alert systems**

And it's all using your existing security cameras! 