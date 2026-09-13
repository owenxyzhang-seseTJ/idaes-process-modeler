# Method Search Packet

Status: READY_FOR_PREPROCESSING / direct model-result and model-principle visualization

Date: 2026-09-13

Figure lane: Composite data/result figure plus workflow/process schematic and model-principle
parameter figure.

Source basis:

- User-provided IDAES + Pyomo demo specification.
- `assets/templates/*.yaml` for initial parameters and step sequences.
- `demo_results/*/summary.json`, `profiles.csv`, `metrics.csv`, and `convergence*.json`.
- The local model implementations in `src/idaes_process_modeler/models/` and
  `src/idaes_process_modeler/idaes_adapter.py`.

Preprocessing method:

- Use the equations implemented by the local model code; do not fit or smooth values.
- Evaluate the specified dual-site Langmuir expression on a pressure grid.
- Evaluate the specified LDF step response from `q(0)=0` using the configured `k` and the
  equilibrium loading at the fixed-bed feed partial pressure.
- Read numerical validation values directly from the result bundles.
- Preserve raw YAML/CSV/JSON files and write derived parameter arrays separately.

No external experimental or literature preprocessing method was applied. No experimental
claim, statistical uncertainty, or Aspen benchmark was added.
