# project_structure.md
# FastAPI FlavorLens Project Structure

```
flavorlens-api/
├── main.py                          # FastAPI main application
├── requirements.txt                 # Python dependencies
├── Dockerfile                       # Docker configuration
├── docker-compose.yml              # Docker Compose configuration
├── .env                            # Environment variables
├── README.md                       # Project documentation
├── database/
│   ├── __init__.py
│   ├── connection.py               # Database connection and query utilities
│   └── models.py                   # Pydantic models for API responses
├── routers/
│   ├── __init__.py
│   ├── texture_router.py           # Texture attributes endpoints
│   ├── temperature_router.py       # Serving temperature endpoints
│   ├── geographic_router.py        # Geographic distribution endpoints
│   ├── format_router.py            # Format adoption endpoints
│   ├── applications_router.py      # Applications dashboard endpoints
│   ├── category_router.py          # Category distribution endpoints
│   ├── subcategory_router.py       # Subcategory trends endpoints
│   ├── recipe_share_router.py      # Recipe share endpoints
│   ├── menu_share_router.py        # Menu share endpoints
│   ├── lifecycle_router.py         # Lifecycle position endpoints
│   ├── flavor_profile_router.py    # Flavor profile endpoints
│   ├── cuisine_router.py           # Cuisine distribution endpoints
│   ├── category_penetration_router.py  # Category penetration endpoints
│   └── trending_router.py          # Trending applications endpoints
└── logs/                           # Application logs directory
```
