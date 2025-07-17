# Personal Analytics Streaming Project

A cost-effective way to explore streaming technologies using your own data.

## Project Overview

Build a real-time analytics dashboard that tracks your personal activities and provides insights using streaming data processing.

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Data        │───▶│ WarpStream  │───▶│ Stream      │───▶│ Real-time   │
│ Sources     │    │   Events    │    │ Processor   │    │ Dashboard   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │                   │
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ GitHub      │    │ Local       │    │ Analytics   │    │ Web App     │
│ Activity    │    │ Development │    │ Engine      │    │ (Vercel)    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │                   │
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Fitness     │    │ Free Tier   │    │ Alerts      │    │ Mobile      │
│ Data        │    │ Production  │    │ System      │    │ App         │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## Data Sources (All Free)

### 1. GitHub Activity
- **API**: GitHub REST API (free, 5000 requests/hour)
- **Data**: Commits, pull requests, issues, repository activity
- **Frequency**: Real-time webhooks or hourly polling

### 2. Fitness Data
- **API**: Fitbit API, Apple Health (via HealthKit), or manual entry
- **Data**: Steps, heart rate, sleep, workouts
- **Frequency**: Daily sync or real-time (if available)

### 3. Social Media Activity
- **API**: Twitter API (free tier), Reddit API
- **Data**: Posts, likes, engagement metrics
- **Frequency**: Daily polling

### 4. Weather Data
- **API**: OpenWeatherMap (free tier: 1000 calls/day)
- **Data**: Temperature, humidity, conditions
- **Frequency**: Hourly updates

### 5. News/Social Sentiment
- **API**: NewsAPI (free tier), Twitter API
- **Data**: News headlines, social media sentiment
- **Frequency**: Daily updates

## Implementation Plan

### Phase 1: Local Development (Cost: $0)
**Duration**: 2-3 weeks

#### Setup Local Environment
```bash
# Install local Kafka for development
docker run -d --name kafka -p 9092:9092 apache/kafka:2.13-3.6.0

# Install dependencies
pip install kafka-python requests fastapi uvicorn plotly dash
```

#### Build Data Collectors
```python
# github_collector.py
import requests
import json
from kafka import KafkaProducer
from datetime import datetime

class GitHubCollector:
    def __init__(self, username, token):
        self.username = username
        self.token = token
        self.producer = KafkaProducer(
            bootstrap_servers='localhost:9092',
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
    
    def collect_activity(self):
        # Collect recent commits
        commits = self.get_recent_commits()
        for commit in commits:
            event = {
                'type': 'github_commit',
                'data': commit,
                'timestamp': datetime.now().isoformat()
            }
            self.producer.send('personal_activity', value=event)
        
        # Collect repository activity
        repos = self.get_repository_activity()
        for repo in repos:
            event = {
                'type': 'github_repo_activity',
                'data': repo,
                'timestamp': datetime.now().isoformat()
            }
            self.producer.send('personal_activity', value=event)
    
    def get_recent_commits(self):
        headers = {'Authorization': f'token {self.token}'}
        url = f'https://api.github.com/users/{self.username}/events'
        response = requests.get(url, headers=headers)
        return response.json()
```

#### Build Stream Processor
```python
# stream_processor.py
from kafka import KafkaConsumer, KafkaProducer
import json
from collections import defaultdict
import time

class PersonalAnalyticsProcessor:
    def __init__(self):
        self.consumer = KafkaConsumer(
            'personal_activity',
            group_id='analytics_processor',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            bootstrap_servers='localhost:9092'
        )
        
        self.producer = KafkaProducer(
            bootstrap_servers='localhost:9092',
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        # In-memory analytics state
        self.daily_stats = defaultdict(lambda: {
            'commits': 0,
            'repositories': set(),
            'fitness_steps': 0,
            'social_posts': 0
        })
    
    def process_events(self):
        for message in self.consumer:
            event = message.value
            event_type = event['type']
            
            # Update daily statistics
            date = event['timestamp'][:10]  # YYYY-MM-DD
            self.update_daily_stats(date, event_type, event['data'])
            
            # Generate insights
            insights = self.generate_insights(date)
            
            # Send to dashboard
            self.producer.send('analytics_insights', value=insights)
    
    def update_daily_stats(self, date, event_type, data):
        if event_type == 'github_commit':
            self.daily_stats[date]['commits'] += 1
        elif event_type == 'fitness_data':
            self.daily_stats[date]['fitness_steps'] += data.get('steps', 0)
        # Add more event types...
    
    def generate_insights(self, date):
        stats = self.daily_stats[date]
        
        insights = {
            'date': date,
            'productivity_score': self.calculate_productivity_score(stats),
            'health_score': self.calculate_health_score(stats),
            'recommendations': self.generate_recommendations(stats),
            'timestamp': datetime.now().isoformat()
        }
        
        return insights
```

