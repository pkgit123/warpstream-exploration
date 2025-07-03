# WarpStream Deployment Guide

This guide provides best practices and examples for deploying applications that use WarpStream for real-time data streaming.

## Why Use WarpStream for Deployment?

WarpStream offers several advantages for production deployments:

### Infrastructure Benefits
- **No cluster management**: Fully managed service
- **Automatic scaling**: Handles traffic spikes automatically
- **High availability**: Built-in redundancy and failover
- **Global distribution**: Multi-region support

### Operational Benefits
- **Reduced DevOps overhead**: No Kafka cluster maintenance
- **Cost optimization**: Pay-per-use pricing
- **Security**: Built-in authentication and encryption
- **Monitoring**: Integrated observability tools

## Deployment Architecture Patterns

### 1. Microservices with Event Streaming

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Service A │───▶│ WarpStream  │───▶│  Service B  │
│ (Producer)  │    │   (Kafka)   │    │ (Consumer)  │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Service C │◀───│   Topics    │───▶│  Service D  │
│ (Consumer)  │    │             │    │ (Consumer)  │
└─────────────┘    └─────────────┘    └─────────────┘
```

### 2. Data Pipeline Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Data Source │───▶│ WarpStream  │───▶│ Stream      │
│ (API/DB)    │    │   Ingest    │    │ Processor   │
└─────────────┘    └─────────────┘    └─────────────┘
                           │                   │
                           ▼                   ▼
                   ┌─────────────┐    ┌─────────────┐
                   │ Analytics   │    │ Data Lake   │
                   │ Dashboard   │    │ (S3/etc.)   │
                   └─────────────┘    └─────────────┘
```

### 3. Real-time Application Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Web App   │───▶│ WarpStream  │───▶│ Real-time   │
│ (Frontend)  │    │   Events    │    │ Dashboard   │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Mobile App  │◀───│   Notify    │───▶│ Alerting    │
│ (Consumer)  │    │   Service   │    │ System      │
└─────────────┘    └─────────────┘    └─────────────┘
```

## Configuration Management

### Environment Variables

```bash
# WarpStream Configuration
WARPSTREAM_BOOTSTRAP_SERVERS=your-cluster.warpstream.com:9092
WARPSTREAM_API_KEY=your_api_key_here
WARPSTREAM_SECURITY_PROTOCOL=SASL_SSL
WARPSTREAM_SASL_MECHANISM=PLAIN

# Application Configuration
APP_ENV=production
LOG_LEVEL=INFO
METRICS_ENABLED=true
HEALTH_CHECK_PORT=8080
```

### Docker Configuration

```dockerfile
# Dockerfile for WarpStream application
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')"

# Run application
CMD ["python", "main.py"]
```

### Kubernetes Configuration

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: warpstream-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: warpstream-app
  template:
    metadata:
      labels:
        app: warpstream-app
    spec:
      containers:
      - name: app
        image: your-registry/warpstream-app:latest
        ports:
        - containerPort: 8080
        env:
        - name: WARPSTREAM_BOOTSTRAP_SERVERS
          valueFrom:
            secretKeyRef:
              name: warpstream-secrets
              key: bootstrap-servers
        - name: WARPSTREAM_API_KEY
          valueFrom:
            secretKeyRef:
              name: warpstream-secrets
              key: api-key
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
```

## Security Best Practices

### 1. API Key Management

```python
# Use environment variables for API keys
import os
from dotenv import load_dotenv

load_dotenv()

WARPSTREAM_API_KEY = os.getenv('WARPSTREAM_API_KEY')
if not WARPSTREAM_API_KEY:
    raise ValueError("WARPSTREAM_API_KEY environment variable is required")
```

### 2. SSL/TLS Configuration

```python
# Producer configuration with SSL
producer_config = {
    'bootstrap_servers': 'your-cluster.warpstream.com:9092',
    'security_protocol': 'SASL_SSL',
    'sasl_mechanism': 'PLAIN',
    'sasl_plain_username': WARPSTREAM_API_KEY,
    'sasl_plain_password': WARPSTREAM_API_KEY,
    'ssl_check_hostname': True,
    'ssl_cafile': '/path/to/ca-certificates.crt',  # Optional
}
```

### 3. Network Security

```yaml
# Network policies for Kubernetes
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: warpstream-app-network-policy
spec:
  podSelector:
    matchLabels:
      app: warpstream-app
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: warpstream
    ports:
    - protocol: TCP
      port: 9092
```

## Monitoring and Observability

### 1. Health Checks

```python
# Health check endpoint
from flask import Flask, jsonify
import requests

app = Flask(__name__)

@app.route('/health')
def health_check():
    try:
        # Check WarpStream connectivity
        producer = get_warpstream_producer()
        producer.metrics()  # This will fail if connection is broken
        
        return jsonify({
            'status': 'healthy',
            'warpstream': 'connected',
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'warpstream': 'disconnected',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 503
```

### 2. Metrics Collection

