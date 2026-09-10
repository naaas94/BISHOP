# G6 Enrichment Quality Sampling

Manual 10-entry checklist for enrichment Call 1 (`challenge_hooks`) and Call 2 (`value_rationale`) against the pinned enrichment profile `config/profiles/professional_v1.0.0.yaml`.

## Protocol

1. Select 10 entries that passed pre-filter from a recent enrichment batch (mix of `core` and `peripheral` tiers if available).
2. Record each entry's `source_id`, model-produced `challenge_hooks`, and `value_rationale`.
3. Judge whether hooks are problem-shaped (2–4 practitioner search framings) and whether `value_rationale` explains professional value.
4. Set `hooks_acceptable` and `rationale_acceptable` to `true` or `false` per entry.
5. When all ten entries are filled and judged, run:
   `BISHOP_G6_MANUAL=1 ./scripts/run-g6-enrichment-sampling.sh`

Gate passes when every entry has both acceptance flags set to `true`. Profile YAML iteration is out of scope unless sampling fails — prefilter pin `professional_v1.2.0.yaml` is already calibrated separately.

```json
{
  "gate": "g6_enrichment",
  "version": 1,
  "profile_under_test": "config/profiles/professional_v1.0.0.yaml",
  "required_entry_count": 10,
  "entries": [
    {
      "slot": 1,
      "source_id": "",
      "challenge_hooks": [],
      "value_rationale": "",
      "hooks_acceptable": null,
      "rationale_acceptable": null,
      "reviewer_notes": ""
    },
    {
      "slot": 2,
      "source_id": "",
      "challenge_hooks": [],
      "value_rationale": "",
      "hooks_acceptable": null,
      "rationale_acceptable": null,
      "reviewer_notes": ""
    },
    {
      "slot": 3,
      "source_id": "",
      "challenge_hooks": [],
      "value_rationale": "",
      "hooks_acceptable": null,
      "rationale_acceptable": null,
      "reviewer_notes": ""
    },
    {
      "slot": 4,
      "source_id": "",
      "challenge_hooks": [],
      "value_rationale": "",
      "hooks_acceptable": null,
      "rationale_acceptable": null,
      "reviewer_notes": ""
    },
    {
      "slot": 5,
      "source_id": "",
      "challenge_hooks": [],
      "value_rationale": "",
      "hooks_acceptable": null,
      "rationale_acceptable": null,
      "reviewer_notes": ""
    },
    {
      "slot": 6,
      "source_id": "",
      "challenge_hooks": [],
      "value_rationale": "",
      "hooks_acceptable": null,
      "rationale_acceptable": null,
      "reviewer_notes": ""
    },
    {
      "slot": 7,
      "source_id": "",
      "challenge_hooks": [],
      "value_rationale": "",
      "hooks_acceptable": null,
      "rationale_acceptable": null,
      "reviewer_notes": ""
    },
    {
      "slot": 8,
      "source_id": "",
      "challenge_hooks": [],
      "value_rationale": "",
      "hooks_acceptable": null,
      "rationale_acceptable": null,
      "reviewer_notes": ""
    },
    {
      "slot": 9,
      "source_id": "",
      "challenge_hooks": [],
      "value_rationale": "",
      "hooks_acceptable": null,
      "rationale_acceptable": null,
      "reviewer_notes": ""
    },
    {
      "slot": 10,
      "source_id": "",
      "challenge_hooks": [],
      "value_rationale": "",
      "hooks_acceptable": null,
      "rationale_acceptable": null,
      "reviewer_notes": ""
    }
  ]
}
```
