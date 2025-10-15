"""
Authentication middleware for Linear GraphQL API.

This module provides JWT-based authentication for GraphQL requests.
It extracts the user ID from the JWT token and adds it to the GraphQL context.
"""

import jwt
from typing import Any, Dict, Optional
from datetime import datetime, timezone


# Configuration - in production, load from environment variables
SECRET_KEY = "your-secret-key-change-this-in-production"  # Use env var: os.getenv('JWT_SECRET_KEY')
JWT_ALGORITHM = "HS256"


def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT token.

    Args:
        token: The JWT token string

    Returns:
        Dict containing the decoded payload, or None if invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])

        # Check if token is expired
        if 'exp' in payload:
            exp_timestamp = payload['exp']
            if datetime.fromtimestamp(exp_timestamp, tz=timezone.utc) < datetime.now(timezone.utc):
                print("Token expired")
                return None

        return payload
    except jwt.InvalidTokenError as e:
        print(f"Invalid token: {e}")
        return None
    except Exception as e:
        print(f"Error decoding token: {e}")
        return None


def get_context_value(request: Any, session: Any) -> Dict[str, Any]:
    """
    Create the GraphQL context for each request.

    This function is called by Ariadne for every GraphQL request.
    It extracts authentication information and provides it to resolvers.

    Args:
        request: The HTTP request object (FastAPI Request, Flask request, etc.)
        session: The SQLAlchemy database session

    Returns:
        Dict containing the context with 'session', 'user_id', and 'request'

    Note:
        - context['user_id'] is a STRING (the user's ID), NOT a User object
        - Resolvers should query the database if they need the User object:
          user = session.query(User).filter_by(id=info.context['user_id']).first()
    """
    context = {
        "session": session,
        "request": request,
        "user_id": None,  # String ID of authenticated user, or None if not authenticated
        "organization_id": None,  # String ID of user's organization, or None if not authenticated
    }

    # Extract authorization header
    auth_header = None

    # Handle different framework request objects
    if hasattr(request, 'headers'):  # FastAPI/Starlette
        auth_header = request.headers.get('Authorization')
    elif hasattr(request, 'META'):  # Django
        auth_header = request.META.get('HTTP_AUTHORIZATION')
    elif hasattr(request, 'environ'):  # Flask/Werkzeug
        auth_header = request.environ.get('HTTP_AUTHORIZATION')

    # Parse the Bearer token
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        payload = decode_jwt_token(token)

        if payload:
            # Extract user_id from token payload
            # Common JWT claim names: 'sub' (subject), 'user_id', 'userId'
            user_id = payload.get('sub') or payload.get('user_id') or payload.get('userId')

            if user_id:
                context['user_id'] = user_id
                print(f"Authenticated request from user: {user_id}")

            # Extract organization_id from token payload
            # Common JWT claim names: 'organization_id', 'organizationId', 'org_id'
            organization_id = payload.get('organization_id') or payload.get('organizationId') or payload.get('org_id')

            if organization_id:
                context['organization_id'] = organization_id
                print(f"User belongs to organization: {organization_id}")

    return context


def create_jwt_token(user_id: str, organization_id: Optional[str] = None, expires_in_hours: int = 24) -> str:
    """
    Create a JWT token for a user.

    This is a helper function for creating tokens after login.

    Args:
        user_id: The user's ID
        organization_id: The user's organization ID (optional)
        expires_in_hours: Token expiration time in hours

    Returns:
        JWT token string
    """
    from datetime import timedelta

    payload = {
        'sub': user_id,  # Standard JWT claim for subject (user ID)
        'user_id': user_id,  # Also include as user_id for compatibility
        'iat': datetime.now(timezone.utc),  # Issued at
        'exp': datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)  # Expiration
    }

    # Include organization_id if provided
    if organization_id:
        payload['organization_id'] = organization_id

    token = jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


# Example usage in a login mutation (add this to resolvers.py if needed):
"""
@mutation.field("login")
def resolve_login(obj, info, **kwargs):
    from Linear.auth_middleware import create_jwt_token

    session: Session = info.context['session']
    email = kwargs.get('email')
    password = kwargs.get('password')

    # Authenticate user (verify password, etc.)
    user = session.query(User).filter_by(email=email).first()

    if user and verify_password(password, user.password_hash):
        # Create JWT token with user_id and organization_id
        token = create_jwt_token(
            user_id=user.id,
            organization_id=user.organizationId  # Include organization from User model
        )

        return {
            'token': token,
            'user': user
        }
    else:
        raise Exception("Invalid credentials")
"""
