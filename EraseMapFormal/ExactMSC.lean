import EraseMapFormal.ExactCDC

namespace EraSeMap.ExactMSC

/--
A finite MSC problem separates executable feasibility from its temporal meaning. A candidate is a
registered set of controls; `feasible` is the replayed RSE decision; `temporallySafe` is the
semantic claim established by the registered-transition soundness obligations.
-/
structure Problem (Candidate : Type) where
  candidates : List Candidate
  feasible : Candidate → Bool
  cost : Candidate → Nat
  temporallySafe : Candidate → Prop
  feasibilitySound : ∀ candidate, feasible candidate = true → temporallySafe candidate

def select (problem : Problem Candidate) : Option Candidate :=
  ExactCDC.select problem.feasible problem.cost problem.candidates

/--
An exact MSC is listed, replay-feasible, temporally safe under the declared soundness obligation,
and no more expensive than any other listed replay-feasible control set.
-/
theorem selected_msc_safe_and_minimum
    (problem : Problem Candidate) {best : Candidate}
    (selected : select problem = some best) :
    best ∈ problem.candidates ∧ problem.feasible best = true ∧
      problem.temporallySafe best ∧
      ∀ other, other ∈ problem.candidates → problem.feasible other = true →
        problem.cost best ≤ problem.cost other := by
  have exact := ExactCDC.selected_is_feasible_minimum
    problem.feasible problem.cost selected
  exact ⟨exact.1, exact.2.1, problem.feasibilitySound best exact.2.1, exact.2.2⟩

/-- Returning no MSC is exactly the fail-closed absence of a feasible registered candidate. -/
theorem no_msc_iff_no_feasible_candidate (problem : Problem Candidate) :
    select problem = none ↔
      ∀ candidate, candidate ∈ problem.candidates → problem.feasible candidate = false := by
  exact ExactCDC.select_eq_none_iff problem.feasible problem.cost problem.candidates

end EraSeMap.ExactMSC
