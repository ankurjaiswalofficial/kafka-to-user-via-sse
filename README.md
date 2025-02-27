# Kafka Monitoring and Load Testing System

A comprehensive system for monitoring Kafka metrics and performance testing with load generation capabilities. This project includes Prometheus for metrics collection and Grafana for visualization.

## System Components

### 1. Kafka Monitor (`kafka_monitor.py`)
- Collects real-time metrics from Kafka brokers and topics
- Exposes metrics via Prometheus endpoint
- Monitors:
  - Broker load
  - Partition sizes
  - Consumer lag
  - Topic message counts

### 2. Load Generator (`load_generator.py`)
- Generates configurable load (default: 3000 RPS)
- Produces messages to specified Kafka topics
- Supports multi-threaded operation
- Configurable message patterns and types

### 3. Supporting Services
- **Prometheus**: Metrics collection and storage
- **Grafana**: Metrics visualization and dashboarding
- **Kafka & Zookeeper**: Message broker infrastructure

## Prerequisites

- Docker and Docker Compose
- Python 3.9+
- Available ports:
  - 2181 (Zookeeper)
  - 9092 (Kafka)
  - 8000 (Kafka Monitor)
  - 9090 (Prometheus)
  - 3000 (Grafana)

## Installation & Setup

1. **Clone the Repository**
```bash
git clone <repository-url>
cd kafka-monitoring-system
```

2. **Build and Start Services**
```bash
docker-compose up -d
```

3. **Verify Services**
```bash
docker-compose ps
```

## Configuration

### Kafka Monitor Configuration
```python
# Environment Variables
KAFKA_BOOTSTRAP_SERVERS=kafka:29092  # Kafka broker address
```

### Load Generator Configuration
```python
# Environment Variables
KAFKA_BOOTSTRAP_SERVERS=kafka:29092  # Kafka broker address
TARGET_RPS=3000                      # Target requests per second
```

### Prometheus Configuration (`prometheus.yml`)
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'kafka_monitor'
    static_configs:
      - targets: ['kafka-monitor:8000']
```

## Usage

### Starting the Monitor
```bash
# Using Docker Compose
docker-compose up kafka-monitor

# Standalone
python kafka_monitor.py
```

### Starting the Load Generator
```bash
# Using Docker Compose
docker-compose up load-generator

# Standalone
python load_generator.py
```

### Accessing Metrics

1. **Prometheus Metrics** (Raw)
   - URL: `http://localhost:8000/metrics`
   - Available metrics:
     - `kafka_consumer_lag`
     - `kafka_broker_load`
     - `kafka_topic_messages`
     - `kafka_partition_size`

2. **Prometheus UI**
   - URL: `http://localhost:9090`
   - Features:
     - Query metrics
     - Create graphs
     - View targets and alerts

3. **Grafana Dashboard**
   - URL: `http://localhost:3000`
   - Default credentials:
     - Username: `admin`
     - Password: `admin`

## Monitoring Metrics

### Broker Metrics
- Network processor average
- Request handler average
- Request queue size
- Response queue size

### Topic Metrics
- Messages per second
- Bytes per second
- Partition count
- Replication status

### Consumer Metrics
- Consumer lag
- Consumption rate
- Offset commit rate

## Docker Services

### Main Services
```yaml
kafka-monitor:
  build:
    context: .
    dockerfile: Dockerfile.monitor
  ports:
    - "8000:8000"
  environment:
    - KAFKA_BOOTSTRAP_SERVERS=kafka:29092

load-generator:
  build:
    context: .
    dockerfile: Dockerfile.load_generator
  environment:
    - KAFKA_BOOTSTRAP_SERVERS=kafka:29092
```

### Monitoring Stack
```yaml
prometheus:
  image: prom/prometheus:latest
  ports:
    - "9090:9090"
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml

grafana:
  image: grafana/grafana:latest
  ports:
    - "3000:3000"
```

## Troubleshooting

### Common Issues

1. **Kafka Connection Issues**
   ```bash
   # Check Kafka status
   docker-compose logs kafka
   
   # Verify network connectivity
   docker-compose exec kafka-monitor ping kafka
   ```

2. **Metric Collection Issues**
   ```bash
   # Check monitor logs
   docker-compose logs kafka-monitor
   
   # Verify Prometheus targets
   curl http://localhost:9090/api/v1/targets
   ```

3. **Load Generator Issues**
   ```bash
   # Check load generator logs
   docker-compose logs load-generator
   
   # Verify message production
   docker-compose exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic user_data_topic
   ```

## Performance Tuning

### Load Generator
- Adjust `target_rps` in `load_generator.py`
- Modify thread pool size for different performance characteristics
- Configure message size and complexity

### Kafka Monitor
- Adjust collection interval in `kafka_monitor.py`
- Configure metric retention in Prometheus
- Optimize Grafana dashboard refresh rates

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

This project is licensed under the Apache-2.0 license - see the LICENSE file for details.
