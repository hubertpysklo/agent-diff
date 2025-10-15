"""
GraphQL server setup for Linear API using Ariadne and FastAPI.

This module demonstrates how to set up a complete GraphQL server with:
- Authentication middleware
- Database session management
- Schema binding
- CORS support
"""

from fastapi import FastAPI, Request
from ariadne import make_executable_schema, graphql
from ariadne.asgi import GraphQL
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Any

# Import your resolvers and schema
from Linear.resolvers import query, mutation
from Linear.auth_middleware import get_context_value


# Database setup
DATABASE_URL = "sqlite:///./linear.db"  # Change to your actual database URL
# For PostgreSQL: "postgresql://user:password@localhost:5432/linear"
# For MySQL: "mysql://user:password@localhost:3306/linear"

engine = create_engine(
    DATABASE_URL,
    echo=True,  # Set to False in production
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Load GraphQL schema (you need to provide your schema file)
# This is a minimal example - replace with your actual Linear-API.graphql schema
type_defs = """
    type Query {
        viewer: User
        issues: [Issue!]!
    }

    type Mutation {
        issueCreate(input: IssueCreateInput!): IssuePayload!
    }

    type User {
        id: ID!
        email: String!
        name: String!
    }

    type Issue {
        id: ID!
        title: String!
        description: String
    }

    input IssueCreateInput {
        title: String!
        description: String
    }

    type IssuePayload {
        issue: Issue!
        success: Boolean!
    }
"""

# Create executable schema
schema = make_executable_schema(type_defs, query, mutation)


# Create FastAPI app
app = FastAPI(
    title="Linear GraphQL API",
    description="GraphQL API for Linear issue tracking",
    version="1.0.0"
)


# Middleware to add CORS headers (if needed)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db_session() -> Session:
    """Create a new database session."""
    return SessionLocal()


async def get_context_value_for_request(request: Request) -> dict[str, Any]:
    """
    Create GraphQL context for each request.

    This function:
    1. Creates a database session
    2. Extracts authentication info from request
    3. Returns context dict for resolvers
    """
    # Create database session
    session = get_db_session()

    try:
        # Get context with authentication
        context = get_context_value(request, session)
        return context
    except Exception as e:
        # Close session on error
        session.close()
        raise e


# Create GraphQL app with custom context
graphql_app = GraphQL(
    schema,
    context_value=get_context_value_for_request,
    debug=True  # Set to False in production
)


# Mount GraphQL endpoint
@app.post("/graphql")
async def graphql_endpoint(request: Request):
    """GraphQL endpoint."""
    return await graphql_app.handle_request(request)


# Add a health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Linear GraphQL API"}


# Add an endpoint to test authentication
@app.get("/test-auth")
async def test_auth(request: Request):
    """Test authentication by showing the extracted user_id."""
    session = get_db_session()
    try:
        context = get_context_value(request, session)
        return {
            "authenticated": context['user_id'] is not None,
            "user_id": context['user_id']
        }
    finally:
        session.close()


if __name__ == "__main__":
    import uvicorn

    print("Starting Linear GraphQL Server...")
    print("GraphQL endpoint: http://localhost:8000/graphql")
    print("Health check: http://localhost:8000/health")
    print("Auth test: http://localhost:8000/test-auth")

    uvicorn.run(
        "Linear.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes (dev only)
        log_level="info"
    )
