from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import json
import asyncio
import threading
from kafka import KafkaProducer, KafkaConsumer
import time
import queue
import os
import logging
import uuid
from typing import Dict, Any, Optional
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('api_handler')

app = FastAPI(title="Real-time Data Processing API", 
              description="FastAPI service for real-time data processing with Kafka")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create metrics
REQUEST_COUNT = Counter("api_requests_total", "Total API requests")
ACTIVE_CONNECTIONS = Gauge("api_active_sse_connections", "Number of active SSE connections")
QUEUE_SIZE = Gauge("api_queue_size", "Size of the results queue")

# Request model
class UserData(BaseModel):
    user_id: str
    user_data: str
    client_timestamp: Optional[float] = Field(default_factory=time.time)

# Response model
class ApiResponse(BaseModel):
    status: str
    message: str
    request_id: Optional[str] = None

# Queue to store processed results from Kafka
results_queue = queue.Queue(maxsize=1000)  # Set a maximum size to prevent memory issues

# Get configuration from environment variables
KAFKA_BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
INCOMING_TOPIC = os.environ.get('INCOMING_TOPIC', 'user_data_topic')
PROCESSED_TOPIC = os.environ.get('PROCESSED_TOPIC', 'processed_data_topic')

logger.info(f"Kafka Bootstrap Servers: {KAFKA_BOOTSTRAP_SERVERS}")
logger.info(f"Incoming Topic: {INCOMING_TOPIC}")
logger.info(f"Processed Topic: {PROCESSED_TOPIC}")

# Initialize Kafka producer with error handling
try:
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        acks='all',  # Wait for all replicas to acknowledge
        retries=5,   # Retry a few times if needed
        retry_backoff_ms=500  # Start with 0.5s between retries
    )
    logger.info("Kafka producer initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Kafka producer: {e}")
    producer = None

# Function to consume processed data from Kafka
def consume_processed_data():
    logger.info(f"Starting consumer for topic: {PROCESSED_TOPIC}")
    max_retries = 10
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            consumer = KafkaConsumer(
                PROCESSED_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                auto_offset_reset='latest',
                group_id='api_handler_group',
                enable_auto_commit=True,
                auto_commit_interval_ms=1000
            )
            
            logger.info("Kafka consumer initialized successfully")
            
            for message in consumer:
                try:
                    # Add the processed data to the queue for SSE
                    if results_queue.full():
                        # If queue is full, remove oldest item to prevent backpressure
                        results_queue.get_nowait()
                        logger.warning("Results queue full, dropped oldest message")
                    
                    results_queue.put(message.value)
                    QUEUE_SIZE.set(results_queue.qsize())
                    logger.debug(f"Received processed data: {message.value}")
                except Exception as e:
                    logger.error(f"Error processing Kafka message: {e}")
            
        except Exception as e:
            retry_count += 1
            logger.error(f"Kafka consumer error (attempt {retry_count}/{max_retries}): {e}")
            time.sleep(5)  # Wait before retrying
        
    logger.critical("Failed to establish Kafka consumer connection after multiple retries")

# Start the Kafka consumer in a separate thread
consumer_thread = threading.Thread(target=consume_processed_data)
consumer_thread.daemon = True
consumer_thread.start()

# Handle Kafka producer errors
def handle_kafka_error(background_tasks: BackgroundTasks, data: Dict[str, Any]) -> None:
    """Try to resend data to Kafka if initial attempt fails"""
    try:
        if producer:
            future = producer.send(INCOMING_TOPIC, data)
            result = future.get(timeout=10)
            logger.info(f"Data successfully resent to Kafka, request_id: {data.get('request_id')}")
    except Exception as e:
        logger.error(f"Failed to resend data to Kafka: {e}")

@app.post("/api/data", response_model=ApiResponse)
async def receive_data(user_data: UserData, background_tasks: BackgroundTasks):
    REQUEST_COUNT.inc()
    
    if producer is None:
        raise HTTPException(status_code=503, detail="Kafka producer not available")
    
    try:
        # Convert Pydantic model to dict
        data_dict = user_data.model_dump()
        request_id = f"{time.time()}-{user_data.user_id}-{uuid.uuid4().hex[:8]}"
        
        # Add metadata for tracking
        data_dict['timestamp_received'] = time.time()
        data_dict['request_id'] = request_id
        
        # Send data to Kafka
        try:
            future = producer.send(INCOMING_TOPIC, data_dict)
            result = future.get(timeout=5)  # Wait for the send to complete with timeout
            logger.info(f"Data sent to Kafka topic {INCOMING_TOPIC}, request_id: {request_id}")
        except Exception as e:
            logger.warning(f"Initial Kafka send failed: {e}, scheduling retry")
            background_tasks.add_task(handle_kafka_error, background_tasks, data_dict)
            return ApiResponse(
                status="pending", 
                message="Data scheduled for processing (retry)", 
                request_id=request_id
            )
        
        return ApiResponse(
            status="success", 
            message="Data sent for processing",
            request_id=request_id
        )
        
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def event_generator():
    """Generate SSE events"""
    # Send initial connected message
    yield f"data: {json.dumps({'connected': True, 'timestamp': time.time()})}\n\n"
    
    while True:
        try:
            # Try to get data from queue (non-blocking)
            try:
                data = results_queue.get_nowait()
                QUEUE_SIZE.set(results_queue.qsize())
                yield f"data: {json.dumps(data)}\n\n"
            except queue.Empty:
                # If no data, wait a bit and send heartbeat
                await asyncio.sleep(5)
                yield f"data: {json.dumps({'heartbeat': True, 'timestamp': time.time()})}\n\n"
        except asyncio.CancelledError:
            # Client disconnected
            ACTIVE_CONNECTIONS.dec()
            logger.info("SSE connection closed")
            break
        except Exception as e:
            logger.error(f"Error in event generator: {e}")
            await asyncio.sleep(1)  # Wait before retry

@app.get("/api/stream")
async def stream(request: Request):
    """SSE endpoint to stream processed results back to frontend"""
    ACTIVE_CONNECTIONS.inc()
    logger.info("New SSE connection established")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'  # Disable buffering in nginx
        }
    )

@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration"""
    health_status = {
        "status": "healthy",
        "kafka_producer": "available" if producer is not None else "unavailable",
        "active_sse_connections": ACTIVE_CONNECTIONS._value.get(),
        "queue_size": results_queue.qsize(),
    }
    
    if producer is None:
        return JSONResponse(status_code=503, content=health_status)
    
    return health_status

@app.get("/metrics")
async def metrics():
    """Metrics endpoint for Prometheus"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    logger.info("FastAPI server started")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("FastAPI server shutting down")
    if producer:
        producer.close()
        logger.info("Kafka producer closed")

# Add a Response class for metrics endpoint
from fastapi.responses import Response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)