"""
Serverless To-Do List — AWS Lambda Handler

Handles CRUD operations for todo items via API Gateway.
Uses boto3 to interact with Amazon DynamoDB.
Each request is routed based on HTTP method and path.
"""

import json
import uuid
import time
import os
import logging
import boto3
from botocore.exceptions import ClientError

# Configure logging for CloudWatch
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# DynamoDB connection — lazily initialized so the module can be imported
# locally without AWS credentials. On Lambda, the first invocation triggers init.
TABLE_NAME = os.environ.get("TABLE_NAME", "TodosTable")
_table = None


def _get_table():
    """Lazy-initialise the DynamoDB Table resource on first use."""
    global _table
    if _table is None:
        dynamodb = boto3.resource("dynamodb")
        _table = dynamodb.Table(TABLE_NAME)
    return _table


# ============================================================
# Helper: Build a standardised HTTP response with CORS headers
# ============================================================
def build_response(status_code, body=None):
    """Return an API Gateway-compatible response dict with CORS headers."""
    response = {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
    }
    if body is not None:
        response["body"] = json.dumps(body, default=str)
    return response


# ============================================================
# CRUD Handlers
# ============================================================

def get_todos():
    """Scan DynamoDB table and return all todo items."""
    logger.info("Fetching all todos")
    try:
        result = _get_table().scan()
        todos = result.get("Items", [])
        return build_response(200, {"todos": todos})
    except ClientError as e:
        logger.error("DynamoDB scan failed: %s", e.response["Error"]["Message"])
        return build_response(500, {"error": "Could not fetch todos"})


def create_todo(body):
    """Create a new todo item in DynamoDB.

    Expects JSON body: { "title": "string" }
    Generates a UUID for the item id and a Unix timestamp.
    """
    title = body.get("title", "").strip()
    if not title:
        return build_response(400, {"error": "Title is required"})

    todo = {
        "id": str(uuid.uuid4()),
        "title": title,
        "completed": False,
        "createdAt": int(time.time() * 1000),  # epoch ms for JS compatibility
    }

    logger.info("Creating todo: %s", todo["id"])
    try:
        _get_table().put_item(Item=todo)
        return build_response(201, {"todo": todo})
    except ClientError as e:
        logger.error("DynamoDB put_item failed: %s", e.response["Error"]["Message"])
        return build_response(500, {"error": "Could not create todo"})


def update_todo(todo_id, body):
    """Update a todo item's completed status.

    Expects JSON body: { "completed": true|false }
    Optionally also accepts { "title": "new title" }.
    """
    update_parts = []
    expr_names = {}
    expr_values = {}

    if "completed" in body:
        update_parts.append("#c = :c")
        expr_names["#c"] = "completed"
        expr_values[":c"] = body["completed"]

    if "title" in body:
        update_parts.append("#t = :t")
        expr_names["#t"] = "title"
        expr_values[":t"] = body["title"]

    if not update_parts:
        return build_response(400, {"error": "No fields to update"})

    logger.info("Updating todo: %s", todo_id)
    try:
        result = _get_table().update_item(
            Key={"id": todo_id},
            UpdateExpression="SET " + ", ".join(update_parts),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
            ReturnValues="ALL_NEW",
        )
        return build_response(200, {"todo": result["Attributes"]})
    except ClientError as e:
        logger.error("DynamoDB update failed: %s", e.response["Error"]["Message"])
        return build_response(500, {"error": "Could not update todo"})


def delete_todo(todo_id):
    """Delete a todo item from DynamoDB by its id."""
    logger.info("Deleting todo: %s", todo_id)
    try:
        _get_table().delete_item(Key={"id": todo_id})
        return build_response(200, {"message": "Todo deleted"})
    except ClientError as e:
        logger.error("DynamoDB delete failed: %s", e.response["Error"]["Message"])
        return build_response(500, {"error": "Could not delete todo"})


# ============================================================
# Lambda Entry Point — Routes requests by method + path
# ============================================================

def lambda_handler(event, context):
    """Main Lambda handler. Routes API Gateway requests to CRUD functions.

    Routing logic:
        GET    /todos          → get_todos()
        POST   /todos          → create_todo(body)
        PUT    /todos/{id}     → update_todo(id, body)
        DELETE /todos/{id}     → delete_todo(id)
        OPTIONS *              → CORS preflight
    """
    logger.info("Event: %s", json.dumps(event))

    http_method = event.get("httpMethod", "")
    path = event.get("path", "")
    path_params = event.get("pathParameters") or {}

    # Handle CORS preflight
    if http_method == "OPTIONS":
        return build_response(200)

    # Parse JSON body for POST / PUT
    body = {}
    if event.get("body"):
        try:
            body = json.loads(event["body"])
        except (json.JSONDecodeError, TypeError):
            return build_response(400, {"error": "Invalid JSON body"})

    # --- Route: GET /todos ---
    if http_method == "GET" and path == "/todos":
        return get_todos()

    # --- Route: POST /todos ---
    if http_method == "POST" and path == "/todos":
        return create_todo(body)

    # --- Route: PUT /todos/{id} ---
    if http_method == "PUT" and path_params.get("id"):
        return update_todo(path_params["id"], body)

    # --- Route: DELETE /todos/{id} ---
    if http_method == "DELETE" and path_params.get("id"):
        return delete_todo(path_params["id"])

    # Fallback for unknown routes
    return build_response(404, {"error": "Route not found"})