```python
# Prometheus metrics for WarpStream
from prometheus_client import Counter, Histogram, Gauge
import time

# Metrics
messages_produced = Counter('warpstream_messages_produced_total', 'Total messages produced')
messages_consumed = Counter('warpstream_messages_consumed_total', 'Total messages consumed')
producer_latency = Histogram('warpstream_producer_latency_seconds', 'Producer latency')
consumer_lag = Gauge('warpstream_consumer_lag', 'Consumer lag by topic and partition')

# Decorator for measuring producer latency
def measure_producer_latency(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start_time
        producer_latency.observe(duration)
        return result
    return wrapper
```

### 3. Logging

```python
# Structured logging for WarpStream operations
import logging
import json
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def log_producer_event(topic, partition, offset, message_size):
    logger.info(json.dumps({
        'event': 'message_produced',
        'topic': topic,
        'partition': partition,
        'offset': offset,
        'message_size': message_size,
        'timestamp': datetime.now().isoformat()
    }))

def log_consumer_event(topic, partition, offset, message_size):
    logger.info(json.dumps({
        'event': 'message_consumed',
        'topic': topic,
        'partition': partition,
        'offset': offset,
        'message_size': message_size,
        'timestamp': datetime.now().isoformat()
    }))
```

## Deployment Strategies

### 1. Blue-Green Deployment

```yaml
# Blue-green deployment with WarpStream
apiVersion: apps/v1
kind: Deployment
metadata:
  name: warpstream-app-blue
spec:
  replicas: 3
  template:
    metadata:
      labels:
        app: warpstream-app
        version: blue
    spec:
      containers:
      - name: app
        image: your-registry/warpstream-app:blue
        env:
        - name: WARPSTREAM_TOPIC_PREFIX
          value: "blue-"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: warpstream-app-green
spec:
  replicas: 0  # Start with 0 replicas
  template:
    metadata:
      labels:
        app: warpstream-app
        version: green
    spec:
      containers:
      - name: app
        image: your-registry/warpstream-app:green
        env:
        - name: WARPSTREAM_TOPIC_PREFIX
          value: "green-"
```

### 2. Canary Deployment

```python
# Canary deployment logic
import random

def should_route_to_canary(user_id):
    """Route a percentage of traffic to canary"""
    # Route 10% of traffic to canary
    return random.random() < 0.1

def get_topic_for_user(user_id):
    if should_route_to_canary(user_id):
        return "canary-events"
    else:
        return "production-events"
```

## Disaster Recovery

### 1. Backup Strategy

```python
# Backup consumer to save messages
class BackupConsumer:
    def __init__(self, topic, backup_storage):
        self.topic = topic
        self.backup_storage = backup_storage
        self.consumer = KafkaConsumer(
            topic,
            group_id='backup-consumer',
            auto_offset_reset='earliest',
            enable_auto_commit=False
        )
    
    def backup_messages(self):
        for message in self.consumer:
            # Save to backup storage
            self.backup_storage.save(
                topic=message.topic,
                partition=message.partition,
                offset=message.offset,
                key=message.key,
                value=message.value,
                timestamp=message.timestamp
            )
            
            # Manually commit offset
            self.consumer.commit()
```

### 2. Failover Configuration

```python
# Failover configuration
WARPSTREAM_CONFIG = {
    'primary': {
        'bootstrap_servers': 'primary-cluster.warpstream.com:9092',
        'api_key': os.getenv('WARPSTREAM_PRIMARY_API_KEY')
    },
    'secondary': {
        'bootstrap_servers': 'secondary-cluster.warpstream.com:9092',
        'api_key': os.getenv('WARPSTREAM_SECONDARY_API_KEY')
    }
}

def get_warpstream_client():
    """Get WarpStream client with failover"""
    try:
        # Try primary first
        return create_client(WARPSTREAM_CONFIG['primary'])
    except Exception as e:
        logger.warning(f"Primary cluster failed: {e}")
        # Fallback to secondary
        return create_client(WARPSTREAM_CONFIG['secondary'])
```

## Performance Optimization

### 1. Producer Optimization

```python
# Optimized producer configuration
producer_config = {
    'bootstrap_servers': WARPSTREAM_BOOTSTRAP_SERVERS,
    'batch_size': 16384,  # 16KB batch size
    'linger_ms': 10,      # Wait 10ms for more messages
    'compression_type': 'gzip',  # Enable compression
    'acks': 'all',        # Wait for all replicas
    'retries': 3,         # Retry failed sends
    'max_in_flight_requests_per_connection': 5,
    'buffer_memory': 33554432,  # 32MB buffer
}
```

### 2. Consumer Optimization

```python
# Optimized consumer configuration
consumer_config = {
    'bootstrap_servers': WARPSTREAM_BOOTSTRAP_SERVERS,
    'group_id': 'optimized-consumer-group',
    'auto_offset_reset': 'earliest',
    'enable_auto_commit': False,  # Manual commit for better control
    'max_poll_records': 500,      # Process 500 records per poll
    'fetch_max_wait_ms': 500,     # Wait up to 500ms for data
    'fetch_min_bytes': 1024,      # Fetch at least 1KB
    'session_timeout_ms': 30000,  # 30 second session timeout
}
```

## Resources

- [WarpStream Documentation](https://docs.warpstream.com/)
- [Kafka Best Practices](https://kafka.apache.org/documentation/#design)
- [Kubernetes Deployment Strategies](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [Prometheus Monitoring](https://prometheus.io/docs/introduction/overview/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/) 