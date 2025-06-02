# README.md

# FlavorLens FastAPI

A FastAPI application for ingredient analytics and food trend insights, converted from Next.js API routes.

## Features

- **Texture Analysis**: Get texture attributes and trends for ingredients
- **Temperature Distribution**: Analyze serving temperature preferences
- **Geographic Insights**: Understand global adoption patterns
- **Format Analysis**: Track ingredient format adoption
- **Application Tracking**: Monitor ingredient applications across categories
- **Lifecycle Analysis**: Track ingredient adoption phases and seasonality
- **Flavor Profiling**: Deep flavor analysis and sensory dimensions
- **Cuisine Distribution**: See how ingredients are used across cuisines
- **Trend Analysis**: Identify trending applications and innovation opportunities

## Quick Start

### Using Docker (Recommended)

1. Clone the repository:
```bash
git clone <repository-url>
cd flavorlens-api
```

2. Create environment file:
```bash
cp .env.example .env
# Edit .env with your MotherDuck token
```

3. Run with Docker Compose:
```bash
docker-compose up -d
```

The API will be available at `http://localhost:8000`

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables:
```bash
export MOTHERDUCK_TOKEN=your_token_here
```

3. Run the application:
```bash
uvicorn main:app --reload
```

## API Documentation

Once running, visit:
- Interactive API docs: `http://localhost:8000/docs`
- ReDoc documentation: `http://localhost:8000/redoc`

## API Endpoints

### Core Endpoints

- `GET /api/texture-attributes?ingredient={name}` - Texture analysis
- `GET /api/serving-temperature?ingredient={name}` - Temperature distribution
- `GET /api/geographic-distribution?ingredient={name}` - Geographic insights
- `GET /api/format-adoption?ingredient={name}` - Format adoption data
- `GET /api/applications?ingredient={name}&category={category}` - Application analysis
- `GET /api/category-distribution?ingredient={name}` - Category breakdown
- `GET /api/subcategory-trends?ingredient={name}` - Trend analysis over time
- `GET /api/recipe-share?ingredient={name}` - Recipe market share
- `GET /api/menu-share?ingredient={name}` - Menu market share
- `GET /api/lifecycle-position?ingredient={name}` - Adoption lifecycle analysis
- `GET /api/flavor-profile?ingredient={name}` - Comprehensive flavor profiling
- `GET /api/cuisine-distribution?ingredient={name}` - Cuisine usage patterns
- `GET /api/category-penetration?ingredient={name}` - Market penetration analysis
- `GET /api/trending-applications?ingredient={name}` - Trending applications and opportunities

### Health Check

- `GET /health` - API health status
- `GET /` - Root endpoint

## Database Configuration

The application connects to MotherDuck (cloud DuckDB) by default. Configure your connection:

```env
MOTHERDUCK_TOKEN=your_motherduck_token
DATABASE_URL=md:flavorlens
```

For local development, you can use a local DuckDB file by omitting the MotherDuck token.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MOTHERDUCK_TOKEN` | MotherDuck authentication token | None |
| `DATABASE_URL` | Database connection string | `md:flavorlens` |
| `LOG_LEVEL` | Logging level | `info` |

## Performance Features

- **Query Caching**: Built-in caching for database queries with configurable TTL
- **Connection Pooling**: Efficient database connection management
- **Async Operations**: Full async support for concurrent request handling
- **Response Compression**: Automatic response compression for large datasets

## Error Handling

The API includes comprehensive error handling:
- Database connection failures fall back gracefully
- Invalid parameters return descriptive error messages
- All endpoints include proper HTTP status codes
- Detailed error logging for debugging

## Development

### Project Structure

```python
from database.connection import execute_query, QueryOptions
from database.models import YourModel
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

@router.get("/your-endpoint", response_model=YourModel)
async def your_endpoint(ingredient: str = Query(...)):
    try:
        query = "SELECT * FROM table WHERE ingredient ILIKE %s"
        result = await execute_query(
            query, 
            [f"%{ingredient}%"],
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        return process_result(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error message")
```

### Adding New Endpoints

1. Create a new router file in `routers/`
2. Define Pydantic models in `database/models.py`
3. Add the router to `main.py`
4. Write your database queries using the `execute_query` function

### Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest
```

## Production Deployment

### Docker Deployment

```bash
# Build and push to registry
docker build -t flavorlens-api .
docker push your-registry/flavorlens-api

# Deploy with environment variables
docker run -d \
  -p 8000:8000 \
  -e MOTHERDUCK_TOKEN=your_token \
  -e LOG_LEVEL=info \
  your-registry/flavorlens-api
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: flavorlens-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: flavorlens-api
  template:
    metadata:
      labels:
        app: flavorlens-api
    spec:
      containers:
      - name: api
        image: your-registry/flavorlens-api
        ports:
        - containerPort: 8000
        env:
        - name: MOTHERDUCK_TOKEN
          valueFrom:
            secretKeyRef:
              name: flavorlens-secrets
              key: motherduck-token
```

## Performance Considerations

- Database queries are optimized for DuckDB/MotherDuck
- Caching is enabled by default with 1-hour TTL for most endpoints
- Use connection pooling in production environments
- Consider adding rate limiting for public APIs
- Monitor query performance and optimize slow queries

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

[Your License Here]
# flavorlens-api
