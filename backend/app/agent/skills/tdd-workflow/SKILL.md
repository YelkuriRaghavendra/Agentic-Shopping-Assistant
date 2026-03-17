# TDD Workflow Skill

## When to Apply This Skill

Apply whenever:
- Implementing a new feature
- Adding a new endpoint or service method
- Writing tests for existing untested code
- Refactoring code that needs test coverage

## The TDD Cycle

```
    ┌──────────────────────────────────┐
    │                                  │
    │   RED → GREEN → REFACTOR         │
    │     ↑               │            │
    │     └───────────────┘            │
    │                                  │
    └──────────────────────────────────┘
```

### RED — Write a failing test

Write the test FIRST. The test should describe the behaviour you want.

```python
# 🔴 RED — this test fails because AuthService doesn't exist yet
def test_login_valid_credentials_returns_token():
    service = AuthService()
    token = await service.login("user@test.com", "correct_password")
    assert token is not None
    assert isinstance(token, str)
```

**Rules for RED phase:**
- Test must fail when you run it
- Test describes BEHAVIOUR not implementation
- One concept per test
- Descriptive name: `test_<what>_<condition>_<expected_result>`

### GREEN — Write minimal implementation

Write the MINIMUM code to make the test pass. Nothing more.

```python
# 🟢 GREEN — just enough to pass
class AuthService:
    async def login(self, email: str, password: str) -> str:
        user = await db.find_user(email)
        if not user or not user.check_password(password):
            raise InvalidCredentialsError()
        return create_token(user.id)
```

**Rules for GREEN phase:**
- Minimum code only — resist the urge to build ahead
- Hard-coded values are acceptable if they make tests pass
- Speed matters here — make it work, make it right later
- Run tests after every change

### REFACTOR — Clean up

Now improve the code. Tests must still pass.

```python
# 🔵 REFACTOR — extracted constants, better error handling, docstring added
class AuthService:
    """Handles user authentication and token management."""

    TOKEN_EXPIRY_HOURS = 24

    async def login(self, email: str, password: str) -> Token:
        """
        Authenticate a user and return a JWT token.
        Raises InvalidCredentialsError if credentials are wrong.
        """
        user = await self._find_and_verify_user(email, password)
        return self._create_token(user)
```

**Rules for REFACTOR phase:**
- Do not add new functionality during refactor
- Run tests after every change
- Extract duplication
- Improve names
- Add docstrings

---

## Interface-First Pattern

Before any tests, define the public interface:

```python
# Define WHAT, not HOW
from abc import ABC, abstractmethod

class AuthServiceBase(ABC):
    @abstractmethod
    async def login(self, email: str, password: str) -> str: ...

    @abstractmethod
    async def logout(self, token: str) -> None: ...

    @abstractmethod
    async def verify_token(self, token: str) -> dict: ...
```

Benefits:
- Clarifies the contract before you write tests
- Makes mocking easy in other tests
- Prevents scope creep

---

## Test Naming Convention

```
test_<subject>_<condition>_<expected>

Examples:
  test_login_valid_credentials_returns_token      ✅
  test_login_wrong_password_raises_error          ✅
  test_verify_expired_token_raises_expired_error  ✅
  test_logout_valid_token_invalidates_it          ✅

  test_login    ❌  (too vague)
  test_auth     ❌  (too vague)
  loginTest     ❌  (wrong convention)
```

---

## Coverage Requirements

Run after each RED→GREEN→REFACTOR cycle:

```bash
pytest tests/ --cov=app --cov-report=term-missing
```

| Coverage | Action |
|----------|--------|
| ≥ 80% | Acceptable — move on |
| 60–79% | Add tests for uncovered branches |
| < 60% | Stop — identify and test all critical paths |

**What to test:**
- Happy path (normal input → expected output)
- Error cases (invalid input → correct exception)
- Edge cases (empty, None, boundary values)
- Integration points (service calls repo correctly)

**What NOT to test:**
- Third-party library internals
- Private methods directly (test through public interface)
- Implementation details that could change

---

## Fixtures Pattern

```python
# conftest.py — shared fixtures
import pytest

@pytest.fixture
def auth_service():
    """Provide a fresh AuthService for each test."""
    return AuthService(db=MockDatabase())

@pytest.fixture
def valid_user():
    return User(id=uuid4(), email="test@test.com", password_hash=hash("correct"))

@pytest.fixture
def expired_token():
    return create_token(user_id=uuid4(), expires_in=-1)  # already expired
```

---

## Mocking External Dependencies

```python
# Never call real external services in unit tests
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_login_calls_database(auth_service):
    with patch.object(auth_service, '_db') as mock_db:
        mock_db.find_user = AsyncMock(return_value=None)

        with pytest.raises(InvalidCredentialsError):
            await auth_service.login("nobody@test.com", "password")

        mock_db.find_user.assert_called_once_with("nobody@test.com")
```

---

## Parametrize for Data-Driven Tests

```python
@pytest.mark.parametrize("email,password,should_raise", [
    ("valid@test.com", "correct", False),
    ("valid@test.com", "wrong",   True),
    ("",               "correct", True),
    ("not-an-email",   "correct", True),
])
async def test_login_validation(auth_service, email, password, should_raise):
    if should_raise:
        with pytest.raises(Exception):
            await auth_service.login(email, password)
    else:
        token = await auth_service.login(email, password)
        assert token is not None
```
