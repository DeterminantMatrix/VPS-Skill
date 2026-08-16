# Migration v3 -> v4

v4 intentionally breaks the controller/worker wire contract.

Major changes:

- local inventory contract is explicit and strict;
- remote worker command uses an absolute path;
- schema/protocol are v4 with worker-manifest verification;
- confirmed shared platforms such as Pantheon are hard policy rejects;
- missing HEAD/CNAME evidence is not proof of directness;
- eligibility pool uses deterministic diversity selection;
- policy state precedes latency in ranking;
- coverage maturity is explicit;
- incumbent discovery prefers the running sing-box process config;
- sing-box fixed ELF paths precede PATH;
- Reality control retries only after a clean first failure;
- Reality failures expose sanitized stages;
- final reporting includes a recommendation-sorted comparison of at least five measured domains when available;
- selection and repair are separate execution modes.

Because the manifest changes, redeploy every owned target worker before using a v4 controller.
