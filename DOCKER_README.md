# 🐳 GST Automation API - Docker Setup

This document explains how to build and run the GST Registration Automation API using Docker.

## 📋 Prerequisites

- **Docker** (version 20.10+)
- **Docker Compose** (version 1.29+)
- **2GB+ RAM** available for the container

## 🏗️ Build & Run

### Option 1: Using Docker Compose (Recommended)

```bash
# 1. Clone/navigate to the project directory
cd GST_REG

# 2. Build and start the container
docker-compose up --build

# 3. Access the API
# - API: http://localhost:8001
# - Swagger UI: http://localhost:8001/docs/
```

### Option 2: Using Docker Commands

```bash
# 1. Build the Docker image
docker build -t gst-automation .

# 2. Run the container
docker run -d \
  --name gst-automation-api \
  -p 8001:8001 \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/uploads:/app/uploads \
  gst-automation

# 3. Check logs
docker logs -f gst-automation-api
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_ENV` | `production` | Flask environment mode |
| `FLASK_DEBUG` | `false` | Enable Flask debug mode |
| `DISPLAY` | `:99` | Virtual display for headless browser |
| `TZ` | `Asia/Kolkata` | Container timezone |

### Volume Mounts

| Host Path | Container Path | Purpose |
|-----------|----------------|---------|
| `./logs` | `/app/logs` | Persist automation logs |
| `./uploads` | `/app/uploads` | Store uploaded documents |
| `./downloads` | `/app/downloads` | Store downloaded files |
| `./config.json` | `/app/config.json` | Default configuration (optional) |

## 🚀 Usage

### 1. Using Swagger UI (Web Interface)

1. Open browser: `http://localhost:8001/docs/`
2. Click on **POST /automate-gst-registration**
3. Click **"Try it out"**
4. Paste your JSON configuration
5. Click **"Execute"**

### 2. Using curl (Command Line)

```bash
# Using JSON file
curl -X POST "http://localhost:8001/api/v1/automate-gst-registration" \
     -H "Content-Type: application/json" \
     -d @config.json

# Using inline JSON
curl -X POST "http://localhost:8001/api/v1/automate-gst-registration" \
     -H "Content-Type: application/json" \
     -d '{
       "initial_registration_details": {...},
       "business_details": {...},
       ...
     }'
```

### 3. Using Python

```python
import requests
import json

# Load configuration
with open('config.json', 'r') as f:
    config = json.load(f)

# Send request
response = requests.post(
    'http://localhost:8001/api/v1/automate-gst-registration',
    json=config
)

print(response.json())
```

## 📊 Monitoring

### Health Check

```bash
# Check if API is running
curl http://localhost:8001/api/v1/health

# Expected response:
# {"status": "ok", "message": "API is running."}
```

### Container Logs

```bash
# View real-time logs
docker-compose logs -f gst-automation

# View specific number of log lines
docker-compose logs --tail=100 gst-automation
```

### Container Status

```bash
# Check container status
docker-compose ps

# Get container stats
docker stats gst-automation-api
```

## 🐛 Troubleshooting

### Common Issues

#### 1. **Port Already in Use**
```bash
# Check what's using port 8001
lsof -i :8001

# Kill the process or change port in docker-compose.yml
```

#### 2. **Permission Issues with Volumes**
```bash
# Fix permissions for log directory
sudo chown -R $USER:$USER ./logs
chmod -R 755 ./logs
```

#### 3. **Container Won't Start**
```bash
# Check detailed logs
docker-compose logs gst-automation

# Restart container
docker-compose restart gst-automation
```

#### 4. **Firefox/Selenium Issues**
```bash
# Check if display is working
docker exec -it gst-automation-api bash
echo $DISPLAY
ps aux | grep Xvfb
```

### Debug Mode

To run the container in debug mode:

```bash
# Edit docker-compose.yml
environment:
  - FLASK_DEBUG=true
  - FLASK_ENV=development

# Restart
docker-compose up --build
```

## 🔄 Updates & Maintenance

### Updating the Application

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose down
docker-compose up --build
```

### Cleaning Up

```bash
# Stop and remove containers
docker-compose down

# Remove images (optional)
docker rmi gst-automation

# Clean up volumes (⚠️ This will delete logs)
docker-compose down -v
```

## 📈 Production Deployment

### Using Docker Swarm

```bash
# Deploy as a service
docker service create \
  --name gst-automation \
  --publish 8001:8001 \
  --mount type=bind,source=$(pwd)/logs,target=/app/logs \
  gst-automation
```

### Using Kubernetes

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gst-automation
spec:
  replicas: 1
  selector:
    matchLabels:
      app: gst-automation
  template:
    metadata:
      labels:
        app: gst-automation
    spec:
      containers:
      - name: gst-automation
        image: gst-automation:latest
        ports:
        - containerPort: 8001
        volumeMounts:
        - name: logs
          mountPath: /app/logs
      volumes:
      - name: logs
        hostPath:
          path: /path/to/logs
```

### Reverse Proxy (Nginx)

Uncomment the nginx service in `docker-compose.yml` and create `nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream gst-api {
        server gst-automation:8001;
    }

    server {
        listen 80;
        server_name your-domain.com;

        location / {
            proxy_pass http://gst-api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
```

## 🔒 Security Considerations

1. **Never expose sensitive data** in environment variables
2. **Use secrets management** for production
3. **Limit container resources** to prevent abuse
4. **Use non-root user** in production builds
5. **Regularly update base images** for security patches

## 📞 Support

For issues with the Docker setup:

1. Check the logs: `docker-compose logs -f`
2. Verify your configuration JSON structure
3. Ensure all required ports are available
4. Check Docker and Docker Compose versions

## 🎯 What's Included

- ✅ **Firefox Browser** (ESR version for stability)
- ✅ **Geckodriver** (Latest version)
- ✅ **Python Dependencies** (From requirements.txt)
- ✅ **Virtual Display** (Xvfb for headless operation)
- ✅ **Health Checks** (Automatic container health monitoring)
- ✅ **Volume Mounts** (Persistent logs and uploads)
- ✅ **Timezone Support** (Configurable timezone)
- ✅ **Error Handling** (Comprehensive error logging) 