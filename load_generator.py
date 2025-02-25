from kafka import KafkaProducer
import time
import json
import threading
import random
import logging
from concurrent.futures import ThreadPoolExecutor
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KafkaLoadGenerator:
    def __init__(self, bootstrap_servers=None, target_rps=3000):
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers or os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092'),
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.target_rps = target_rps
        self.topics = ['user_data_topic',]

    def generate_message(self):
        return {
            'timestamp': time.time(),
            'value': random.random(),
            'metadata': {
                'source': 'load_generator',
                'type': random.choice(['type_a', 'type_b', 'type_c'])
            }
        }

    def send_message(self):
        try:
            topic = random.choice(self.topics)
            message = self.generate_message()
            self.producer.send(topic, message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    def run(self):
        logger.info(f"Starting load generator targeting {self.target_rps} RPS")
        
        # Calculate sleep time between requests to achieve target RPS
        sleep_time = 1.0 / (self.target_rps / 10)  # Using 10 threads
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            while True:
                futures = []
                start_time = time.time()

                # Submit batch of requests
                for _ in range(10):
                    futures.append(executor.submit(self.send_message))
                
                # Wait for batch completion
                for future in futures:
                    future.result()
                
                # Sleep to maintain target RPS
                elapsed = time.time() - start_time
                if elapsed < sleep_time:
                    time.sleep(sleep_time - elapsed)

if __name__ == "__main__":
    generator = KafkaLoadGenerator()
    generator.run() 