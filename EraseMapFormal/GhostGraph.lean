namespace EraSeMap.GhostGraph

/-- A finite, explicitly closed discovery problem with sound executed observations. -/
structure Problem (Hypothesis Query Trace : Type) [DecidableEq Hypothesis] where
  hypotheses : List Hypothesis
  actual : Hypothesis
  predict : Hypothesis → Query → Trace
  observations : List (Query × Trace)
  actualListed : actual ∈ hypotheses
  observationSound : ∀ query trace, (query, trace) ∈ observations →
    predict actual query = trace

def Consistent [DecidableEq Hypothesis] [DecidableEq Trace]
    (problem : Problem Hypothesis Query Trace) (hypothesis : Hypothesis) : Bool :=
  problem.observations.all fun observation =>
    decide (problem.predict hypothesis observation.1 = observation.2)

def survivors [DecidableEq Hypothesis] [DecidableEq Trace]
    (problem : Problem Hypothesis Query Trace) : List Hypothesis :=
  problem.hypotheses.filter (Consistent problem)

/-- Under catalogue closure and sound traces, filtering cannot discard the real graph. -/
theorem true_graph_survives [DecidableEq Hypothesis] [DecidableEq Trace]
    (problem : Problem Hypothesis Query Trace) :
    problem.actual ∈ survivors problem := by
  apply List.mem_filter.mpr
  constructor
  · exact problem.actualListed
  · rw [Consistent, List.all_eq_true]
    intro observation observationMem
    apply decide_eq_true
    exact problem.observationSound observation.1 observation.2 observationMem

/-- A singleton version space identifies the real listed graph, rather than a representative. -/
theorem singleton_discovery_sound [DecidableEq Hypothesis] [DecidableEq Trace]
    (problem : Problem Hypothesis Query Trace) (candidate : Hypothesis)
    (singleton : survivors problem = [candidate]) :
    candidate = problem.actual := by
  have actualMem : problem.actual ∈ [candidate] := by
    rw [← singleton]
    exact true_graph_survives problem
  have actualEq : problem.actual = candidate := by
    simpa using actualMem
  exact actualEq.symm

/-- Two graphs equivalent under every allowed query survive exactly the same observation set. -/
theorem inseparable_class_fail_closed
    [DecidableEq Hypothesis] [DecidableEq Trace]
    (problem : Problem Hypothesis Query Trace)
    {left right : Hypothesis}
    (indistinguishable : ∀ query, problem.predict left query = problem.predict right query) :
    Consistent problem left = Consistent problem right := by
  unfold Consistent
  congr 1
  funext observation
  rw [indistinguishable observation.1]

/-- The emitted finite certificate states the exact one-step minimax obligation. -/
structure MinimaxCertificate (Query Score : Type) [LE Score] where
  candidates : List Query
  selected : Query
  score : Query → Score
  selectedListed : selected ∈ candidates
  minimum : ∀ candidate, candidate ∈ candidates → score selected ≤ score candidate

theorem selected_query_minimax [LE Score] (certificate : MinimaxCertificate Query Score) :
    certificate.selected ∈ certificate.candidates ∧
      ∀ candidate, candidate ∈ certificate.candidates →
        certificate.score certificate.selected ≤ certificate.score candidate := by
  exact ⟨certificate.selectedListed, certificate.minimum⟩

end EraSeMap.GhostGraph
