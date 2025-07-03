#!/usr/bin/env python3
"""
Basic WarpStream Producer/Consumer Example
Demonstrates basic Kafka-compatible operations with WarpStream
"""

import os
import json
import time
import threading
from datetime import datetime
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class WarpStreamExample:
    def __init__(self):
        """Initialize WarpStream connection"""
        self.bootstrap_servers = os.getenv('WARPSTREAM_BOOTSTRAP_SERVERS')
        self.api_key = os.getenv('WARPSTREAM_API_KEY')
        
        if not self.bootstrap_servers:
            print("❌ Please set WARPSTREAM_BOOTSTRAP_SERVERS in your .env file")
            return
        
        print(f"✅ Connecting to WarpStream at: {self.bootstrap_servers}")
        
        # Initialize producer and consumer
        self.producer = None
        self.consumer = None
        self.setup_connections()
    
    def setup_connections(self):
        """Setup Kafka producer and consumer connections"""
        try:
            # Producer configuration
            producer_config = {
                'bootstrap_servers': self.bootstrap_servers,
                'value_serializer': lambda v: json.dumps(v).encode('utf-8'),
                'key_serializer': lambda k: k.encode('utf-8') if k else None,
            }
            
            # Add API key if provided
            if self.api_key:
                producer_config['security_protocol'] = 'SASL_SSL'
                producer_config['sasl_mechanism'] = 'PLAIN'
                producer_config['sasl_plain_username'] = self.api_key
                producer_config['sasl_plain_password'] = self.api_key
            
            self.producer = KafkaProducer(**producer_config)
            print("✅ Producer initialized successfully")
            
            # Consumer configuration
            consumer_config = {
                'bootstrap_servers': self.bootstrap_servers,
                'group_id': 'warpstream_exploration_group',
                'auto_offset_reset': 'earliest',
                'enable_auto_commit': True,
                'value_deserializer': lambda x: json.loads(x.decode('utf-8')),
                'key_deserializer': lambda x: x.decode('utf-8') if x else None,
            }
            
            # Add API key if provided
            if self.api_key:
                consumer_config['security_protocol'] = 'SASL_SSL'
                consumer_config['sasl_mechanism'] = 'PLAIN'
                consumer_config['sasl_plain_username'] = self.api_key
                consumer_config['sasl_plain_password'] = self.api_key
            
            self.consumer = KafkaConsumer(**consumer_config)
            print("✅ Consumer initialized successfully")
            
        except Exception as e:
            print(f"❌ Error setting up connections: {e}")
    
    def create_topic(self, topic_name):
        """Create a topic (if supported by your WarpStream setup)"""
        print(f"📝 Note: Topic '{topic_name}' should be created in WarpStream console")
        print("   Most managed Kafka services require topics to be created via UI/API")
        return topic_name
    
    def produce_messages(self, topic_name, num_messages=10):
        """Produce sample messages to a topic"""
        if not self.producer:
            print("❌ Producer not initialized")
            return
        
        print(f"\n📤 Producing {num_messages} messages to topic: {topic_name}")
        
        try:
            for i in range(num_messages):
                # Create sample message
                message = {
                    'id': i,
                    'timestamp': datetime.now().isoformat(),
                    'message': f'Hello WarpStream! Message #{i}',
                    'data': {
                        'value': i * 10,
                        'category': 'sample',
                        'processed': False
                    }
                }
                
                # Send message
                future = self.producer.send(
                    topic_name,
                    key=f'key_{i}',
                    value=message
                )
                
                # Wait for send to complete
                record_metadata = future.get(timeout=10)
                print(f"✅ Message {i} sent to {record_metadata.topic} "
                      f"[partition: {record_metadata.partition}, "
                      f"offset: {record_metadata.offset}]")
                
                time.sleep(0.1)  # Small delay between messages
            
            # Flush to ensure all messages are sent
            self.producer.flush()
            print("✅ All messages sent successfully")
            
        except KafkaError as e:
            print(f"❌ Kafka error: {e}")
        except Exception as e:
            print(f"❌ Error producing messages: {e}")
    
    def consume_messages(self, topic_name, timeout_seconds=30):
        """Consume messages from a topic"""
        if not self.consumer:
            print("❌ Consumer not initialized")
            return
        
        print(f"\n📥 Consuming messages from topic: {topic_name}")
        print(f"⏱️  Will timeout after {timeout_seconds} seconds")
        
        try:
            # Subscribe to topic
            self.consumer.subscribe([topic_name])
            
            # Start consuming
            start_time = time.time()
            message_count = 0
            
            for message in self.consumer:
                if time.time() - start_time > timeout_seconds:
                    print(f"⏰ Timeout reached after {timeout_seconds} seconds")
                    break
                
                message_count += 1
                print(f"\n📨 Message #{message_count}:")
                print(f"   Topic: {message.topic}")
                print(f"   Partition: {message.partition}")
                print(f"   Offset: {message.offset}")
                print(f"   Key: {message.key}")
                print(f"   Value: {json.dumps(message.value, indent=2)}")
                print(f"   Timestamp: {datetime.fromtimestamp(message.timestamp/1000)}")
                
                # Stop after receiving all expected messages
                if message_count >= 10:
                    print("✅ Received all expected messages")
                    break
            
            print(f"\n📊 Total messages consumed: {message_count}")
            
        except KafkaError as e:
            print(f"❌ Kafka error: {e}")
        except Exception as e:
            print(f"❌ Error consuming messages: {e}")
        finally:
            self.consumer.close()
    
    def run_producer_consumer_demo(self):
        """Run a complete producer/consumer demonstration"""
        topic_name = "warpstream_demo_topic"
        
        print("🚀 Starting WarpStream Producer/Consumer Demo")
        print("=" * 60)
        
        # Create topic (informational)
        self.create_topic(topic_name)
        
        # Start consumer in a separate thread
        consumer_thread = threading.Thread(
            target=self.consume_messages,
            args=(topic_name, 60)  # 60 second timeout
        )
        consumer_thread.daemon = True
        consumer_thread.start()
        
        # Give consumer time to start
        time.sleep(2)
        
        # Produce messages
        self.produce_messages(topic_name, 10)
        
        # Wait for consumer to finish
        consumer_thread.join(timeout=65)
        
        print("\n🎉 Demo completed!")
    
    def cleanup(self):
        """Clean up connections"""
        if self.producer:
            self.producer.close()
            print("✅ Producer connection closed")
        
        if self.consumer:
            self.consumer.close()
            print("✅ Consumer connection closed")

def main():
    """Main function to run the example"""
    print("WARPSTREAM BASIC PRODUCER/CONSUMER EXAMPLE")
    print("=" * 60)
    
    # Initialize WarpStream example
    ws_example = WarpStreamExample()
    
    if not ws_example.producer or not ws_example.consumer:
        print("❌ Failed to initialize connections. Please check your configuration.")
        return
    
    try:
        # Run the demo
        ws_example.run_producer_consumer_demo()
        
    except KeyboardInterrupt:
        print("\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
    finally:
        # Cleanup
        ws_example.cleanup()

if __name__ == "__main__":
    main() 