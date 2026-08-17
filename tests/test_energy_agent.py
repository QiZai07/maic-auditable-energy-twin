from __future__ import annotations

import sys
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from src.energy_agent import OPENAI_TOOL_DEFINITIONS, QUICK_PROMPTS, answer_energy_question  # noqa: E402
from src.openai_energy_agent import answer_energy_question_hybrid, test_openai_connection  # noqa: E402


class TestEnergyAgent(unittest.TestCase):
    def test_quick_prompts_cover_core_decisions(self) -> None:
        self.assertGreaterEqual(len(QUICK_PROMPTS), 6)
        self.assertTrue(any("anomal" in prompt.lower() for prompt in QUICK_PROMPTS))
        self.assertTrue(any("missing" in prompt.lower() for prompt in QUICK_PROMPTS))

    def test_baseline_answer_uses_audited_values(self) -> None:
        response = answer_energy_question("How much electricity does reference case use annually, and what is the HVAC share?")
        self.assertEqual(response.intent, "energy_baseline")
        self.assertIn("345,676.69", response.answer)
        self.assertIn("29.01%", response.answer)
        self.assertIn("APPROVED AGGREGATE", response.evidence_class)
        self.assertIn("kWh × CNY 0.538", response.answer)
        self.assertIn("no time-of-use, demand", response.answer)

    def test_october_fault_is_not_imputed_as_measured(self) -> None:
        response = answer_energy_question("Why is October 2024 electricity anomalous?")
        self.assertEqual(response.tool_name, "inspect_meter_quality_event")
        self.assertIn("meter fault", response.answer)
        self.assertIn("never presents an estimate as a measured value", response.answer)

    def test_storage_answer_keeps_current_and_future_separate(self) -> None:
        response = answer_energy_question("How does the storage strategy work?")
        self.assertEqual(response.intent, "storage_sandbox")
        self.assertIn("No Storage Is Installed", response.title)
        self.assertIn("SANDBOX", response.evidence_class)

    def test_unknown_question_refuses_to_invent(self) -> None:
        response = answer_energy_question("What is on the cafeteria menu tomorrow?")
        self.assertEqual(response.intent, "capability_help")
        self.assertIn("will not invent", response.answer)

    def test_what_if_recalculates_tariff_and_payback(self) -> None:
        response = answer_energy_question("If the electricity tariff rises by 20%, what is the combined package payback?")
        self.assertEqual(response.intent, "scenario_roi")
        self.assertIn("0.646", response.answer)
        self.assertIn("2.31 years", response.answer)
        self.assertTrue(response.calculations)
        self.assertIn("USER WHAT-IF", response.evidence_class)
        self.assertIn("1.85–3.08 years", response.answer)
        self.assertIn("Scenario screening", response.decision_readiness)
        self.assertTrue(any("no time-of-use or demand-charge inputs" in step for step in response.next_steps))

    def test_multi_tool_planner_combines_pv_and_storage(self) -> None:
        response = answer_energy_question("How do installed PV and future storage affect grid imports?")
        self.assertEqual(response.tool_name, "local_multi_tool_planner")
        self.assertIn("pv_status", response.intents)
        self.assertIn("storage_sandbox", response.intents)
        self.assertIn("currently has no battery storage", response.answer)
        self.assertIn("106.14 kWp", response.answer)

    def test_follow_up_inherits_subject_from_history(self) -> None:
        response = answer_energy_question(
            "What if it falls by 10%?",
            history=["If the electricity tariff rises by 20%, what is the combined package payback?"],
        )
        self.assertEqual(response.intent, "scenario_roi")
        self.assertIn("0.484", response.answer)
        self.assertIn("previous-question context was retained", response.confidence)

    def test_first_what_if_is_not_marked_as_inherited_context(self) -> None:
        response = answer_energy_question("If the electricity tariff rises by 20%, what is the combined package payback?")
        self.assertNotIn("previous-question context was retained", response.confidence)

    def test_semantic_paraphrase_routes_without_exact_prompt(self) -> None:
        response = answer_energy_question("How does the building's overall energy intensity perform?")
        self.assertEqual(response.intent, "energy_baseline")
        self.assertGreater(response.route_confidence, 0.5)

    def test_single_topic_does_not_trigger_accidental_multi_tool(self) -> None:
        response = answer_energy_question("How does the storage strategy work?")
        self.assertEqual(response.intents, ("storage_sandbox",))
        self.assertEqual(response.tool_name, "compare_storage_strategies")

    def test_model_upgrade_diagnostic_prioritizes_evidence(self) -> None:
        response = answer_energy_question("What should the next model upgrade be to improve accuracy?")
        self.assertEqual(response.intent, "model_improvement")
        self.assertEqual(response.tool_name, "prioritize_model_upgrades")
        self.assertIn("15-minute", response.answer)
        self.assertIn("cannot honestly improve", response.answer)

    def test_match_score_is_not_presented_as_probability(self) -> None:
        response = answer_energy_question("How much electricity does reference case use annually?")
        self.assertIn("heuristic", response.confidence)
        self.assertTrue(response.decision_readiness)

    def test_openai_tool_contract_covers_all_domain_routes(self) -> None:
        self.assertEqual(len(OPENAI_TOOL_DEFINITIONS), 9)
        self.assertTrue(all(tool["strict"] for tool in OPENAI_TOOL_DEFINITIONS))
        self.assertTrue(all(tool["parameters"]["additionalProperties"] is False for tool in OPENAI_TOOL_DEFINITIONS))

    def test_hybrid_agent_executes_deterministic_tool_then_synthesizes(self) -> None:
        responses = iter([
            {
                "output": [{"type": "function_call", "name": "rank_and_recalculate_scenarios", "call_id": "call_1", "arguments": "{}"}],
                "usage": {"input_tokens": 120, "output_tokens": 18},
            },
            {
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "The combined package was recalculated from tool results; calculations and evidence are shown in the audit trace."}]}],
                "usage": {"input_tokens": 230, "output_tokens": 36},
            },
        ])

        def fake_transport(payload, headers):
            self.assertEqual(headers["Authorization"], "Bearer test-key")
            self.assertFalse(payload["store"])
            return next(responses)

        response = answer_energy_question_hybrid(
            "If the electricity tariff rises by 20%, what is the combined package payback?",
            mode="openai",
            api_key="test-key",
            transport=fake_transport,
        )
        self.assertEqual(response.engine, "openai")
        self.assertEqual(response.tool_name, "rank_and_recalculate_scenarios")
        self.assertEqual(response.tool_call_count, 1)
        self.assertEqual(response.input_tokens, 350)
        self.assertEqual(response.output_tokens, 54)
        self.assertIn("recalculated", response.answer)
        self.assertTrue(any("saved" in item for item in response.calculations))

    def test_hybrid_agent_falls_back_without_api_key(self) -> None:
        response = answer_energy_question_hybrid("How much electricity does reference case use annually?", mode="openai", api_key="")
        self.assertEqual(response.engine, "fallback")
        self.assertIn("No OpenAI API key", response.fallback_reason)
        self.assertIn("345,676.69", response.answer)

    def test_connection_check_uses_minimal_stateless_request(self) -> None:
        def fake_transport(payload, _headers):
            self.assertEqual(payload["input"], "Connection test")
            self.assertFalse(payload["store"])
            return {"id": "resp_test", "output": []}

        ok, message = test_openai_connection("test-key", transport=fake_transport)
        self.assertTrue(ok)
        self.assertIn("Connection succeeded", message)


if __name__ == "__main__":
    unittest.main(verbosity=2)
