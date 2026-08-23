import EraseMapFormal.ExactCDC

namespace EraSeMap.ExactTRE

/--
A finite TRE problem selects one registered control set for an explicitly listed topology
uncertainty envelope. `robustFeasible` is the executable all-scenario replay decision;
`safe` is the temporal erasure meaning for one scenario.
-/
structure Problem (Candidate Scenario : Type) where
  candidates : List Candidate
  scenarios : List Scenario
  robustFeasible : Candidate → Bool
  cost : Candidate → Nat
  safe : Candidate → Scenario → Prop
  feasibilitySound : ∀ candidate, robustFeasible candidate = true →
    ∀ scenario, scenario ∈ scenarios → safe candidate scenario

def select (problem : Problem Candidate Scenario) : Option Candidate :=
  ExactCDC.select problem.robustFeasible problem.cost problem.candidates

/--
The selected exact TRE candidate is listed, executable-feasible for the complete declared
envelope, temporally safe for every listed scenario under the soundness obligation, and no more
expensive than any other listed robust-feasible candidate.
-/
theorem selected_tre_safe_for_every_scenario_and_minimum
    (problem : Problem Candidate Scenario) {best : Candidate}
    (selected : select problem = some best) :
    best ∈ problem.candidates ∧ problem.robustFeasible best = true ∧
      (∀ scenario, scenario ∈ problem.scenarios → problem.safe best scenario) ∧
      ∀ other, other ∈ problem.candidates → problem.robustFeasible other = true →
        problem.cost best ≤ problem.cost other := by
  have exact := ExactCDC.selected_is_feasible_minimum
    problem.robustFeasible problem.cost selected
  exact ⟨exact.1, exact.2.1, problem.feasibilitySound best exact.2.1, exact.2.2⟩

/-- No TRE plan is returned exactly when no listed candidate protects the declared envelope. -/
theorem no_tre_iff_no_robust_feasible_candidate
    (problem : Problem Candidate Scenario) :
    select problem = none ↔
      ∀ candidate, candidate ∈ problem.candidates →
        problem.robustFeasible candidate = false := by
  exact ExactCDC.select_eq_none_iff
    problem.robustFeasible problem.cost problem.candidates

end EraSeMap.ExactTRE
