# Authentication Setup Guide

This guide explains how to set up authentication for the Linear GraphQL API.

## Overview

The authentication system uses **JWT (JSON Web Tokens)** to authenticate users. Here's how it works:

1. User logs in → Server generates JWT token
2. Client includes token in `Authorization` header for subsequent requests
3. Server validates token and extracts `user_id`
4. Resolvers access `user_id` via `info.context['user_id']`

## Files

- **`auth_middleware.py`**: JWT authentication logic
- **`server.py`**: FastAPI server setup with authentication
- **`resolvers.py`**: GraphQL resolvers that use authentication

## Quick Start

### 1. Install Dependencies

```bash
pip install fastapi uvicorn ariadne sqlalchemy pyjwt python-multipart
```

### 2. Set Environment Variables

```bash
export JWT_SECRET_KEY="your-super-secret-key-change-this"
export DATABASE_URL="postgresql://user:pass@localhost/linear"
```

### 3. Run the Server

```bash
python -m Linear.server
```

Or using uvicorn directly:

```bash
uvicorn Linear.server:app --reload --host 0.0.0.0 --port 8000
```

### 4. Test Authentication

#### Get a JWT Token (example)

Since we don't have a login mutation yet, you can generate a test token using Python:

```python
from Linear.auth_middleware import create_jwt_token

# Create a token for a test user with organization
token = create_jwt_token(
    user_id="test-user-id-123",
    organization_id="test-org-id-456"
)
print(f"Token: {token}")
```

#### Make Authenticated GraphQL Request

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE" \
  -d '{
    "query": "{ viewer { id email name } }"
  }'
```

#### Test Authentication Endpoint

```bash
curl http://localhost:8000/test-auth \
  -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE"
```

## How It Works

### Context Flow

```
HTTP Request
    ↓
FastAPI receives request
    ↓
get_context_value_for_request() called
    ↓
1. Creates database session
2. Extracts "Authorization: Bearer <token>" header
3. Decodes JWT token
4. Extracts user_id from token payload
5. Returns context dict: { "session": session, "user_id": user_id, "request": request }
    ↓
GraphQL resolver executes
    ↓
Resolver accesses: info.context['user_id']
    ↓
Response sent back to client
```

### Token Structure

A JWT token contains:

```json
{
  "sub": "user-id-here",
  "user_id": "user-id-here",
  "organization_id": "org-id-here",
  "iat": 1697385600,
  "exp": 1697472000
}
```

- `sub`: Standard JWT claim for subject (user ID)
- `user_id`: Duplicate for compatibility
- `organization_id`: User's organization ID (optional)
- `iat`: Issued at timestamp
- `exp`: Expiration timestamp

## Naming Convention Standardization

The codebase previously had inconsistent naming conventions for context keys.

**Standard: All context keys use snake_case (Python convention)**

### Context Keys

The context provides these standardized keys:

```python
info.context['user_id']          # The authenticated user's ID (string)
info.context['organization_id']  # The user's organization ID (string)
info.context['session']          # SQLAlchemy database session
info.context['request']          # HTTP request object
```

### What Changed

| Old (Inconsistent) | New (Standardized) |
|-------------------|-------------------|
| `current_user_id` | `user_id` |
| `user` (User object) | `user_id` (string) |
| `organizationId` (camelCase) | `organization_id` (snake_case) |

**All context access now follows Python snake_case convention.**

## Production Checklist

Before deploying to production:

- [ ] Change `SECRET_KEY` in `auth_middleware.py` to use environment variable
- [ ] Set `JWT_SECRET_KEY` environment variable with a strong random key
- [ ] Update `DATABASE_URL` to production database
- [ ] Set `debug=False` in GraphQL app
- [ ] Configure CORS properly (don't use `allow_origins=["*"]`)
- [ ] Add rate limiting
- [ ] Add logging for authentication failures
- [ ] Implement token refresh mechanism
- [ ] Add token revocation (blacklist)
- [ ] Use HTTPS only
- [ ] Set appropriate token expiration times

## Creating a Login Mutation

Add this to your `resolvers.py`:

```python
@mutation.field("login")
def resolve_login(obj, info, **kwargs):
    """
    Authenticate user and return JWT token.

    Args:
        email: User's email
        password: User's password

    Returns:
        { token: String!, user: User! }
    """
    from Linear.auth_middleware import create_jwt_token
    import bcrypt  # pip install bcrypt

    session: Session = info.context['session']
    email = kwargs.get('email')
    password = kwargs.get('password')

    if not email or not password:
        raise Exception("Email and password required")

    # Find user by email
    user = session.query(User).filter_by(email=email).first()

    if not user:
        raise Exception("Invalid credentials")

    # Verify password (assumes you store bcrypt hashed passwords)
    if not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
        raise Exception("Invalid credentials")

    # Create JWT token
    token = create_jwt_token(user.id, expires_in_hours=24)

    return {
        'token': token,
        'user': user,
        'success': True
    }
```

And add this to your GraphQL schema:

```graphql
type Mutation {
  login(email: String!, password: String!): LoginPayload!
}

type LoginPayload {
  token: String!
  user: User!
  success: Boolean!
}
```

## Testing Without Authentication (Development)

For development/testing, you can bypass authentication by modifying `get_context_value()`:

```python
def get_context_value(request: Any, session: Any) -> Dict[str, Any]:
    context = {
        "session": session,
        "request": request,
        "user_id": "test-user-id-123",  # Hardcode for testing
    }
    # ... rest of auth logic
```

## Troubleshooting

### "No authenticated user found" error

- Check that `Authorization` header is present
- Verify token format: `Bearer <token>`
- Ensure token is not expired
- Check that `SECRET_KEY` matches between token creation and validation

### Token validation fails

- Ensure PyJWT is installed: `pip install pyjwt`
- Check that algorithm matches (`HS256`)
- Verify secret key is correct
- Check token hasn't expired

### user_id is None in resolver

- Print debug info in `get_context_value()`
- Check request headers are being parsed correctly
- Verify your framework (FastAPI/Flask/Django) request object format
