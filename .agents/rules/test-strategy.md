---
trigger: model_decision
description: Applied when implementing or modifying test code. Rules for creating test perspective tables (equivalence partitioning/boundary values), Given/When/Then format, and coverage targets
globs: 
---

# Test Strategy Rules

Mandatory testing process for implementing or modifying tests in this repository.

## 1. Test Perspective Table (Design Phase)
Before implementing test code, generate a concise Markdown perspectives table covering:
- **Columns:** `Case ID`, `Input / Precondition`, `Perspective`, `Expected Result`, `Notes`.
- **Perspectives:** Nominal scenarios, error paths, and boundary values (`0 / min / max / ±1 / empty / NULL`).
- **Non-Blocking Flow:** Do not pause for user confirmation after displaying the table; proceed directly with implementation in the same response unless critical ambiguities arise.

| Case ID | Input / Precondition | Perspective | Expected Result | Notes |
| :--- | :--- | :--- | :--- | :--- |
| TC-N-01 | Valid payload | Equivalence – Normal | 200 OK & expected output | - |
| TC-E-01 | Missing required field | Boundary – Empty | 400 Bad Request | - |

## 2. Test Implementation Policy
- **Failure Cases Priority:** Always include **failure cases $\ge$ normal cases** (validation errors, timeouts, external service failures).
- **Core Perspectives:**
  - Normal execution paths.
  - Validation errors and edge inputs.
  - Boundary conditions (`0`, empty strings, null/None, max sizes).
  - External dependency failures (simulated via mocks/stubs).
- **Coverage Target:** Aim for **100% branch coverage**. Cover all critical decision branches and error handlers.

## 3. Given / When / Then Structure
Every test case must follow the explicit **Given / When / Then** structure:
```python
# Given: Preconditions, authenticated client, mock state
# When:  Action or request executed
# Then:  Assertions on status code, response body, and mock calls
```

## 4. Exception & Error Assertions
- Verify both the exception **type** and the specific error **message/code**.
- For mocks and stubs, verify call arguments and retry/fallback behaviors.

## 5. Execution Commands & Operational Verification
- Run tests in the dedicated environment: `/mnt/venv_ext4/venv_render_signal_server/bin/pytest`.
- Always verify test passage and report coverage commands (e.g., `pytest --cov=. tests/`).
- Code changes impacting behavior must include automated tests; refactorings must preserve green status.
