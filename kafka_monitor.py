from kafka.admin import KafkaAdminClient
from kafka import KafkaConsumer
from prometheus_client import start_http_server, Gauge
import time
import json
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus metrics
PARTITION_LAG = Gauge('kafka_consumer_lag', 'Lag by partition', ['topic', 'partition'])
BROKER_LOAD = Gauge('kafka_broker_load', 'Broker load metrics', ['broker_id', 'metric_type'])
TOPIC_MESSAGES = Gauge('kafka_topic_messages', 'Messages per topic', ['topic'])
PARTITION_SIZE = Gauge('kafka_partition_size', 'Size of each partition', ['topic', 'partition'])

class KafkaMonitor:
    def __init__(self, bootstrap_servers=None):
        self.bootstrap_servers = bootstrap_servers or os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        self.admin_client = KafkaAdminClient(bootstrap_servers=self.bootstrap_servers)
        self.consumer = KafkaConsumer(
            bootstrap_servers=self.bootstrap_servers,
            enable_auto_commit=False,
            group_id='kafka_monitor'
        )

    def collect_broker_metrics(self):
        try:
            cluster_info = self.admin_client.describe_cluster()
            for broker in cluster_info.brokers:
                # Collect broker metrics
                BROKER_LOAD.labels(
                    broker_id=broker.id,
                    metric_type='network_processor_avg'
                ).set(broker.metrics.get('network_processor_avg', 0))
        except Exception as e:
            logger.error(f"Error collecting broker metrics: {e}")

    def collect_topic_metrics(self):
        try:
            topics = self.admin_client.list_topics()
            for topic in topics:
                partitions = self.consumer.partitions_for_topic(topic)
                if partitions:
                    for partition in partitions:
                        # Get end offsets
                        end_offset = self.consumer.end_offsets([
                            (topic, partition)])[topic, partition]
                        PARTITION_SIZE.labels(
                            topic=topic,
                            partition=partition
                        ).set(end_offset)
        except Exception as e:
            logger.error(f"Error collecting topic metrics: {e}")

    def run(self):
        start_http_server(8000)  # Start Prometheus metrics endpoint
        logger.info("Kafka monitoring started on port 8000")
        
        while True:
            self.collect_broker_metrics()
            self.collect_topic_metrics()
            time.sleep(10)  # Collect metrics every 10 seconds

if __name__ == "__main__":
    monitor = KafkaMonitor()
    monitor.run() 