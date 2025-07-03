# WarpStream Architecture Examples

This document provides real-world architecture examples and patterns for building applications with WarpStream.

## 1. Real-time Analytics Pipeline

### Architecture Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Web App   │───▶│ WarpStream  │───▶│ Stream      │───▶│ Analytics   │
│ (Events)    │    │   Events    │    │ Processor   │    │ Dashboard   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                           │                   │                   │
                           ▼                   ▼                   ▼
                   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
                   │ Data Lake   │    │ Alerting    │    │ ML Pipeline │
                   │ (S3/Delta)  │    │ System      │    │ (Training)  │
                   └─────────────┘    └─────────────┘    └─────────────┘
```

### Implementation Example

```python
# Event Producer (Web Application)
from kafka import KafkaProducer
import json
import uuid
from datetime import datetime

class EventProducer:
    def __init__(self):
        self.producer = KafkaProducer(
            bootstrap_servers='your-warpstream-cluster:9092',
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None
        )
    
    def track_user_action(self, user_id, action, properties=None):
        event = {
            'event_id': str(uuid.uuid4()),
            'user_id': user_id,
            'action': action,
            'properties': properties or {},
            'timestamp': datetime.now().isoformat(),
            'session_id': self.get_session_id(user_id)
        }
        
        # Send to events topic
        self.producer.send('user_events', key=user_id, value=event)
        
        # Send to real-time topic for immediate processing
        self.producer.send('realtime_events', key=user_id, value=event)
    
    def track_page_view(self, user_id, page_url, referrer=None):
        self.track_user_action(user_id, 'page_view', {
            'page_url': page_url,
            'referrer': referrer
        })

# Stream Processor (Apache Flink/Kafka Streams)
from kafka import KafkaConsumer
import json
from collections import defaultdict
import time

class RealTimeProcessor:
    def __init__(self):
        self.consumer = KafkaConsumer(
            'realtime_events',
            group_id='realtime_processor',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            key_deserializer=lambda x: x.decode('utf-8') if x else None
        )
        
        # In-memory state for real-time aggregations
        self.user_sessions = defaultdict(list)
        self.page_views = defaultdict(int)
        self.active_users = set()
    
    def process_events(self):
        for message in self.consumer:
            event = message.value
            user_id = message.key
            
            # Update real-time metrics
            self.update_metrics(event, user_id)
            
            # Send alerts for specific conditions
            self.check_alerts(event, user_id)
            
            # Update dashboard
            self.update_dashboard()
    
    def update_metrics(self, event, user_id):
        # Track active users
        self.active_users.add(user_id)
        
        # Track page views
        if event['action'] == 'page_view':
            page = event['properties'].get('page_url', 'unknown')
            self.page_views[page] += 1
        
        # Track user session
        self.user_sessions[user_id].append(event)
        
        # Clean up old sessions (older than 30 minutes)
        cutoff_time = time.time() - 1800
        self.user_sessions[user_id] = [
            e for e in self.user_sessions[user_id]
            if time.time() - time.mktime(time.strptime(e['timestamp'], '%Y-%m-%dT%H:%M:%S.%f')) < cutoff_time
        ]
    
    def check_alerts(self, event, user_id):
        # Alert on high-value actions
        if event['action'] == 'purchase':
            self.send_alert(f"Purchase detected for user {user_id}: {event['properties']}")
        
        # Alert on unusual behavior
        if len(self.user_sessions[user_id]) > 100:
            self.send_alert(f"High activity detected for user {user_id}")
    
    def update_dashboard(self):
        # Send metrics to dashboard
        metrics = {
            'active_users': len(self.active_users),
            'total_page_views': sum(self.page_views.values()),
            'top_pages': dict(sorted(self.page_views.items(), key=lambda x: x[1], reverse=True)[:10])
        }
        
        # Send to dashboard topic
        self.send_to_dashboard(metrics)
```

## 2. Microservices Event Sourcing

### Architecture Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Order       │───▶│ WarpStream  │───▶│ Payment     │
│ Service     │    │   Events    │    │ Service     │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Inventory   │◀───│   Event     │───▶│ Shipping    │
│ Service     │    │   Store     │    │ Service     │
└─────────────┘    └─────────────┘    └─────────────┘
                           │
                           ▼
                   ┌─────────────┐
                   │ Analytics   │
                   │ Service     │
                   └─────────────┘
```

### Implementation Example

