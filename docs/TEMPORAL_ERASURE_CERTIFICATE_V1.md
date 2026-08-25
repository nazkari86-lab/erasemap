# Time-bound erasure certificate v1

The certificate replaces an unqualified `COMPLETE` claim with `COMPLETE_WITHIN_ENVELOPE`. It binds
the declaration to topology, uncertainty envelope, model set, observations, global-policy
certificate, PCUG proof bundle, action signature, producer revision, and a finite validity window.

An independent checker receives a recomputed verification context. It rejects a signed but forged
verdict, an undischarged coverage/observation/replay/model-channel obligation, an unknown key, or a
modified signature. Expiry and topology/envelope/model drift produce `EXPIRED`, not continued
confidence. The JSON decoder rejects missing and unknown fields.

This is a cryptographically bound verification envelope, not proof that the declared topology
contains every physical copy in the world. Its soundness remains conditional on instrumentation,
coverage, observation, replay, and channel assumptions supplied by the independent context.
