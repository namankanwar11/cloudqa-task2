from app.models import Action, Assertion, SemanticTarget, TestPlan

def target(role, name):
    return SemanticTarget(role=role, name=name, scope_role=None, scope_name=None)

def assertion(id="result", kind="visible", role="heading", name="Customer dashboard", expected=""):
    return Assertion(id=id, description=f"{name} must satisfy {kind}", kind=kind, target=target(role,name), expected=expected)

class ScriptedPlanner:
    """Fake LLM boundary: real browsers/actions/assertions, no model quality claim."""
    def __init__(self, assertions, actions):
        self.result = TestPlan(summary="Scripted provider fixture", assertions=assertions)
        self.actions = list(actions)
        self.seen = []
        self.replans = []
    async def plan(self, instruction, observation, secret_aliases):
        self.seen.append((instruction, observation, secret_aliases))
        return self.result
    async def next_action(self, instruction, observation, plan, history, verified, last_error):
        self.replans.append(last_error)
        spec = self.actions.pop(0)
        if callable(spec):
            spec = spec(observation)
        ref = None
        if "name" in spec:
            matches = [e for e in observation["elements"] if e["name"]==spec["name"] and e["role"]==spec["role"]]
            if len(matches)!=1:
                raise RuntimeError("Test script semantic target ambiguous/missing")
            ref = matches[0]["ref"]
        return Action(kind=spec["kind"],ref=spec.get("ref",ref), value=spec.get("value"),
            assertion_id=spec.get("assertion_id"),destructive=spec.get("destructive",False),reason="Scripted test response")
    async def close(self):
        pass