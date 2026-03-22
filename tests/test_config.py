"""Tests for configuration dataclasses."""

from veritas_rpm.config import CooldownConfig, PipelineConfig, RoutingConfig


class TestCooldownConfig:
    def test_defaults(self):
        c = CooldownConfig()
        assert c.doctor_minutes == 30
        assert c.nurse_minutes == 15
        assert c.patient_minutes == 5

    def test_custom_values(self):
        c = CooldownConfig(doctor_minutes=60)
        assert c.doctor_minutes == 60

    def test_as_dict(self):
        c = CooldownConfig(doctor_minutes=10, nurse_minutes=5, patient_minutes=2)
        d = c.as_dict()
        assert d == {"doctor": 10, "nurse": 5, "patient": 2}


class TestRoutingConfig:
    def test_default_has_all_alert_types(self):
        r = RoutingConfig()
        expected_types = {
            "tachycardia", "bradycardia", "desaturation", "flatline",
            "nocturnal_event", "probe_issue", "activity_spike", "other",
        }
        assert set(r.routing_table.keys()) == expected_types

    def test_custom_routing(self):
        r = RoutingConfig(routing_table={"tachycardia": ["AgentA"]})
        assert r.routing_table == {"tachycardia": ["AgentA"]}


class TestPipelineConfig:
    def test_defaults(self):
        p = PipelineConfig()
        assert isinstance(p.cooldown, CooldownConfig)
        assert isinstance(p.routing, RoutingConfig)
