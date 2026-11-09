import pytest
from pydantic import ValidationError
from app.models import Action, TestPlan as Plan
from app.security import NavigationPolicy, PolicyError, Redactor
from .helpers import assertion

@pytest.mark.parametrize("url",[
    "file:///etc/passwd","javascript:alert(1)","https://user:pass@example.com/",
    "http://127.0.0.1/","http://169.254.169.254/latest/meta-data/","http://10.0.0.1/","http://[::1]/"])
async def test_unsafe_urls_rejected(url):
    with pytest.raises(PolicyError):
        await NavigationPolicy(url).validate(url)

async def test_dns_to_private_address_rejected(monkeypatch):
    import socket
    monkeypatch.setattr(socket,"getaddrinfo",lambda *args,**kwargs:[(2,1,6,"",("10.1.2.3",443))])
    with pytest.raises(PolicyError):
        await NavigationPolicy("https://looks-public.test").validate("https://looks-public.test")

def test_arbitrary_code_action_rejected():
    with pytest.raises(ValidationError):
        Action(kind="evaluate",ref=None,value="document.cookie",assertion_id=None,destructive=False,reason="attack")

def test_extra_selector_field_rejected():
    with pytest.raises(ValidationError):
        Action(kind="click",ref="e1",value=None,assertion_id=None,destructive=False,reason="test",selector="#fixed")

def test_empty_or_duplicate_assertions_rejected():
    with pytest.raises(ValidationError):
        Plan(summary="empty",assertions=[])
    with pytest.raises(ValidationError):
        Plan(summary="duplicate",assertions=[assertion(),assertion()])

def test_secret_resolution_and_redaction():
    redact=Redactor({"PASS":"not-for-logs"})
    assert redact.resolve("{{PASS}}")=="not-for-logs"
    assert "not-for-logs" not in redact.clean("value: not-for-logs")
    assert "alice@example.com" not in redact.clean("alice@example.com")
    with pytest.raises(PolicyError):
        redact.resolve("{{UNKNOWN}}")
def test_url_observation_strips_credentials_and_query_but_preserves_port():
    from app.security import safe_url_text
    assert safe_url_text("http://user:pass@127.0.0.1:8765/demo?token=secret#hash")=="http://127.0.0.1:8765/demo"

def test_redaction_happens_before_json_escaping():
    import json
    value=r'quote"and\slash'
    clean=Redactor({"SECRET":value}).data({"summary":value,"items":[value]})
    assert clean=={"summary":"[REDACTED]","items":["[REDACTED]"]}
    assert json.loads(json.dumps(clean))==clean

async def test_localhost_opt_in_does_not_allow_public_page_to_fetch_loopback():
    with pytest.raises(PolicyError):
        await NavigationPolicy("https://example.com",allow_localhost=True).validate("http://127.0.0.1:8765/api/config",navigation=False)

def test_provider_key_is_redaction_only_never_an_executor_secret():
    redact=Redactor({"PASSWORD":"fixture-only"},redaction_only=["provider-api-secret"])
    assert redact.clean("provider-api-secret")=="[REDACTED]"
    with pytest.raises(PolicyError):
        redact.resolve("{{OPENAI_API_KEY}}")
    with pytest.raises(PolicyError):
        redact.resolve("{{MISSING}}")

def test_visible_text_assertion_needs_an_explicit_text_target():
    from app.models import Assertion,SemanticTarget
    with pytest.raises(ValidationError):
        Assertion(id="result",description="Required message",kind="visible",
            target=SemanticTarget(role="text",name="",scope_role=None,scope_name=None),expected="Required message")