```python
# Event Sourcing Base Classes
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import json
from datetime import datetime
from kafka import KafkaProducer, KafkaConsumer

class Event:
    def __init__(self, event_type: str, aggregate_id: str, data: Dict[str, Any], version: int = 1):
        self.event_id = str(uuid.uuid4())
        self.event_type = event_type
        self.aggregate_id = aggregate_id
        self.data = data
        self.version = version
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self):
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'aggregate_id': self.aggregate_id,
            'data': self.data,
            'version': self.version,
            'timestamp': self.timestamp
        }

class Aggregate(ABC):
    def __init__(self, aggregate_id: str):
        self.aggregate_id = aggregate_id
        self.version = 0
        self.events: List[Event] = []
    
    @abstractmethod
    def apply_event(self, event: Event):
        """Apply an event to the aggregate"""
        pass
    
    def load_from_events(self, events: List[Event]):
        """Reconstruct aggregate from event stream"""
        for event in events:
            self.apply_event(event)
            self.version = event.version

# Order Service Example
class Order(Aggregate):
    def __init__(self, order_id: str):
        super().__init__(order_id)
        self.status = 'created'
        self.items = []
        self.total_amount = 0.0
        self.customer_id = None
    
    def apply_event(self, event: Event):
        if event.event_type == 'OrderCreated':
            self.customer_id = event.data['customer_id']
            self.items = event.data['items']
            self.total_amount = event.data['total_amount']
            self.status = 'created'
        
        elif event.event_type == 'OrderConfirmed':
            self.status = 'confirmed'
        
        elif event.event_type == 'OrderShipped':
            self.status = 'shipped'
        
        elif event.event_type == 'OrderDelivered':
            self.status = 'delivered'
    
    def create_order(self, customer_id: str, items: List[Dict], total_amount: float):
        event = Event(
            event_type='OrderCreated',
            aggregate_id=self.aggregate_id,
            data={
                'customer_id': customer_id,
                'items': items,
                'total_amount': total_amount
            },
            version=self.version + 1
        )
        return event
    
    def confirm_order(self):
        event = Event(
            event_type='OrderConfirmed',
            aggregate_id=self.aggregate_id,
            data={},
            version=self.version + 1
        )
        return event

class OrderService:
    def __init__(self):
        self.producer = KafkaProducer(
            bootstrap_servers='your-warpstream-cluster:9092',
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None
        )
        
        self.consumer = KafkaConsumer(
            'order_events',
            group_id='order_service',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            key_deserializer=lambda x: x.decode('utf-8') if x else None
        )
        
        # In-memory order store (in production, use a database)
        self.orders = {}
    
    def create_order(self, customer_id: str, items: List[Dict], total_amount: float):
        order_id = str(uuid.uuid4())
        order = Order(order_id)
        
        # Create the order creation event
        event = order.create_order(customer_id, items, total_amount)
        
        # Apply event to aggregate
        order.apply_event(event)
        
        # Store order
        self.orders[order_id] = order
        
        # Publish event
        self.producer.send('order_events', key=order_id, value=event.to_dict())
        
        return order_id
    
    def confirm_order(self, order_id: str):
        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")
        
        order = self.orders[order_id]
        event = order.confirm_order()
        
        # Apply event to aggregate
        order.apply_event(event)
        
        # Publish event
        self.producer.send('order_events', key=order_id, value=event.to_dict())
    
    def get_order(self, order_id: str):
        if order_id not in self.orders:
            # Try to reconstruct from event stream
            events = self.load_events(order_id)
            if events:
                order = Order(order_id)
                order.load_from_events(events)
                self.orders[order_id] = order
                return order
            return None
        
        return self.orders[order_id]
    
    def load_events(self, aggregate_id: str) -> List[Event]:
        """Load events for an aggregate from the event store"""
        # In a real implementation, this would query the event store
        # For now, we'll return an empty list
        return []

# Payment Service Example
class PaymentService:
    def __init__(self):
        self.consumer = KafkaConsumer(
            'order_events',
            group_id='payment_service',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            key_deserializer=lambda x: x.decode('utf-8') if x else None
        )
        
        self.producer = KafkaProducer(
            bootstrap_servers='your-warpstream-cluster:9092',
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None
        )
    
    def process_order_events(self):
        for message in self.consumer:
            event_data = message.value
            order_id = message.key
            
            if event_data['event_type'] == 'OrderCreated':
                # Process payment for new order
                self.process_payment(order_id, event_data['data'])
            
            elif event_data['event_type'] == 'OrderConfirmed':
                # Payment was successful, order confirmed
                self.record_payment_success(order_id)
    
    def process_payment(self, order_id: str, order_data: Dict):
        # Simulate payment processing
        payment_successful = self.charge_customer(order_data['customer_id'], order_data['total_amount'])
        
        if payment_successful:
            # Publish payment success event
            event = Event(
                event_type='PaymentSucceeded',
                aggregate_id=order_id,
                data={'amount': order_data['total_amount']}
            )
            self.producer.send('payment_events', key=order_id, value=event.to_dict())
        else:
            # Publish payment failure event
            event = Event(
                event_type='PaymentFailed',
                aggregate_id=order_id,
                data={'amount': order_data['total_amount']}
            )
            self.producer.send('payment_events', key=order_id, value=event.to_dict())
    
    def charge_customer(self, customer_id: str, amount: float) -> bool:
        # Simulate payment processing
        import random
        return random.random() > 0.1  # 90% success rate
```

