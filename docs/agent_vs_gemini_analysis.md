# Agent vs Gemini: Extraction and Inconsistencies Comparison

For the query **"Extract components, check communication mappings, and report inconsistencies"** on `SystemExtract 5_original.arxml`.

## Summary

| Aspect | Your agent (Llama) | Gemini |
|--------|--------------------|--------|
| **Components** | 7 SWCs (TopLevelComposition, Core0, Core1, …) | Same plus richer naming (CompA, InputComp, OutputComp, ASILCompositions) |
| **Port refs / interfaces** | "All port references properly defined" | **Missing interfaces:** CompA_SR_Interface1/2, CompB_SR_Interface3, CompB_CS_Interface1 → broken refs |
| **Communication mappings** | "Communication mappings are correct" | Detailed (Message1–6, signal groups, transmission/reception) |
| **Inconsistencies** | Version 00052 unsupported; "No UUIDs for ECU instances" | Version + **missing interface defs** + **undefined CompB** + **invalid internal behavior refs** + **signal mapping path mismatch** |

## Why the agent can say “port refs OK” while Gemini says “missing interfaces”

1. **Same rule, different outcome**  
   Your validator ([`validators/data_consistency.py`](../validators/data_consistency.py)) treats an interface as “defined” only if there is an element with tag in `_INTERFACE_TAGS` (e.g. `SENDER-RECEIVER-INTERFACE`, `CLIENT-SERVER-INTERFACE`) whose path (from root using `SHORT-NAME`) matches the port’s `PROVIDED-INTERFACE-TREF` / `REQUIRED-INTERFACE-TREF`. If Gemini is right and those interfaces are missing, then either:
   - The **plan did not run** `validate_port_references_tool` or `validate_data_consistency_tool` for that run, or
   - **Path format** differs (e.g. namespace in path, or different segment order) so our normalized path does not match the ref.

2. **What to check**  
   In the run where the agent said “Port References: All port references were found to be properly defined”, open **Results** (raw tool outputs) and look at:
   - `validate_port_references_tool`
   - `validate_data_consistency_tool` (section “4. Port interface references”)  
   If they report **broken** refs or “interface reference not found” but the **Summary** still said “properly defined”, the bug is in the summarizer. If the tools really reported **all valid**, then the validator’s path logic may not match how this file references interfaces (e.g. cross-file or path style).

## Gaps the agent does not yet cover

These are reported by Gemini but **not** implemented as validators today:

1. **Undefined component (CompB)**  
   Internal behavior references a component “CompB” that has no SWC definition in the file. There is no tool that checks “referenced component in behavior exists”.

2. **Invalid internal behavioral references**  
   Runnables reading/writing from non-existent interfaces or components. No validator for “runnable data access points to existing interface/component”.

3. **Signal mapping context vs package structure**  
   Mapping paths (e.g. `/Root_Package/TopLevelComposition/ASILCompositions/...`) vs actual component location (e.g. `/Root_Package/SWCs/Core0/QM/...`). No tool checks this alignment.

So even with perfect summarization, the agent will not report those until new checks exist.

## Recommendations

1. **Verify tool outputs**  
   For the same file and query, confirm in **Results** what `validate_port_references_tool` and `validate_data_consistency_tool` actually returned. That tells you whether the mismatch is summarization vs path/validator logic.

2. **Optional: path robustness**  
   If the file uses path variants (e.g. with/without namespace prefix, or trailing slash), extend `_normalize_path` and/or the way we build interface paths so that refs still match.

3. **Optional: new validators**  
   To move closer to Gemini’s “inconsistencies”:
   - **Undefined component refs:** For each internal behavior / component ref, resolve the target; if it’s not in the same file (or in a declared set of files), report “undefined component”.
   - **Behavioral refs:** Check that runnable read/write and send/receive points reference existing interfaces/elements.
   - **Mapping context vs structure:** Compare signal mapping context paths to the actual AR-PACKAGE/SWC hierarchy and report mismatches.

4. **Query coverage**  
   For “check communication mappings and report inconsistencies”, the **analysis** intent already recommends `validate_data_consistency_tool`, `validate_port_references_tool`, and `validate_communication_tool`. Ensuring the planner always includes these for such phrasing will maximize the chance the agent reports interface and communication issues when the validators detect them.
