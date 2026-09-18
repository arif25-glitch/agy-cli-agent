---
name: api_tester
description: Procedure for probing REST/HTTP endpoints, validating status codes, verifying JSON payload contracts, testing boundary cases, and reporting API health.
version: 1.0.0
tags: [api, testing, curl, rest, schema, validation]
---

# API Tester Procedure

Use this skill when developing, refactoring, or verifying REST APIs, webhook receivers, or external integrations.

### 1. Endpoint Contract Mapping
- Identify route paths, HTTP methods (GET, POST, PUT, DELETE), headers (`Content-Type: application/json`), and required query parameters.
- Define expected success status codes (200 OK, 201 Created, 204 No Content).

### 2. Probing Execution via Shell / Curl
- Test happy path with minimal valid payload:
  `curl -s -w "\n%{http_code}\n" -X POST "http://localhost:PORT/api/endpoint" -H "Content-Type: application/json" -d '{"key":"value"}'`
- Verify HTTP response status code matches expectation.
- Validate response body format against expected JSON schema.

### 3. Edge-Case Boundary Testing
- Test missing required fields (expect 400 Bad Request with actionable error).
- Test malformed JSON payloads.
- Test boundary values (empty strings, negative numbers, oversized arrays).
- Test non-existent IDs (expect 404 Not Found).

### 4. Results Reporting
- Compile a clear validation summary:
  * Tested Endpoints: list of paths and methods
  * Status Codes & Latency
  * Payload Schema Verification results