## 3. IoT Data Pipeline

### Architecture Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ IoT Devices │───▶│ WarpStream  │───▶│ Stream      │───▶│ Alerting    │
│ (Sensors)   │    │   Ingest    │    │ Processor   │    │ System      │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                           │                   │                   │
                           ▼                   ▼                   ▼
                   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
                   │ Time Series │    │ ML Model    │    │ Dashboard   │
                   │ Database    │    │ (Anomaly)   │    │ (Real-time) │
                   └─────────────┘    └─────────────┘    └─────────────┘
```

### Implementation Example

```python
# IoT Data Producer
import random
import time
from datetime import datetime

class IoTSensor:
    def __init__(self, sensor_id: str, sensor_type: str):
        self.sensor_id = sensor_id
        self.sensor_type = sensor_type
        self.producer = KafkaProducer(
            bootstrap_servers='your-warpstream-cluster:9092',
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None
        )
    
    def generate_reading(self):
        """Generate a sensor reading"""
        if self.sensor_type == 'temperature':
            # Simulate temperature sensor (15-35°C with some noise)
            base_temp = 25
            noise = random.uniform(-5, 5)
            value = base_temp + noise
            
        elif self.sensor_type == 'humidity':
            # Simulate humidity sensor (30-80% with some noise)
            base_humidity = 55
            noise = random.uniform(-10, 10)
            value = max(0, min(100, base_humidity + noise))
            
        elif self.sensor_type == 'pressure':
            # Simulate pressure sensor (1000-1020 hPa with some noise)
            base_pressure = 1013
            noise = random.uniform(-5, 5)
            value = base_pressure + noise
        
        return {
            'sensor_id': self.sensor_id,
            'sensor_type': self.sensor_type,
            'value': round(value, 2),
            'timestamp': datetime.now().isoformat(),
            'location': 'building_a_floor_2',
            'battery_level': random.uniform(0.3, 1.0)
        }
    
    def send_reading(self):
        """Send a sensor reading to WarpStream"""
        reading = self.generate_reading()
        
        # Send to raw sensor data topic
        self.producer.send('sensor_data', key=self.sensor_id, value=reading)
        
        # Send to real-time processing topic
        self.producer.send('realtime_sensor_data', key=self.sensor_id, value=reading)
        
        print(f"📡 {self.sensor_id} ({self.sensor_type}): {reading['value']}")
    
    def run_continuous(self, interval_seconds=5):
        """Run sensor continuously"""
        print(f"🚀 Starting {self.sensor_id} ({self.sensor_type}) sensor")
        
        while True:
            try:
                self.send_reading()
                time.sleep(interval_seconds)
            except KeyboardInterrupt:
                print(f"⏹️  Stopping {self.sensor_id}")
                break

