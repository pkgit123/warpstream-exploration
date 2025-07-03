#!/usr/bin/env python3
"""
Kafka Compatibility Test for WarpStream
Tests various Kafka features to ensure compatibility
"""

import os
import json
import time
import threading
from datetime import datetime
from kafka import KafkaProducer, KafkaConsumer, KafkaAdminClient
from kafka.admin import NewTopic
from kafka.errors import KafkaError, TopicAlreadyExistsError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class KafkaCompatibilityTest:
    def __init__(self):
        """Initialize compatibility test"""
        self.bootstrap_servers = os.getenv('WARPSTREAM_BOOTSTRAP_SERVERS')
        self.api_key = os.getenv('WARPSTREAM_API_KEY')
        
        if not self.bootstrap_servers:
            print("❌ Please set WARPSTREAM_BOOTSTRAP_SERVERS in your .env file")
            return
        
        self.producer = None
        self.consumer = None
        self.admin_client = None
        self.setup_clients()
    
    def setup_clients(self):
        """Setup Kafka clients for testing"""
        try:
            # Common configuration
            common_config = {
                'bootstrap_servers': self.bootstrap_servers,
            }
            
            # Add authentication if API key is provided
            if self.api_key:
                common_config.update({
                    'security_protocol': 'SASL_SSL',
                    'sasl_mechanism': 'PLAIN',
                    'sasl_plain_username': self.api_key,
                    'sasl_plain_password': self.api_key,
                })
            
            # Producer configuration
            producer_config = common_config.copy()
            producer_config.update({
                'value_serializer': lambda v: json.dumps(v).encode('utf-8'),
                'key_serializer': lambda k: k.encode('utf-8') if k else None,
            })
            
            # Consumer configuration
            consumer_config = common_config.copy()
            consumer_config.update({
                'group_id': 'compatibility_test_group',
                'auto_offset_reset': 'earliest',
                'enable_auto_commit': True,
                'value_deserializer': lambda x: json.loads(x.decode('utf-8')),
                'key_deserializer': lambda x: x.decode('utf-8') if x else None,
            })
            
            # Admin client configuration
            admin_config = common_config.copy()
            
            # Initialize clients
            self.producer = KafkaProducer(**producer_config)
            self.consumer = KafkaConsumer(**consumer_config)
            self.admin_client = KafkaAdminClient(**admin_config)
            
            print("✅ All Kafka clients initialized successfully")
            
        except Exception as e:
            print(f"❌ Error setting up clients: {e}")
    
    def test_topic_creation(self):
        """Test topic creation functionality"""
        print("\n" + "="*50)
        print("TESTING TOPIC CREATION")
        print("="*50)
        
        topic_name = "compatibility_test_topic"
        
        try:
            # Create topic
            topic = NewTopic(
                name=topic_name,
                num_partitions=3,
                replication_factor=1
            )
            
            result = self.admin_client.create_topics([topic])
            print(f"✅ Topic '{topic_name}' created successfully")
            print(f"   Result: {result}")
            
            return topic_name
            
        except TopicAlreadyExistsError:
            print(f"⚠️  Topic '{topic_name}' already exists")
            return topic_name
        except Exception as e:
            print(f"❌ Error creating topic: {e}")
            return None
    
    def test_producer_functionality(self, topic_name):
        """Test producer functionality"""
        print("\n" + "="*50)
        print("TESTING PRODUCER FUNCTIONALITY")
        print("="*50)
        
        if not self.producer:
            print("❌ Producer not initialized")
            return False
        
        try:
            # Test different message types
            test_messages = [
                {"type": "string", "data": "Hello WarpStream!"},
                {"type": "number", "data": 42},
                {"type": "object", "data": {"key": "value", "nested": {"array": [1, 2, 3]}}},
                {"type": "null", "data": None},
                {"type": "boolean", "data": True}
            ]
            
            for i, message in enumerate(test_messages):
                # Send with key
                future = self.producer.send(
                    topic_name,
                    key=f"test_key_{i}",
                    value=message
                )
                
                # Wait for send to complete
                record_metadata = future.get(timeout=10)
                print(f"✅ Message {i} sent successfully")
                print(f"   Topic: {record_metadata.topic}")
                print(f"   Partition: {record_metadata.partition}")
                print(f"   Offset: {record_metadata.offset}")
            
            # Test sending without key
            future = self.producer.send(topic_name, value={"type": "no_key", "data": "test"})
            record_metadata = future.get(timeout=10)
            print(f"✅ Message without key sent successfully")
            
            # Flush to ensure all messages are sent
            self.producer.flush()
            print("✅ All producer tests passed")
            return True
            
        except Exception as e:
            print(f"❌ Producer test failed: {e}")
            return False
    
    def test_consumer_functionality(self, topic_name):
        """Test consumer functionality"""
        print("\n" + "="*50)
        print("TESTING CONSUMER FUNCTIONALITY")
        print("="*50)
        
        if not self.consumer:
            print("❌ Consumer not initialized")
            return False
        
        try:
            # Subscribe to topic
            self.consumer.subscribe([topic_name])
            
            # Consume messages
            message_count = 0
            start_time = time.time()
            
            for message in self.consumer:
                message_count += 1
                print(f"\n📨 Message #{message_count}:")
                print(f"   Topic: {message.topic}")
                print(f"   Partition: {message.partition}")
                print(f"   Offset: {message.offset}")
                print(f"   Key: {message.key}")
                print(f"   Value: {json.dumps(message.value, indent=2)}")
                print(f"   Timestamp: {datetime.fromtimestamp(message.timestamp/1000)}")
                
                # Stop after receiving 6 messages (5 with keys + 1 without key)
                if message_count >= 6:
                    break
                
                # Timeout after 30 seconds
                if time.time() - start_time > 30:
                    print("⏰ Consumer timeout reached")
                    break
            
            print(f"\n📊 Total messages consumed: {message_count}")
            
            if message_count >= 6:
                print("✅ All consumer tests passed")
                return True
            else:
                print("❌ Consumer test failed - not enough messages received")
                return False
                
        except Exception as e:
            print(f"❌ Consumer test failed: {e}")
            return False
        finally:
            self.consumer.close()
    
    def test_partition_assignment(self, topic_name):
        """Test partition assignment and rebalancing"""
        print("\n" + "="*50)
        print("TESTING PARTITION ASSIGNMENT")
        print("="*50)
        
        try:
            # Create multiple consumers with same group
            consumers = []
            for i in range(3):
                consumer_config = {
                    'bootstrap_servers': self.bootstrap_servers,
                    'group_id': 'partition_test_group',
                    'auto_offset_reset': 'earliest',
                    'enable_auto_commit': True,
                    'value_deserializer': lambda x: json.loads(x.decode('utf-8')),
                    'key_deserializer': lambda x: x.decode('utf-8') if x else None,
                }
                
                if self.api_key:
                    consumer_config.update({
                        'security_protocol': 'SASL_SSL',
                        'sasl_mechanism': 'PLAIN',
                        'sasl_plain_username': self.api_key,
                        'sasl_plain_password': self.api_key,
                    })
                
                consumer = KafkaConsumer(**consumer_config)
                consumer.subscribe([topic_name])
                consumers.append(consumer)
                print(f"✅ Consumer {i+1} created and subscribed")
            
            # Let them run for a few seconds to see partition assignment
            time.sleep(5)
            
            # Check partition assignments
            for i, consumer in enumerate(consumers):
                assignment = consumer.assignment()
                print(f"Consumer {i+1} assigned to partitions: {assignment}")
                consumer.close()
            
            print("✅ Partition assignment test completed")
            return True
            
        except Exception as e:
            print(f"❌ Partition assignment test failed: {e}")
            return False
    
    def test_metadata_operations(self):
        """Test metadata operations"""
        print("\n" + "="*50)
        print("TESTING METADATA OPERATIONS")
        print("="*50)
        
        try:
            # Get cluster metadata
            cluster_metadata = self.admin_client.describe_cluster()
            print(f"✅ Cluster metadata retrieved")
            print(f"   Controller: {cluster_metadata.controller_id}")
            print(f"   Brokers: {len(cluster_metadata.brokers())}")
            
            # Get topic metadata
            topic_metadata = self.admin_client.describe_topics(["compatibility_test_topic"])
            print(f"✅ Topic metadata retrieved")
            for topic in topic_metadata:
                print(f"   Topic: {topic.topic}")
                print(f"   Partitions: {len(topic.partitions)}")
                for partition in topic.partitions:
                    print(f"     Partition {partition.partition_id}: "
                          f"leader={partition.leader}, "
                          f"replicas={partition.replicas}")
            
            return True
            
        except Exception as e:
            print(f"❌ Metadata test failed: {e}")
            return False
    
    def run_compatibility_suite(self):
        """Run the complete compatibility test suite"""
        print("🚀 WARPSTREAM KAFKA COMPATIBILITY TEST SUITE")
        print("=" * 60)
        
        if not self.producer or not self.consumer or not self.admin_client:
            print("❌ Failed to initialize clients")
            return
        
        test_results = {}
        
        # Test topic creation
        topic_name = self.test_topic_creation()
        test_results['topic_creation'] = topic_name is not None
        
        if topic_name:
            # Test producer
            test_results['producer'] = self.test_producer_functionality(topic_name)
            
            # Test consumer
            test_results['consumer'] = self.test_consumer_functionality(topic_name)
            
            # Test partition assignment
            test_results['partition_assignment'] = self.test_partition_assignment(topic_name)
        
        # Test metadata operations
        test_results['metadata'] = self.test_metadata_operations()
        
        # Summary
        print("\n" + "="*60)
        print("COMPATIBILITY TEST SUMMARY")
        print("="*60)
        
        passed = 0
        total = len(test_results)
        
        for test_name, result in test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{test_name.replace('_', ' ').title()}: {status}")
            if result:
                passed += 1
        
        print(f"\n📊 Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All compatibility tests passed! WarpStream is fully Kafka-compatible.")
        else:
            print("⚠️  Some tests failed. Check the output above for details.")
    
    def cleanup(self):
        """Clean up resources"""
        if self.producer:
            self.producer.close()
        if self.consumer:
            self.consumer.close()
        if self.admin_client:
            self.admin_client.close()
        print("✅ All connections closed")

def main():
    """Main function"""
    test_suite = KafkaCompatibilityTest()
    
    if not test_suite.producer:
        print("❌ Failed to initialize test suite")
        return
    
    try:
        test_suite.run_compatibility_suite()
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
    finally:
        test_suite.cleanup()

if __name__ == "__main__":
    main() 