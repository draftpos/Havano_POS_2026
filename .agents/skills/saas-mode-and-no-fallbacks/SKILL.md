---
name: saas-mode-and-no-fallbacks
description: Mandatory architectural standard and policy for Havano POS. Prohibits any fallback to localhost or dummy addresses in code and mandates that SaaS mode always targets https://backoffice.havano.pro/. Must be consulted before writing or modifying any network, API, host configuration, or database connection code.
---

# SaaS Mode & Anti-Fallback Policy

This skill defines mandatory architectural standards for handling backend hosts, endpoints, and credentials across the Havano POS codebase.

## 1. Absolute Prohibition of Localhost Fallbacks
- **Never write fallbacks to localhost**: Do not use `http://localhost`, `http://localhost:8069`, `http://localhost:8000`, `127.0.0.1`, or similar dummy strings as fallback defaults in `dict.get()`, `getattr()`, function signatures, or configuration fallbacks.
- **Fail Fast Principle**: If an API URL, server host, or database target is required but missing/unconfigured, the system must fail fast, prompt the user/admin to configure it, or raise an explicit error. It must **never** silently fall back to a local or dummy server.

## 2. SaaS Mode Base URL Standard
- **Official SaaS Endpoint**: SaaS mode operates exclusively against:
  ```
  https://backoffice.havano.pro/
  ```
- Any default server host, synchronization target, API route prefix, or test script interacting with SaaS backend must use `https://backoffice.havano.pro`.
- Trailing slashes should be stripped when concatenating subpaths (e.g. `host.rstrip('/') + '/saas_api/...'`).

## 3. Configuration Precedence for SaaS
When reading host configuration:
1. Check configured setting `api_url` or `server_api_host` from `company_defaults` or `app_data/sql_settings.json`.
2. If empty or absent in SaaS mode, resolve directly to `https://backoffice.havano.pro`.
3. Under no circumstances should `localhost` or local ports be substituted.