# Stream Processor for IoT Data
class IoTSensorProcessor:
    def __init__(self):
        self.consumer = KafkaConsumer(
            'realtime_sensor_data',
            group_id='iot_processor',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            key_deserializer=lambda x: x.decode('utf-8') if x else None
        )
        
        self.producer = KafkaProducer(
            bootstrap_servers='your-warpstream-cluster:9092',
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None
        )
        
        # Store recent readings for anomaly detection
        self.sensor_history = defaultdict(list)
        self.alert_thresholds = {
            'temperature': {'min': 10, 'max': 40},
            'humidity': {'min': 20, 'max': 90},
            'pressure': {'min': 990, 'max': 1030}
        }
    
    def process_sensor_data(self):
        for message in self.consumer:
            sensor_data = message.value
            sensor_id = message.key
            
            # Store in history (keep last 100 readings)
            self.sensor_history[sensor_id].append(sensor_data)
            if len(self.sensor_history[sensor_id]) > 100:
                self.sensor_history[sensor_id].pop(0)
            
            # Check for anomalies
            if self.detect_anomaly(sensor_data):
                self.send_alert(sensor_data, 'anomaly_detected')
            
            # Check for threshold violations
            if self.check_thresholds(sensor_data):
                self.send_alert(sensor_data, 'threshold_violation')
            
            # Check for low battery
            if sensor_data['battery_level'] < 0.2:
                self.send_alert(sensor_data, 'low_battery')
            
            # Send to time series database
            self.send_to_timeseries(sensor_data)
    
    def detect_anomaly(self, sensor_data):
        """Simple anomaly detection based on statistical outliers"""
        sensor_id = sensor_data['sensor_id']
        sensor_type = sensor_data['sensor_type']
        current_value = sensor_data['value']
        
        if len(self.sensor_history[sensor_id]) < 10:
            return False  # Need more data
        
        # Calculate mean and standard deviation
        values = [reading['value'] for reading in self.sensor_history[sensor_id][-20:]]
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std_dev = variance ** 0.5
        
        # Check if current value is more than 2 standard deviations from mean
        if abs(current_value - mean) > 2 * std_dev:
            return True
        
        return False
    
    def check_thresholds(self, sensor_data):
        """Check if sensor reading violates thresholds"""
        sensor_type = sensor_data['sensor_type']
        value = sensor_data['value']
        
        if sensor_type in self.alert_thresholds:
            thresholds = self.alert_thresholds[sensor_type]
            if value < thresholds['min'] or value > thresholds['max']:
                return True
        
        return False
    
    def send_alert(self, sensor_data, alert_type):
        """Send alert to alerting system"""
        alert = {
            'alert_id': str(uuid.uuid4()),
            'alert_type': alert_type,
            'sensor_id': sensor_data['sensor_id'],
            'sensor_type': sensor_data['sensor_type'],
            'value': sensor_data['value'],
            'threshold': self.alert_thresholds.get(sensor_data['sensor_type'], {}),
            'timestamp': datetime.now().isoformat(),
            'location': sensor_data['location'],
            'severity': 'high' if alert_type == 'anomaly_detected' else 'medium'
        }
        
        self.producer.send('alerts', key=sensor_data['sensor_id'], value=alert)
        print(f"🚨 Alert: {alert_type} for {sensor_data['sensor_id']} ({sensor_data['value']})")
    
    def send_to_timeseries(self, sensor_data):
        """Send data to time series database"""
        # In a real implementation, this would send to InfluxDB, TimescaleDB, etc.
        timeseries_data = {
            'measurement': sensor_data['sensor_type'],
            'tags': {
                'sensor_id': sensor_data['sensor_id'],
                'location': sensor_data['location']
            },
            'fields': {
                'value': sensor_data['value'],
                'battery_level': sensor_data['battery_level']
            },
            'timestamp': sensor_data['timestamp']
        }
        
        # Send to timeseries topic
        self.producer.send('timeseries_data', key=sensor_data['sensor_id'], value=timeseries_data)

# Usage Example
if __name__ == "__main__":
    # Create sensors
    sensors = [
        IoTSensor('temp_001', 'temperature'),
        IoTSensor('hum_001', 'humidity'),
        IoTSensor('press_001', 'pressure')
    ]
    
    # Start sensors in separate threads
    import threading
    
    sensor_threads = []
    for sensor in sensors:
        thread = threading.Thread(target=sensor.run_continuous, args=(3,))
        thread.daemon = True
        thread.start()
        sensor_threads.append(thread)
    
    # Start processor
    processor = IoTSensorProcessor()
    processor.process_sensor_data()
```

## 4. CQRS (Command Query Responsibility Segregation)

### Architecture Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Commands    │───▶│ WarpStream  │───▶│ Event       │
│ (Write)     │    │   Events    │    │ Handlers    │
└─────────────┘    └─────────────┘    └─────────────┘
                           │                   │
                           ▼                   ▼
                   ┌─────────────┐    ┌─────────────┐
                   │ Read Models │    │ Query       │
                   │ (Projection)│    │ Handlers    │
                   └─────────────┘    └─────────────┘
                           │                   │
                           ▼                   ▼
                   ┌─────────────┐    ┌─────────────┐
                   │ Read        │    │ API         │
                   │ Database    │    │ (Queries)   │
                   └─────────────┘    └─────────────┘
```

### Implementation Example

