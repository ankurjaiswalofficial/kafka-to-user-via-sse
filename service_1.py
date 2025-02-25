from kafka import KafkaConsumer, KafkaProducer
import json
import time
import threading
import os
import logging
import signal
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('service_1')

# Get configuration from environment variables
KAFKA_BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
INCOMING_TOPIC = os.environ.get('INCOMING_TOPIC', 'user_data_topic')
PROCESSED_TOPIC = os.environ.get('PROCESSED_TOPIC', 'processed_data_topic')
PROCESSING_TIME_MS = int(os.environ.get('PROCESSING_TIME_MS', 10))

logger.info(f"Kafka Bootstrap Servers: {KAFKA_BOOTSTRAP_SERVERS}")
logger.info(f"Incoming Topic: {INCOMING_TOPIC}")
logger.info(f"Processed Topic: {PROCESSED_TOPIC}")
logger.info(f"Processing Time: {PROCESSING_TIME_MS}ms")

# Flag for shutdown signaling
shutdown_flag = False

# Initialize Kafka producer with error handling
try:
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        acks='all',
        retries=5,
        retry_backoff_ms=500
    )
    logger.info("Kafka producer initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Kafka producer: {e}")
    producer = None
    sys.exit(1)

def process_data(data):
    """
    Example data processing function.
    In a real application, this would contain your actual business logic.
    """
    # Add processing timestamp
    data['timestamp_processing_start'] = time.time()
    
    # Simulate processing time (10ms by default)
    time.sleep(PROCESSING_TIME_MS / 1000)
    
    # Add some processing results
    data['processed'] = True
    data['processing_result'] = f"Processed data for user {data.get('user_id', 'unknown')}"
    data['timestamp_processing_end'] = time.time()
    data['processing_time_ms'] = PROCESSING_TIME_MS
    
    return data

def consume_and_process():
    """
    Main consumer function that reads from Kafka, processes data,
    and sends results back to Kafka.
    """
    logger.info("Service-1 started. Waiting for messages...")
    
    max_retries = 10
    retry_count = 0
    
    while retry_count < max_retries and not shutdown_flag:
        try:
            consumer = KafkaConsumer(
                INCOMING_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                auto_offset_reset='latest',
                group_id='service_1_group',
                enable_auto_commit=True,
                auto_commit_interval_ms=1000
            )
            
            logger.info("Kafka consumer initialized successfully")
            
            # Process messages until shutdown signal
            for message in consumer:
                if shutdown_flag:
                    break
                    
                try:
                    data = message.value
                    logger.info(f"Received data: {data.get('request_id', 'unknown')}")
                    
                    # Process the data
                    processed_data = process_data(data)
                    
                    # Send processed data back to Kafka
                    future = producer.send(PROCESSED_TOPIC, processed_data)
                    future.get(timeout=10)  # Wait for the send to complete with timeout
                    
                    logger.info(f"Sent processed data: {processed_data.get('request_id', 'unknown')}")
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
            
            # Exit the loop if shutdown was requested
            if shutdown_flag:
                break
                
        except Exception as e:
            retry_count += 1
            logger.error(f"Kafka consumer error (attempt {retry_count}/{max_retries}): {e}")
            time.sleep(5)  # Wait before retrying
            
            # Exit the loop if shutdown was requested
            if shutdown_flag:
                break
        
    if retry_count >= max_retries:
        logger.critical("Failed to establish Kafka consumer connection after multiple retries")

# Handle graceful shutdown
def handle_shutdown(sig, frame):
    global shutdown_flag
    logger.info("Shutdown signal received, closing connections...")
    shutdown_flag = True
    
    # Close producer if it exists
    if producer:
        producer.close()
        logger.info("Kafka producer closed")
    
    # Allow some time for cleanup
    time.sleep(2)
    sys.exit(0)

# Register shutdown handlers
signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)

if __name__ == "__main__":
    consume_and_process()