### Phase 2: Production Deployment (Cost: $5-15/month)
**Duration**: 1-2 weeks

#### Infrastructure Setup
```yaml
# docker-compose.yml for production
version: '3.8'
services:
  app:
    build: .
    environment:
      - WARPSTREAM_BOOTSTRAP_SERVERS=${WARPSTREAM_BOOTSTRAP_SERVERS}
      - WARPSTREAM_API_KEY=${WARPSTREAM_API_KEY}
    ports:
      - "8000:8000"
  
  dashboard:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./dashboard:/usr/share/nginx/html
```

#### Deploy to Vercel
```bash
# Deploy dashboard to Vercel (free)
vercel --prod

# Deploy API to Railway (free tier)
railway up
```

### Phase 3: Advanced Features (Cost: $10-20/month)
**Duration**: 2-3 weeks

#### Add Machine Learning
```python
# ml_processor.py
import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import datetime, timedelta

class MLInsightsProcessor:
    def __init__(self):
        self.model = LinearRegression()
        self.historical_data = []
    
    def predict_productivity(self, recent_data):
        # Predict productivity for next week
        features = self.extract_features(recent_data)
        prediction = self.model.predict([features])
        return prediction[0]
    
    def detect_anomalies(self, current_data):
        # Detect unusual patterns in activity
        mean_activity = np.mean([d['commits'] for d in self.historical_data[-7:]])
        current_activity = current_data['commits']
        
        if abs(current_activity - mean_activity) > 2 * np.std([d['commits'] for d in self.historical_data[-7:]]):
            return True
        return False
```

## Cost Breakdown

### Development Phase (Month 1)
- **Local Development**: $0
- **GitHub API**: $0 (free tier)
- **Weather API**: $0 (free tier)
- **Total**: $0

### Production Phase (Month 2+)
- **WarpStream**: $0-10/month (free tier + minimal usage)
- **Vercel Hosting**: $0 (free tier)
- **Database**: $0-5/month (free tier)
- **Monitoring**: $0 (free tier)
- **Total**: $0-15/month

### Advanced Features (Month 3+)
- **Additional APIs**: $5-10/month
- **ML Processing**: $5-10/month
- **Total**: $10-25/month

## Learning Outcomes

### Technical Skills
- **Streaming Architecture**: Event sourcing, real-time processing
- **Data Integration**: API integration, data transformation
- **Real-time Analytics**: Time-series analysis, aggregations
- **ML Integration**: Predictive analytics, anomaly detection
- **Full-stack Development**: Frontend, backend, data pipeline

### Business Skills
- **Data-driven Decision Making**: Using analytics for personal improvement
- **Product Development**: Building features based on data insights
- **Cost Optimization**: Managing cloud resources efficiently
- **Project Management**: Phased development approach

## Alternative Low-Cost Projects

### 1. Personal Finance Streamer
- **Data**: Bank transactions, investments, expenses
- **Cost**: $0-5/month
- **Learning**: Financial data processing, real-time calculations

### 2. Home Automation Dashboard
- **Data**: Smart home sensors, energy usage, automation events
- **Cost**: $20-50 one-time + $5/month
- **Learning**: IoT integration, sensor data processing

### 3. Learning Progress Tracker
- **Data**: Course progress, study time, quiz scores
- **Cost**: $0-5/month
- **Learning**: Educational analytics, progress tracking

### 4. Social Media Analytics
- **Data**: Posts, engagement, follower growth
- **Cost**: $0-10/month
- **Learning**: Social media APIs, engagement analytics

## Getting Started

1. **Choose a project** from the list above
2. **Set up local development** environment
3. **Build MVP** with local Kafka
4. **Deploy to production** with WarpStream
5. **Add advanced features** incrementally

This approach lets you explore streaming technologies without breaking the bank while building something genuinely useful for yourself! 