```python
# Command Handler
class CommandHandler:
    def __init__(self):
        self.producer = KafkaProducer(
            bootstrap_servers='your-warpstream-cluster:9092',
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None
        )
    
    def handle_create_user(self, command):
        """Handle CreateUser command"""
        event = Event(
            event_type='UserCreated',
            aggregate_id=command['user_id'],
            data={
                'username': command['username'],
                'email': command['email'],
                'created_at': datetime.now().isoformat()
            }
        )
        
        # Publish event
        self.producer.send('user_events', key=command['user_id'], value=event.to_dict())
        return event
    
    def handle_update_user(self, command):
        """Handle UpdateUser command"""
        event = Event(
            event_type='UserUpdated',
            aggregate_id=command['user_id'],
            data={
                'username': command.get('username'),
                'email': command.get('email'),
                'updated_at': datetime.now().isoformat()
            }
        )
        
        # Publish event
        self.producer.send('user_events', key=command['user_id'], value=event.to_dict())
        return event

# Event Handler (Projection)
class UserProjection:
    def __init__(self):
        self.consumer = KafkaConsumer(
            'user_events',
            group_id='user_projection',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            key_deserializer=lambda x: x.decode('utf-8') if x else None
        )
        
        # In-memory read model (in production, use a database)
        self.users = {}
    
    def process_events(self):
        for message in self.consumer:
            event_data = message.value
            user_id = message.key
            
            if event_data['event_type'] == 'UserCreated':
                self.create_user_read_model(user_id, event_data['data'])
            
            elif event_data['event_type'] == 'UserUpdated':
                self.update_user_read_model(user_id, event_data['data'])
    
    def create_user_read_model(self, user_id, data):
        """Create user read model"""
        self.users[user_id] = {
            'user_id': user_id,
            'username': data['username'],
            'email': data['email'],
            'created_at': data['created_at'],
            'updated_at': data['created_at']
        }
    
    def update_user_read_model(self, user_id, data):
        """Update user read model"""
        if user_id in self.users:
            if 'username' in data:
                self.users[user_id]['username'] = data['username']
            if 'email' in data:
                self.users[user_id]['email'] = data['email']
            self.users[user_id]['updated_at'] = data['updated_at']
    
    def get_user(self, user_id):
        """Get user from read model"""
        return self.users.get(user_id)
    
    def get_all_users(self):
        """Get all users from read model"""
        return list(self.users.values())

# Query Handler
class QueryHandler:
    def __init__(self, projection):
        self.projection = projection
    
    def get_user(self, user_id):
        """Handle GetUser query"""
        return self.projection.get_user(user_id)
    
    def get_all_users(self):
        """Handle GetAllUsers query"""
        return self.projection.get_all_users()
    
    def search_users(self, query):
        """Handle SearchUsers query"""
        users = self.projection.get_all_users()
        return [
            user for user in users
            if query.lower() in user['username'].lower() or
               query.lower() in user['email'].lower()
        ]

# API Layer
from flask import Flask, request, jsonify

app = Flask(__name__)

# Initialize components
command_handler = CommandHandler()
user_projection = UserProjection()
query_handler = QueryHandler(user_projection)

# Start event processing in background
import threading
projection_thread = threading.Thread(target=user_projection.process_events)
projection_thread.daemon = True
projection_thread.start()

@app.route('/users', methods=['POST'])
def create_user():
    """Create user command"""
    command = request.json
    command['user_id'] = str(uuid.uuid4())
    
    event = command_handler.handle_create_user(command)
    
    return jsonify({
        'user_id': command['user_id'],
        'message': 'User created successfully'
    }), 201

@app.route('/users/<user_id>', methods=['PUT'])
def update_user(user_id):
    """Update user command"""
    command = request.json
    command['user_id'] = user_id
    
    event = command_handler.handle_update_user(command)
    
    return jsonify({
        'message': 'User updated successfully'
    }), 200

@app.route('/users/<user_id>', methods=['GET'])
def get_user(user_id):
    """Get user query"""
    user = query_handler.get_user(user_id)
    
    if user:
        return jsonify(user), 200
    else:
        return jsonify({'error': 'User not found'}), 404

@app.route('/users', methods=['GET'])
def get_all_users():
    """Get all users query"""
    users = query_handler.get_all_users()
    return jsonify(users), 200

@app.route('/users/search', methods=['GET'])
def search_users():
    """Search users query"""
    query = request.args.get('q', '')
    users = query_handler.search_users(query)
    return jsonify(users), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

## Resources

- [Event Sourcing Pattern](https://martinfowler.com/eaaDev/EventSourcing.html)
- [CQRS Pattern](https://martinfowler.com/bliki/CQRS.html)
- [Microservices Patterns](https://microservices.io/patterns/)
- [IoT Architecture Patterns](https://aws.amazon.com/architecture/iot/)
- [Real-time Analytics](https://www.confluent.io/blog/real-time-analytics/) 